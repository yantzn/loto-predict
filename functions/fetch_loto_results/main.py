from __future__ import annotations

import json
import logging
import os
import sys
from pathlib import Path
from typing import Any

from google.cloud import pubsub_v1

CURRENT_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = CURRENT_DIR.parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.append(str(PROJECT_ROOT))

from src.config.settings import settings
from src.infrastructure.gcs.storage_factory import create_storage_client
from src.infrastructure.rakuten_loto import RakutenLotoClient
from src.usecases.fetch_latest_results import FetchLatestResultsUseCase

logging.basicConfig(level=os.getenv("LOG_LEVEL", "INFO"))
logger = logging.getLogger(__name__)

IMPORT_TOPIC_NAME = os.getenv("PUBSUB_IMPORT_TOPIC", "import-loto-results")
RAW_BUCKET_NAME = os.getenv("GCS_BUCKET_RAW", "")


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

    normalized = str(lottery_type).strip().upper()
    if normalized not in {"LOTO6", "LOTO7"}:
        raise ValueError("lottery_type must be LOTO6 or LOTO7")

    return normalized


def _extract_execution_id(request) -> str:
    body = request.get_json(silent=True) or {}
    execution_id = body.get("execution_id") or request.args.get("execution_id")
    return str(execution_id).strip() if execution_id else ""


def _publish_import_message(
    *,
    execution_id: str,
    lottery_type: str,
    gcs_object: str,
    draw_no: int,
    draw_date: str,
) -> str:
    if settings.app_env == "local":
        logger.info(
            "Skip Pub/Sub publish in local mode. execution_id=%s lottery_type=%s gcs_object=%s",
            execution_id,
            lottery_type,
            gcs_object,
        )
        return "local-skip"

    publisher = pubsub_v1.PublisherClient()
    topic_path = publisher.topic_path(settings.gcp_project_id, IMPORT_TOPIC_NAME)

    message = {
        "event_type": "FETCH_COMPLETED",
        "execution_id": execution_id,
        "lottery_type": lottery_type,
        "gcs_bucket": RAW_BUCKET_NAME,
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
    execution_id = ""
    lottery_type = ""

    try:
        lottery_type = _extract_lottery_type(request)
        execution_id = _extract_execution_id(request)

        scraper = RakutenLotoClient()
        storage_client = create_storage_client()

        usecase = FetchLatestResultsUseCase(
            scraper=scraper,
            gcs_client=storage_client,
            bucket_name=RAW_BUCKET_NAME,
            logger=logger,
        )

        result = usecase.execute(lottery_type.lower())

        publish_message_id = _publish_import_message(
            execution_id=execution_id,
            lottery_type=lottery_type,
            gcs_object=result["gcs_object"],
            draw_no=int(result["draw_no"]),
            draw_date=str(result["draw_date"]),
        )

        return _json_response(
            {
                "status": "ok",
                "execution_id": execution_id,
                "lottery_type": lottery_type,
                "gcs_uri": result["gcs_uri"],
                "gcs_bucket": RAW_BUCKET_NAME if settings.app_env != "local" else "",
                "gcs_object": result["gcs_object"],
                "draw_no": result["draw_no"],
                "draw_date": result["draw_date"],
                "published_message_id": publish_message_id,
            }
        )

    except Exception as exc:
        logger.exception(
            "fetch_loto_results failed. execution_id=%s lottery_type=%s",
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
