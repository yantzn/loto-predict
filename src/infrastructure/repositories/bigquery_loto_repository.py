from __future__ import annotations

import logging
from datetime import date, datetime, timedelta
from typing import Any

from google.cloud import bigquery

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

        normalized_rows = [self._normalize_draw_date(row) for row in rows]

        # DEBUG: Log draw_date values and types for first 3 rows
        for i, row in enumerate(normalized_rows[:3]):
            draw_date = row.get("draw_date")
            logger.info(
                "DEBUG import_rows: row[%d] draw_date=%r (type=%s)",
                i,
                draw_date,
                type(draw_date).__name__,
            )

        job_config = bigquery.LoadJobConfig(
            write_disposition=bigquery.WriteDisposition.WRITE_APPEND,
        )
        load_job = self.bq_client.load_table_from_json(normalized_rows, table_id, job_config=job_config)
        load_job.result()
        return {
            "inserted_rows": len(normalized_rows),
            "draw_no": normalized_rows[0].get("draw_no") if normalized_rows else None,
            "skipped_as_duplicate": False,
            "table_id": table_id,
        }

    def _normalize_draw_date(self, row: dict[str, Any]) -> dict[str, Any]:
        normalized = dict(row)
        raw = normalized.get("draw_date")

        if raw is None:
            return normalized

        if isinstance(raw, str):
            text = raw.strip()
            if not text:
                normalized["draw_date"] = None
                return normalized

            if len(text) == 10 and text[4] == "-" and text[7] == "-":
                normalized["draw_date"] = text
                return normalized

            if len(text) == 8 and text.isdigit():
                normalized["draw_date"] = datetime.strptime(text, "%Y%m%d").date().isoformat()
                return normalized

            if text.isdigit():
                normalized["draw_date"] = (date(1970, 1, 1) + timedelta(days=int(text))).isoformat()
                return normalized

            return normalized

        if isinstance(raw, int):
            normalized["draw_date"] = (date(1970, 1, 1) + timedelta(days=raw)).isoformat()
            return normalized

        if isinstance(raw, datetime):
            normalized["draw_date"] = raw.date().isoformat()
            return normalized

        if isinstance(raw, date):
            normalized["draw_date"] = raw.isoformat()
            return normalized

        return normalized

    def fetch_existing_draw_nos(self, lottery_type: str, draw_nos: list[int]) -> set[int]:
        # backfill や再実行時の安全性を上げるため、履歴全件取得ではなく
        # 対象 draw_no の存在確認だけを BigQuery に投げて重複混入を防ぐ。
        normalized_draw_nos = [int(draw_no) for draw_no in draw_nos if draw_no is not None]
        if not normalized_draw_nos:
            return set()

        table_id = self._table_id(lottery_type)
        query = f"""
SELECT draw_no
FROM `{table_id}`
WHERE draw_no IN UNNEST(@draw_nos)
"""
        job_config = bigquery.QueryJobConfig(
            query_parameters=[bigquery.ArrayQueryParameter("draw_nos", "INT64", normalized_draw_nos)]
        )
        rows = self.bq_client.query(query, job_config=job_config).result()
        return {int(row["draw_no"]) for row in rows}

    def fetch_recent_history_rows(self, lottery_type: str, limit: int) -> list[dict[str, Any]]:
        # 返却順は draw_no DESC(最新順) を契約とする。
        # local実装は dict を返すため、BigQuery Row との差をここで吸収して
        # UseCase 側は常に row.get(...) で同じように扱えるようにする。
        table_id = self._table_id(lottery_type)
        query = f"""
SELECT *
FROM `{table_id}`
ORDER BY draw_no DESC
LIMIT {int(limit)}
"""
        return [dict(row.items()) for row in self.bq_client.query(query).result()]

    def fetch_recent_draws(self, lottery_type: str, limit: int) -> list[list[int]]:
        # 履歴テーブルの n1..n7 カラムから、統計計算用の draw 配列へ変換する。
        rows = self.fetch_recent_history_rows(lottery_type, limit)
        draws: list[list[int]] = []
        for row in rows:
            pick_count = 6 if str(lottery_type).strip().lower() == "loto6" else 7
            draws.append([int(row[f"n{index}"]) for index in range(1, pick_count + 1)])
        return draws

    def save_prediction_run(self, payload: dict[str, Any]) -> None:
        # repository 層は UseCase payload と BigQuery schema の橋渡しを担う。
        # prediction_runs は「1口=1行」スキーマなので、生 payload をそのまま保存せず、
        # predictions(list[list[int]]) をスキーマ準拠の複数行へ正規化して保存する。
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

        errors = self.bq_client.insert_rows_json(table_id, rows_to_insert)
        if errors:
            raise RuntimeError(f"BigQuery insert failed: table_id={table_id} errors={errors}")
