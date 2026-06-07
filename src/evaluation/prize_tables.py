"""Prize table definitions used by backtests.

ロト7の過去検証でexpected valueを概算するための賞金テーブルを提供します。
実際の当選金は回ごとに変わるため、評価補助の近似値として扱います。
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class PrizeTable:
    first: int
    second: int
    third: int
    fourth: int
    fifth: int
    sixth: int
    ticket_cost: int = 300


def prize_table_for_draw(lottery_type: str, draw_id: int) -> PrizeTable:
    normalized = str(lottery_type).strip().lower()
    if normalized != "loto7":
        raise ValueError(f"unsupported lottery_type for prize table: {lottery_type}")

    if draw_id <= 612:
        return PrizeTable(
            first=600_000_000,
            second=7_300_000,
            third=730_000,
            fourth=9_100,
            fifth=1_400,
            sixth=1_000,
        )

    return PrizeTable(
        first=700_000_000,
        second=6_100_000,
        third=500_000,
        fourth=6_500,
        fifth=1_400,
        sixth=1_000,
    )


def payout_for_prize_label(prize_label: str, prize_table: PrizeTable) -> int:
    mapping = {
        "1等相当": prize_table.first,
        "2等相当": prize_table.second,
        "3等相当": prize_table.third,
        "4等相当": prize_table.fourth,
        "5等相当": prize_table.fifth,
        "6等相当": prize_table.sixth,
        "該当なし": 0,
    }
    if prize_label not in mapping:
        raise ValueError(f"unsupported prize label: {prize_label}")
    return mapping[prize_label]
