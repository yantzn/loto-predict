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
            latest = self._parse_latest_result_from_html(
                html=html,
                lottery_type=normalized,
                source_url=url,
            )
            latest.validate()
            return latest
        except Exception:
            logger.exception(
                "Failed to fetch latest result. lottery_type=%s url=%s",
                normalized,
                url,
            )
            raise

    def _parse_latest_result_from_html(
        self,
        html: str,
        lottery_type: str,
        source_url: str,
    ) -> LotoResult:
        # latest は monthly と HTML 構造が異なるため専用パスに分ける。
        # monthly 側の抽出ロジックを無理に共通化すると、backfill 成功パターンを壊しやすい。
        soup = BeautifulSoup(html, "html.parser")
        rows = soup.find_all("tr")

        candidate_samples: list[str] = []
        unexpected_samples: list[str] = []
        logger.info(
            "Latest parse started. lottery_type=%s url=%s tr_count=%s",
            lottery_type,
            source_url,
            len(rows),
        )

        for row in rows:
            row_text = row.get_text(" | ", strip=True)
            if not row_text:
                continue

            if row_text.startswith("第") and len(candidate_samples) < 5:
                candidate_samples.append(row_text)

            parsed = self._parse_latest_row_text(row_text, lottery_type, source_url)
            if parsed is not None:
                logger.info(
                    "Latest parse succeeded. lottery_type=%s url=%s draw_no=%s candidates=%s",
                    lottery_type,
                    source_url,
                    parsed.draw_no,
                    candidate_samples,
                )
                return parsed

            if row_text.startswith("第") and len(unexpected_samples) < 5:
                parts = [part.strip() for part in row_text.split("|") if part.strip()]
                unexpected_samples.append(f"parts={len(parts)} text={row_text}")

        logger.info(
            "Latest parse failed. lottery_type=%s url=%s candidates=%s unexpected_parts=%s",
            lottery_type,
            source_url,
            candidate_samples,
            unexpected_samples,
        )
        raise ValueError(f"latest result not found: lottery_type={lottery_type}")

    def _parse_latest_row_text(
        self,
        row_text: str,
        lottery_type: str,
        source_url: str,
    ) -> LotoResult | None:
        if not row_text.startswith("第"):
            return None

        parts = [part.strip() for part in row_text.split("|") if part.strip()]
        if len(parts) < 3:
            return None

        draw_match = re.match(r"^第0*(\d+)回$", parts[0])
        if draw_match is None:
            return None

        draw_no = int(draw_match.group(1))
        draw_date = parts[1].replace("/", "-")

        try:
            if lottery_type == "loto6":
                # latest は「第回 | 日付 | 本数字6個 | ボーナス1個」が基本。
                # 8/9 列揺れに備え、必要個数を満たすかで判定する。
                if len(parts) not in {8, 9}:
                    return None
                if len(parts[2:]) < 7:
                    return None
                main_numbers = [int(value) for value in parts[2:8]]
                bonus_numbers = [int(parts[8])] if len(parts) >= 9 else [int(parts[-1])]
            else:
                # loto7 latest は「第回 | 日付 | 本数字7個 | ボーナス2個」が基本。
                if len(parts) < 11:
                    return None
                main_numbers = [int(value) for value in parts[2:9]]
                bonus_numbers = [int(value) for value in parts[9:11]]
        except ValueError:
            return None

        result = LotoResult(
            lottery_type=lottery_type,
            draw_no=draw_no,
            draw_date=draw_date,
            main_numbers=main_numbers,
            bonus_numbers=bonus_numbers,
            source_url=source_url,
        )
        result.validate()
        return result

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

        for year, month in self._iter_year_month(
            start.year,
            start.month,
            end.year,
            end.month,
        ):
            yyyymm = f"{year}{month:02d}"
            url = self.BASE_URLS[normalized]["monthly"].format(yyyymm=yyyymm)

            try:
                html = self._fetch_html(url)
                monthly_results = self._parse_results_from_html(
                    html=html,
                    lottery_type=normalized,
                    source_url=url,
                )

                logger.info(
                    "Fetched monthly history. lottery_type=%s yyyymm=%s count=%s url=%s",
                    normalized,
                    yyyymm,
                    len(monthly_results),
                    url,
                )

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
        """
        楽天の結果ページは、少なくとも現行の月別ページでは
        「回号 / 抽せん日 / 本数字 / ボーナス数字」が縦並びのプレーンテキストとして
        取得できるため、<tr> 単位ではなくページ全文テキストから抽出する。

        旧実装互換のため、最後に <tr> ベースのフォールバックも残す。
        """
        soup = BeautifulSoup(html, "html.parser")

        results = self._parse_results_from_full_text(
            soup=soup,
            lottery_type=lottery_type,
            source_url=source_url,
        )
        if results:
            return results

        logger.info(
            "Full-text parse returned no results. Fallback to row-based parse. lottery_type=%s url=%s",
            lottery_type,
            source_url,
        )

        fallback_results = self._parse_results_from_rows(
            soup=soup,
            lottery_type=lottery_type,
            source_url=source_url,
        )
        return fallback_results

    def _parse_results_from_full_text(
        self,
        soup: BeautifulSoup,
        lottery_type: str,
        source_url: str,
    ) -> list[LotoResult]:
        spec = self.SPECS[lottery_type]
        text = soup.get_text("\n", strip=True)
        normalized = self._normalize_page_text(text)

        # 楽天ページは「回号 第1962回 / 抽せん日 2025/01/06 / 本数字 ... / ボーナス数字 (...)」
        # の縦並びなので、このまとまりごとに抽出する。
        block_pattern = re.compile(
            rf"回号\s*第0*(?P<draw_no>\d+)回\s*"
            rf"抽せん日\s*(?P<draw_date>\d{{4}}/\d{{2}}/\d{{2}})\s*"
            rf"本数字\s*(?P<main>(?:\d+\s+){{{spec.pick_count - 1}}}\d+)\s*"
            rf"ボーナス数字\s*[\(（](?P<bonus>(?:\d+\s*){{{spec.bonus_count}}})[\)）]",
            flags=re.MULTILINE,
        )

        results: list[LotoResult] = []
        for match in block_pattern.finditer(normalized):
            main_numbers = self._extract_numbers(
                match.group("main"),
                expected_count=spec.pick_count,
            )
            bonus_numbers = self._extract_numbers(
                match.group("bonus"),
                expected_count=spec.bonus_count,
            )

            if main_numbers is None or bonus_numbers is None:
                continue

            result = LotoResult(
                lottery_type=lottery_type,
                draw_no=int(match.group("draw_no")),
                draw_date=match.group("draw_date").replace("/", "-"),
                main_numbers=main_numbers,
                bonus_numbers=bonus_numbers,
                source_url=source_url,
            )
            result.validate()
            results.append(result)

        deduped = {result.draw_no: result for result in results}
        parsed = sorted(deduped.values(), key=lambda result: result.draw_no, reverse=True)

        logger.info(
            "Parsed full-text history. lottery_type=%s url=%s parsed_count=%s sample_draw_nos=%s",
            lottery_type,
            source_url,
            len(parsed),
            [result.draw_no for result in parsed[:5]],
        )

        return parsed

    def _parse_results_from_rows(
        self,
        soup: BeautifulSoup,
        lottery_type: str,
        source_url: str,
    ) -> list[LotoResult]:
        results: list[LotoResult] = []
        unmatched_samples: list[str] = []

        rows = soup.find_all("tr")
        logger.info(
            "Fallback row parse started. lottery_type=%s url=%s tr_count=%s",
            lottery_type,
            source_url,
            len(rows),
        )

        for row in rows:
            row_text = row.get_text(" | ", strip=True)
            parsed = self._parse_row_text(
                row_text,
                lottery_type=lottery_type,
                source_url=source_url,
            )
            if parsed is not None:
                results.append(parsed)
            elif len(unmatched_samples) < 5 and row_text:
                unmatched_samples.append(row_text)

        logger.info(
            "Fallback row parse finished. lottery_type=%s url=%s parsed_count=%s unmatched_samples=%s",
            lottery_type,
            source_url,
            len(results),
            unmatched_samples,
        )

        deduped = {result.draw_no: result for result in results}
        return sorted(deduped.values(), key=lambda result: result.draw_no, reverse=True)

    def _parse_row_text(
        self,
        row_text: str,
        lottery_type: str,
        source_url: str,
    ) -> LotoResult | None:
        normalized = re.sub(r"\s+", " ", row_text).strip()

        # 旧ページ構造向けのフォールバック。
        match = re.match(
            r"第0*(?P<draw_no>\d+)回\s+(?P<draw_date>\d{4}/\d{2}/\d{2})\s*\|\s*(?P<main>[\d ]+)\s*\|\s*(?P<bonus>[\d ]+)$",
            normalized,
        )
        if match is None:
            return None

        spec = self.SPECS[lottery_type]
        main_numbers = self._extract_numbers(
            match.group("main"),
            expected_count=spec.pick_count,
        )
        bonus_numbers = self._extract_numbers(
            match.group("bonus"),
            expected_count=spec.bonus_count,
        )
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

    def _normalize_page_text(self, text: str) -> str:
        normalized = text.replace("\xa0", " ").replace("\u3000", " ")
        normalized = normalized.replace("（", "(").replace("）", ")")
        normalized = re.sub(r"[ \t\r\f\v]+", " ", normalized)
        normalized = re.sub(r"\n+", "\n", normalized)
        return normalized

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
