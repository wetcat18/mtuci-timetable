"""
Неофициальный клиент к расписанию МТУСИ
Библиотека ходит в тот же AJAX-компонент Bitrix, который обслуживает
страницу https://mtuci.ru/time-table/. Эндпоинт открыт и не требует
авторизации; проект не связан с университетом
"""

from __future__ import annotations

from .client import LEVELS, MOSCOW_SITE_ID, TimetableClient
from .errors import (
    AmbiguousQuery,
    ApiError,
    BotCheckError,
    MonthUnavailable,
    MtuciTimetableError,
    NotFound,
    TransportError,
)
from .models import Day, EntityType, Lesson, SearchItem, Timetable
from .session import DEFAULT_USER_AGENT

__version__ = "0.1.0"

__all__ = [
    "TimetableClient",
    "LEVELS",
    "MOSCOW_SITE_ID",
    "DEFAULT_USER_AGENT",
    "EntityType",
    "SearchItem",
    "Lesson",
    "Day",
    "Timetable",
    "MtuciTimetableError",
    "TransportError",
    "BotCheckError",
    "ApiError",
    "NotFound",
    "AmbiguousQuery",
    "MonthUnavailable",
]
