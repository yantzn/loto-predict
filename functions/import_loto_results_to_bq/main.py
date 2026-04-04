from __future__ import annotations

import json
from urllib.parse import unquote

import functions_framework

from src.loto_predict.config import Settings
from src.loto_predict.infrastructure.bigquery_client import BigQueryClient
from src.loto_predict.infrastructure.gcs_client import GCSClient
from src.loto_predict.infrastructure.loto_repository import LotoRepository
from src.loto_predict.usecases.import_results_csv import ImportResultsCsvUseCase
from src.loto_predict.utils.logger import configure_logging
from src.loto_predict.utils.validators import validate_lottery_type


def _build_usecase(settings: Settings):
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


@functions_framework.http
def import_loto_results_http(request):
    settings = Settings()
    usecase, _logger = _build_usecase(settings)

    body = request.get_json(silent=True) or {}
    lottery_type = body.get("lottery_type", "").strip()
    gcs_uri = body.get("gcs_uri", "").strip()

    validate_lottery_type(lottery_type)
    result = usecase.execute(lottery_type, gcs_uri)
    return (json.dumps(result, ensure_ascii=False), 200, {"Content-Type": "application/json"})


@functions_framework.cloud_event
def import_loto_results_event(cloud_event):
    settings = Settings()
    usecase, logger = _build_usecase(settings)

    data = cloud_event.data
    bucket = data["bucket"]
    name = unquote(data["name"])

    if not name.endswith(".csv"):
        logger.info("Skip non-csv object: %s", name)
        return

    lottery_type = "loto6" if "loto6" in name else "loto7" if "loto7" in name else None
    if lottery_type is None:
        logger.info("Skip unsupported csv path: %s", name)
        return

    gcs_uri = f"gs://{bucket}/{name}"
    usecase.execute(lottery_type, gcs_uri)
