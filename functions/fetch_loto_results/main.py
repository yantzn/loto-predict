from __future__ import annotations

import base64
import json
from typing import Any

import functions_framework
from google.cloud import pubsub_v1

from src.loto_predict.config import Settings
from src.loto_predict.infrastructure.gcs_client import GCSClient
from src.loto_predict.infrastructure.scraper import LotoScraper
from src.loto_predict.usecases.fetch_latest_results import FetchLatestResultsUseCase
from src.loto_predict.utils.logger import configure_logging
from src.loto_predict.utils.validators import validate_lottery_type


def _build_publisher(settings: Settings) -> tuple[pubsub_v1.PublisherClient, str]:
    publisher = pubsub_v1.PublisherClient()
    topic_path = publisher.topic_path(
        settings.gcp_project_id,
        settings.pubsub_import_topic,
    )
    return publisher, topic_path


def _publish_import_request(
    *,
    publisher: pubsub_v1.PublisherClient,
    topic_path: str,
    lottery_type: str,
    gcs_uri: str,
    logger: Any,
) -> str:
    payload = {
        "lottery_type": lottery_type,
        "gcs_uri": gcs_uri,
    }
    future = publisher.publish(
        topic_path,
        json.dumps(payload, ensure_ascii=False).encode("utf-8"),
        lottery_type=lottery_type,
    )
    message_id = future.result()
    logger.info(
        "Published import request. lottery_type=%s gcs_uri=%s message_id=%s",
        lottery_type,
        gcs_uri,
        message_id,
    )
    return message_id


@functions_framework.http
def entry_point(request):
    settings = Settings()
    logger = configure_logging(settings.log_level)

    body = request.get_json(silent=True) or {}
    lottery_type = str(body.get("lottery_type", "")).strip().lower()
    validate_lottery_type(lottery_type)

    usecase = FetchLatestResultsUseCase(
        scraper=LotoScraper(),
        gcs_client=GCSClient(settings.gcp_project_id),
        bucket_name=settings.gcs_bucket_raw,
        logger=logger,
    )

    result = usecase.execute(lottery_type)

    gcs_uri = result.get("gcs_uri")
    if not gcs_uri:
        raise ValueError("Fetch result does not include gcs_uri.")

    publisher, topic_path = _build_publisher(settings)
    message_id = _publish_import_request(
        publisher=publisher,
        topic_path=topic_path,
        lottery_type=lottery_type,
        gcs_uri=gcs_uri,
        logger=logger,
    )

    response = {
        "status": "accepted",
        "stage": "fetch_completed",
        "lottery_type": lottery_type,
        "gcs_uri": gcs_uri,
        "pubsub_message_id": message_id,
        "fetch_result": result,
    }
    return (
        json.dumps(response, ensure_ascii=False),
        200,
        {"Content-Type": "application/json"},
    )
