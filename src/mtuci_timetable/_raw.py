from __future__ import annotations

from typing import Any, Mapping

import requests

from .errors import ApiError, BotCheckError, TransportError
from .session import describe_block, is_html

__all__ = ["COMPONENT", "call"]

# Имя Bitrix-компонента, который обслуживает страницу расписания.
COMPONENT = "mtuci:timetable"

_ENDPOINT = "/bitrix/services/main/ajax.php"


def call(
    session: requests.Session,
    base_url: str,
    action: str,
    data: Mapping[str, Any],
    timeout: float,
) -> Any:
    params = {"c": COMPONENT, "action": action, "mode": "class"}
    payload = {key: value for key, value in data.items() if value is not None}

    try:
        response = session.post(
            f"{base_url}{_ENDPOINT}", params=params, data=payload, timeout=timeout
        )
    except requests.RequestException as exc:
        raise TransportError(f"{action}: {exc}") from exc

    if is_html(response):
        raise BotCheckError(
            f"{action}: вместо JSON пришёл заслон ({describe_block(response)}). "
            "Обычно помогает браузерный User-Agent; если нет — передайте "
            "куки из браузера: TimetableClient(cookies={...})."
        )

    try:
        body = response.json()
    except ValueError as exc:
        snippet = response.text[:200].replace("\n", " ")
        raise ApiError(action, [f"ответ не JSON (HTTP {response.status_code}): {snippet}"]) from exc

    if body.get("status") != "success":
        messages = [
            str(error.get("message", error))
            for error in (body.get("errors") or [])
        ]
        raise ApiError(action, messages)

    return body.get("data")
