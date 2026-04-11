from __future__ import annotations

import os
import re
import time
from dataclasses import dataclass
from datetime import date, datetime
from typing import Iterable
from urllib.parse import urljoin, urlparse

import requests
from bs4 import BeautifulSoup


@dataclass(frozen=True)
class LotoResult:
    lottery_type: str  # LOTO6 / LOTO7
    draw_no: int
    draw_date: str  # YYYY-MM-DD
    main_numbers: list[int]
    bonus_numbers: list[int]
    source_url: str

    def validate(self) -> None:
        if self.lottery_type == "LOTO6":
            if len(self.main_numbers) != 6:
                raise ValueError(f"LOTO6 main_numbers must be 6: {self.main_numbers}")
            if len(self.bonus_numbers) != 1:
                raise ValueError(f"LOTO6 bonus_numbers must be 1: {self.bonus_numbers}")
            if len(set(self.main_numbers)) != 6:
                raise ValueError(f"LOTO6 main_numbers duplicated: {self.main_numbers}")
            if not all(1 <= n <= 43 for n in self.main_numbers + self.bonus_numbers):
                raise ValueError(
                    f"LOTO6 numbers out of range: main={self.main_numbers}, bonus={self.bonus_numbers}"
                )
            return

        if self.lottery_type == "LOTO7":
            if len(self.main_numbers) != 7:
                raise ValueError(f"LOTO7 main_numbers must be 7: {self.main_numbers}")
            if len(self.bonus_numbers) != 2:
                raise ValueError(f"LOTO7 bonus_numbers must be 2: {self.bonus_numbers}")
            if len(set(self.main_numbers)) != 7:
                raise ValueError(f"LOTO7 main_numbers duplicated: {self.main_numbers}")
            if not all(1 <= n <= 37 for n in self.main_numbers + self.bonus_numbers):
                raise ValueError(
                    f"LOTO7 numbers out of range: main={self.main_numbers}, bonus={self.bonus_numbers}"
                )
            return

        raise ValueError(f"unsupported lottery_type: {self.lottery_type}")


