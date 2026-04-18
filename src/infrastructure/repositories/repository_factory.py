from __future__ import annotations

from src.config.settings import get_settings
from src.infrastructure.repositories.bigquery_loto_repository import BigQueryLotoRepository
from src.infrastructure.repositories.local_loto_repository import LocalLotoRepository

def create_loto_repository(bq_client=None):
    settings = get_settings()

    table_loto6 = settings.gcp.table_loto6_history
    table_loto7 = settings.gcp.table_loto7_history
    prediction_runs_table = settings.gcp.table_prediction_runs

    if settings.is_local:
        return LocalLotoRepository(
            base_path=settings.local_storage_path,
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
