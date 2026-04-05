from __future__ import annotations

import os
from datetime import datetime
from zoneinfo import ZoneInfo

APP_TIMEZONE = os.getenv("APP_TIMEZONE", "Asia/Tokyo")


def now_local() -> datetime:
    return datetime.now(ZoneInfo(APP_TIMEZONE))


def today_local_iso() -> str:
    return now_local().date().isoformat()


def now_local_iso() -> str:
    return now_local().isoformat()
