"""Разбор ответов сервера в объекты."""

from __future__ import annotations

from datetime import date, datetime, time

from conftest import json_response

from mtuci_timetable import EntityType


def test_search_keeps_guid_in_value(make_client):
    client = make_client(json_response("search_teacher.json"))

    found = client.search("Таньков")

    assert len(found) == 1
    item = found[0]
    assert item.type is EntityType.TEACHER
    assert item.name == "Таньков Олег Иванович"
    # Без GUID сервер расписание не отдаст, поэтому value отличается от имени.
    assert item.value.endswith("_3cba721c-ee9f-11ef-949b-6cb3115e8255")


def test_timetable_parses_lessons(make_client):
    client = make_client(json_response("timetable_september.json"))

    timetable = client.timetable("БВТ2301")

    assert timetable.entity_type is EntityType.GROUP
    assert timetable.updated_at == datetime.fromtimestamp(1788609748)
    assert timetable.covers == (date(2026, 9, 1), date(2026, 9, 7))

    lesson = timetable.on(date(2026, 9, 2)).lessons[0]
    assert lesson.discipline == "Основы военной подготовки"
    assert lesson.start == time(9, 30)
    assert lesson.end == time(11, 0)
    assert lesson.teachers == ("Таньков Олег Иванович",)
    assert lesson.audiences == ("И-2",)
    assert lesson.kind == "Лекции"
    assert lesson.is_online is False


def test_lesson_date_comes_from_key_not_uf_date(make_client):
    """UF_DATE приходит со сдвигом пояса и указывает на предыдущий день."""
    client = make_client(json_response("timetable_september.json"))

    lesson = client.timetable("БВТ2301").on(date(2026, 9, 2)).lessons[0]

    assert lesson.raw["UF_DATE"].startswith("2026-09-01")
    assert lesson.date == date(2026, 9, 2)
    assert lesson.starts_at == datetime(2026, 9, 2, 9, 30)


def test_empty_day_is_falsy(make_client):
    client = make_client(json_response("timetable_september.json"))

    timetable = client.timetable("БВТ2301")

    assert not timetable.on(date(2026, 9, 1))
    assert timetable.on(date(2026, 9, 1)).is_empty
    # Дня, которого нет в ответе, тоже не должно быть больно спросить.
    assert timetable.on(date(2026, 9, 30)).lessons == ()


def test_online_lesson_flag(make_client):
    client = make_client(json_response("timetable_september.json"))

    lessons = client.timetable("БВТ2301").on(date(2026, 9, 4)).lessons

    assert lessons[0].is_online is True
    assert lessons[0].audiences == ("Аудитория (дистанционно)",)


def test_lessons_sorted_within_day(make_client):
    client = make_client(json_response("timetable_september.json"))

    for day in client.timetable("БВТ2301"):
        numbers = [lesson.number for lesson in day]
        assert numbers == sorted(numbers)
