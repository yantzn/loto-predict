"""Tests for prize table lookup.

backtestで使うロト7賞金テーブルの取得とfallbackが期待通りに動くことを確認します。
"""

import pytest

from src.evaluation.prize_tables import (
    PrizeTable,
    payout_for_prize_label,
    prize_table_for_draw,
)


def test_prize_table_for_draw_switches_at_613() -> None:
    old_table = prize_table_for_draw("loto7", 612)
    new_table = prize_table_for_draw("loto7", 613)

    assert old_table.first == 600_000_000
    assert old_table.second == 7_300_000
    assert old_table.third == 730_000
    assert new_table.first == 700_000_000
    assert new_table.second == 6_100_000
    assert new_table.third == 500_000


def test_payout_for_prize_label_returns_correct_amounts() -> None:
    prize_table = PrizeTable(
        first=600_000_000,
        second=7_300_000,
        third=730_000,
        fourth=9_100,
        fifth=1_400,
        sixth=1_000,
    )

    assert payout_for_prize_label("1等相当", prize_table) == 600_000_000
    assert payout_for_prize_label("2等相当", prize_table) == 7_300_000
    assert payout_for_prize_label("3等相当", prize_table) == 730_000
    assert payout_for_prize_label("4等相当", prize_table) == 9_100
    assert payout_for_prize_label("5等相当", prize_table) == 1_400
    assert payout_for_prize_label("6等相当", prize_table) == 1_000
    assert payout_for_prize_label("該当なし", prize_table) == 0

    with pytest.raises(ValueError, match="unsupported prize label"):
        payout_for_prize_label("unknown", prize_table)
