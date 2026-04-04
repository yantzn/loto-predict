from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone

from domain.models import DrawResult, LotteryType
from infrastructure.data_fetcher import DrawResultFetcher
from infrastructure.loto_repository import BigQueryLotoRepository
from utils.exceptions import ValidationError
from utils.logger import get_logger, log_failure, log_start, log_success

logger = get_logger(__name__)


@dataclass(frozen=True)
class DataSyncRequest:
    lottery_type: LotteryType


@dataclass(frozen=True)
class DataSyncResult:
    lottery_type: LotteryType
    fetched_count: int
    inserted_count: int
    executed_at: datetime


class DataSyncUseCase:
    def __init__(
        self,
        fetcher: DrawResultFetcher,
        repository: BigQueryLotoRepository,
    ) -> None:
        self.fetcher = fetcher
        self.repository = repository

    def execute(self, request: DataSyncRequest) -> DataSyncResult:
        log_start(
            logger,
            "data_sync_started",
            lottery_type=request.lottery_type.value,
        )

        try:
            fetch_result = self.fetcher.fetch(request.lottery_type)

            for row in fetch_result.rows:
                self._validate(row)

            inserted_count = self.repository.save_draw_results_idempotent(
                fetch_result.rows
            )

            result = DataSyncResult(
                lottery_type=request.lottery_type,
                fetched_count=len(fetch_result.rows),
                inserted_count=inserted_count,
                executed_at=datetime.now(timezone.utc),
            )

            log_success(
                logger,
                "data_sync_completed",
                lottery_type=request.lottery_type.value,
                fetched_count=result.fetched_count,
                inserted_count=result.inserted_count,
            )
            return result

        except Exception as exc:
            log_failure(
                logger,
                "data_sync_failed",
                lottery_type=request.lottery_type.value,
                error_type=type(exc).__name__,
                message=str(exc),
            )
            raise

    def _validate(self, row: DrawResult) -> None:
        if row.draw_no <= 0:
            raise ValidationError(
                message="draw_no must be greater than 0.",
                details={"draw_no": row.draw_no},
                is_retryable=False,
            )

        if row.lottery_type == LotteryType.LOTO6:
            expected_main_count = 6
            max_number = 43
            expected_bonus_count = 1
        else:
            expected_main_count = 7
            max_number = 37
            expected_bonus_count = 2

        if len(row.main_numbers) != expected_main_count:
            raise ValidationError(
                message="Invalid main number count.",
                details={
                    "lottery_type": row.lottery_type.value,
                    "draw_no": row.draw_no,
                    "expected": expected_main_count,
                    "actual": len(row.main_numbers),
                },
                is_retryable=False,
            )

        if len(row.bonus_numbers) != expected_bonus_count:
            raise ValidationError(
                message="Invalid bonus number count.",
                details={
                    "lottery_type": row.lottery_type.value,
                    "draw_no": row.draw_no,
                    "expected": expected_bonus_count,
                    "actual": len(row.bonus_numbers),
                },
                is_retryable=False,
            )

        if len(set(row.main_numbers)) != len(row.main_numbers):
            raise ValidationError(
                message="main_numbers contains duplicates.",
                details={"draw_no": row.draw_no},
                is_retryable=False,
            )

        if len(set(row.bonus_numbers)) != len(row.bonus_numbers):
            raise ValidationError(
                message="bonus_numbers contains duplicates.",
                details={"draw_no": row.draw_no},
                is_retryable=False,
            )

        overlap = set(row.main_numbers) & set(row.bonus_numbers)
        if overlap:
            raise ValidationError(
                message="main_numbers and bonus_numbers overlap.",
                details={
                    "draw_no": row.draw_no,
                    "overlap": sorted(overlap),
                },
                is_retryable=False,
            )

        for number in row.main_numbers + row.bonus_numbers:
            if number < 1 or number > max_number:
                raise ValidationError(
                    message="Number is out of allowed range.",
                    details={
                        "draw_no": row.draw_no,
                        "number": number,
                        "min": 1,
                        "max": max_number,
                    },
                    is_retryable=False,
                )
