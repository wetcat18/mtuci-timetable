"""Подделка requests.Session: тесты не ходят в сеть"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

FIXTURES = Path(__file__).parent / "fixtures"


def fixture(name: str) -> str:
    return (FIXTURES / name).read_text(encoding="utf-8")


class FakeResponse:
    def __init__(self, body: str, *, content_type: str, status_code: int = 200) -> None:
        self.text = body
        self.status_code = status_code
        self.headers = {"Content-Type": content_type}

    def json(self) -> Any:
        return json.loads(self.text)


class FakeSession:
    """Отдаёт заранее подготовленные ответы и запоминает запросы."""

    def __init__(self, responses: "list[FakeResponse] | FakeResponse") -> None:
        if isinstance(responses, FakeResponse):
            responses = [responses]
        self._responses = list(responses)
        self.headers: dict[str, str] = {}
        self.cookies: dict[str, str] = {}
        self.requests: list[dict[str, Any]] = []

    def _next(self) -> FakeResponse:
        if not self._responses:
            raise AssertionError("запросов больше, чем подготовленных ответов")
        return self._responses.pop(0) if len(self._responses) > 1 else self._responses[0]

    def post(self, url: str, *, params=None, data=None, timeout=None) -> FakeResponse:
        self.requests.append(
            {"method": "POST", "url": url, "params": params or {}, "data": data or {}}
        )
        return self._next()

    def get(self, url: str, *, timeout=None) -> FakeResponse:
        self.requests.append({"method": "GET", "url": url, "params": {}, "data": {}})
        return self._next()

    def close(self) -> None:
        pass


def json_response(name: str) -> FakeResponse:
    return FakeResponse(fixture(name), content_type="application/json; charset=UTF-8")


def html_response(name: str) -> FakeResponse:
    return FakeResponse(fixture(name), content_type="text/html; charset=UTF-8")


@pytest.fixture
def make_client():
    from mtuci_timetable import TimetableClient

    def factory(responses) -> "TimetableClient":
        session = FakeSession(responses)
        client = TimetableClient(session=session, warm=False)
        client.fake = session  # type: ignore[attr-defined]
        return client

    return factory
