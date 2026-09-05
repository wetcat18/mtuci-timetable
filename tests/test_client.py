"""Поведение клиента: форма запроса, месяцы, ошибки."""

from __future__ import annotations

from datetime import date

import pytest
from conftest import FakeResponse, fixture, html_response, json_response

from mtuci_timetable import (
    AmbiguousQuery,
    ApiError,
    BotCheckError,
    EntityType,
    MonthUnavailable,
    NotFound,
    SearchItem,
)


def test_parameters_go_into_post_body(make_client):
    client = make_client(json_response("timetable_september.json"))

    client.timetable("БВТ2301", month=date(2026, 9, 1))

    request = client.fake.requests[-1]
    assert request["method"] == "POST"
    assert request["params"] == {
        "c": "mtuci:timetable",
        "action": "getTimetableByValue",
        "mode": "class",
    }
    assert request["data"] == {
        "VALUE": "БВТ2301",
        "MONTH": 8,
        "TYPE": "group",
        "SITE_ID": "s3",
    }


def test_month_index_counts_from_zero(make_client):
    client = make_client(json_response("timetable_september.json"))

    client.timetable("БВТ2301", month=8)

    assert client.fake.requests[-1]["data"]["MONTH"] == 8


def test_month_index_out_of_range(make_client):
    client = make_client(json_response("timetable_september.json"))

    with pytest.raises(ValueError):
        client.timetable("БВТ2301", month=12)


def test_wrong_year_from_server_is_caught(make_client):
    """Сервер сам достраивает год и на границе учебного года промахивается."""
    client = make_client(json_response("timetable_wrong_year.json"))

    with pytest.raises(MonthUnavailable) as exc:
        client.timetable("БВТ2301", month=date(2026, 9, 1))

    assert "09.2026" in str(exc.value)


def test_int_month_skips_year_check(make_client):
    """Номером месяца просят сырые данные - проверять нечего."""
    client = make_client(json_response("timetable_wrong_year.json"))

    timetable = client.timetable("БВТ2301", month=0)

    assert timetable.covers == (date(2027, 1, 1), date(2027, 1, 2))


def test_search_item_carries_its_own_type(make_client):
    client = make_client(json_response("timetable_september.json"))
    teacher = SearchItem("Таньков Олег Иванович", EntityType.TEACHER, "Таньков_guid")

    client.timetable(teacher)

    data = client.fake.requests[-1]["data"]
    assert data["TYPE"] == "teacher"
    assert data["VALUE"] == "Таньков_guid"


def test_between_filters_and_merges(make_client):
    client = make_client(json_response("timetable_september.json"))

    week = client.between("БВТ2301", date(2026, 9, 1), date(2026, 9, 5))

    assert week.dates == (date(2026, 9, 1), date(2026, 9, 2), date(2026, 9, 3), date(2026, 9, 4))
    assert len(client.fake.requests) == 1  # один месяц — один запрос


def test_between_spans_two_months(make_client):
    client = make_client(json_response("timetable_september.json"))

    with pytest.raises(MonthUnavailable):
        # Октябрь фикстура не отдаёт, и клиент не выдаёт сентябрь за октябрь.
        client.between("БВТ2301", date(2026, 9, 1), date(2026, 10, 5))

    months = [request["data"]["MONTH"] for request in client.fake.requests]
    assert months == [8, 9]


def test_between_rejects_reversed_range(make_client):
    client = make_client(json_response("timetable_september.json"))

    with pytest.raises(ValueError):
        client.between("БВТ2301", date(2026, 9, 5), date(2026, 9, 1))


def test_resolve_requires_single_match(make_client):
    client = make_client(json_response("search_teacher.json"))

    assert client.resolve("Таньков").type is EntityType.TEACHER


def test_resolve_reports_nothing_found(make_client):
    empty = FakeResponse('{"status":"success","data":[],"errors":[]}', content_type="application/json")
    client = make_client(empty)

    with pytest.raises(NotFound):
        client.resolve("zzzqqq")


def test_resolve_reports_ambiguity(make_client):
    many = FakeResponse(
        '{"status":"success","data":['
        '{"UF_NAME":"БВТ2301","type":"group","value":"БВТ2301"},'
        '{"UF_NAME":"БВТ2302","type":"group","value":"БВТ2302"}],"errors":[]}',
        content_type="application/json",
    )
    client = make_client(many)

    with pytest.raises(AmbiguousQuery) as exc:
        client.resolve("БВТ23")

    assert "БВТ2301" in str(exc.value)


def test_exact_name_wins_over_substring_matches(make_client):
    many = FakeResponse(
        '{"status":"success","data":['
        '{"UF_NAME":"БВТ2301","type":"group","value":"БВТ2301"},'
        '{"UF_NAME":"БВТ23011","type":"group","value":"БВТ23011"}],"errors":[]}',
        content_type="application/json",
    )
    client = make_client(many)

    assert client.resolve("БВТ2301").value == "БВТ2301"


def test_captcha_page_is_recognised(make_client):
    client = make_client(html_response("bot_check.html"))

    with pytest.raises(BotCheckError):
        client.search("БВТ")


def test_access_blocked_403_is_recognised(make_client):
    """Запрос без браузерного User-Agent получает 403 без слова про капчу."""
    blocked = FakeResponse(
        fixture("access_blocked.html"), content_type="text/html", status_code=403
    )
    client = make_client(blocked)

    with pytest.raises(BotCheckError) as exc:
        client.search("БВТ")

    assert "403" in str(exc.value)
    assert "User-Agent" in str(exc.value)


def test_html_is_never_parsed_as_json(make_client):
    """Любой HTML на эндпоинте - заслон, а не битый JSON."""
    surprise = FakeResponse("<html><body>что-то новое</body></html>", content_type="text/html")
    client = make_client(surprise)

    with pytest.raises(BotCheckError):
        client.search("БВТ")


def test_server_error_becomes_api_error(make_client):
    broken = FakeResponse(
        '{"status":"error","data":null,'
        '"errors":[{"message":"Unsupported operand types: string + int","code":0}]}',
        content_type="application/json",
    )
    client = make_client(broken)

    with pytest.raises(ApiError) as exc:
        client.timetable("БВТ2301")

    assert "Unsupported operand" in str(exc.value)


def test_selector_chain_sends_previous_choices(make_client):
    forms = FakeResponse(
        '{"status":"success","data":[{"UF_FORM":"Очная"},{"UF_FORM":"Заочная"}],"errors":[]}',
        content_type="application/json",
    )
    client = make_client(forms)

    assert client.forms("Бакалавриат") == ["Очная", "Заочная"]
    assert client.fake.requests[-1]["data"] == {"UF_LEVEL": "Бакалавриат", "SITE_ID": "s3"}
