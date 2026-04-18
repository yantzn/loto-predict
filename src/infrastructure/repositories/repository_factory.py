from __future__ import annotations

import os

from src.config.settings import get_settings
from src.infrastructure.repositories.bigquery_loto_repository import BigQueryLotoRepository
from src.infrastructure.repositories.local_loto_repository import LocalLotoRepository


def _get_table_name(name: str, default: str) -> str:
    value = os.getenv(name, default).strip()
    if not value:
        raise ValueError(f"Table name is empty: {name}")
    return value


def create_loto_repository(bq_client=None):
    """
    実行環境に応じて repository を返す。
    local では LocalLotoRepository、それ以外では BigQueryLotoRepository を使う。
    """
    settings = get_settings()

    table_loto6 = _get_table_name("BQ_TABLE_LOTO6_HISTORY", "loto6_history")
    table_loto7 = _get_table_name("BQ_TABLE_LOTO7_HISTORY", "loto7_history")
    prediction_runs_table = _get_table_name("BQ_TABLE_PREDICTION_RUNS", "prediction_runs")

    if settings.is_local:
        return LocalLotoRepository(
            base_path=settings.local.storage_path,
            table_loto6=table_loto6,
            table_loto7=table_loto7,
            prediction_runs_table=prediction_runs_table,
        )

    if bq_client is None:
        raise ValueError("bq_client is required when env is not local")

    return BigQueryLotoRepository(
        bq_client=bq_client,
        project_id=settings.gcp.project_id,
        dataset=settings.gcp.bigquery_dataset,
        table_loto6=table_loto6,
        table_loto7=table_loto7,
        prediction_runs_table=prediction_runs_table,
    )
