from __future__ import annotations

import json
import logging
import os
import sys
import uuid
from pathlib import Path
from typing import Any

from google.cloud import pubsub_v1

CURRENT_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = CURRENT_DIR.parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.append(str(PROJECT_ROOT))

from src.config.settings import get_settings
from src.infrastructure.gcs.storage_factory import create_storage_client
from src.infrastructure.rakuten_loto import RakutenLotoClient
from src.usecases.fetch_latest_results import FetchLatestResultsUseCase

logging.basicConfig(level=os.getenv("LOG_LEVEL", "INFO"))
logger = logging.getLogger(__name__)


def _json_response(payload: dict[str, Any], status_code: int = 200):
    return (
        json.dumps(payload, ensure_ascii=False),
        status_code,
        {"Content-Type": "application/json; charset=utf-8"},
    )


def _extract_lottery_type(request) -> str:
    body = request.get_json(silent=True) or {}
    lottery_type = body.get("lottery_type") or request.args.get("lottery_type")
    if not lottery_type:
        raise ValueError("lottery_type is required")

    normalized = str(lottery_type).strip().lower()
    if normalized not in {"loto6", "loto7"}:
        raise ValueError("lottery_type must be loto6 or loto7")
    return normalized


def _extract_execution_id(request) -> str:
    body = request.get_json(silent=True) or {}
    execution_id = body.get("execution_id") or request.args.get("execution_id")
    return str(execution_id).strip() if execution_id else str(uuid.uuid4())


def _publish_import_message(
    *,
    execution_id: str,
    lottery_type: str,
    gcs_bucket: str,
    gcs_object: str,
    draw_no: int,
    draw_date: str,
) -> str:
    settings = get_settings()

    if settings.is_local:
        logger.info(
            "Skip Pub/Sub publish in local mode. execution_id=%s lottery_type=%s gcs_object=%s",
            execution_id,
            lottery_type,
            gcs_object,
        )
        return "local-skip"

    if not settings.gcp.project_id:
        raise ValueError("GCP_PROJECT_ID is required in non-local mode")

    publisher = pubsub_v1.PublisherClient()
    topic_path = publisher.topic_path(settings.gcp.project_id, settings.gcp.import_topic_name)

    message = {
        "event_type": "FETCH_COMPLETED",
        "execution_id": execution_id,
        "lottery_type": lottery_type,
        "gcs_bucket": gcs_bucket,
        "gcs_object": gcs_object,
        "draw_no": draw_no,
        "draw_date": draw_date,
    }

    future = publisher.publish(
        topic_path,
        json.dumps(message, ensure_ascii=False).encode("utf-8"),
    )
    return future.result()


def entry_point(request):
    settings = get_settings()
    execution_id = ""
    lottery_type = ""
    try:
        data = request.get_json()
        lottery_type = data.get("lottery_type")
        execution_id = data.get("execution_id")
        result = fetch_and_save_latest_results(lottery_type)
        # Pub/Sub import topic へpublish（ダミー）
        # publish_import_topic(result)
        logger.info(f"fetch_loto_results: lottery_type={lottery_type} draw_no={result['draw_no']} execution_id={execution_id}")
        return {"status": "ok", "result": result}
    except Exception as e:
        logger.error(f"fetch_loto_results error: {e}")
        return {"status": "error", "message": str(e)}
