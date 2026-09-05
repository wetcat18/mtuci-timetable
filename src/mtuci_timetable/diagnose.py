from __future__ import annotations

import sys
from datetime import date

import requests

from .client import TimetableClient
from .errors import BotCheckError, MtuciTimetableError
from .session import DEFAULT_USER_AGENT

BASE_URL = "https://mtuci.ru"
ENDPOINT = f"{BASE_URL}/bitrix/services/main/ajax.php"
PARAMS = {"c": "mtuci:timetable", "action": "getItemsListBySearch", "mode": "class"}


def _probe(label: str, headers: dict[str, str]) -> bool:
    try:
        response = requests.post(
            ENDPOINT, params=PARAMS, data={"NAME": "БВТ"}, headers=headers, timeout=20
        )
    except requests.RequestException as exc:
        print(f"  [сеть]  {label}: {type(exc).__name__}: {exc}")
        return False

    body = response.text[:120].replace("\n", " ")
    if "html" in response.headers.get("Content-Type", "").lower():
        print(f"  [капча] {label}: HTTP {response.status_code}, пришёл HTML: {body}")
        return False
    print(f"  [ок]    {label}: HTTP {response.status_code}, {body}")
    return True


def main() -> int:
    print("1. Сырые запросы\n")
    bare = _probe("без заголовков", {})
    with_ua = _probe("с браузерным User-Agent", {"User-Agent": DEFAULT_USER_AGENT})

    print("\n2. Через библиотеку\n")
    try:
        with TimetableClient() as client:
            found = client.search("БВТ")
            print(f"  [ок]    поиск: {len(found)} совпадений, первое — {found[0].name}")
            timetable = client.timetable(found[0], month=date.today())
            print(f"  [ок]    расписание: {timetable}")
    except BotCheckError as exc:
        print(f"  [капча] {exc}")
        return 1
    except MtuciTimetableError as exc:
        print(f"  [ошибка] {type(exc).__name__}: {exc}")
        return 1

    print("\nИтог:")
    if bare:
        print("  Антибот пропускает даже голый requests.")
    elif with_ua:
        print("  Антибот смотрит на User-Agent, браузерного хватает.")
    else:
        print("  Сырые запросы не проходят, но сессия библиотеки работает —")
        print("  дело в прогреве и куках, менять ничего не нужно.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
