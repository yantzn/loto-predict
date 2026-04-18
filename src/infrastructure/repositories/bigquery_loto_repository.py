from __future__ import annotations

import logging
from typing import Any

logger = logging.getLogger(__name__)


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
        # import 関数側と同じ BigQuery API を使い、実装差分を減らす。
        self.bq_client.insert_rows_json(table_id, rows)
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
        # UseCase 側は list[dict-like] を前提に扱うため、iterator ではなく result() を明示する。
        return list(self.bq_client.query(query).result())

    def fetch_recent_draws(self, lottery_type: str, limit: int) -> list[list[int]]:
        # 履歴テーブルの n1..n7 カラムから、統計計算用の draw 配列へ変換する。
        rows = self.fetch_recent_history_rows(lottery_type, limit)
        draws: list[list[int]] = []
        for row in rows:
            pick_count = 6 if str(lottery_type).strip().lower() == "loto6" else 7
            draws.append([int(row[f"n{index}"]) for index in range(1, pick_count + 1)])
        return draws

    def save_prediction_run(self, payload: dict[str, Any]) -> None:
        # prediction_runs は「1口=1行」のスキーマなので、
        # UseCase の predictions(list[list[int]]) をここで正規化して保存する。
        table_id = f"{self.project_id}.{self.dataset}.{self.prediction_runs_table}"
        predictions = payload.get("predictions") or []
        if not predictions:
            # 現行スキーマは n1..n6 必須のため、FAILED をダミー行で保存できない。
            # 失敗情報は execution_logs 側へ寄せる前提で、ここでは warning のみ残す。
            logger.warning(
                "Skip save_prediction_run because predictions is empty. execution_id=%s status=%s",
                payload.get("execution_id"),
                payload.get("status"),
            )
            return

        lottery_type = str(payload.get("lottery_type") or "").strip().lower()
        if lottery_type not in {"loto6", "loto7"}:
            raise ValueError(f"unsupported lottery_type in payload: {payload.get('lottery_type')}")

        rows_to_insert: list[dict[str, Any]] = []
        message_sent = str(payload.get("status") or "").upper() == "SUCCESS"
        latest_draw_no = payload.get("latest_draw_no")
        draw_date = payload.get("draw_date")
        created_at = payload.get("created_at")

        for index, prediction in enumerate(predictions, start=1):
            if len(prediction) < 6:
                raise ValueError(f"prediction must contain at least 6 numbers: {prediction}")

            n7_value = int(prediction[6]) if lottery_type == "loto7" and len(prediction) >= 7 else None
            rows_to_insert.append(
                {
                    "execution_id": payload.get("execution_id"),
                    "lottery_type": lottery_type,
                    "draw_no": latest_draw_no,
                    "draw_date": draw_date,
                    "prediction_index": index,
                    "n1": int(prediction[0]),
                    "n2": int(prediction[1]),
                    "n3": int(prediction[2]),
                    "n4": int(prediction[3]),
                    "n5": int(prediction[4]),
                    "n6": int(prediction[5]),
                    "n7": n7_value,
                    "message_sent": message_sent,
                    "created_at": created_at,
                }
            )

        self.bq_client.insert_rows_json(table_id, rows_to_insert)
