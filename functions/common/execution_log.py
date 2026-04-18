
# Cloud Functions/Jobsの実行ログをBigQueryに記録するユーティリティ
# - 監査・障害解析・運用可視化用途
# - 必ずtry/exceptでラップし、失敗時もアプリ本体に影響しない設計

from __future__ import annotations
import logging
import os
from typing import Any
from google.cloud import bigquery

try:
    from common.time_utils import now_local_iso
except ImportError:
    from functions.common.time_utils import now_local_iso

logger = logging.getLogger(__name__)

# GCPプロジェクト・データセット・テーブル名を環境変数から取得
# なぜ必要か:
# - README / Terraform / settings と同じ環境変数名を使い、運用時の設定ミスを防ぐため。
# - execution_logs は prediction_runs と用途が異なり、SUCCESS/FAILED を含む処理監査の
#   監査線として常時書き込めることが重要なため。
PROJECT_ID = os.getenv("GCP_PROJECT_ID", "")
DATASET_ID = os.getenv("BQ_DATASET") or os.getenv("BIGQUERY_DATASET", "")
TABLE_EXECUTION_LOGS = os.getenv("BQ_TABLE_EXECUTION_LOGS", "execution_logs")

_bq_client: bigquery.Client | None = None


def _get_bq_client() -> bigquery.Client | None:
    global _bq_client
    if _bq_client is not None:
        return _bq_client
    try:
        _bq_client = bigquery.Client(project=PROJECT_ID or None)
        return _bq_client
    except Exception:
        # ログ監査が失敗しても本処理を止めないため、ここでは握りつぶして継続する。
        logger.exception("failed to initialize BigQuery client for execution_logs")
        return None



# 実行ログテーブルのフルIDを返す
def execution_logs_table_id() -> str:
    if not PROJECT_ID or not DATASET_ID:
        raise ValueError("GCP_PROJECT_ID and BQ_DATASET (or BIGQUERY_DATASET) are required")
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
    effective_stage = stage or function_name
    row: dict[str, Any] = {
        "execution_id": execution_id,
        "lottery_type": lottery_type,
        "stage": effective_stage,
        "status": status,
        "message": message,
        "error_detail": error_detail,
        "created_at": now_local_iso(),
    }

    try:
        client = _get_bq_client()
        if client is None:
            return
        errors = client.insert_rows_json(execution_logs_table_id(), [row])
        if errors:
            logger.error("failed to insert execution log: %s", errors)
    except Exception as exc:
        # ログ記録失敗時もアプリ本体には影響させない
        logger.error(
            "unexpected error while writing execution log. execution_id=%s function_name=%s stage=%s status=%s error=%s",
            execution_id,
            function_name,
            effective_stage,
            status,
            str(exc),
        )


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
        "stage": stage or function_name,
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