class RakutenLotoClient:
    BASE_URL = "https://takarakuji.rakuten.co.jp"

    REQUEST_TIMEOUT_SECONDS = int(os.getenv("REQUEST_TIMEOUT_SECONDS", "60"))
    HTTP_USER_AGENT = os.getenv("HTTP_USER_AGENT", "loto-predict/1.0")

    LOTO6_CURRENT_BASE = "https://takarakuji.rakuten.co.jp/backnumber/loto6/"
    LOTO7_CURRENT_BASE = "https://takarakuji.rakuten.co.jp/backnumber/loto7/"
    LOTO6_RECENT10_URL = "https://takarakuji.rakuten.co.jp/backnumber/loto6/lastresults/"
    LOTO7_RECENT10_URL = "https://takarakuji.rakuten.co.jp/backnumber/loto7/lastresults/"
    LOTO6_PAST_INDEX = "https://takarakuji.rakuten.co.jp/backnumber/loto6_past/"
    LOTO7_PAST_INDEX = "https://takarakuji.rakuten.co.jp/backnumber/loto7_past/"

    def __init__(self) -> None:
        self.session = requests.Session()
        self.session.headers.update(
            {
                "User-Agent": self.HTTP_USER_AGENT,
                "Accept-Language": "ja,en-US;q=0.9,en;q=0.8",
            }
        )

    def fetch_latest_result(self, lottery_type: str) -> LotoResult:
        lottery_type = lottery_type.upper()
        candidates = [
            self._current_month_url(lottery_type),
            self._current_base_url(lottery_type),
            self._recent10_url(lottery_type),
        ]

        all_results: dict[int, LotoResult] = {}
        for url in candidates:
            try:
                results = self.fetch_page_results(lottery_type, url)
                for result in results:
                    all_results[result.draw_no] = result
            except Exception:
                continue

        if not all_results:
            raise ValueError(f"failed to fetch latest result: {lottery_type}")

        return sorted(all_results.values(), key=lambda x: x.draw_no)[-1]

    def fetch_history(
        self,
        lottery_type: str,
        *,
        start_date: date | None = None,
        end_date: date | None = None,
        sleep_seconds: float = 0.2,
    ) -> list[LotoResult]:
        lottery_type = lottery_type.upper()
        urls = set()

        urls.add(self._current_base_url(lottery_type))
        urls.add(self._recent10_url(lottery_type))
        urls.add(self._current_month_url(lottery_type))

        if start_date and end_date:
            for year, month in self._iter_year_month(
                start_date.year,
                start_date.month,
                end_date.year,
                end_date.month,
            ):
                urls.add(self._month_url(lottery_type, year, month))

        past_index_url = self._past_index_url(lottery_type)
        urls.update(self._discover_backfill_urls_from_index(lottery_type, past_index_url))

        collected: dict[int, LotoResult] = {}
        for url in sorted(urls):
            try:
                results = self.fetch_page_results(lottery_type, url)
                for result in results:
                    result_date = datetime.strptime(result.draw_date, "%Y-%m-%d").date()
                    if start_date and result_date < start_date:
                        continue
                    if end_date and result_date > end_date:
                        continue
                    collected[result.draw_no] = result
            except Exception:
                pass
            time.sleep(sleep_seconds)

        return sorted(collected.values(), key=lambda x: x.draw_no)

    def fetch_page_results(self, lottery_type: str, url: str) -> list[LotoResult]:
        lottery_type = lottery_type.upper()
        html = self._download_html(url)
        text = self._normalize_text(html)
        return self._parse_blocked_page(lottery_type, text, url)

    def _download_html(self, url: str) -> str:
        response = self.session.get(url, timeout=self.REQUEST_TIMEOUT_SECONDS)
        response.raise_for_status()
        response.encoding = response.apparent_encoding or "utf-8"
        return response.text

    def _discover_backfill_urls_from_index(self, lottery_type: str, index_url: str) -> set[str]:
        html = self._download_html(index_url)
        soup = BeautifulSoup(html, "html.parser")
        urls: set[str] = set()

        for a in soup.find_all("a", href=True):
            href = a["href"].strip()
            absolute = urljoin(index_url, href)
            parsed = urlparse(absolute)

            if parsed.netloc and parsed.netloc != "takarakuji.rakuten.co.jp":
                continue

            path = parsed.path
            if lottery_type == "LOTO6":
                if (
                    "/backnumber/loto6/" in path
                    or "/backnumber/loto6_detail/" in path
                    or path.endswith("/backnumber/loto6_past/")
                ):
                    urls.add(absolute)
            elif lottery_type == "LOTO7":
                if (
                    "/backnumber/loto7/" in path
                    or "/backnumber/loto7_detail/" in path
                    or path.endswith("/backnumber/loto7_past/")
                ):
                    urls.add(absolute)

        return urls

    def _parse_blocked_page(self, lottery_type: str, text: str, source_url: str) -> list[LotoResult]:
        max_number = 43 if lottery_type == "LOTO6" else 37
        total_needed = 7 if lottery_type == "LOTO6" else 9

        blocks = re.split(r"(?=第0*\d+回)", text)
        results: dict[int, LotoResult] = {}

        for block in blocks:
            block = block.strip()
            if not block.startswith("第"):
                continue

            draw_match = re.search(r"第0*(\d+)回", block)
            date_match = re.search(r"(\d{4}/\d{2}/\d{2})", block)
            if not draw_match or not date_match:
                continue

            draw_no = int(draw_match.group(1))
            draw_date = datetime.strptime(date_match.group(1), "%Y/%m/%d").strftime("%Y-%m-%d")

            tail = block[date_match.end():]
            all_numbers = [int(x) for x in re.findall(r"\b\d{1,2}\b", tail)]
            candidate_numbers = [n for n in all_numbers if 1 <= n <= max_number]

            if len(candidate_numbers) < total_needed:
                continue

            picked = candidate_numbers[:total_needed]
            if lottery_type == "LOTO6":
                main_numbers = picked[:6]
                bonus_numbers = picked[6:7]
            else:
                main_numbers = picked[:7]
                bonus_numbers = picked[7:9]

            result = LotoResult(
                lottery_type=lottery_type,
                draw_no=draw_no,
                draw_date=draw_date,
                main_numbers=main_numbers,
                bonus_numbers=bonus_numbers,
                source_url=source_url,
            )

            try:
                result.validate()
            except Exception:
                continue

            results[result.draw_no] = result

        return sorted(results.values(), key=lambda x: x.draw_no)

    def _normalize_text(self, html: str) -> str:
        soup = BeautifulSoup(html, "html.parser")
        for tag in soup(["script", "style", "noscript"]):
            tag.decompose()
        text = soup.get_text("\n", strip=True)
        text = text.replace("\u3000", " ")
        text = re.sub(r"[ \t]+", " ", text)
        text = re.sub(r"\n+", "\n", text)
        return text

    def _current_base_url(self, lottery_type: str) -> str:
        if lottery_type == "LOTO6":
            return self.LOTO6_CURRENT_BASE
        if lottery_type == "LOTO7":
            return self.LOTO7_CURRENT_BASE
        raise ValueError(f"unsupported lottery_type: {lottery_type}")

    def _recent10_url(self, lottery_type: str) -> str:
        if lottery_type == "LOTO6":
            return self.LOTO6_RECENT10_URL
        if lottery_type == "LOTO7":
            return self.LOTO7_RECENT10_URL
        raise ValueError(f"unsupported lottery_type: {lottery_type}")

    def _past_index_url(self, lottery_type: str) -> str:
        if lottery_type == "LOTO6":
            return self.LOTO6_PAST_INDEX
        if lottery_type == "LOTO7":
            return self.LOTO7_PAST_INDEX
        raise ValueError(f"unsupported lottery_type: {lottery_type}")

    def _current_month_url(self, lottery_type: str) -> str:
        now = datetime.now()
        return self._month_url(lottery_type, now.year, now.month)

    def _month_url(self, lottery_type: str, year: int, month: int) -> str:
        year_month = f"{year}{month:02d}"
        if lottery_type == "LOTO6":
            return f"{self.LOTO6_CURRENT_BASE}{year_month}/"
        if lottery_type == "LOTO7":
            return f"{self.LOTO7_CURRENT_BASE}{year_month}/"
        raise ValueError(f"unsupported lottery_type: {lottery_type}")

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
