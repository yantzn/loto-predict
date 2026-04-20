from __future__ import annotations

from src.config.settings import get_settings
from src.infrastructure.repositories.bigquery_loto_repository import BigQueryLotoRepository
from src.infrastructure.repositories.local_loto_repository import LocalLotoRepository


def create_loto_repository(bq_client=None):
    settings = get_settings()

    # 本リポジトリは、予想生成(generate)の参照元として history テーブルを前提にする。
    # import 処理も同じ history テーブルへ投入することで、取り込みデータを即座に参照できる。
    # 既定値は Terraform / settings / README と揃え、loto6_history / loto7_history を使う。
    # もし別名テーブルへ投入したい場合は、import_loto_results_to_bq 側の投入先も
    # 同時に変更しないと、取り込み先と参照先が分離して不整合になる。
    # その場合は Terraform 定義と README 記載も同時に更新して運用前提を一致させること。
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
