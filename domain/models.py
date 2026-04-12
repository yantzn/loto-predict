from __future__ import annotations


from dataclasses import dataclass, field
from datetime import date, datetime
from enum import Enum
from typing import Any


#
# ロト種別（LOTO6/LOTO7）を表すEnum
#
class LotteryType(str, Enum):
    LOTO6 = "LOTO6"
    LOTO7 = "LOTO7"


#
# 1回分の抽選履歴（番号のみ、日付等は持たない）
#
@dataclass(frozen=True)
class DrawHistory:
    draw_no: int  # 抽選回番号
    main_numbers: list[int]  # 本数字
    bonus_numbers: list[int] = field(default_factory=list)  # ボーナス数字（任意）


#
# 1回分の抽選結果（種別・日付・出典情報なども含む）
#
@dataclass(frozen=True)
class DrawResult:
    lottery_type: LotteryType  # ロト種別
    draw_no: int  # 抽選回番号
    draw_date: date | str  # 抽選日
    main_numbers: list[int]  # 本数字
    bonus_numbers: list[int]  # ボーナス数字
    source_type: str  # データ取得元種別
    source_reference: str | None = None  # データ取得元の参照情報
    fetched_at: datetime | str | None = None  # 取得日時
    created_at: datetime | str | None = None  # レコード作成日時
    updated_at: datetime | str | None = None  # レコード更新日時


#
# 予想番号1口分（ロト種別＋番号）
#
@dataclass(frozen=True)
class PredictionTicket:
    lottery_type: LotteryType  # ロト種別
    numbers: tuple[int, ...]  # 予想番号（タプル）

    def as_list(self) -> list[int]:
        """
        番号をリスト型で返す（外部API等でリスト形式が必要な場合に利用）
        """
        return list(self.numbers)


#
# 通知用の予想番号（ランク付き）
#
@dataclass(frozen=True)
class NotificationTicket:
    rank: int  # 通知時の順位（1位,2位...）
    numbers: tuple[int, ...]  # 番号


#
# 予想通知データ（ロト種別・回号・通知用チケット群）
#
@dataclass(frozen=True)
class PredictionNotification:
    lottery_type: LotteryType  # ロト種別
    draw_no: int | None  # 抽選回番号（未確定時はNone）
    tickets: tuple[NotificationTicket, ...]  # 通知用チケット（順位付き）


#
# 予想生成処理の実行記録
#
@dataclass(frozen=True)
class PredictionRunRecord:
    lottery_type: LotteryType  # ロト種別
    draw_no: int | None  # 抽選回番号
    stats_target_draws: int  # 直近何回分を統計対象にしたか
    score_snapshot: dict[int, float]  # 番号ごとのスコアスナップショット
    generated_predictions: list[list[int]]  # 生成した予想番号リスト
    created_at: datetime  # 生成日時


#
# モジュール外部に公開するシンボル一覧
#
__all__ = [
    "LotteryType",
    "DrawHistory",
    "DrawResult",
    "PredictionTicket",
    "NotificationTicket",
    "PredictionNotification",
    "PredictionRunRecord",
]
