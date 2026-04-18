
# Cloud Functions/Jobsの実行ログをBigQueryに記録するユーティリティ
# - 監査・障害解析・運用可視化用途
# - 必ずtry/exceptでラップし、失敗時もアプリ本体に影響しない設計

from __future__ import annotations
import logging
import os
from typing import Any
from google.cloud import bigquery
from common.time_utils import now_local, now_local_iso

logger = logging.getLogger(__name__)

# GCPプロジェクト・データセット・テーブル名を環境変数から取得
PROJECT_ID = os.environ["GCP_PROJECT_ID"]
DATASET_ID = os.environ["BQ_DATASET"]
TABLE_EXECUTION_LOGS = os.getenv("BQ_TABLE_EXECUTION_LOGS", "execution_logs")

# BigQueryクライアント（グローバルで使い回し）
bq_client = bigquery.Client(project=PROJECT_ID)



# 実行ログテーブルのフルIDを返す
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
    """
    1件の実行ログをBigQueryに書き込む
    - 失敗しても例外を外に出さず、loggerで記録のみ
    - 必須: execution_id, function_name, status
    - その他は状況に応じて付与
    """
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
        # ログ記録失敗時もアプリ本体には影響させない
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
    """
    ログ出力とBigQuery記録を同時に行うユーティリティ
    - まず構造化ログとしてlogger.info出力
    - その後write_execution_logでBQにも記録
    """
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
