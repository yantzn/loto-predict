from dataclasses import dataclass
from typing import List, Optional


@dataclass
class Loto6Result:
    """
    ロト6抽選結果のドメインモデル。
    - draw_number: 抽選回
    - draw_date: 日付(YYYY-MM-DD)
    - numbers: 本数字6個
    - bonus: ボーナス数字
    """
    draw_number: int
    draw_date: str
    numbers: List[int]
    bonus: int


@dataclass
class Loto7Result:
    """
    ロト7抽選結果のドメインモデル。
    - draw_number: 抽選回
    - draw_date: 日付(YYYY-MM-DD)
    - numbers: 本数字7個
    - bonus1, bonus2: ボーナス数字
    """
    draw_number: int
    draw_date: str
    numbers: List[int]
    bonus1: int
    bonus2: int


@dataclass
class Prediction:
    """
    予想番号のドメインモデル。
    - lottery_type: 'loto6' or 'loto7'
    - draw_number: 抽選回
    - numbers: 予想番号リスト
    - created_at: 生成日時
    """
    lottery_type: str
    draw_number: int
    numbers: List[int]
    created_at: str


@dataclass
class PredictionRun:
    """
    予想実行記録のドメインモデル。
    - lottery_type: 'loto6' or 'loto7'
    - draw_number: 抽選回
    - predictions: 予想リスト
    - created_at: 実行日時
    """
    lottery_type: str
    draw_number: int
    predictions: List[Prediction]
    created_at: str
