from __future__ import annotations

import logging
import os
from typing import Any

from google.cloud import bigquery

from common.time_utils import now_local, now_local_iso

logger = logging.getLogger(__name__)

PROJECT_ID = os.environ["GCP_PROJECT_ID"]
DATASET_ID = os.environ["BIGQUERY_DATASET"]
TABLE_EXECUTION_LOGS = os.getenv("BQ_TABLE_EXECUTION_LOGS", "execution_logs")

bq_client = bigquery.Client(project=PROJECT_ID)


def execution_logs_table_id() -> str:
    return f"{PROJECT_ID}.{DATASET_ID}.{TABLE_EXECUTION_LOGS}"


def write_execution_log(
    *,
    execution_id: str,
    function_name: str,
    lottery_type: str | None,
    stage: str | None,
    status: str,
    message: str | None = None,
    gcs_bucket: str | None = None,
    gcs_object: str | None = None,
    draw_no: int | None = None,
    run_id: str | None = None,
    error_type: str | None = None,
    error_detail: str | None = None,
) -> None:
    row: dict[str, Any] = {
        "execution_id": execution_id,
        "function_name": function_name,
        "lottery_type": lottery_type,
        "stage": stage,
        "status": status,
        "message": message,
        "gcs_bucket": gcs_bucket,
        "gcs_object": gcs_object,
        "draw_no": draw_no,
        "run_id": run_id,
        "error_type": error_type,
        "error_detail": error_detail,
        "executed_at": now_local_iso(),
        "executed_date": now_local().date().isoformat(),
    }

    try:
        errors = bq_client.insert_rows_json(execution_logs_table_id(), [row])
        if errors:
            logger.error("failed to insert execution log: %s", errors)
    except Exception:
        logger.exception("unexpected error while writing execution log")


def log_and_write(
    *,
    execution_id: str,
    function_name: str,
    lottery_type: str | None,
    stage: str | None,
    status: str,
    message: str | None = None,
    gcs_bucket: str | None = None,
    gcs_object: str | None = None,
    draw_no: int | None = None,
    run_id: str | None = None,
    error_type: str | None = None,
    error_detail: str | None = None,
) -> None:
    structured = {
        "execution_id": execution_id,
        "function_name": function_name,
        "lottery_type": lottery_type,
        "stage": stage,
        "status": status,
        "message": message,
        "gcs_bucket": gcs_bucket,
        "gcs_object": gcs_object,
        "draw_no": draw_no,
        "run_id": run_id,
        "error_type": error_type,
    }
    logger.info(structured)

    write_execution_log(
        execution_id=execution_id,
        function_name=function_name,
        lottery_type=lottery_type,
        stage=stage,
        status=status,
        message=message,
        gcs_bucket=gcs_bucket,
        gcs_object=gcs_object,
        draw_no=draw_no,
        run_id=run_id,
        error_type=error_type,
        error_detail=error_detail,
    )
