from __future__ import annotations

import json
from typing import Any
from urllib.parse import unquote

import functions_framework
from flask import Request

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


def _infer_lottery_type_from_path(object_name: str) -> str | None:
    lowered = object_name.lower()
    if "loto6" in lowered:
        return "loto6"
    if "loto7" in lowered:
        return "loto7"
    return None


def _handle_manual_request(request: Request, usecase: ImportResultsCsvUseCase) -> tuple[str, int, dict[str, str]]:
    body = request.get_json(silent=True) or {}
    lottery_type = str(body.get("lottery_type", "")).strip()
    gcs_uri = str(body.get("gcs_uri", "")).strip()

    validate_lottery_type(lottery_type)
    result = usecase.execute(lottery_type, gcs_uri)
    return (
        json.dumps(result, ensure_ascii=False),
        200,
        {"Content-Type": "application/json"},
    )


def _handle_eventarc_request(
    request: Request,
    usecase: ImportResultsCsvUseCase,
    logger: Any,
) -> tuple[str, int, dict[str, str]]:
    envelope = request.get_json(silent=True) or {}
    data = envelope.get("data") or {}

    bucket = data.get("bucket")
    object_name = data.get("name")

    if not bucket or not object_name:
        logger.info("Skip request because bucket/name is missing in Eventarc payload.")
        return (
            json.dumps({"status": "skipped", "reason": "missing bucket or object name"}, ensure_ascii=False),
            200,
            {"Content-Type": "application/json"},
        )

    object_name = unquote(str(object_name))

    if not object_name.endswith(".csv"):
        logger.info("Skip non-csv object: %s", object_name)
        return (
            json.dumps({"status": "skipped", "reason": "non-csv object"}, ensure_ascii=False),
            200,
            {"Content-Type": "application/json"},
        )

    lottery_type = _infer_lottery_type_from_path(object_name)
    if lottery_type is None:
        logger.info("Skip unsupported csv path: %s", object_name)
        return (
            json.dumps({"status": "skipped", "reason": "unsupported lottery path"}, ensure_ascii=False),
            200,
            {"Content-Type": "application/json"},
        )

    gcs_uri = f"gs://{bucket}/{object_name}"
    result = usecase.execute(lottery_type, gcs_uri)
    result["trigger"] = "eventarc"

    return (
        json.dumps(result, ensure_ascii=False),
        200,
        {"Content-Type": "application/json"},
    )


@functions_framework.http
def import_loto_results(request: Request):
    settings = Settings()
    usecase, logger = _build_usecase(settings)

    ce_type = request.headers.get("ce-type")
    if ce_type == "google.cloud.storage.object.v1.finalized":
        return _handle_eventarc_request(request, usecase, logger)

    return _handle_manual_request(request, usecase)
