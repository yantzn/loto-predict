from __future__ import annotations

import base64
import json

import functions_framework
from flask import Request

from src.loto_predict.config import Settings
from src.loto_predict.infrastructure.bigquery_client import BigQueryClient
from src.loto_predict.infrastructure.line_client import LineClient
from src.loto_predict.infrastructure.loto_repository import LotoRepository
from src.loto_predict.usecases.generate_and_notify import GenerateAndNotifyUseCase
from src.loto_predict.utils.logger import configure_logging
from src.loto_predict.utils.validators import validate_lottery_type


def _parse_pubsub_push_request(request: Request) -> dict:
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


@functions_framework.http
def entry_point(request: Request):
    settings = Settings()
    logger = configure_logging(settings.log_level)

    payload = _parse_pubsub_push_request(request)
    lottery_type = str(payload.get("lottery_type", "")).strip().lower()
    validate_lottery_type(lottery_type)

    history_limit = (
        settings.history_limit_loto6
        if lottery_type == "loto6"
        else settings.history_limit_loto7
    )

    bq_client = BigQueryClient(settings.gcp_project_id)
    repository = LotoRepository(
        bq_client=bq_client,
        dataset=settings.bq_dataset,
        table_loto6=settings.bq_table_loto6_history,
        table_loto7=settings.bq_table_loto7_history,
        prediction_runs_table=settings.bq_table_prediction_runs,
    )
    line_client = LineClient(settings.line_channel_access_token)

    usecase = GenerateAndNotifyUseCase(
        repository=repository,
        line_client=line_client,
        logger=logger,
    )

    result = usecase.execute(
        lottery_type=lottery_type,
        history_limit=history_limit,
        line_to_user_id=settings.line_to_user_id,
    )

    response = {
        "status": "completed",
        "stage": "notify_completed",
        "lottery_type": lottery_type,
        "result": result,
    }
    return (
        json.dumps(response, ensure_ascii=False),
        200,
        {"Content-Type": "application/json"},
    )
