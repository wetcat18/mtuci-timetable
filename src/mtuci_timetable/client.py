"""Клиент к расписанию МТУСИ"""

from __future__ import annotations

from datetime import date
from typing import Iterable, Mapping, Sequence

import requests

from . import _raw
from .errors import AmbiguousQuery, MonthUnavailable, NotFound
from .models import (
    Day,
    EntityType,
    SearchItem,
    Timetable,
    parse_search,
    parse_timetable,
)
from .session import build_session, warm_up

__all__ = ["TimetableClient", "LEVELS", "MOSCOW_SITE_ID"]

# Идентификатор московской площадки. У филиалов свои поддомены.
MOSCOW_SITE_ID = "s3"

# Уровни образования зашиты в вёрстку страницы.
LEVELS = ("Бакалавриат", "Магистратура", "Специалитет", "Аспирантура", "Неизвестно")


class TimetableClient:
    def __init__(
        self,
        *,
        base_url: str = "https://mtuci.ru",
        site_id: str = MOSCOW_SITE_ID,
        timeout: float = 20.0,
        user_agent: str | None = None,
        cookies: Mapping[str, str] | None = None,
        session: requests.Session | None = None,
        warm: bool = True,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.site_id = site_id
        self.timeout = timeout
        self.session = build_session(
            base_url=self.base_url,
            user_agent=user_agent,
            cookies=cookies,
            session=session,
        )
        self._warmed = not warm

    def _call(self, action: str, data: Mapping[str, object]) -> object:
        if not self._warmed:
            self._warmed = True
            warm_up(self.session, self.base_url, self.timeout)
        payload = dict(data)
        payload.setdefault("SITE_ID", self.site_id)
        return _raw.call(self.session, self.base_url, action, payload, self.timeout)

    def close(self) -> None:
        self.session.close()

    def __enter__(self) -> "TimetableClient":
        return self

    def __exit__(self, *exc_info: object) -> None:
        self.close()

    def search(self, query: str) -> list[SearchItem]:
        return parse_search(self._call("getItemsListBySearch", {"NAME": query}) or [])

    def resolve(
        self, query: str, *, type: EntityType | str | None = None
    ) -> SearchItem:
        matches = self.search(query)
        if type is not None:
            wanted = EntityType(type)
            matches = [item for item in matches if item.type is wanted]

        if not matches:
            raise NotFound(f"по запросу {query!r} ничего не найдено")

        exact = [item for item in matches if item.name.casefold() == query.casefold()]
        if len(exact) == 1:
            return exact[0]
        if len(matches) == 1:
            return matches[0]
        raise AmbiguousQuery(query, [item.name for item in matches])

    def timetable(
        self,
        entity: SearchItem | str,
        *,
        type: EntityType | str | None = None,
        month: date | int | None = None,
    ) -> Timetable:
        value, kind = self._entity(entity, type)
        index = self._month_index(month)

        data = self._call(
            "getTimetableByValue",
            {"VALUE": value, "MONTH": index, "TYPE": kind.value},
        )
        timetable = parse_timetable(data or {}, entity=value, entity_type=kind)

        if isinstance(month, date):
            self._ensure_month(timetable, month)
        return timetable

    def between(
        self,
        entity: SearchItem | str,
        start: date,
        end: date,
        *,
        type: EntityType | str | None = None,
    ) -> Timetable:
        if start > end:
            raise ValueError("start позже end")

        value, kind = self._entity(entity, type)
        merged: dict[date, Day] = {}
        updated_at = None

        for month in _months_between(start, end):
            chunk = self.timetable(SearchItem(value, kind, value), month=month)
            updated_at = chunk.updated_at or updated_at
            for day in chunk.days:
                if day.date not in merged or (day.lessons and not merged[day.date].lessons):
                    merged[day.date] = day

        days = tuple(merged[key] for key in sorted(merged) if start <= key <= end)
        return Timetable(
            entity=value, entity_type=kind, days=days, updated_at=updated_at
        )

    def forms(self, level: str) -> list[str]:
        return self._names(
            "getFormsListBySelector", {"UF_LEVEL": level}, "UF_FORM"
        )

    def faculties(self, level: str, form: str) -> list[str]:
        return self._names(
            "getFacultiesListBySelector",
            {"UF_LEVEL": level, "UF_FORM": form},
            "UF_FACULTY",
        )

    def courses(self, level: str, form: str, faculty: str) -> list[str]:
        return self._names(
            "getCoursesListBySelector",
            {"UF_LEVEL": level, "UF_FORM": form, "UF_FACULTY": faculty},
            "UF_COURSE",
        )

    def groups(self, level: str, form: str, faculty: str, course: str) -> list[str]:
        return self._names(
            "getGroupsListBySelector",
            {
                "UF_LEVEL": level,
                "UF_FORM": form,
                "UF_FACULTY": faculty,
                "UF_COURSE": course,
            },
            "UF_NAME",
        )

    def _names(self, action: str, data: Mapping[str, object], key: str) -> list[str]:
        rows: Sequence[Mapping[str, object]] = self._call(action, data) or []
        names = []
        for row in rows:
            value = row.get(key) if key in row else next(iter(row.values()), None)
            if value:
                names.append(str(value))
        return names

    @staticmethod
    def _entity(
        entity: SearchItem | str, type: EntityType | str | None
    ) -> tuple[str, EntityType]:
        if isinstance(entity, SearchItem):
            return entity.value, entity.type
        kind = EntityType(type) if type is not None else EntityType.GROUP
        return str(entity), kind

    @staticmethod
    def _month_index(month: date | int | None) -> int:
        if month is None:
            return date.today().month - 1
        if isinstance(month, date):
            return month.month - 1
        index = int(month)
        if not 0 <= index <= 11:
            raise ValueError("номер месяца считается с нуля и лежит в 0..11")
        return index

    @staticmethod
    def _ensure_month(timetable: Timetable, month: date) -> None:
        if any(
            day.date.year == month.year and day.date.month == month.month
            for day in timetable.days
        ):
            return
        span = timetable.covers
        got = f"{span[0]:%m.%Y}–{span[1]:%m.%Y}" if span else "пустой ответ"
        raise MonthUnavailable(
            f"просили {month:%m.%Y}, сервер вернул {got}. "
            "Расписание доступно примерно на +-4 месяца от текущего."
        )


def _months_between(start: date, end: date) -> Iterable[date]:
    year, month = start.year, start.month
    while (year, month) <= (end.year, end.month):
        yield date(year, month, 1)
        year, month = (year + 1, 1) if month == 12 else (year, month + 1)
