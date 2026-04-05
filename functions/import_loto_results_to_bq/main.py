from __future__ import annotations

import base64
import json
from typing import Any

import functions_framework
from flask import Request
from google.cloud import pubsub_v1

from src.loto_predict.config import Settings
from src.loto_predict.infrastructure.bigquery_client import BigQueryClient
from src.loto_predict.infrastructure.gcs_client import GCSClient
from src.loto_predict.infrastructure.loto_repository import LotoRepository
from src.loto_predict.usecases.import_results_csv import ImportResultsCsvUseCase
from src.loto_predict.utils.logger import configure_logging
from src.loto_predict.utils.validators import validate_lottery_type


def _build_usecase(settings: Settings) -> tuple[ImportResultsCsvUseCase, Any]:
    logger = configure_logging(settings.log_level)
    bq_client = BigQueryClient(settings.gcp_project_id)

    repository = LotoRepository(
        bq_client=bq_client,
        dataset=settings.bq_dataset,
        table_loto6=settings.bq_table_loto6_history,
        table_loto7=settings.bq_table_loto7_history,
        prediction_runs_table=settings.bq_table_prediction_runs,
    )

    usecase = ImportResultsCsvUseCase(
        settings=settings,
        gcs_client=GCSClient(settings.gcp_project_id),
        bq_client=bq_client,
        repository=repository,
        logger=logger,
    )
    return usecase, logger


def _build_publisher(settings: Settings) -> tuple[pubsub_v1.PublisherClient, str]:
    publisher = pubsub_v1.PublisherClient()
    topic_path = publisher.topic_path(
        settings.gcp_project_id,
        settings.pubsub_notify_topic,
    )
    return publisher, topic_path


def _parse_pubsub_push_request(request: Request) -> dict[str, Any]:
    envelope = request.get_json(silent=True) or {}

    message = envelope.get("message")
    if not message:
        raise ValueError("Pub/Sub push payload is missing 'message'.")

    data_b64 = message.get("data", "")
    if not data_b64:
        raise ValueError("Pub/Sub push payload is missing 'message.data'.")

    decoded = base64.b64decode(data_b64).decode("utf-8")
    payload = json.loads(decoded)

    if not isinstance(payload, dict):
        raise ValueError("Pub/Sub message data must decode to a JSON object.")

    return payload


def _publish_notify_request(
    *,
    publisher: pubsub_v1.PublisherClient,
    topic_path: str,
    lottery_type: str,
    logger: Any,
) -> str:
    payload = {
        "lottery_type": lottery_type,
    }
    future = publisher.publish(
        topic_path,
        json.dumps(payload, ensure_ascii=False).encode("utf-8"),
        lottery_type=lottery_type,
    )
    message_id = future.result()
    logger.info(
        "Published notify request. lottery_type=%s message_id=%s",
        lottery_type,
        message_id,
    )
    return message_id


@functions_framework.http
def entry_point(request: Request):
    settings = Settings()
    usecase, logger = _build_usecase(settings)

    payload = _parse_pubsub_push_request(request)
    lottery_type = str(payload.get("lottery_type", "")).strip().lower()
    gcs_uri = str(payload.get("gcs_uri", "")).strip()

    validate_lottery_type(lottery_type)
    if not gcs_uri:
        raise ValueError("Pub/Sub payload does not include gcs_uri.")

    result = usecase.execute(lottery_type, gcs_uri)

    publisher, topic_path = _build_publisher(settings)
    message_id = _publish_notify_request(
        publisher=publisher,
        topic_path=topic_path,
        lottery_type=lottery_type,
        logger=logger,
    )

    response = {
        "status": "accepted",
        "stage": "import_completed",
        "lottery_type": lottery_type,
        "gcs_uri": gcs_uri,
        "pubsub_message_id": message_id,
        "import_result": result,
    }
    return (
        json.dumps(response, ensure_ascii=False),
        200,
        {"Content-Type": "application/json"},
    )
