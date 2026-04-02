from __future__ import annotations

import csv
import io
import json
from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import datetime, timezone
from urllib.request import Request, urlopen

from utils.exceptions import DataFetchError
from domain.models import LotteryType


@dataclass(frozen=True)
class RawDrawResultRecord:
    lottery_type: LotteryType
    draw_no: int
    draw_date: str
    main_numbers: list[int]
    bonus_numbers: list[int]
    source_type: str
    source_reference: str | None
    fetched_at: datetime


class DrawResultFetcher(ABC):
    @abstractmethod
    def fetch(self, lottery_type: LotteryType) -> list[RawDrawResultRecord]:
        raise NotImplementedError


class CsvDrawResultFetcher(DrawResultFetcher):
    """
    LOTO6 CSV 例:
    draw_no,draw_date,n1,n2,n3,n4,n5,n6,bonus1

    LOTO7 CSV 例:
    draw_no,draw_date,n1,n2,n3,n4,n5,n6,n7,bonus1,bonus2
    """

    def __init__(self, csv_text: str, source_reference: str | None = None) -> None:
        self.csv_text = csv_text
        self.source_reference = source_reference or "inline_csv"

    def fetch(self, lottery_type: LotteryType) -> list[RawDrawResultRecord]:
        try:
            reader = csv.DictReader(io.StringIO(self.csv_text))
            fetched_at = datetime.now(timezone.utc)
            records: list[RawDrawResultRecord] = []

            for row in reader:
                draw_no = int(row["draw_no"])
                draw_date = row["draw_date"]

                if lottery_type == LotteryType.LOTO6:
                    main_numbers = [int(row[f"n{i}"]) for i in range(1, 7)]
                    bonus_numbers = [int(row["bonus1"])]
                elif lottery_type == LotteryType.LOTO7:
                    main_numbers = [int(row[f"n{i}"]) for i in range(1, 8)]
                    bonus_numbers = [int(row["bonus1"]), int(row["bonus2"])]
                else:
                    raise DataFetchError(
                        message="Unsupported lottery type in CSV fetcher.",
                        details={"lottery_type": str(lottery_type)},
                        is_retryable=False,
                    )

                records.append(
                    RawDrawResultRecord(
                        lottery_type=lottery_type,
                        draw_no=draw_no,
                        draw_date=draw_date,
                        main_numbers=main_numbers,
                        bonus_numbers=bonus_numbers,
                        source_type="CSV",
                        source_reference=self.source_reference,
                        fetched_at=fetched_at,
                    )
                )

            return records

        except Exception as exc:
            raise DataFetchError(
                message="Failed to fetch draw results from CSV.",
                details={
                    "lottery_type": lottery_type.value,
                    "source_reference": self.source_reference,
                },
                cause=exc,
                is_retryable=False,
            ) from exc


class ApiDrawResultFetcher(DrawResultFetcher):
    """
    APIレスポンス想定:
    [
      {
        "draw_no": 100,
        "draw_date": "2026-03-01",
        "main_numbers": [1,2,3,4,5,6],
        "bonus_numbers": [7]
      }
    ]
    """

    def __init__(self, endpoint_map: dict[LotteryType, str], timeout: int = 15) -> None:
        self.endpoint_map = endpoint_map
        self.timeout = timeout

    def fetch(self, lottery_type: LotteryType) -> list[RawDrawResultRecord]:
        endpoint = self.endpoint_map.get(lottery_type)
        if not endpoint:
            raise DataFetchError(
                message="API endpoint is not configured.",
                details={"lottery_type": lottery_type.value},
                is_retryable=False,
            )

        try:
            request = Request(
                endpoint,
                headers={"User-Agent": "loto-predict-line/1.0"},
                method="GET",
            )
            with urlopen(request, timeout=self.timeout) as response:
                payload = json.loads(response.read().decode("utf-8"))

            fetched_at = datetime.now(timezone.utc)
            records: list[RawDrawResultRecord] = []

            for item in payload:
                records.append(
                    RawDrawResultRecord(
                        lottery_type=lottery_type,
                        draw_no=int(item["draw_no"]),
                        draw_date=str(item["draw_date"]),
                        main_numbers=[int(n) for n in item["main_numbers"]],
                        bonus_numbers=[int(n) for n in item["bonus_numbers"]],
                        source_type="API",
                        source_reference=endpoint,
                        fetched_at=fetched_at,
                    )
                )

            return records

        except Exception as exc:
            raise DataFetchError(
                message="Failed to fetch draw results from API.",
                details={
                    "lottery_type": lottery_type.value,
                    "endpoint": endpoint,
                },
                cause=exc,
                is_retryable=True,
            ) from exc


class ScraperDrawResultFetcher(DrawResultFetcher):
    """
    将来のスクレイピング差し替え用のひな型。
    """

    def __init__(self, target_url_map: dict[LotteryType, str]) -> None:
        self.target_url_map = target_url_map

    def fetch(self, lottery_type: LotteryType) -> list[RawDrawResultRecord]:
        target_url = self.target_url_map.get(lottery_type)
        if not target_url:
            raise DataFetchError(
                message="Scraper target URL is not configured.",
                details={"lottery_type": lottery_type.value},
                is_retryable=False,
            )

        raise DataFetchError(
            message="ScraperDrawResultFetcher is not implemented yet.",
            details={
                "lottery_type": lottery_type.value,
                "target_url": target_url,
            },
            is_retryable=False,
        )
