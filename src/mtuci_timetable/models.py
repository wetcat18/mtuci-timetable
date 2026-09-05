from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime, time
from enum import Enum
from typing import Any, Iterator, Mapping, Sequence

__all__ = ["EntityType", "SearchItem", "Lesson", "Day", "Timetable"]

# Сервер помечает неизвестное время и аудиторию двумя дефисами
_MISSING = "--"


class EntityType(str, Enum):
    GROUP = "group"
    TEACHER = "teacher"
    AUDIENCE = "audience"

    def __str__(self) -> str:
        return self.value


@dataclass(frozen=True)
class SearchItem:
    name: str
    type: EntityType
    value: str

    def __str__(self) -> str:
        return self.name


@dataclass(frozen=True)
class Lesson:
    """Одна пара"""

    id: str
    date: date
    number: int
    discipline: str
    start: time | None
    end: time | None
    teachers: tuple[str, ...]
    audiences: tuple[str, ...]
    groups: tuple[str, ...]
    kind: str
    is_retake: bool
    is_online: bool
    is_form_control: bool
    raw: Mapping[str, Any] = field(repr=False, compare=False, default_factory=dict)

    @property
    def starts_at(self) -> datetime | None:
        """Начало пары как datetime, или None если сервер не знает времени"""
        return datetime.combine(self.date, self.start) if self.start else None

    @property
    def ends_at(self) -> datetime | None:
        return datetime.combine(self.date, self.end) if self.end else None

    def __str__(self) -> str:
        when = self.start.strftime("%H:%M") if self.start else "--:--"
        where = ", ".join(self.audiences) or "?"
        return f"{when} {self.discipline} ({self.kind}) — {where}"


@dataclass(frozen=True)
class Day:
    """Учебный день. Может быть пустым, сервер отдаёт и такие"""

    date: date
    lessons: tuple[Lesson, ...] = ()

    def __iter__(self) -> Iterator[Lesson]:
        return iter(self.lessons)

    def __len__(self) -> int:
        return len(self.lessons)

    def __bool__(self) -> bool:
        return bool(self.lessons)

    @property
    def is_empty(self) -> bool:
        return not self.lessons


@dataclass(frozen=True)
class Timetable:
    """Расписание сущности за отрезок, который отдал сервер"""

    entity: str
    entity_type: EntityType
    days: tuple[Day, ...]
    updated_at: datetime | None = None
    raw: Mapping[str, Any] = field(repr=False, compare=False, default_factory=dict)

    def __iter__(self) -> Iterator[Day]:
        return iter(self.days)

    def __len__(self) -> int:
        return len(self.days)

    @property
    def lessons(self) -> tuple[Lesson, ...]:
        """Все пары подряд, отсортированные по дате и номеру"""
        return tuple(lesson for day in self.days for lesson in day.lessons)

    @property
    def dates(self) -> tuple[date, ...]:
        return tuple(day.date for day in self.days)

    @property
    def covers(self) -> tuple[date, date] | None:
        """Первая и последняя дата ответа, или None если дней нет"""
        return (self.days[0].date, self.days[-1].date) if self.days else None

    def on(self, day: date) -> Day:
        """День по дате. Если сервер его не прислал - пустой Day"""
        for existing in self.days:
            if existing.date == day:
                return existing
        return Day(date=day)

    def between(self, start: date, end: date) -> "Timetable":
        """Срез по датам включительно"""
        kept = tuple(d for d in self.days if start <= d.date <= end)
        return Timetable(
            entity=self.entity,
            entity_type=self.entity_type,
            days=kept,
            updated_at=self.updated_at,
            raw=self.raw,
        )

    def __str__(self) -> str:
        span = self.covers
        where = f"{span[0]:%d.%m.%Y}–{span[1]:%d.%m.%Y}" if span else "пусто"
        return f"{self.entity} ({self.entity_type}): {where}, пар {len(self.lessons)}"


def _parse_time(value: Any) -> time | None:
    if not isinstance(value, str) or value.strip() in ("", _MISSING):
        return None
    try:
        hours, minutes = value.strip().split(":")[:2]
        return time(int(hours), int(minutes))
    except (ValueError, TypeError):
        return None


def _parse_date(value: str) -> date:
    """Даты приходят ключами словаря в формате DD.MM.YYYY."""
    return datetime.strptime(value, "%d.%m.%Y").date()


def _as_tuple(value: Any) -> tuple[str, ...]:
    if value is None:
        return ()
    if isinstance(value, str):
        value = [value]
    return tuple(str(item) for item in value if str(item).strip() not in ("", _MISSING))


def _as_bool(value: Any) -> bool:
    return str(value) not in ("0", "", "None", "False")


def _as_int(value: Any) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return 0


def parse_lesson(payload: Mapping[str, Any], day: date) -> Lesson:
    """
    Собрать Lesson из сырого словаря.
    Дата берётся из ключа словаря дней, а не из поля UF_DATE: последнее
    приходит со сдвигом часового пояса и на границе суток указывает
    на предыдущий день.
    """
    return Lesson(
        id=str(payload.get("ID", "")),
        date=day,
        number=_as_int(payload.get("UF_NUMBER")),
        discipline=str(payload.get("UF_DISCIPLINE", "")).strip(),
        start=_parse_time(payload.get("UF_TIME_START")),
        end=_parse_time(payload.get("UF_TIME_END")),
        teachers=_as_tuple(payload.get("UF_TEACHER")),
        audiences=_as_tuple(payload.get("UF_AUDIENCE")),
        groups=_as_tuple(payload.get("UF_GROUP")),
        kind=str(payload.get("UF_TYPE", "")).strip(),
        is_retake=_as_bool(payload.get("UF_IS_RETAKE")),
        is_online=_as_bool(payload.get("UF_IS_ONLINE")),
        is_form_control=_as_bool(payload.get("UF_IS_FORM_CONTROL")),
        raw=dict(payload),
    )


def parse_days(payload: Mapping[str, Any]) -> tuple[Day, ...]:
    days: list[Day] = []
    for key, lessons in (payload or {}).items():
        try:
            day = _parse_date(key)
        except ValueError:
            continue
        parsed = [parse_lesson(item, day) for item in (lessons or [])]
        parsed.sort(key=lambda lesson: (lesson.number, lesson.start or time.min))
        days.append(Day(date=day, lessons=tuple(parsed)))
    days.sort(key=lambda d: d.date)
    return tuple(days)


def parse_timetable(
    data: Mapping[str, Any], entity: str, entity_type: EntityType
) -> Timetable:
    updated = data.get("updated_at")
    return Timetable(
        entity=entity,
        entity_type=entity_type,
        days=parse_days(data.get("days") or {}),
        updated_at=datetime.fromtimestamp(updated) if updated else None,
        raw=dict(data),
    )


def parse_search(items: Sequence[Mapping[str, Any]]) -> list[SearchItem]:
    result: list[SearchItem] = []
    for item in items or []:
        name = str(item.get("UF_NAME", "")).strip()
        if not name:
            continue
        try:
            kind = EntityType(item.get("type"))
        except ValueError:
            continue
        result.append(SearchItem(name=name, type=kind, value=str(item.get("value", name))))
    return result
