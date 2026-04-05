from __future__ import annotations

import logging
import os
import csv
import io
from typing import Any

from google.cloud import bigquery, pubsub_v1, storage

from common.execution_log import log_and_write
from common.pubsub_message import decode_pubsub_push_request, require_fields, to_pubsub_data
from common.time_utils import now_local_iso

logging.basicConfig(level=os.getenv("LOG_LEVEL", "INFO"))
logger = logging.getLogger(__name__)

PROJECT_ID = os.environ["GCP_PROJECT_ID"]
DATASET_ID = os.environ["BIGQUERY_DATASET"]
TABLE_LOTO6 = os.environ["BQ_TABLE_LOTO6_HISTORY"]
TABLE_LOTO7 = os.environ["BQ_TABLE_LOTO7_HISTORY"]
NOTIFY_TOPIC_NAME = os.environ["NOTIFY_TOPIC_NAME"]

storage_client = storage.Client(project=PROJECT_ID)
bq_client = bigquery.Client(project=PROJECT_ID)
publisher = pubsub_v1.PublisherClient()
notify_topic_path = publisher.topic_path(PROJECT_ID, NOTIFY_TOPIC_NAME)


def _table_name(lottery_type: str) -> str:
    if lottery_type == "LOTO6":
        return TABLE_LOTO6
    if lottery_type == "LOTO7":
        return TABLE_LOTO7
    raise ValueError(f"unsupported lottery_type: {lottery_type}")


def _read_csv_rows(bucket_name: str, object_name: str) -> list[dict[str, str]]:
    blob = storage_client.bucket(bucket_name).blob(object_name)
    text = blob.download_as_text(encoding="utf-8")
    return list(csv.DictReader(io.StringIO(text)))


def _normalize_rows(
    lottery_type: str,
    rows: list[dict[str, str]],
    source_file_name: str,
) -> list[dict[str, Any]]:
    normalized: list[dict[str, Any]] = []

    for row in rows:
        if lottery_type == "LOTO6":
            normalized.append({
                "draw_no": int(row["draw_no"]),
                "draw_date": row["draw_date"],
                "number1": int(row["number1"]),
                "number2": int(row["number2"]),
                "number3": int(row["number3"]),
                "number4": int(row["number4"]),
                "number5": int(row["number5"]),
                "number6": int(row["number6"]),
                "bonus_number": int(row["bonus_number"]) if row.get("bonus_number") else None,
                "source_file_name": source_file_name,
                "ingested_at": now_local_iso(),
            })
        else:
            normalized.append({
                "draw_no": int(row["draw_no"]),
                "draw_date": row["draw_date"],
                "number1": int(row["number1"]),
                "number2": int(row["number2"]),
                "number3": int(row["number3"]),
                "number4": int(row["number4"]),
                "number5": int(row["number5"]),
                "number6": int(row["number6"]),
                "number7": int(row["number7"]),
                "bonus_number1": int(row["bonus_number1"]) if row.get("bonus_number1") else None,
                "bonus_number2": int(row["bonus_number2"]) if row.get("bonus_number2") else None,
                "source_file_name": source_file_name,
                "ingested_at": now_local_iso(),
            })

    return normalized


def _extract_draw_nos(rows: list[dict[str, Any]]) -> list[int]:
    return sorted({int(row["draw_no"]) for row in rows})


def _exists_same_source_file(table_id: str, source_file_name: str) -> bool:
    query = f"""
    SELECT COUNT(1) AS cnt
    FROM `{table_id}`
    WHERE source_file_name = @source_file_name
    """
    job = bq_client.query(
        query,
        job_config=bigquery.QueryJobConfig(
            query_parameters=[
                bigquery.ScalarQueryParameter("source_file_name", "STRING", source_file_name)
            ]
        ),
    )
    return list(job.result())[0]["cnt"] > 0


def _existing_draw_nos(table_id: str, draw_nos: list[int]) -> set[int]:
    query = f"""
    SELECT draw_no
    FROM `{table_id}`
    WHERE draw_no IN UNNEST(@draw_nos)
    """
    job = bq_client.query(
        query,
        job_config=bigquery.QueryJobConfig(
            query_parameters=[
                bigquery.ArrayQueryParameter("draw_nos", "INT64", draw_nos)
            ]
        ),
    )
    return {int(row["draw_no"]) for row in job.result()}


