from __future__ import annotations

import json

import functions_framework

from src.loto_predict.config import Settings
from src.loto_predict.infrastructure.bigquery_client import BigQueryClient
from src.loto_predict.infrastructure.line_client import LineClient
from src.loto_predict.infrastructure.loto_repository import LotoRepository
from src.loto_predict.usecases.generate_and_notify import GenerateAndNotifyUseCase
from src.loto_predict.utils.logger import configure_logging
from src.loto_predict.utils.validators import validate_lottery_type


@functions_framework.http
def generate_prediction_and_notify(request):
    settings = Settings()
    logger = configure_logging(settings.log_level)

    body = request.get_json(silent=True) or {}
    lottery_type = body.get("lottery_type", "").strip()

    validate_lottery_type(lottery_type)

    history_limit = settings.history_limit_loto6 if lottery_type == "loto6" else settings.history_limit_loto7

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
    return (json.dumps(result, ensure_ascii=False), 200, {"Content-Type": "application/json"})
