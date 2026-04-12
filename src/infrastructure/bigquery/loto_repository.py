from __future__ import annotations


class LotoRepository:
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

    def import_rows(self, lottery_type: str, rows: list[dict]) -> dict:
        table_id = self._table_id(lottery_type)
        errors = self.bq_client.insert_rows_json(table_id, rows)
        if errors:
            raise RuntimeError(f"BigQuery insert failed: {errors}")

        draw_no = rows[0].get("draw_no") if rows else None
        return {
            "table_id": table_id,
            "inserted_rows": len(rows),
            "draw_no": draw_no,
            "skipped_as_duplicate": False,
        }
