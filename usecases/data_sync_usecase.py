from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from domain.models import DrawResult, LotteryType
from infrastructure.data_fetcher import DrawResultFetcher, RawDrawResultRecord
from infrastructure.loto_repository import BigQueryLotoRepository
from utils.exceptions import ValidationError
from utils.logger import get_logger, log_start, log_success

logger = get_logger(__name__)


@dataclass(frozen=True)
class DataSyncResult:
    lottery_type: LotteryType
    fetched_count: int
    valid_count: int
    saved_count: int
    skipped_count: int
    skipped_reasons: list[dict[str, object]]


class DataSyncUseCase:
    """
    外部データ取得 → 検証 → BigQuery 保存のユースケース。
    """

    def __init__(
        self,
        fetcher: DrawResultFetcher,
        repository: BigQueryLotoRepository,
        skip_existing: bool = True,
        fail_on_invalid_record: bool = False,
    ) -> None:
        self.fetcher = fetcher
        self.repository = repository
        self.skip_existing = skip_existing
        self.fail_on_invalid_record = fail_on_invalid_record

    def execute(self, lottery_type: LotteryType) -> DataSyncResult:
        log_start(logger, "data_sync", lottery_type=lottery_type.value)

        raw_records = self.fetcher.fetch(lottery_type)
        fetched_count = len(raw_records)

        valid_entities: list[DrawResult] = []
        skipped_reasons: list[dict[str, object]] = []

        for raw in raw_records:
            try:
                entity = self._to_entity(raw)

                if self.skip_existing:
                    existing = self.repository.find_draw_result_by_draw_no(
                        lottery_type=entity.lottery_type,
                        draw_no=entity.draw_no,
                    )
                    if existing is not None:
                        skipped_reasons.append(
                            {
                                "draw_no": entity.draw_no,
                                "reason": "already_exists",
                            }
                        )
                        continue

                # 保存前の最終検証は repository 側でも行う
                valid_entities.append(entity)

            except ValidationError as exc:
                if self.fail_on_invalid_record:
                    raise

                skipped_reasons.append(
                    {
                        "draw_no": raw.draw_no,
                        "reason": "validation_error",
                        "details": exc.details,
                        "message": str(exc),
                    }
                )
            except Exception as exc:
                if self.fail_on_invalid_record:
                    raise

                skipped_reasons.append(
                    {
                        "draw_no": raw.draw_no,
                        "reason": "unexpected_parse_error",
                        "message": str(exc),
                    }
                )

        if valid_entities:
            self.repository.save_draw_results(valid_entities)

        result = DataSyncResult(
            lottery_type=lottery_type,
            fetched_count=fetched_count,
            valid_count=len(valid_entities),
            saved_count=len(valid_entities),
            skipped_count=len(skipped_reasons),
            skipped_reasons=skipped_reasons,
        )

        log_success(
            logger,
            "data_sync",
            lottery_type=lottery_type.value,
            fetched_count=result.fetched_count,
            valid_count=result.valid_count,
            saved_count=result.saved_count,
            skipped_count=result.skipped_count,
        )
        return result

    def _to_entity(self, raw: RawDrawResultRecord) -> DrawResult:
        return DrawResult(
            lottery_type=raw.lottery_type,
            draw_no=int(raw.draw_no),
            draw_date=self._parse_date(raw.draw_date),
            main_numbers=[int(n) for n in raw.main_numbers],
            bonus_numbers=[int(n) for n in raw.bonus_numbers],
            source_type=raw.source_type,
            source_reference=raw.source_reference,
            fetched_at=raw.fetched_at,
        )

    def _parse_date(self, value: str):
        normalized = value.strip().replace("/", "-")
        return datetime.strptime(normalized, "%Y-%m-%d").date()
