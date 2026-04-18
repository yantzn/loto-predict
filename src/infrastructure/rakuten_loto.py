
from __future__ import annotations
import logging
import re
from dataclasses import dataclass
from datetime import datetime
from typing import List
import requests
from bs4 import BeautifulSoup

logger = logging.getLogger(__name__)

@dataclass(frozen=True)
class LotoResult:
    """
    ロト抽選結果のドメインモデル。
    """
    lottery_type: str  # 'loto6' or 'loto7'
    draw_no: int
    draw_date: str  # YYYY-MM-DD
    main_numbers: List[int]
    bonus_numbers: List[int]
    source_url: str

    def validate(self) -> None:
        """
        結果データの妥当性検証。件数・範囲・重複・日付・回号を厳密にチェック。
        """
        if self.lottery_type == "loto6":
            if len(self.main_numbers) != 6 or len(self.bonus_numbers) != 1:
                raise ValueError(f"LOTO6: main={self.main_numbers}, bonus={self.bonus_numbers}")
            if not all(1 <= n <= 43 for n in self.main_numbers + self.bonus_numbers):
                raise ValueError(f"LOTO6: 数字範囲不正: {self.main_numbers}, {self.bonus_numbers}")
        elif self.lottery_type == "loto7":
            if len(self.main_numbers) != 7 or len(self.bonus_numbers) != 2:
                raise ValueError(f"LOTO7: main={self.main_numbers}, bonus={self.bonus_numbers}")
            if not all(1 <= n <= 37 for n in self.main_numbers + self.bonus_numbers):
                raise ValueError(f"LOTO7: 数字範囲不正: {self.main_numbers}, {self.bonus_numbers}")
        else:
            raise ValueError(f"unsupported lottery_type: {self.lottery_type}")
        if len(set(self.main_numbers + self.bonus_numbers)) != len(self.main_numbers + self.bonus_numbers):
            raise ValueError(f"重複数字あり: {self.main_numbers}, {self.bonus_numbers}")
        if not self.draw_no or not self.draw_date:
            raise ValueError(f"draw_no/draw_dateが取得できていない: {self}")

class RakutenLotoClient:
    """
    楽天ロト公式サイトから最新のロト6/ロト7抽選結果を取得するクライアント。
    HTML取得とパースを分離し、バリデーション・詳細ログ付きで堅牢化。
    """
    LOTO_URLS = {
        "loto6": "https://www.rakuten-bank.co.jp/event/loto6/winning-numbers/",
        "loto7": "https://www.rakuten-bank.co.jp/event/loto7/winning-numbers/",
    }

    def fetch_latest_result(self, lottery_type: str) -> LotoResult:
        """
        指定ロト種別の最新抽選結果を取得。
        Args:
            lottery_type (str): 'loto6' or 'loto7'
        Returns:
            LotoResult: 取得結果
        Raises:
            Exception: パース失敗時
        """
        url = self.LOTO_URLS.get(lottery_type.lower())
        if not url:
            raise ValueError(f"unsupported lottery_type: {lottery_type}")
        try:
            html = self._fetch_html(url)
            result = self._parse_html(lottery_type, html, url)
            result.validate()
            return result
        except Exception as e:
            logger.error(f"[RakutenLotoClient] パース失敗: type={lottery_type} url={url} error={e}")
            raise

    def _fetch_html(self, url: str) -> str:
        resp = requests.get(url, timeout=10)
        resp.raise_for_status()
        return resp.text

    def _parse_html(self, lottery_type: str, html: str, url: str) -> LotoResult:
        """
        HTMLから抽選結果を厳密にパースする。
        - 本数字/ボーナス数字のラベルや表構造を優先利用
        - 失敗時は例外
        """
        soup = BeautifulSoup(html, "html.parser")
        # 最新回のテーブルを特定
        table = soup.find("table", class_=re.compile(r"tbl-winning-numbers"))
        if not table:
            raise ValueError("抽選結果テーブルが見つかりません")
        rows = table.find_all("tr")
        # 1行目: ヘッダ, 2行目: 最新回
        if len(rows) < 2:
            raise ValueError("抽選結果行が不足しています")
        cells = rows[1].find_all("td")
        if lottery_type == "loto6":
            # [回号, 日付, 本数字6, ボーナス1, ...]
            draw_no = int(cells[0].text.strip())
            draw_date = cells[1].text.strip()
            main_numbers = [int(c.text.strip()) for c in cells[2:8]]
            bonus_numbers = [int(cells[8].text.strip())]
        elif lottery_type == "loto7":
            # [回号, 日付, 本数字7, ボーナス2, ...]
            draw_no = int(cells[0].text.strip())
            draw_date = cells[1].text.strip()
            main_numbers = [int(c.text.strip()) for c in cells[2:9]]
            bonus_numbers = [int(cells[9].text.strip()), int(cells[10].text.strip())]
        else:
            raise ValueError(f"unsupported lottery_type: {lottery_type}")
        return LotoResult(
            lottery_type=lottery_type,
            draw_no=draw_no,
            draw_date=draw_date,
            main_numbers=main_numbers,
            bonus_numbers=bonus_numbers,
            source_url=url,
        )
