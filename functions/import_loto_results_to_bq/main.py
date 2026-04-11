from __future__ import annotations

import csv
import io
import json
import logging
import os
from typing import Any

from google.cloud import bigquery, pubsub_v1, storage


# Cloud Functions entrypoint: usecase呼び出しのみ
import logging
import os
from src.usecases.import_results_csv import ImportResultsCsvUseCase

def import_loto_results_to_bq(request):
    # lottery_type, gcs_uriを取得
    data = request.get_json(silent=True) or {}
    lottery_type = data.get("lottery_type") or request.args.get("lottery_type")
    gcs_uri = data.get("gcs_uri") or request.args.get("gcs_uri")
    if not lottery_type or not gcs_uri:
        return {"error": "lottery_type and gcs_uri are required"}, 400
    lottery_type = str(lottery_type).lower()

    # 必要な依存を初期化
    from src.config import settings
    from src.infrastructure.gcs.gcs_client import GCSClient
    from src.infrastructure.bigquery.bigquery_client import BigQueryClient
    from src.infrastructure.bigquery.loto_repository import LotoRepository
    logger = logging.getLogger(__name__)
    gcs_client = GCSClient(project_id=os.environ["GCP_PROJECT_ID"])
    bq_client = BigQueryClient(project_id=os.environ["GCP_PROJECT_ID"])
    repository = LotoRepository(
        bq_client,
        dataset=os.environ["BIGQUERY_DATASET"],
        table_loto6=os.environ["BQ_TABLE_LOTO6_HISTORY"],
        table_loto7=os.environ["BQ_TABLE_LOTO7_HISTORY"],
        prediction_runs_table=os.environ["BQ_TABLE_PREDICTION_RUNS"]
    )
    usecase = ImportResultsCsvUseCase(settings, gcs_client, bq_client, repository, logger)

    result = usecase.execute(lottery_type, gcs_uri)
    return result, 200


def _require_fields(message: dict[str, Any], fields: list[str]) -> None:
    missing = [field for field in fields if field not in message or message[field] in (None, "")]
    if missing:
        raise ValueError(f"missing required fields: {missing}")


def _table_name(lottery_type: str) -> str:
    lottery_type = lottery_type.upper()
    if lottery_type == "LOTO6":
        return BQ_TABLE_LOTO6_HISTORY
    if lottery_type == "LOTO7":
        return BQ_TABLE_LOTO7_HISTORY
    raise ValueError(f"unsupported lottery_type: {lottery_type}")


def _read_csv_rows(bucket_name: str, object_name: str) -> list[dict[str, str]]:
    blob = storage_client.bucket(bucket_name).blob(object_name)
    text = blob.download_as_text(encoding="utf-8")
    return list(csv.DictReader(io.StringIO(text)))


def _require_columns(row: dict[str, str], required_columns: list[str]) -> None:
    missing = [col for col in required_columns if col not in row]
    if missing:
        raise ValueError(f"missing required CSV columns: {missing}")


def _normalize_rows(
    lottery_type: str,
    rows: list[dict[str, str]],
    source_file_name: str,
) -> list[dict[str, Any]]:
    lottery_type = lottery_type.upper()
    normalized: list[dict[str, Any]] = []

    for row in rows:
        if lottery_type == "LOTO6":
            required = [
                "draw_no",
                "draw_date",
                "number1",
                "number2",
                "number3",
                "number4",
                "number5",
                "number6",
                "bonus_number",
            ]
            _require_columns(row, required)

            normalized.append(
                {
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
                }
            )
        elif lottery_type == "LOTO7":
            required = [
                "draw_no",
                "draw_date",
                "number1",
                "number2",
                "number3",
                "number4",
                "number5",
                "number6",
                "number7",
                "bonus_number1",
                "bonus_number2",
            ]
            _require_columns(row, required)

            normalized.append(
                {
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
                }
            )
        else:
            raise ValueError(f"unsupported lottery_type: {lottery_type}")

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
                bigquery.ScalarQueryParameter("source_file_name", "STRING", source_file_name),
            ]
        ),
    )
    return list(job.result())[0]["cnt"] > 0


def _existing_draw_nos(table_id: str, draw_nos: list[int]) -> set[int]:
    if not draw_nos:
        return set()

    query = f"""
    SELECT draw_no
    FROM `{table_id}`
    WHERE draw_no IN UNNEST(@draw_nos)
    """
    job = bq_client.query(
        query,
        job_config=bigquery.QueryJobConfig(
            query_parameters=[
                bigquery.ArrayQueryParameter("draw_nos", "INT64", draw_nos),
            ]
        ),
    )
    return {int(row["draw_no"]) for row in job.result()}


def _insert_rows(table_id: str, rows: list[dict[str, Any]]) -> None:
    if not rows:
        return

    errors = bq_client.insert_rows_json(table_id, rows)
    if errors:
        raise RuntimeError(f"BigQuery insert failed: {errors}")


def _publish_notify_message(
    *,
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
    bucket_name = ""
    object_name = ""

    try:
        message = _extract_event_message(request)
        _require_fields(message, ["execution_id", "lottery_type", "gcs_bucket", "gcs_object"])

        execution_id = str(message["execution_id"])
        lottery_type = str(message["lottery_type"]).upper()
        bucket_name = str(message["gcs_bucket"])
        object_name = str(message["gcs_object"])

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
            return (
                json.dumps({"status": "ok", "reason": "duplicate_source_file"}, ensure_ascii=False),
                200,
                {"Content-Type": "application/json; charset=utf-8"},
            )

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
            return (
                json.dumps({"status": "ok", "reason": "duplicate_draw_no"}, ensure_ascii=False),
                200,
                {"Content-Type": "application/json; charset=utf-8"},
            )

        _insert_rows(table_id, rows_to_insert)

        message_id = _publish_notify_message(
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
            message=f"imported_rows={len(rows_to_insert)} message_id={message_id}",
            gcs_bucket=bucket_name,
            gcs_object=object_name,
            draw_no=draw_nos[0] if draw_nos else None,
        )

        return (
            json.dumps(
                {
                    "status": "ok",
                    "inserted_rows": len(rows_to_insert),
                    "target_table": table_id,
                    "published_message_id": message_id,
                },
                ensure_ascii=False,
            ),
            200,
            {"Content-Type": "application/json; charset=utf-8"},
        )

    except Exception as exc:
        log_and_write(
            execution_id=execution_id or "UNKNOWN",
            function_name="import_loto_results_to_bq",
            lottery_type=lottery_type or None,
            stage="import",
            status="FAILED",
            message="import failed",
            gcs_bucket=bucket_name or None,
            gcs_object=object_name or None,
            error_type=type(exc).__name__,
            error_detail=str(exc),
        )
        logger.exception("import_loto_results_to_bq failed")
        return (
            json.dumps({"error": str(exc)}, ensure_ascii=False),
            500,
            {"Content-Type": "application/json; charset=utf-8"},
        )
