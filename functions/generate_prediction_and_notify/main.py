from __future__ import annotations

import base64
import json
import logging
import os
import sys
from pathlib import Path
from typing import Any

CURRENT_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = CURRENT_DIR.parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.append(str(PROJECT_ROOT))

from src.config.settings import settings
from src.infrastructure.bigquery.bigquery_client import BigQueryClient
from src.infrastructure.line.line_client import LineClient
from src.infrastructure.repositories.repository_factory import create_loto_repository
from src.usecases.generate_and_notify import GenerateAndNotifyUseCase

logging.basicConfig(level=os.getenv("LOG_LEVEL", "INFO"))
logger = logging.getLogger(__name__)


def _json_response(payload: dict[str, Any], status_code: int = 200):
    return (
        json.dumps(payload, ensure_ascii=False),
        status_code,
        {"Content-Type": "application/json; charset=utf-8"},
    )


def _extract_event_message(request) -> dict[str, Any]:
    body = request.get_json(silent=True) or {}

    if "message" in body and isinstance(body["message"], dict):
        encoded = body["message"].get("data")
        if not encoded:
            raise ValueError("Pub/Sub message.data is missing")
        decoded = base64.b64decode(encoded).decode("utf-8")
        return json.loads(decoded)

    return body


def _require_fields(message: dict[str, Any], required_fields: list[str]) -> None:
    missing = [field for field in required_fields if not message.get(field)]
    if missing:
        raise ValueError(f"missing required fields: {', '.join(missing)}")


def _history_limit_for(lottery_type: str) -> int:
    key = f"HISTORY_LIMIT_{lottery_type.upper()}"
    return int(os.getenv(key, "100"))


def entry_point(request):
    execution_id = ""
    lottery_type = ""

    try:
        message = _extract_event_message(request)
        _require_fields(message, ["execution_id", "lottery_type"])

        execution_id = str(message["execution_id"]).strip()
        lottery_type = str(message["lottery_type"]).strip().upper()

        if lottery_type not in {"LOTO6", "LOTO7"}:
            raise ValueError("lottery_type must be LOTO6 or LOTO7")

        if not settings.line_channel_access_token:
            raise ValueError("LINE_CHANNEL_ACCESS_TOKEN is not set")
        if not settings.line_to_user_id:
            raise ValueError("LINE_TO_USER_ID is not set")

        history_limit = _history_limit_for(lottery_type)

        bq_client = None if settings.app_env == "local" else BigQueryClient(project_id=settings.gcp_project_id)
        repository = create_loto_repository(bq_client=bq_client)

        line_client = LineClient(
            channel_access_token=settings.line_channel_access_token,
        )

        usecase = GenerateAndNotifyUseCase(
            repository=repository,
            line_client=line_client,
            logger=logger,
        )

        result = usecase.execute(
            lottery_type=lottery_type.lower(),
            history_limit=history_limit,
            line_to_user_id=settings.line_to_user_id,
        )

        return _json_response(
            {
                "status": "ok",
                "execution_id": execution_id,
                "lottery_type": lottery_type,
                "history_limit": history_limit,
                "result": result,
            }
        )

    except Exception as exc:
        logger.exception(
            "generate_prediction_and_notify failed. execution_id=%s lottery_type=%s",
            execution_id,
            lottery_type,
        )
        return _json_response(
            {
                "status": "error",
                "execution_id": execution_id,
                "lottery_type": lottery_type,
                "message": str(exc),
            },
            500,
        )
