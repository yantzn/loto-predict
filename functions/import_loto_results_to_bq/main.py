from __future__ import annotations

import base64
import json
import logging
import os
import sys
from io import StringIO
from pathlib import Path

from google.cloud import bigquery, pubsub_v1

CURRENT_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = CURRENT_DIR.parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.append(str(PROJECT_ROOT))

from src.config.settings import get_settings
from src.infrastructure.gcs.storage_factory import create_storage_client
from src.infrastructure.serializer.loto_csv import parse_csv_to_rows

try:
    from common.execution_log import write_execution_log
except ImportError:
    from functions.common.execution_log import write_execution_log

logging.basicConfig(level=os.getenv("LOG_LEVEL", "INFO"))
logger = logging.getLogger(__name__)


def _decode_pubsub_message(cloud_event) -> dict[str, object]:
    # CloudEvent互換の揺れを吸収し、常に message.data(JSON/base64) を復元する。
    envelope = getattr(cloud_event, "data", cloud_event)
    message = envelope.get("message", envelope)
    data = message.get("data", "")
    if not data:
        raise ValueError("Pub/Sub message data is empty")
    decoded = base64.b64decode(data).decode("utf-8")
    return json.loads(decoded)


def _table_name(lottery_type: str) -> str:
    # repository_factory の既定値は loto6_history / loto7_history。
    # generate_prediction_and_notify もこの history テーブルを参照する前提のため、
    # import 先だけ results 系へずれると処理フローが分断される。
    normalized = str(lottery_type).strip().lower()
    if normalized == "loto6":
        return "loto6_history"
    if normalized == "loto7":
        return "loto7_history"
    raise ValueError(f"unsupported lottery_type: {lottery_type}")


def _existing_draw_nos(client: bigquery.Client, table_id: str, draw_nos: list[int]) -> set[int]:
    # 冪等性確保のため、同一draw_noの再取り込みを事前に除外する。
    if not draw_nos:
        return set()

    sql = f"""
    SELECT draw_no
    FROM `{table_id}`
    WHERE draw_no IN UNNEST(@draw_nos)
    """
    job_config = bigquery.QueryJobConfig(
        query_parameters=[bigquery.ArrayQueryParameter("draw_nos", "INT64", draw_nos)]
    )
    rows = client.query(sql, job_config=job_config).result()
    return {int(row["draw_no"]) for row in rows}


def _publish_notify_message(
    *,
    execution_id: str,
    lottery_type: str,
    draw_no: int | None,
    draw_date: str | None,
) -> str:
    settings = get_settings()
    if settings.is_local:
        # ローカルでは通知トピックに publish せず、取り込みロジックだけを検証する。
        logger.info("Skip notify publish in local mode.")
        return "local-skip"

    publisher = pubsub_v1.PublisherClient()
    topic_path = publisher.topic_path(settings.gcp.project_id, settings.gcp.notify_topic_name)
    payload = {
        "event_type": "IMPORT_COMPLETED",
        "execution_id": execution_id,
        "lottery_type": lottery_type,
        "draw_no": draw_no,
        "draw_date": draw_date,
    }
    future = publisher.publish(topic_path, json.dumps(payload, ensure_ascii=False).encode("utf-8"))
    return future.result()


def entry_point(cloud_event):
    # import関数の責務:
    # 1) fetchで保存されたCSVを取得
    # 2) 行データへ復元
    # 3) 重複を除いてBigQuery投入
    # 4) 予想通知関数へイベント連携
    execution_id = ""
    lottery_type: str | None = None
    gcs_bucket: str | None = None
    gcs_object: str | None = None
    try:
        settings = get_settings()
        message = _decode_pubsub_message(cloud_event)
        execution_id = str(message.get("execution_id") or "")
        lottery_type = str(message["lottery_type"]).strip().lower()
        gcs_bucket = str(message["gcs_bucket"])
        gcs_object = str(message["gcs_object"])

        storage_client = create_storage_client(settings)
        csv_text = storage_client.download_text(gcs_bucket, gcs_object)
        rows = parse_csv_to_rows(StringIO(csv_text))
        if not rows:
            raise ValueError("No rows found in CSV")

        if settings.is_local:
            write_execution_log(
                execution_id=execution_id,
                function_name="import_loto_results_to_bq",
                lottery_type=lottery_type,
                stage="import",
                status="SUCCESS",
                # local preview でも監査線を揃えることで、環境差分での調査手順を同一化する。
                message=f"preview_only processed_count={len(rows)}",
                gcs_bucket=gcs_bucket,
                gcs_object=gcs_object,
            )
            logger.info(
                "Local mode import preview only. execution_id=%s lottery_type=%s rows=%s",
                execution_id,
                lottery_type,
                len(rows),
            )
            return {
                "status": "preview",
                "execution_id": execution_id,
                "lottery_type": lottery_type,
                "rows": len(rows),
            }

        bq_client = bigquery.Client(project=settings.gcp.project_id or None)
        table_id = f"{settings.gcp.project_id}.{settings.gcp.bigquery_dataset}.{_table_name(lottery_type)}"
        draw_nos = [row["draw_no"] for row in rows]
        existing = _existing_draw_nos(bq_client, table_id, draw_nos)
        # 既存回号を差し引いてからinsertし、再実行時の重複登録を防ぐ。
        # parse_csv_to_rows() は n1..n7, b1..b2 のBQスキーマ前提で返すため、
        # ここでは number1 等への再変換を行わず、そのまま履歴テーブルへ投入する。
        # 列名統一方針は BigQuery schema / repository 側と合わせて別修正で管理する。
        insert_rows = [row for row in rows if row["draw_no"] not in existing]
        if insert_rows:
            errors = bq_client.insert_rows_json(table_id, insert_rows)
            if errors:
                raise RuntimeError(f"BigQuery insert failed: {errors}")

        notify_message_id = _publish_notify_message(
            execution_id=execution_id,
            lottery_type=lottery_type,
            draw_no=rows[0]["draw_no"],
            draw_date=str(rows[0]["draw_date"]),
        )

        write_execution_log(
            execution_id=execution_id,
            function_name="import_loto_results_to_bq",
            lottery_type=lottery_type,
            stage="import",
            status="SUCCESS",
            message=f"processed_count={len(rows)} imported_count={len(insert_rows)} skipped_count={len(existing)}",
            gcs_bucket=gcs_bucket,
            gcs_object=gcs_object,
            draw_no=rows[0]["draw_no"],
        )

        logger.info(
            "import_loto_results_to_bq completed. execution_id=%s lottery_type=%s table_id=%s inserted=%s skipped=%s notify_message_id=%s",
            execution_id,
            lottery_type,
            table_id,
            len(insert_rows),
            len(existing),
            notify_message_id,
        )
        return {
            "status": "ok",
            "execution_id": execution_id,
            "lottery_type": lottery_type,
            "inserted_rows": len(insert_rows),
            "skipped_rows": len(existing),
        }
    except Exception as exc:
        write_execution_log(
            execution_id=execution_id or "unknown",
            function_name="import_loto_results_to_bq",
            lottery_type=lottery_type,
            stage="import",
            status="FAILED",
            message="import_loto_results_to_bq failed",
            gcs_bucket=gcs_bucket,
            gcs_object=gcs_object,
            error_type=type(exc).__name__,
            error_detail=str(exc),
        )
        logger.exception(
            "import_loto_results_to_bq failed. execution_id=%s lottery_type=%s error_message=%s",
            execution_id,
            lottery_type,
            str(exc),
        )
        raise
