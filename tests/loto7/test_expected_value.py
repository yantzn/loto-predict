"""Tests for expected value calculation.

backtestの等級別件数を賞金テーブルに当て、EV/ROI proxyを安定して計算できることを確認します。
"""

from src.evaluation.expected_value import compute_expected_value
from src.evaluation.prize_tables import PrizeTable


def test_compute_expected_value_uses_prize_mapping_and_ticket_cost() -> None:
    summary = {
        "1等相当": 1,
        "2等相当": 0,
        "3等相当": 2,
        "4等相当": 1,
        "5等相当": 1,
        "6等相当": 0,
        "該当なし": 1,
    }
    prize_table = PrizeTable(
        first=600_000_000,
        second=7_300_000,
        third=730_000,
        fourth=9_100,
        fifth=1_400,
        sixth=1_000,
    )

    ev = compute_expected_value(summary, prize_table)

    assert ev["expected_value_sum"] == float(600_000_000 + 2 * 730_000 + 9_100 + 1_400)
    assert ev["expected_value_per_ticket"] == round((600_000_000 + 2 * 730_000 + 9_100 + 1_400) / 6, 2)
    assert ev["roi_proxy"] == round(ev["expected_value_per_ticket"] / 300, 4)
    assert ev["prize_table_version"] == "old"


def test_compute_expected_value_handles_empty_summary() -> None:
    prize_table = PrizeTable(
        first=700_000_000,
        second=6_100_000,
        third=500_000,
        fourth=6_500,
        fifth=1_400,
        sixth=1_000,
    )

    ev = compute_expected_value({}, prize_table)

    assert ev["expected_value_sum"] == 0.0
    assert ev["expected_value_per_ticket"] == 0.0
    assert ev["roi_proxy"] == 0.0
    assert ev["prize_table_version"] == "new"
