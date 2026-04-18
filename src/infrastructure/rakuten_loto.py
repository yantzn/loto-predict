from __future__ import annotations

import logging
import re
from datetime import datetime
from typing import Iterable

import requests
from bs4 import BeautifulSoup, Tag

from src.domain.loto_result import LotoResult

logger = logging.getLogger(__name__)


class RakutenLotoClient:
    """
    楽天銀行の当せん番号ページから最新結果を取得する。
    取得・抽出・変換を分け、最低限の妥当性検証を必ず通す。
    """

    LOTO_URLS = {
        "loto6": "https://www.rakuten-bank.co.jp/event/loto6/winning-numbers/",
        "loto7": "https://www.rakuten-bank.co.jp/event/loto7/winning-numbers/",
    }

    def __init__(self, timeout: int = 10) -> None:
        self.timeout = timeout

    def fetch_latest_result(self, lottery_type: str) -> LotoResult:
        normalized = str(lottery_type).strip().lower()
        url = self.LOTO_URLS.get(normalized)
        if not url:
            raise ValueError(f"unsupported lottery_type: {lottery_type}")

        html = self._fetch_html(url)
        result = self._parse_latest_result(normalized, html, url)
        result.validate()
        return result

    def _fetch_html(self, url: str) -> str:
        response = requests.get(url, timeout=self.timeout)
        response.raise_for_status()
        return response.text

    def _parse_latest_result(self, lottery_type: str, html: str, url: str) -> LotoResult:
        soup = BeautifulSoup(html, "html.parser")
        table = soup.find("table")
        if table is None:
            raise ValueError("winning number table not found")

        row = self._find_first_data_row(table)
        if row is None:
            raise ValueError("no data row found in winning number table")

        cells = [self._clean_text(td) for td in row.find_all(["td", "th"])]
        numbers = self._extract_numbers(cells)

        if lottery_type == "loto6":
            minimum_cells = 9
            main_count = 6
            bonus_count = 1
        else:
            minimum_cells = 11
            main_count = 7
            bonus_count = 2

        if len(cells) < minimum_cells:
            raise ValueError(f"table row is too short for {lottery_type}: cells={cells}")

        draw_no = self._parse_draw_no(cells[0])
        draw_date = self._parse_draw_date(cells[1])

        expected_total = main_count + bonus_count
        if len(numbers) < expected_total:
            raise ValueError(
                f"insufficient numbers extracted for {lottery_type}: numbers={numbers}"
            )

        main_numbers = numbers[:main_count]
        bonus_numbers = numbers[main_count:expected_total]

        try:
            return LotoResult.from_values(
                lottery_type=lottery_type,
                draw_no=draw_no,
                draw_date=draw_date,
                main_numbers=main_numbers,
                bonus_numbers=bonus_numbers,
                source_url=url,
            )
        except Exception as exc:
            logger.error(
                "rakuten parse validation failed. lottery_type=%s url=%s draw_no=%s error=%s",
                lottery_type,
                url,
                draw_no,
                exc,
            )
            raise

    @staticmethod
    def _find_first_data_row(table: Tag) -> Tag | None:
        rows = table.find_all("tr")
        for row in rows:
            cells = row.find_all("td")
            if cells:
                return row
        return None

    @staticmethod
    def _clean_text(tag: Tag) -> str:
        return " ".join(tag.get_text(" ", strip=True).split())

    @staticmethod
    def _extract_numbers(cells: Iterable[str]) -> list[int]:
        values: list[int] = []
        for cell in cells[2:]:
            matches = re.findall(r"\d+", cell)
            for match in matches:
                values.append(int(match))
        return values

    @staticmethod
    def _parse_draw_no(text: str) -> int:
        match = re.search(r"\d+", text)
        if not match:
            raise ValueError(f"draw_no not found: {text}")
        return int(match.group())

    @staticmethod
    def _parse_draw_date(text: str):
        normalized = text.replace("年", "-").replace("月", "-").replace("日", "")
        normalized = normalized.replace("/", "-").strip()
        return datetime.strptime(normalized, "%Y-%m-%d").date()
