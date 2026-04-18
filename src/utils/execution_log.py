bq_client = bigquery.Client(project=PROJECT_ID)
def execution_logs_table_id() -> str:
def write_execution_log(
from __future__ import annotations

import logging
import os
from typing import Any

# Google BigQueryクライアント
from google.cloud import bigquery

# 日時ユーティリティ
from .time_utils import now_local, now_local_iso

# ログ出力用ロガー
logger = logging.getLogger(__name__)

# 環境変数からBigQueryの各種設定を取得
PROJECT_ID = os.environ["GCP_PROJECT_ID"]  # GCPプロジェクトID
DATASET_ID = os.environ["BQ_DATASET"]  # BigQueryデータセット名
TABLE_EXECUTION_LOGS = os.getenv("BQ_TABLE_EXECUTION_LOGS", "execution_logs")  # 実行ログテーブル名

# BigQueryクライアント初期化
bq_client = bigquery.Client(project=PROJECT_ID)

def execution_logs_table_id() -> str:
    """
    実行ログ用の完全修飾テーブルIDを返す。
    Returns:
        str: プロジェクト.データセット.テーブル名
    """
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
    BigQueryのexecution_logsテーブルに実行ログを1件書き込む。
    Args:
        execution_id (str): 実行単位のID（トレース用）
        function_name (str): 関数・処理名
        lottery_type (str|None): ロト種別
        stage (str|None): 処理ステージ
        status (str): ステータス（success, error等）
        message (str|None): 任意のメッセージ
        gcs_bucket (str|None): GCSバケット名
        gcs_object (str|None): GCSオブジェクト名
        draw_no (int|None): 抽選回
        run_id (str|None): 予想実行ID
        error_type (str|None): エラー種別
        error_detail (str|None): エラー詳細
    Raises:
        なし（失敗時はエラーログ出力のみ）
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
        # BigQueryへ1行インサート
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
