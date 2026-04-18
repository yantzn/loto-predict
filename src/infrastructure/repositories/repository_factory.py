from __future__ import annotations

from src.config.settings import get_settings
from src.infrastructure.repositories.bigquery_loto_repository import BigQueryLotoRepository
from src.infrastructure.repositories.local_loto_repository import LocalLotoRepository


def create_loto_repository(bq_client=None):
    settings = get_settings()

    # import 関数と generate 関数は、同じ history テーブルを参照する前提。
    # 既定値は Terraform / settings と揃え、loto6_history / loto7_history を使う。
    # もし別名テーブルへ投入したい場合は、import_loto_results_to_bq 側の投入先も
    # 同時に変更しないと、取り込み先と参照先が分離して不整合になる。
    table_loto6 = settings.gcp.table_loto6_history
    table_loto7 = settings.gcp.table_loto7_history
    prediction_runs_table = settings.gcp.table_prediction_runs

    # local はファイルベース、gcp は BigQuery ベースに切り替える。
    # repository 生成以外の責務はここへ持ち込まない。
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
