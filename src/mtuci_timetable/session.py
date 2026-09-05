"""Сессия и обход проверки"""

from __future__ import annotations

from typing import Mapping

import requests

from .errors import BotCheckError, TransportError

__all__ = [
    "DEFAULT_USER_AGENT",
    "build_session",
    "describe_block",
    "is_html",
    "looks_like_bot_check",
    "warm_up",
]

DEFAULT_USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/140.0.0.0 Safari/537.36"
)

_BOT_CHECK_MARKERS = (
    "Вы человек?",
    "Are you human?",
    "complete the captcha",
    "Access Blocked",
)

_BOT_CHECK_STATUSES = (403, 429)


def build_session(
    *,
    base_url: str,
    user_agent: str | None = None,
    cookies: Mapping[str, str] | None = None,
    session: requests.Session | None = None,
) -> requests.Session:
    session = session or requests.Session()
    session.headers.update(
        {
            "User-Agent": user_agent or DEFAULT_USER_AGENT,
            "Accept": "application/json, text/javascript, */*; q=0.01",
            "Accept-Language": "ru-RU,ru;q=0.9,en-US;q=0.8,en;q=0.7",
            "X-Requested-With": "XMLHttpRequest",
            "Origin": base_url,
            "Referer": f"{base_url}/time-table/",
            "Sec-Fetch-Dest": "empty",
            "Sec-Fetch-Mode": "cors",
            "Sec-Fetch-Site": "same-origin",
        }
    )
    if cookies:
        session.cookies.update(dict(cookies))
    return session


def is_html(response: requests.Response) -> bool:
    return "html" in response.headers.get("Content-Type", "").lower()


def looks_like_bot_check(response: requests.Response) -> bool:
    if not is_html(response):
        return False
    if response.status_code in _BOT_CHECK_STATUSES:
        return True
    head = response.text[:4000]
    return any(marker in head for marker in _BOT_CHECK_MARKERS)


def describe_block(response: requests.Response) -> str:
    head = " ".join(response.text[:400].split())
    return f"HTTP {response.status_code}, {head[:120]}"


def warm_up(session: requests.Session, base_url: str, timeout: float) -> None:
    try:
        response = session.get(f"{base_url}/time-table/", timeout=timeout)
    except requests.RequestException as exc:
        raise TransportError(f"не удалось открыть {base_url}/time-table/: {exc}") from exc

    if looks_like_bot_check(response):
        raise BotCheckError(
            "mtuci.ru показал проверку 'Вы человек?' вместо страницы расписания. "
            "Передайте куки из браузера: TimetableClient(cookies={...})."
        )
