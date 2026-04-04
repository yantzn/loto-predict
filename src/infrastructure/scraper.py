from __future__ import annotations

import re
from datetime import datetime

import requests

from loto_predict.domain.models import LotoResult
from loto_predict.utils.exceptions import ScrapingError
from loto_predict.utils.validators import validate_numbers


class LotoScraper:
    URLS = {
        "loto6": "https://www.mizuhobank.co.jp/takarakuji/check/loto/loto6/index.html",
        "loto7": "https://www.mizuhobank.co.jp/takarakuji/check/loto/loto7/index.html",
    }

    def fetch_latest_result(self, lottery_type: str) -> LotoResult:
        url = self.URLS[lottery_type]
        response = requests.get(url, timeout=30)
        response.raise_for_status()
        html = response.text

        draw_number = self._extract_draw_number(html)
        draw_date = self._extract_draw_date(html)

        if lottery_type == "loto6":
            main_numbers = self._extract_first_n_numbers(html, 6)
            bonus_numbers = self._extract_bonus_numbers(html, expected=1)
        else:
            main_numbers = self._extract_first_n_numbers(html, 7)
            bonus_numbers = self._extract_bonus_numbers(html, expected=2)

        validate_numbers(lottery_type, main_numbers, bonus_numbers)

        return LotoResult(
            lottery_type=lottery_type,
            draw_date=draw_date,
            draw_number=draw_number,
            numbers=main_numbers,
            bonus_numbers=bonus_numbers,
            source="scraping",
        )

    def _extract_draw_number(self, html: str) -> int:
        patterns = [
            r"第\s*(\d+)\s*回",
            r"(\d+)\s*回",
        ]
        for pattern in patterns:
            m = re.search(pattern, html)
            if m:
                return int(m.group(1))
        raise ScrapingError("draw number not found")

    def _extract_draw_date(self, html: str):
        patterns = [
            r"(\d{4})年(\d{1,2})月(\d{1,2})日",
            r"(\d{4})/(\d{1,2})/(\d{1,2})",
        ]
        for pattern in patterns:
            m = re.search(pattern, html)
            if m:
                y, mo, d = map(int, m.groups())
                return datetime(y, mo, d).date()
        raise ScrapingError("draw date not found")

    def _extract_first_n_numbers(self, html: str, n: int) -> list[int]:
        numbers = [int(x) for x in re.findall(r">\s*(\d{1,2})\s*<", html)]
        unique: list[int] = []
        for num in numbers:
            if num not in unique:
                unique.append(num)
            if len(unique) >= n:
                return sorted(unique[:n])
        raise ScrapingError("main numbers not found")

    def _extract_bonus_numbers(self, html: str, expected: int) -> list[int]:
        numbers = [int(x) for x in re.findall(r">\s*(\d{1,2})\s*<", html)]
        if len(numbers) < expected + 6:
            raise ScrapingError("bonus numbers not found")
        tail = []
        for num in numbers[::-1]:
            if num not in tail:
                tail.append(num)
            if len(tail) >= expected:
                break
        return sorted(tail[::-1])
