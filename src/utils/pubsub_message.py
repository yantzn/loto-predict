from __future__ import annotations

import base64
import json
from typing import Any

def decode_pubsub_push_request(request) -> dict[str, Any]:
    """
    GCP Pub/SubのPushリクエストからメッセージデータをデコードして辞書化する。
    なぜ必要か:
      - Push配送時のHTTPボディは「envelope(message.data=base64)」形式で届くため、
        ユースケースで扱える辞書形式に正規化する前処理が必要。
    Args:
        request: Flask等のリクエストオブジェクト
    Returns:
        dict: デコード済みメッセージ
    Raises:
        ValueError: フォーマット不正やデータ欠損時
    """
    envelope = request.get_json(silent=True)
    # 受信ボディ全体(envelope)を取り出し、Pub/Sub形式かを先に検証する。
    if not envelope or "message" not in envelope:
        raise ValueError("Pub/Sub push envelope is invalid")

    data = envelope["message"].get("data")
    if not data:
        raise ValueError("Pub/Sub message data is missing")

    # 実データはbase64文字列で入っているため、取り出し必須。
    decoded = base64.b64decode(data).decode("utf-8")
    return json.loads(decoded)

def require_fields(payload: dict[str, Any], required_fields: list[str]) -> None:
    """
    指定フィールドがpayloadに全て存在するか検証。
    なぜ必要か:
      - 入口で必須項目を揃えておくと、下流処理でのKeyErrorや不正状態を早期に防げる。
    Args:
        payload (dict): 検証対象データ
        required_fields (list[str]): 必須フィールド名リスト
    Raises:
        ValueError: 欠損時
    """
    for field in required_fields:
        if field not in payload or payload[field] in (None, ""):
            raise ValueError(f"missing required field: {field}")

def to_pubsub_data(payload: dict[str, Any]) -> bytes:
    """
    dictをPub/Sub送信用のバイト列(JSON, UTF-8)に変換。
    なぜ必要か:
      - Pub/Sub publishはbytesを受け取るため、送信前に共通フォーマットへ変換する。
    Args:
        payload (dict): 送信データ
    Returns:
        bytes: エンコード済みデータ
    """
    return json.dumps(payload, ensure_ascii=False).encode("utf-8")
