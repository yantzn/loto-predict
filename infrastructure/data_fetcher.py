from __future__ import annotations

import csv
from dataclasses import dataclass
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Protocol

from domain.models import DrawResult, LotteryType
from utils.exceptions import ValidationError


@dataclass(frozen=True)
class FetchResult:
    lottery_type: LotteryType
    rows: list[DrawResult]


class DrawResultFetcher(Protocol):
    def fetch(self, lottery_type: LotteryType) -> FetchResult:
        raise NotImplementedError


class CsvDrawResultFetcher:
    """
    CSV から draw results を取得する実装。

    想定カラム:
      draw_no,draw_date,main_numbers,bonus_numbers,source_reference

    例:
      draw_no,draw_date,main_numbers,bonus_numbers,source_reference
      1,2024-01-01,"1 7 14 22 31 43","9","seed"
    """

    FILE_MAP = {
        LotteryType.LOTO6: "loto6_draw_results.csv",
        LotteryType.LOTO7: "loto7_draw_results.csv",
    }

    def __init__(self, base_dir: str = "docs/sample_data") -> None:
        self.base_dir = Path(base_dir)

    def fetch(self, lottery_type: LotteryType) -> FetchResult:
        path = self.base_dir / self.FILE_MAP[lottery_type]
        if not path.exists():
            raise ValidationError(
                message="CSV file for draw results was not found.",
                details={
                    "lottery_type": lottery_type.value,
                    "path": str(path),
                },
                is_retryable=False,
            )

        rows: list[DrawResult] = []
        with path.open("r", encoding="utf-8") as fp:
            reader = csv.DictReader(fp)
            for raw in reader:
                rows.append(self._parse_row(raw, lottery_type))

        return FetchResult(
            lottery_type=lottery_type,
            rows=rows,
        )

    def _parse_row(
        self,
        raw: dict[str, str],
        lottery_type: LotteryType,
    ) -> DrawResult:
        now = datetime.now(timezone.utc)

        return DrawResult(
            lottery_type=lottery_type,
            draw_no=int(raw["draw_no"]),
            draw_date=date.fromisoformat(raw["draw_date"]),
            main_numbers=self._parse_numbers(raw["main_numbers"]),
            bonus_numbers=self._parse_numbers(raw.get("bonus_numbers", "")),
            source_type="csv",
            source_reference=raw.get("source_reference") or None,
            fetched_at=now,
            created_at=now,
            updated_at=now,
        )

    @staticmethod
    def _parse_numbers(value: str) -> list[int]:
        text = (value or "").replace(",", " ").strip()
        if not text:
            return []
        return [int(x) for x in text.split()]


class InMemoryDrawResultFetcher:
    """
    開発・疎通確認用。
    """

    def fetch(self, lottery_type: LotteryType) -> FetchResult:
        now = datetime.now(timezone.utc)

        if lottery_type == LotteryType.LOTO6:
            rows = [
                DrawResult(
                    lottery_type=LotteryType.LOTO6,
                    draw_no=1,
                    draw_date=date(2024, 1, 1),
                    main_numbers=[1, 7, 14, 22, 31, 43],
                    bonus_numbers=[9],
                    source_type="in_memory",
                    source_reference="seed",
                    fetched_at=now,
                    created_at=now,
                    updated_at=now,
                )
            ]
        else:
            rows = [
                DrawResult(
                    lottery_type=LotteryType.LOTO7,
                    draw_no=1,
                    draw_date=date(2024, 1, 5),
                    main_numbers=[3, 8, 12, 19, 24, 31, 37],
                    bonus_numbers=[5, 11],
                    source_type="in_memory",
                    source_reference="seed",
                    fetched_at=now,
                    created_at=now,
                    updated_at=now,
                )
            ]

        return FetchResult(
            lottery_type=lottery_type,
            rows=rows,
        )
