

import logging
import re
import traceback
from typing import List
import requests
from bs4 import BeautifulSoup
from src.domain.models import Loto6Result, Loto7Result

logger = logging.getLogger(__name__)

class RakutenLotoClient:
    """
    楽天ロト公式サイトから最新のロト6/ロト7抽選結果を取得するクライアント。
    - 本数字/ボーナス分離・範囲/重複チェック・詳細ログ
    """
    LOTO_URLS = {
        "loto6": "https://www.rakuten-bank.co.jp/event/loto6/winning-numbers/",
        "loto7": "https://www.rakuten-bank.co.jp/event/loto7/winning-numbers/",
    }

    def fetch_latest_result(self, lottery_type: str) -> Loto6Result | Loto7Result:
        url = self.LOTO_URLS.get(lottery_type.lower())
        if not url:
            raise ValueError(f"unsupported lottery_type: {lottery_type}")
        try:
            html = self._fetch_html(url)
            result = self._parse_html(lottery_type, html, url)
            logger.info(f"[RakutenLotoClient] 取得成功: type={lottery_type} no={result.draw_number} date={result.draw_date}")
            return result
        except Exception as e:
            logger.error(f"[RakutenLotoClient] パース失敗: type={lottery_type} url={url} error={e}\n{traceback.format_exc()}")
            raise

    def _fetch_html(self, url: str) -> str:
        resp = requests.get(url, timeout=10)
        resp.raise_for_status()
        return resp.text

    def _parse_html(self, lottery_type: str, html: str, url: str) -> Loto6Result | Loto7Result:
        soup = BeautifulSoup(html, "html.parser")
        table = soup.find("table", class_=re.compile(r"tbl-winning-numbers"))
        if not table:
            raise ValueError("抽選結果テーブルが見つかりません")
        rows = table.find_all("tr")
        if len(rows) < 2:
            raise ValueError("抽選結果行が不足しています")
        cells = rows[1].find_all("td")
        if lottery_type == "loto6":
            draw_number = int(cells[0].text.strip())
            draw_date = cells[1].text.strip()
            numbers = [int(c.text.strip()) for c in cells[2:8]]
            bonus = int(cells[8].text.strip())
            self._validate(numbers + [bonus], "loto6")
            return Loto6Result(draw_number=draw_number, draw_date=draw_date, numbers=numbers, bonus=bonus)
        elif lottery_type == "loto7":
            draw_number = int(cells[0].text.strip())
            draw_date = cells[1].text.strip()
            numbers = [int(c.text.strip()) for c in cells[2:9]]
            bonus1 = int(cells[9].text.strip())
            bonus2 = int(cells[10].text.strip())
            self._validate(numbers + [bonus1, bonus2], "loto7")
            return Loto7Result(draw_number=draw_number, draw_date=draw_date, numbers=numbers, bonus1=bonus1, bonus2=bonus2)
        else:
            raise ValueError(f"unsupported lottery_type: {lottery_type}")

    def _validate(self, numbers: list[int], lottery_type: str) -> None:
        if lottery_type == "loto6":
            if len(numbers) != 7 or not all(1 <= n <= 43 for n in numbers):
                raise ValueError("LOTO6: 数字範囲不正")
        elif lottery_type == "loto7":
            if len(numbers) != 9 or not all(1 <= n <= 37 for n in numbers):
                raise ValueError("LOTO7: 数字範囲不正")
        if len(set(numbers)) != len(numbers):
            raise ValueError("重複数字あり")

class RakutenLotoClient:
    """
    楽天ロト公式サイトから最新のロト6/ロト7抽選結果を取得するクライアント。
    HTML取得とパースを分離し、バリデーション・詳細ログ付きで堅牢化。
    """
    LOTO_URLS = {
        "loto6": "https://www.rakuten-bank.co.jp/event/loto6/winning-numbers/",
        "loto7": "https://www.rakuten-bank.co.jp/event/loto7/winning-numbers/",
    }

    def fetch_latest_result(self, lottery_type: str) -> Loto6Result | Loto7Result:
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

    def _parse_html(self, lottery_type: str, html: str, url: str) -> Loto6Result | Loto7Result:
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
