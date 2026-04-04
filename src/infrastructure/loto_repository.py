from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone

from google.cloud import bigquery

from loto_predict.domain.models import LotoResult


class LotoRepository:
    def __init__(self, bq_client, dataset: str, table_loto6: str, table_loto7: str, prediction_runs_table: str):
        self.bq_client = bq_client
        self.dataset = dataset
        self.table_loto6 = table_loto6
        self.table_loto7 = table_loto7
        self.prediction_runs_table = prediction_runs_table

    def history_table(self, lottery_type: str) -> str:
        table = self.table_loto6 if lottery_type == "loto6" else self.table_loto7
        return f"{self.bq_client.client.project}.{self.dataset}.{table}"

    def get_recent_results(self, lottery_type: str, limit: int) -> list[LotoResult]:
        table = self.history_table(lottery_type)
        if lottery_type == "loto6":
            sql = f"""
            SELECT draw_date, draw_number, number1, number2, number3, number4, number5, number6, bonus1
            FROM `{table}`
            ORDER BY draw_date DESC, draw_number DESC
            LIMIT {limit}
            """
        else:
            sql = f"""
            SELECT draw_date, draw_number, number1, number2, number3, number4, number5, number6, number7, bonus1, bonus2
            FROM `{table}`
            ORDER BY draw_date DESC, draw_number DESC
            LIMIT {limit}
            """

        rows = self.bq_client.query(sql)
        results: list[LotoResult] = []
        for row in rows:
            if lottery_type == "loto6":
                numbers = [row["number1"], row["number2"], row["number3"], row["number4"], row["number5"], row["number6"]]
                bonuses = [row["bonus1"]] if row["bonus1"] is not None else []
            else:
                numbers = [row["number1"], row["number2"], row["number3"], row["number4"], row["number5"], row["number6"], row["number7"]]
                bonuses = [x for x in [row["bonus1"], row["bonus2"]] if x is not None]

            results.append(
                LotoResult(
                    lottery_type=lottery_type,
                    draw_date=row["draw_date"],
                    draw_number=row["draw_number"],
                    numbers=numbers,
                    bonus_numbers=bonuses,
                    source="bigquery",
                )
            )
        return results

    def merge_staging_to_history(self, lottery_type: str, dataset: str, staging_table: str, history_table: str) -> None:
        project = self.bq_client.client.project
        staging = f"`{project}.{dataset}.{staging_table}`"
        target = f"`{project}.{dataset}.{history_table}`"

        if lottery_type == "loto6":
            sql = f"""
            MERGE {target} T
            USING (
              SELECT
                draw_date,
                draw_number,
                number1, number2, number3, number4, number5, number6,
                bonus1,
                source,
                CURRENT_TIMESTAMP() AS loaded_at
              FROM {staging}
            ) S
            ON T.draw_number = S.draw_number
            WHEN MATCHED THEN
              UPDATE SET
                draw_date = S.draw_date,
                number1 = S.number1,
                number2 = S.number2,
                number3 = S.number3,
                number4 = S.number4,
                number5 = S.number5,
                number6 = S.number6,
                bonus1  = S.bonus1,
                source  = S.source,
                loaded_at = S.loaded_at
            WHEN NOT MATCHED THEN
              INSERT (
                draw_date, draw_number,
                number1, number2, number3, number4, number5, number6,
                bonus1, source, loaded_at
              )
              VALUES (
                S.draw_date, S.draw_number,
                S.number1, S.number2, S.number3, S.number4, S.number5, S.number6,
                S.bonus1, S.source, S.loaded_at
              )
            """
        else:
            sql = f"""
            MERGE {target} T
            USING (
              SELECT
                draw_date,
                draw_number,
                number1, number2, number3, number4, number5, number6, number7,
                bonus1, bonus2,
                source,
                CURRENT_TIMESTAMP() AS loaded_at
              FROM {staging}
            ) S
            ON T.draw_number = S.draw_number
            WHEN MATCHED THEN
              UPDATE SET
                draw_date = S.draw_date,
                number1 = S.number1,
                number2 = S.number2,
                number3 = S.number3,
                number4 = S.number4,
                number5 = S.number5,
                number6 = S.number6,
                number7 = S.number7,
                bonus1  = S.bonus1,
                bonus2  = S.bonus2,
                source  = S.source,
                loaded_at = S.loaded_at
            WHEN NOT MATCHED THEN
              INSERT (
                draw_date, draw_number,
                number1, number2, number3, number4, number5, number6, number7,
                bonus1, bonus2, source, loaded_at
              )
              VALUES (
                S.draw_date, S.draw_number,
                S.number1, S.number2, S.number3, S.number4, S.number5, S.number6, S.number7,
                S.bonus1, S.bonus2, S.source, S.loaded_at
              )
            """
        self.bq_client.execute(sql)

    def save_prediction_run(self, lottery_type: str, history_limit: int, predictions: list[list[int]]) -> str:
        run_id = str(uuid.uuid4())
        project = self.bq_client.client.project
        table_id = f"{project}.{self.dataset}.{self.prediction_runs_table}"
        self.bq_client.insert_json_rows(table_id, [{
            "run_id": run_id,
            "lottery_type": lottery_type,
            "history_limit": history_limit,
            "prediction_json": json.dumps(predictions, ensure_ascii=False),
            "created_at": datetime.now(timezone.utc).isoformat(),
        }])
        return run_id
