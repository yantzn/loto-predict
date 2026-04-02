from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from google.cloud import bigquery

from infrastructure.bigquery_client import BigQueryClient
from utils.exceptions import ValidationError
from utils.validators import (
    validate_no_overlap,
    validate_number_count,
    validate_number_range,
    validate_unique_numbers,
)

from domain.models import (
    DrawHistory,
    DrawResult,
    LotteryType,
    PredictionRunRecord,
)


class BigQueryLotoRepository:
    DRAW_RESULT_TABLE_MAP = {
        LotteryType.LOTO6: "loto6_draw_results",
        LotteryType.LOTO7: "loto7_draw_results",
    }

    PREDICTION_RUN_TABLE = "prediction_runs"

    def __init__(self, bq_client: BigQueryClient | None = None) -> None:
        self.bq = bq_client or BigQueryClient()

    # =========================
    # Draw results
    # =========================

    def save_draw_result(self, draw_result: DrawResult) -> None:
        self._validate_draw_result(draw_result)
        row = self._to_draw_result_row(draw_result)
        self.bq.insert_rows_json(self._table_name(draw_result.lottery_type), [row])

    def save_draw_results(self, draw_results: list[DrawResult]) -> None:
        if not draw_results:
            return

        grouped: dict[LotteryType, list[dict[str, Any]]] = {
            LotteryType.LOTO6: [],
            LotteryType.LOTO7: [],
        }

        for item in draw_results:
            self._validate_draw_result(item)
            grouped[item.lottery_type].append(self._to_draw_result_row(item))

        for lottery_type, rows in grouped.items():
            if rows:
                self.bq.insert_rows_json(self._table_name(lottery_type), rows)

    def find_draw_result_by_draw_no(
        self,
        lottery_type: LotteryType,
        draw_no: int,
    ) -> DrawResult | None:
        sql = f"""
        SELECT
          lottery_type,
          draw_no,
          draw_date,
          main_numbers,
          bonus_numbers,
          source_type,
          source_reference,
          fetched_at,
          created_at,
          updated_at
        FROM `{self.bq.table_ref(self._table_name(lottery_type))}`
        WHERE draw_no = @draw_no
        LIMIT 1
        """
        result = self.bq.query(
            sql,
            parameters=[bigquery.ScalarQueryParameter("draw_no", "INT64", draw_no)],
        )
        if not result.rows:
            return None
        return self._from_draw_result_row(result.rows[0])

    def find_recent_draw_histories(
        self,
        lottery_type: LotteryType,
        limit: int,
    ) -> list[DrawHistory]:
        sql = f"""
        SELECT
          draw_no,
          main_numbers,
          bonus_numbers
        FROM `{self.bq.table_ref(self._table_name(lottery_type))}`
        ORDER BY draw_date DESC, draw_no DESC
        LIMIT @limit
        """
        result = self.bq.query(
            sql,
            parameters=[bigquery.ScalarQueryParameter("limit", "INT64", limit)],
        )
        return [
            DrawHistory(
                draw_no=int(row["draw_no"]),
                main_numbers=list(row["main_numbers"]),
                bonus_numbers=list(row.get("bonus_numbers", []) or []),
            )
            for row in result.rows
        ]

    # =========================
    # Prediction runs
    # =========================

    def save_prediction_run(self, record: PredictionRunRecord) -> None:
        row = {
            "lottery_type": record.lottery_type.value,
            "draw_no": record.draw_no,
            "stats_target_draws": record.stats_target_draws,
            "score_snapshot": [
                {"number": int(number), "score": float(score)}
                for number, score in record.score_snapshot.items()
            ],
            "generated_predictions": record.generated_predictions,
            "created_at": record.created_at.isoformat(),
        }
        self.bq.insert_rows_json(self.PREDICTION_RUN_TABLE, [row])

    # =========================
    # Internal helpers
    # =========================

    def _table_name(self, lottery_type: LotteryType) -> str:
        return self.DRAW_RESULT_TABLE_MAP[lottery_type]

    def _validate_draw_result(self, draw_result: DrawResult) -> None:
        if draw_result.draw_no <= 0:
            raise ValidationError(
                message="draw_no must be greater than 0.",
                details={"draw_no": draw_result.draw_no},
            )

        if draw_result.lottery_type == LotteryType.LOTO6:
            validate_number_count(draw_result.main_numbers, 6, "main_numbers")
            validate_number_count(draw_result.bonus_numbers, 1, "bonus_numbers")
            validate_unique_numbers(draw_result.main_numbers, "main_numbers")
            validate_unique_numbers(draw_result.bonus_numbers, "bonus_numbers")
            validate_number_range(draw_result.main_numbers, 1, 43, "main_numbers")
            validate_number_range(draw_result.bonus_numbers, 1, 43, "bonus_numbers")
            validate_no_overlap(
                draw_result.main_numbers,
                draw_result.bonus_numbers,
                "main_numbers",
                "bonus_numbers",
            )
            return

        if draw_result.lottery_type == LotteryType.LOTO7:
            validate_number_count(draw_result.main_numbers, 7, "main_numbers")
            validate_number_count(draw_result.bonus_numbers, 2, "bonus_numbers")
            validate_unique_numbers(draw_result.main_numbers, "main_numbers")
            validate_unique_numbers(draw_result.bonus_numbers, "bonus_numbers")
            validate_number_range(draw_result.main_numbers, 1, 37, "main_numbers")
            validate_number_range(draw_result.bonus_numbers, 1, 37, "bonus_numbers")
            validate_no_overlap(
                draw_result.main_numbers,
                draw_result.bonus_numbers,
                "main_numbers",
                "bonus_numbers",
            )
            return

        raise ValidationError(
            message="Unsupported lottery type.",
            details={"lottery_type": str(draw_result.lottery_type)},
        )

    def _to_draw_result_row(self, draw_result: DrawResult) -> dict[str, Any]:
        now = datetime.now(timezone.utc)
        return {
            "lottery_type": draw_result.lottery_type.value,
            "draw_no": draw_result.draw_no,
            "draw_date": draw_result.draw_date.isoformat(),
            "main_numbers": sorted(draw_result.main_numbers),
            "bonus_numbers": sorted(draw_result.bonus_numbers),
            "source_type": draw_result.source_type,
            "source_reference": draw_result.source_reference,
            "fetched_at": draw_result.fetched_at.isoformat(),
            "created_at": (draw_result.created_at or now).isoformat(),
            "updated_at": (draw_result.updated_at or now).isoformat(),
        }

    def _from_draw_result_row(self, row: dict[str, Any]) -> DrawResult:
        return DrawResult(
            lottery_type=LotteryType(row["lottery_type"]),
            draw_no=int(row["draw_no"]),
            draw_date=row["draw_date"],
            main_numbers=list(row["main_numbers"]),
            bonus_numbers=list(row["bonus_numbers"]),
            source_type=row["source_type"],
            source_reference=row.get("source_reference"),
            fetched_at=row["fetched_at"],
            created_at=row.get("created_at"),
            updated_at=row.get("updated_at"),
        )
