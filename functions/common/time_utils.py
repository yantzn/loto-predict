"""
タイムゾーン付きの現在時刻・日付取得ユーティリティ
アプリ全体で一貫したローカル時刻（デフォルト: Asia/Tokyo）を扱うための関数群
"""

from __future__ import annotations

import os
from datetime import datetime
from zoneinfo import ZoneInfo

#
# アプリケーションで利用するタイムゾーン名（環境変数APP_TIMEZONEで上書き可）
# デフォルトは"Asia/Tokyo"
APP_TIMEZONE = os.getenv("APP_TIMEZONE", "Asia/Tokyo")


#
# 現在のローカル時刻（タイムゾーン付き）をdatetime型で返す
# - APP_TIMEZONEで指定したタイムゾーンを常に利用
#
def now_local() -> datetime:
    return datetime.now(ZoneInfo(APP_TIMEZONE))


#
# 現在のローカル日付（YYYY-MM-DD形式のISO文字列）を返す
#
def today_local_iso() -> str:
    return now_local().date().isoformat()


#
# 現在のローカル時刻（ISO8601文字列、タイムゾーン付き）を返す
#
def now_local_iso() -> str:
    return now_local().isoformat()
