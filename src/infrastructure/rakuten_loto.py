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
    """
    ロト抽選結果のドメインモデル。
    - lottery_type: 'LOTO6' or 'LOTO7'
    - draw_no: 抽選回
    - draw_date: 日付(YYYY-MM-DD)
    - main_numbers: 本数字リスト
    - bonus_numbers: ボーナス数字リスト
    - source_url: 取得元URL
    """
    lottery_type: str  # LOTO6 / LOTO7
    draw_no: int
    draw_date: str  # YYYY-MM-DD
    main_numbers: list[int]
    bonus_numbers: list[int]
    source_url: str

    def validate(self) -> None:
        """
        結果データの妥当性検証。
        Raises:
            ValueError: 不正なデータの場合
        """
        if self.lottery_type == "LOTO6":
            if len(self.main_numbers) != 6:
                raise ValueError(f"LOTO6 main_numbers must be 6: {self.main_numbers}")
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
