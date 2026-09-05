from __future__ import annotations

__all__ = [
    "MtuciTimetableError",
    "TransportError",
    "BotCheckError",
    "ApiError",
    "NotFound",
    "AmbiguousQuery",
    "MonthUnavailable",
]


class MtuciTimetableError(Exception):
    """Базовое исключение"""


class TransportError(MtuciTimetableError):
    """Сеть не ответила: таймаут, DNS, обрыв соединения."""


class BotCheckError(MtuciTimetableError):
    """Вместо JSON пришёл заслон антибота.

    Перед mtuci.ru стоит антибот, и решает он по User-Agent: запрос без него
    получает 403 «Access Blocked», обычный GET из не-браузера - страницу
    с капчей. Браузерного User-Agent, который клиент ставит по умолчанию,
    достаточно. Если проверка всё равно сработала, есть два пути:

    1. Открыть https://mtuci.ru/time-table/ в обычном браузере, пройти
       проверку, скопировать куки и передать их в клиент::

           TimetableClient(cookies={"...": "..."})

    2. Подставить свой User-Agent, совпадающий с браузером, из которого
       эти куки взяты::

           TimetableClient(user_agent="...")
    """


class ApiError(MtuciTimetableError):
    """Сервер ответил JSON-ом со status != success"""

    def __init__(self, action: str, messages: "list[str]") -> None:
        self.action = action
        self.messages = messages
        detail = "; ".join(messages) if messages else "без описания"
        super().__init__(f"{action}: {detail}")


class NotFound(MtuciTimetableError):
    """Поиск не нашёл ни одной группы, преподавателя или аудитории"""


class AmbiguousQuery(MtuciTimetableError):
    """Поиск нашёл больше одного совпадения, а нужно было ровно одно"""

    def __init__(self, query: str, matches: "list[str]") -> None:
        self.query = query
        self.matches = matches
        shown = ", ".join(matches[:5])
        tail = f" и ещё {len(matches) - 5}" if len(matches) > 5 else ""
        super().__init__(f"по запросу {query!r} найдено {len(matches)}: {shown}{tail}")


class MonthUnavailable(MtuciTimetableError):
    """Сервер вернул не тот месяц, который просили.

    Расписание доступно примерно на +-4 месяца от текущего, а год к номеру
    месяца сервер подставляет сам по зашитому правилу. Если запрошенный
    месяц вне окна, вернётся соседний - библиотека это ловит и не выдаёт
    чужие данные за нужные.
    """