def _insert_rows(table_id: str, rows: list[dict[str, Any]]) -> None:
    errors = bq_client.insert_rows_json(table_id, rows)
    if errors:
        raise RuntimeError(f"BigQuery insert failed: {errors}")


def _publish_notify_message(
    execution_id: str,
    lottery_type: str,
    bucket_name: str,
    object_name: str,
    table_id: str,
    imported_rows: int,
    skipped_as_duplicate: bool,
) -> str:
    message = {
        "event_type": "IMPORT_COMPLETED",
        "execution_id": execution_id,
        "lottery_type": lottery_type,
        "gcs_bucket": bucket_name,
        "gcs_object": object_name,
        "target_table": table_id,
        "imported_rows": imported_rows,
        "skipped_as_duplicate": skipped_as_duplicate,
        "imported_at": now_local_iso(),
    }
    future = publisher.publish(notify_topic_path, to_pubsub_data(message))
    return future.result()


def entry_point(request):
    execution_id = ""
    lottery_type = ""
    bucket_name = None
    object_name = None

    try:
        message = decode_pubsub_push_request(request)
        require_fields(message, ["execution_id", "lottery_type", "gcs_bucket", "gcs_object"])

        execution_id = message["execution_id"]
        lottery_type = message["lottery_type"]
        bucket_name = message["gcs_bucket"]
        object_name = message["gcs_object"]

        log_and_write(
            execution_id=execution_id,
            function_name="import_loto_results_to_bq",
            lottery_type=lottery_type,
            stage="import",
            status="STARTED",
            message="import started",
            gcs_bucket=bucket_name,
            gcs_object=object_name,
        )

        table_id = f"{PROJECT_ID}.{DATASET_ID}.{_table_name(lottery_type)}"
        raw_rows = _read_csv_rows(bucket_name, object_name)
        normalized_rows = _normalize_rows(lottery_type, raw_rows, object_name)
        draw_nos = _extract_draw_nos(normalized_rows)

        if _exists_same_source_file(table_id, object_name):
            log_and_write(
                execution_id=execution_id,
                function_name="import_loto_results_to_bq",
                lottery_type=lottery_type,
                stage="import",
                status="SKIPPED_DUPLICATE",
                message="duplicate by source_file_name",
                gcs_bucket=bucket_name,
                gcs_object=object_name,
                draw_no=draw_nos[0] if draw_nos else None,
            )
            return {"status": "ok", "reason": "duplicate_source_file"}, 200

        existing_draws = _existing_draw_nos(table_id, draw_nos)
        rows_to_insert = [row for row in normalized_rows if int(row["draw_no"]) not in existing_draws]

        if not rows_to_insert:
            log_and_write(
                execution_id=execution_id,
                function_name="import_loto_results_to_bq",
                lottery_type=lottery_type,
                stage="import",
                status="SKIPPED_DUPLICATE",
                message="duplicate by draw_no",
                gcs_bucket=bucket_name,
                gcs_object=object_name,
                draw_no=draw_nos[0] if draw_nos else None,
            )
            return {"status": "ok", "reason": "duplicate_draw_no"}, 200

        _insert_rows(table_id, rows_to_insert)
        _publish_notify_message(
            execution_id=execution_id,
            lottery_type=lottery_type,
            bucket_name=bucket_name,
            object_name=object_name,
            table_id=table_id,
            imported_rows=len(rows_to_insert),
            skipped_as_duplicate=False,
        )

        log_and_write(
            execution_id=execution_id,
            function_name="import_loto_results_to_bq",
            lottery_type=lottery_type,
            stage="import",
            status="SUCCESS",
            message=f"imported_rows={len(rows_to_insert)}",
            gcs_bucket=bucket_name,
            gcs_object=object_name,
            draw_no=draw_nos[0] if draw_nos else None,
        )

        return {"status": "ok", "inserted_rows": len(rows_to_insert)}, 200

    except Exception as exc:
        log_and_write(
            execution_id=execution_id or "UNKNOWN",
            function_name="import_loto_results_to_bq",
            lottery_type=lottery_type or None,
            stage="import",
            status="FAILED",
            message="import failed",
            gcs_bucket=bucket_name,
            gcs_object=object_name,
            error_type=type(exc).__name__,
            error_detail=str(exc),
        )
        logger.exception("import_loto_results_to_bq failed")
        return {"error": str(exc)}, 500
