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
    ):
        self.bq_client = bq_client
        self.project_id = project_id
        self.dataset = dataset
        self.table_loto6 = table_loto6
        self.table_loto7 = table_loto7
        self.prediction_runs_table = prediction_runs_table

    def _table_name(self, lottery_type: str) -> str:
        lottery_type = lottery_type.lower()
        if lottery_type == "loto6":
            return self.table_loto6
        if lottery_type == "loto7":
            return self.table_loto7
        raise ValueError(f"unsupported lottery_type: {lottery_type}")

    def _table_id(self, lottery_type: str) -> str:
        return f"{self.project_id}.{self.dataset}.{self._table_name(lottery_type)}"

    def import_rows(self, lottery_type: str, rows: list[dict[str, Any]]) -> dict[str, Any]:
        table_id = self._table_id(lottery_type)
        errors = self.bq_client.insert_rows_json(table_id, rows)
        if errors:
            raise RuntimeError(f"BigQuery insert failed: {errors}")

        return {
            "inserted_rows": len(rows),
            "draw_no": rows[0].get("draw_no") if rows else None,
            "skipped_as_duplicate": False,
            "table_id": table_id,
        }

    def fetch_recent_draws(self, lottery_type: str, limit: int) -> list[list[int]]:
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
            values = [int(v) for v in row.values()]
            draws.append(values)
        return draws

    def save_prediction_run(self, payload: dict[str, Any]) -> None:
        table_id = f"{self.project_id}.{self.dataset}.{self.prediction_runs_table}"
        errors = self.bq_client.insert_rows_json(table_id, [payload])
        if errors:
            raise RuntimeError(f"BigQuery insert prediction run failed: {errors}")
