import logging
from datetime import datetime
from typing import List
from src.domain.models import LotoResult

class RakutenLotoClient:
    LOTO_URLS = {
        "loto6": "https://www.rakuten-bank.co.jp/event/loto6/winning-numbers/",
        "loto7": "https://www.rakuten-bank.co.jp/event/loto7/winning-numbers/",
    }

    def fetch_latest_result(self, lottery_type: str) -> LotoResult:
        # TODO: 本番はHTMLパース実装
        logger = logging.getLogger(__name__)
        try:
            if lottery_type == "loto6":
                main = [1, 2, 3, 4, 5, 6]
                bonus = [7]
            else:
                main = [1, 2, 3, 4, 5, 6, 7]
                bonus = [8, 9]
            result = LotoResult(
                lottery_type=lottery_type,
                draw_no=1234,
                draw_date=datetime.now().strftime("%Y-%m-%d"),
                main_numbers=main,
                bonus_numbers=bonus,
                source_url=self.LOTO_URLS[lottery_type],
            )
            result.validate()
            return result
        except Exception as e:
            logger.error(f"[RakutenLotoClient] failed: type={lottery_type} url={self.LOTO_URLS[lottery_type]} reason={e}")
            raise

    def fetch_history(self, lottery_type: str, start_date: str, end_date: str) -> List[LotoResult]:
        # TODO: 本番はHTMLパース実装
        logger = logging.getLogger(__name__)
        results = []
        for i in range(10):
            try:
                if lottery_type == "loto6":
                    main = [1, 2, 3, 4, 5, 6]
                    bonus = [7]
                else:
                    main = [1, 2, 3, 4, 5, 6, 7]
                    bonus = [8, 9]
                result = LotoResult(
                    lottery_type=lottery_type,
                    draw_no=1000 + i,
                    draw_date="2024-01-01",
                    main_numbers=main,
                    bonus_numbers=bonus,
                    source_url=self.LOTO_URLS[lottery_type],
                )
                result.validate()
                results.append(result)
            except Exception as e:
                logger.error(f"[RakutenLotoClient] history failed: type={lottery_type} url={self.LOTO_URLS[lottery_type]} reason={e}")
                continue
        return results
from __future__ import annotations

import logging
import re
import time
from dataclasses import dataclass
from datetime import date, datetime
from typing import Iterable

import requests
from bs4 import BeautifulSoup

from src.domain.models import Loto6Result, Loto7Result, LotoResult

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class LotteryRule:
    name: str
    pick_count: int
    bonus_count: int
    max_number: int


class RakutenLotoClient:
    """
    楽天×宝くじの当せん番号案内ページからロト6/ロト7結果を取得するクライアント。

    対応ページ:
    - 最新10回: /backnumber/loto6/lastresults/, /backnumber/loto7/lastresults/
    - 月別履歴: /backnumber/loto6/YYYYMM/, /backnumber/loto7/YYYYMM/
    """

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

    RULES = {
        "loto6": LotteryRule(name="loto6", pick_count=6, bonus_count=1, max_number=43),
        "loto7": LotteryRule(name="loto7", pick_count=7, bonus_count=2, max_number=37),
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
        html = self._fetch_html(url)
        results = self._parse_results_from_html(html=html, lottery_type=normalized, source_url=url)

        if not results:
            raise ValueError(f"latest result not found: lottery_type={normalized}")

        latest = sorted(results, key=lambda x: x.draw_no, reverse=True)[0]
        latest.validate()
        return latest

    def fetch_history(
        self,
        lottery_type: str,
        start_date: date,
        end_date: date,
    ) -> list[LotoResult]:
        normalized = self._normalize_lottery_type(lottery_type)
        if start_date > end_date:
            raise ValueError("start_date must be <= end_date")

        all_results: dict[int, LotoResult] = {}

        for year, month in self._iter_year_month(
            start_year=start_date.year,
            start_month=start_date.month,
            end_year=end_date.year,
            end_month=end_date.month,
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
                for result in monthly_results:
                    draw_dt = datetime.strptime(result.draw_date, "%Y-%m-%d").date()
                    if start_date <= draw_dt <= end_date:
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

        results = sorted(all_results.values(), key=lambda x: x.draw_no)
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
        text = BeautifulSoup(html, "html.parser").get_text("\n", strip=True)
        text = re.sub(r"[ \t\u3000]+", " ", text)
        blocks = self._split_draw_blocks(text)

        results: list[LotoResult] = []
        for block in blocks:
            try:
                result = self._parse_draw_block(block, lottery_type=lottery_type, source_url=source_url)
                if result is not None:
                    results.append(result)
            except Exception as exc:
                logger.debug("Skip unparsable block. lottery_type=%s error=%s block=%s", lottery_type, exc, block[:300])

        deduped: dict[int, LotoResult] = {result.draw_no: result for result in results}
        return sorted(deduped.values(), key=lambda x: x.draw_no, reverse=True)

    def _split_draw_blocks(self, text: str) -> list[str]:
        matches = list(re.finditer(r"第0*\d+回", text))
        if not matches:
            return []

        blocks: list[str] = []
        for index, match in enumerate(matches):
            start = match.start()
            end = matches[index + 1].start() if index + 1 < len(matches) else len(text)
            blocks.append(text[start:end])
        return blocks

    def _parse_draw_block(
        self,
        block: str,
        lottery_type: str,
        source_url: str,
    ) -> LotoResult | None:
        draw_match = re.search(r"第0*(\d+)回", block)
        date_match = re.search(r"(\d{4}/\d{2}/\d{2})", block)
        if not draw_match or not date_match:
            return None

        draw_no = int(draw_match.group(1))
        draw_date = date_match.group(1).replace("/", "-")
        rule = self.RULES[lottery_type]

        main_numbers = self._extract_numbers_after_label(block, "本数字", expected_count=rule.pick_count)
        bonus_numbers = self._extract_numbers_after_label(block, "ボーナス数字", expected_count=rule.bonus_count)

        if main_numbers is None or bonus_numbers is None:
            return None

        if lottery_type == "loto6":
            result = Loto6Result(
                draw_number=draw_no,
                draw_date=draw_date,
                numbers=main_numbers,
                bonus=bonus_numbers[0],
                source_url=source_url,
            )
        else:
            result = Loto7Result(
                draw_number=draw_no,
                draw_date=draw_date,
                numbers=main_numbers,
                bonus1=bonus_numbers[0],
                bonus2=bonus_numbers[1],
                source_url=source_url,
            )

        result.validate()
        return result

    def _extract_numbers_after_label(self, text: str, label: str, expected_count: int) -> list[int] | None:
        pattern = rf"{label}(.*?)(?:1等|2等|キャリーオーバー|第0*\d+回|$)"
        match = re.search(pattern, text, flags=re.DOTALL)
        if not match:
            return None

        candidate_text = match.group(1)
        numbers = [int(num) for num in re.findall(r"\d+", candidate_text)]

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

    def _normalize_lottery_type(self, lottery_type: str) -> str:
        normalized = str(lottery_type).strip().lower()
        if normalized not in {"loto6", "loto7"}:
            raise ValueError(f"unsupported lottery_type: {lottery_type}")
        return normalized
