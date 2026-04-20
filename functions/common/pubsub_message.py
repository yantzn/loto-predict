"""
Pub/Subメッセージのデコード・バリデーション・エンコード用ユーティリティ
Google Cloud Functions等でPub/Sub Pushトリガーを扱う際に利用
"""

from __future__ import annotations

import base64
import json
from typing import Any


#
# Pub/Sub Pushリクエストのデータ部をデコードし、辞書型で返すユーティリティ関数
# - Google Cloud Functions等でPub/Sub Pushトリガーを受けた際に利用
# - base64デコード→JSONデコードまでを一括で行う
#
def decode_pubsub_push_request(request) -> dict[str, Any]:
    # リクエストボディをJSONとして取得
    envelope = request.get_json(silent=True)
    if not envelope or "message" not in envelope:
        # messageキーが無い場合は不正なリクエストとして例外
        raise ValueError("Pub/Sub push envelope is invalid")

    # dataフィールド（base64エンコード文字列）を取得
    data = envelope["message"].get("data")
    if not data:
        # dataが無い場合も例外
        raise ValueError("Pub/Sub message data is missing")

    # base64デコード→UTF-8デコード→JSONデコード
    decoded = base64.b64decode(data).decode("utf-8")
    return json.loads(decoded)


#
# 必須フィールドの存在・値チェックユーティリティ
# - payload: チェック対象の辞書
# - required_fields: 必須フィールド名リスト
# - いずれかが未設定(None/空文字)なら例外を投げる
#
def require_fields(payload: dict[str, Any], required_fields: list[str]) -> None:
    for field in required_fields:
        if field not in payload or payload[field] in (None, ""):
            raise ValueError(f"missing required field: {field}")


#
# Pub/Subへpublishする際のデータ変換ユーティリティ
# - payload: 任意の辞書
# - JSON文字列化→UTF-8バイト列化して返す
#
def to_pubsub_data(payload: dict[str, Any]) -> bytes:
    return json.dumps(payload, ensure_ascii=False).encode("utf-8")
