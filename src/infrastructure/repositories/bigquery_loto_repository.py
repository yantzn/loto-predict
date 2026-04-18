from __future__ import annotations

from typing import Any


class BigQueryLotoRepository:
    """
    BigQueryを用いたロト履歴・予想記録のリポジトリ実装。
    - 履歴データや予想実行記録の保存・取得を担当
    - インフラ層の責務としてBigQuery操作のみを行う
    """

    def __init__(
        self,
        bq_client,
        project_id: str,
        dataset: str,
        table_loto6: str,
        table_loto7: str,
        prediction_runs_table: str,
    ):
        """
        Args:
            bq_client: BigQueryクライアントインスタンス
            project_id (str): GCPプロジェクトID
            dataset (str): BigQueryデータセット名
            table_loto6 (str): ロト6テーブル名
            table_loto7 (str): ロト7テーブル名
            prediction_runs_table (str): 予想記録テーブル名
        """
        self.bq_client = bq_client
        self.project_id = project_id
        self.dataset = dataset
        self.table_loto6 = table_loto6
        self.table_loto7 = table_loto7
        self.prediction_runs_table = prediction_runs_table

    def _table_name(self, lottery_type: str) -> str:
        """
        ロト種別からテーブル名を返す。
        Args:
            lottery_type (str): 'loto6' or 'loto7'
        Returns:
            str: テーブル名
        """
        lottery_type = lottery_type.lower()
        if lottery_type == "loto6":
            return self.table_loto6
        if lottery_type == "loto7":
            return self.table_loto7
        raise ValueError(f"unsupported lottery_type: {lottery_type}")

    def _table_id(self, lottery_type: str) -> str:
        """
        完全修飾テーブルIDを返す。
        Args:
            lottery_type (str): 'loto6' or 'loto7'
        Returns:
            str: プロジェクト.データセット.テーブル名
        """
        return f"{self.project_id}.{self.dataset}.{self._table_name(lottery_type)}"

    def import_rows(self, lottery_type: str, rows: list[dict[str, Any]]) -> dict[str, Any]:
        """
        履歴データをBigQueryにインサートする。
        Args:
            lottery_type (str): 'loto6' or 'loto7'
            rows (list[dict]): 追加する行データ
        Returns:
            dict: 結果情報（挿入件数など）
        Raises:
            RuntimeError: 挿入失敗時
        """
        table_id = self._table_id(lottery_type)
        try:
            self.bq_client.insert_json_rows(table_id, rows)
        except Exception as e:
            print(f"BigQuery insert failed: {e}")
            raise
        return {
            "inserted_rows": len(rows),
            "draw_no": rows[0].get("draw_no") if rows else None,
            "skipped_as_duplicate": False,
            "table_id": table_id,
        }

    def fetch_recent_draws(self, lottery_type: str, limit: int) -> list[list[int]]:
        """
        直近の抽選結果（本数字リスト）を取得。
        Args:
            lottery_type (str): 'loto6' or 'loto7'
            limit (int): 取得件数
        Returns:
            list[list[int]]: 各回の本数字リスト
        """
        table_id = self._table_id(lottery_type)
        if lottery_type.lower() == "loto6":
            query = f"""
SELECT number1, number2, number3, number4, number5, number6
FROM `{table_id}`
ORDER BY draw_no DESC
LIMIT {int(limit)}
"""
        else:
            query = f"""
SELECT number1, number2, number3, number4, number5, number6, number7
FROM `{table_id}`
ORDER BY draw_no DESC
LIMIT {int(limit)}
"""
        rows = self.bq_client.query(query)
        draws: list[list[int]] = []
        for row in rows:
            # 各行の値をintに変換しリスト化
            values = [int(v) for v in row.values()]
            draws.append(values)
        return draws

    def save_prediction_run(self, payload: dict[str, Any]) -> None:
        """
        予想実行記録をBigQueryに保存。
        Args:
            payload (dict): 保存する予想実行データ
        Raises:
            RuntimeError: 挿入失敗時
        """
        table_id = f"{self.project_id}.{self.dataset}.{self.prediction_runs_table}"
        try:
            self.bq_client.insert_json_rows(table_id, [payload])
        except Exception as e:
            print(f"BigQuery insert prediction run failed: {e}")
            raise
