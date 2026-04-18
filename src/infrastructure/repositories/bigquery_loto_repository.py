from __future__ import annotations

from typing import Any


class BigQueryLotoRepository:
    def __init__(
        self,
        bq_client,
        project_id: str,
        dataset: str,
        table_loto6: str,
        table_loto7: str,
        prediction_runs_table: str,
    ) -> None:
        self.bq_client = bq_client
        self.project_id = project_id
        self.dataset = dataset
        self.table_loto6 = table_loto6
        self.table_loto7 = table_loto7
        self.prediction_runs_table = prediction_runs_table

    def _table_name(self, lottery_type: str) -> str:
        normalized = str(lottery_type).strip().lower()
        if normalized == "loto6":
            return self.table_loto6
        if normalized == "loto7":
            return self.table_loto7
        raise ValueError(f"unsupported lottery_type: {lottery_type}")

    def _table_id(self, lottery_type: str) -> str:
        return f"{self.project_id}.{self.dataset}.{self._table_name(lottery_type)}"

    def import_rows(self, lottery_type: str, rows: list[dict[str, Any]]) -> dict[str, Any]:
        table_id = self._table_id(lottery_type)
        self.bq_client.insert_json_rows(table_id, rows)
        return {
            "inserted_rows": len(rows),
            "draw_no": rows[0].get("draw_no") if rows else None,
            "skipped_as_duplicate": False,
            "table_id": table_id,
        }

    def fetch_recent_history_rows(self, lottery_type: str, limit: int) -> list[dict[str, Any]]:
        # 返却順は draw_no DESC(最新順) を契約とする。
        # local実装も同契約に揃え、UseCaseの解釈を環境非依存にする。
        table_id = self._table_id(lottery_type)
        query = f"""
SELECT *
FROM `{table_id}`
ORDER BY draw_no DESC
LIMIT {int(limit)}
"""
        return self.bq_client.query(query)

    def fetch_recent_draws(self, lottery_type: str, limit: int) -> list[list[int]]:
        rows = self.fetch_recent_history_rows(lottery_type, limit)
        draws: list[list[int]] = []
        for row in rows:
            pick_count = 6 if str(lottery_type).strip().lower() == "loto6" else 7
            draws.append([int(row[f"n{index}"]) for index in range(1, pick_count + 1)])
        return draws

    def save_prediction_run(self, payload: dict[str, Any]) -> None:
        table_id = f"{self.project_id}.{self.dataset}.{self.prediction_runs_table}"
        self.bq_client.insert_json_rows(table_id, [payload])
