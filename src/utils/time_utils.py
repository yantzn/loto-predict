from __future__ import annotations

import os
from datetime import datetime
from zoneinfo import ZoneInfo

APP_TIMEZONE = os.getenv("APP_TIMEZONE", "Asia/Tokyo")

# アプリケーションのタイムゾーン（デフォルト: Asia/Tokyo）
APP_TIMEZONE = os.getenv("APP_TIMEZONE", "Asia/Tokyo")

def now_local() -> datetime:
    return datetime.now(ZoneInfo(APP_TIMEZONE))

def today_local_iso() -> str:
    """
    現地タイムゾーンの日付（YYYY-MM-DD）をISO形式で返す。
    Returns:
        str: 日付文字列
    """
    return now_local().date().isoformat()

def now_local_iso() -> str:
    """
    現地タイムゾーンの現在時刻をISO8601文字列で返す。
    Returns:
        str: 日時文字列
    """
    return now_local().isoformat()
