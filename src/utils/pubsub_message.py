from __future__ import annotations

import base64
import json
from typing import Any

def decode_pubsub_push_request(request) -> dict[str, Any]:
    envelope = request.get_json(silent=True)
    if not envelope or "message" not in envelope:
        raise ValueError("Pub/Sub push envelope is invalid")

    data = envelope["message"].get("data")
    if not data:
        raise ValueError("Pub/Sub message data is missing")

    decoded = base64.b64decode(data).decode("utf-8")
    return json.loads(decoded)

def require_fields(payload: dict[str, Any], required_fields: list[str]) -> None:
    for field in required_fields:
        if field not in payload or payload[field] in (None, ""):
            raise ValueError(f"missing required field: {field}")

def to_pubsub_data(payload: dict[str, Any]) -> bytes:
    return json.dumps(payload, ensure_ascii=False).encode("utf-8")
