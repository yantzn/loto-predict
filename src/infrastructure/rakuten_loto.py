from __future__ import annotations

import logging
import re
import time
from dataclasses import dataclass
from datetime import date, datetime
from typing import Iterable

import requests
from bs4 import BeautifulSoup

from src.domain.loto_result import LotoResult

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class LotterySpec:
    pick_count: int
    bonus_count: int
    max_number: int


class RakutenLotoClient:
    """楽天宝くじの当せん番号案内ページを取得するクライアント。"""

    BASE_URLS = {
        "loto6": {
            "latest": "https://takarakuji.rakuten.co.jp/backnumber/loto6/lastresults/",
            "monthly": "https://takarakuji.rakuten.co.jp/backnumber/loto6/{yyyymm}/",
        },
        "loto7": {
            "latest": "https://takarakuji.rakuten.co.jp/backnumber/loto7/lastresults/",
            "monthly": "https://takarakuji.rakuten.co.jp/backnumber/loto7/{yyyymm}/",
        },
    }

    SPECS = {
        "loto6": LotterySpec(pick_count=6, bonus_count=1, max_number=43),
        "loto7": LotterySpec(pick_count=7, bonus_count=2, max_number=37),
    }

    def __init__(self, timeout: int = 20, sleep_seconds: float = 0.0) -> None:
        self.timeout = timeout
        self.sleep_seconds = sleep_seconds
        self.session = requests.Session()
        self.session.headers.update(
            {
                "User-Agent": (
                    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) "
                    "Chrome/124.0.0.0 Safari/537.36"
                )
            }
        )

    def fetch_latest_result(self, lottery_type: str) -> LotoResult:
        normalized = self._normalize_lottery_type(lottery_type)
        url = self.BASE_URLS[normalized]["latest"]

        try:
            html = self._fetch_html(url)
            results = self._parse_results_from_html(html=html, lottery_type=normalized, source_url=url)
            if not results:
                raise ValueError(f"latest result not found: lottery_type={normalized}")
            latest = max(results, key=lambda result: result.draw_no)
            latest.validate()
            return latest
        except Exception:
            logger.exception("Failed to fetch latest result. lottery_type=%s url=%s", normalized, url)
            raise

    def fetch_history(
        self,
        lottery_type: str,
        start_date: date | str,
        end_date: date | str,
    ) -> list[LotoResult]:
        normalized = self._normalize_lottery_type(lottery_type)
        start = self._coerce_date(start_date)
        end = self._coerce_date(end_date)
        if start > end:
            raise ValueError("start_date must be <= end_date")

        all_results: dict[int, LotoResult] = {}

        for year, month in self._iter_year_month(start.year, start.month, end.year, end.month):
            yyyymm = f"{year}{month:02d}"
            url = self.BASE_URLS[normalized]["monthly"].format(yyyymm=yyyymm)

            try:
                html = self._fetch_html(url)
                monthly_results = self._parse_results_from_html(html=html, lottery_type=normalized, source_url=url)
                for result in monthly_results:
                    draw_date = self._coerce_date(result.draw_date)
                    if start <= draw_date <= end:
                        all_results[result.draw_no] = result
            except Exception as exc:
                logger.warning(
                    "Failed to fetch monthly history. lottery_type=%s url=%s error=%s",
                    normalized,
                    url,
                    exc,
                )

            if self.sleep_seconds > 0:
                time.sleep(self.sleep_seconds)

        results = sorted(all_results.values(), key=lambda result: result.draw_no)
        for result in results:
            result.validate()
        return results

    def _fetch_html(self, url: str) -> str:
        response = self.session.get(url, timeout=self.timeout)
        response.raise_for_status()
        return response.text

    def _parse_results_from_html(
        self,
        html: str,
        lottery_type: str,
        source_url: str,
    ) -> list[LotoResult]:
        soup = BeautifulSoup(html, "html.parser")
        results: list[LotoResult] = []

        for row in soup.find_all("tr"):
            row_text = row.get_text(" | ", strip=True)
            parsed = self._parse_row_text(row_text, lottery_type=lottery_type, source_url=source_url)
            if parsed is not None:
                results.append(parsed)

        deduped = {result.draw_no: result for result in results}
        return sorted(deduped.values(), key=lambda result: result.draw_no, reverse=True)

    def _parse_row_text(
        self,
        row_text: str,
        lottery_type: str,
        source_url: str,
    ) -> LotoResult | None:
        normalized = re.sub(r"\s+", " ", row_text).strip()
        match = re.match(
            r"第0*(?P<draw_no>\d+)回\s+(?P<draw_date>\d{4}/\d{2}/\d{2})\s*\|\s*(?P<main>[\d ]+)\s*\|\s*(?P<bonus>[\d ]+)$",
            normalized,
        )
        if match is None:
            return None

        spec = self.SPECS[lottery_type]
        main_numbers = self._extract_numbers(match.group("main"), expected_count=spec.pick_count)
        bonus_numbers = self._extract_numbers(match.group("bonus"), expected_count=spec.bonus_count)
        if main_numbers is None or bonus_numbers is None:
            return None

        result = LotoResult(
            lottery_type=lottery_type,
            draw_no=int(match.group("draw_no")),
            draw_date=match.group("draw_date").replace("/", "-"),
            main_numbers=main_numbers,
            bonus_numbers=bonus_numbers,
            source_url=source_url,
        )
        result.validate()
        return result

    def _extract_numbers(self, text: str, expected_count: int) -> list[int] | None:
        numbers = [int(value) for value in re.findall(r"\d+", text)]
        if len(numbers) < expected_count:
            return None
        return numbers[:expected_count]

    def _iter_year_month(
        self,
        start_year: int,
        start_month: int,
        end_year: int,
        end_month: int,
    ) -> Iterable[tuple[int, int]]:
        year = start_year
        month = start_month
        while (year, month) <= (end_year, end_month):
            yield year, month
            if month == 12:
                year += 1
                month = 1
            else:
                month += 1

    def _coerce_date(self, value: date | str) -> date:
        if isinstance(value, date):
            return value
        return datetime.strptime(str(value), "%Y-%m-%d").date()

    def _normalize_lottery_type(self, lottery_type: str) -> str:
        normalized = str(lottery_type).strip().lower()
        if normalized not in {"loto6", "loto7"}:
            raise ValueError(f"unsupported lottery_type: {lottery_type}")
        return normalized
