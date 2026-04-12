from __future__ import annotations

import os

from src.config.settings import get_settings
from src.infrastructure.repositories.local_loto_repository import LocalLotoRepository
from src.infrastructure.repositories.bigquery_loto_repository import BigQueryLotoRepository


def create_loto_repository(bq_client=None):
    table_loto6 = os.environ["BQ_TABLE_LOTO6_HISTORY"]
    table_loto7 = os.environ["BQ_TABLE_LOTO7_HISTORY"]
    prediction_runs_table = os.environ["BQ_TABLE_PREDICTION_RUNS"]

    settings = get_settings()
    if settings.env == "local":
        return LocalLotoRepository(
            base_path="./local_storage",
            table_loto6=table_loto6,
            table_loto7=table_loto7,
            prediction_runs_table=prediction_runs_table,
        )

    if bq_client is None:
        raise ValueError("bq_client is required when app_env is not local")

    return BigQueryLotoRepository(
        bq_client=bq_client,
        project_id=settings.gcp.project_id,
        dataset=settings.gcp.bigquery_dataset,
        table_loto6=table_loto6,
        table_loto7=table_loto7,
        prediction_runs_table=prediction_runs_table,
    )
