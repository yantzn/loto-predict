"""Expected value helper for backtest output.

backtestで得た等級別件数を、drawごとの賞金テーブルへ当ててEV/ROI proxyを計算します。
あくまで過去データ上の参考評価であり、将来の当選期待を保証しません。
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import asdict

from src.evaluation.prize_tables import PrizeTable, payout_for_prize_label


def compute_expected_value(summary: Mapping[str, int], prize_table: PrizeTable) -> dict[str, float]:
    if prize_table is None:
        raise ValueError("prize_table is required")

    total_tickets = sum(summary.get(prize, 0) for prize in summary)
    total_payout = 0
    for prize_label, count in summary.items():
        payout = payout_for_prize_label(prize_label, prize_table)
        total_payout += payout * count

    ticket_count = total_tickets if total_tickets > 0 else 1
    expected_value_per_ticket = total_payout / ticket_count
    roi_proxy = expected_value_per_ticket / prize_table.ticket_cost

    return {
        "expected_value_sum": float(total_payout),
        "expected_value_per_ticket": round(expected_value_per_ticket, 2),
        "roi_proxy": round(roi_proxy, 4),
        "prize_table_version": "old" if prize_table.first == 600_000_000 else "new",
    }
