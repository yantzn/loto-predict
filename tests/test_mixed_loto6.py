"""Tests for the LOTO6 mixed_loto6 strategy.

LOTO6専用profileの定義、seed再現性、5口内の重複抑制、0頻度数字の扱いを確認します。
"""

from __future__ import annotations

from src.domain.prediction import generate_predictions
from src.domain.strategies.mixed_loto6 import (
    MIXED_LOTO6_PROFILES,
    PROFILE_HISTORY_WINDOWS,
    PROFILE_SCORE_WEIGHTS,
    MixedLoto6Strategy,
    build_default_mixed_loto6_config,
)


def _history() -> list[list[int]]:
    return [
        [
            ((draw + offset * 7) % 43) + 1
            for offset in range(6)
        ]
        for draw in range(180, 0, -1)
    ]


def _number_scores() -> list[tuple[int, float]]:
    return [(number, float(44 - number)) for number in range(1, 44)]


def test_mixed_loto6_profile_definitions() -> None:
    assert MIXED_LOTO6_PROFILES == [
        "l6_hot_100_core",
        "l6_balanced_150",
        "l6_recent_50",
        "l6_gap_repair",
        "l6_diverse_explore",
    ]
    assert PROFILE_HISTORY_WINDOWS["l6_hot_100_core"]["primary"] == 100
    assert PROFILE_HISTORY_WINDOWS["l6_balanced_150"]["primary"] == 150
    assert PROFILE_HISTORY_WINDOWS["l6_recent_50"]["primary"] == 50
    assert PROFILE_HISTORY_WINDOWS["l6_diverse_explore"]["primary"] == 50


def test_mixed_loto6_profile_weights_sum_to_one() -> None:
    for weights in PROFILE_SCORE_WEIGHTS.values():
        assert abs(sum(weights.values()) - 1.0) < 0.000001


def test_mixed_loto6_keeps_zero_frequency_numbers_in_score_map() -> None:
    strategy = MixedLoto6Strategy(build_default_mixed_loto6_config())
    score_map = strategy._score_numbers(
        "l6_hot_100_core",
        [[1, 2, 3, 4, 5, 6]] * 10,
        {number: 0.0 for number in range(1, 44)},
    )

    assert set(score_map) == set(range(1, 44))
    assert all(score > 0 for score in score_map.values())


def test_mixed_loto6_same_seed_same_predictions() -> None:
    predictions1 = generate_predictions(
        number_scores=_number_scores(),
        lottery_type="loto6",
        prediction_count=5,
        strategy="mixed_loto6",
        seed=123,
        history=_history(),
        target_draw=2000,
        history_limit=100,
    )
    predictions2 = generate_predictions(
        number_scores=_number_scores(),
        lottery_type="loto6",
        prediction_count=5,
        strategy="mixed_loto6",
        seed=123,
        history=_history(),
        target_draw=2000,
        history_limit=100,
    )

    assert predictions1 == predictions2


def test_mixed_loto6_different_seed_changes_predictions() -> None:
    predictions1 = generate_predictions(
        number_scores=_number_scores(),
        lottery_type="loto6",
        prediction_count=5,
        strategy="mixed_loto6",
        seed=123,
        history=_history(),
        target_draw=2000,
        history_limit=100,
    )
    predictions2 = generate_predictions(
        number_scores=_number_scores(),
        lottery_type="loto6",
        prediction_count=5,
        strategy="mixed_loto6",
        seed=124,
        history=_history(),
        target_draw=2000,
        history_limit=100,
    )

    assert predictions1 != predictions2


def test_mixed_loto6_generates_five_unique_loto6_tickets() -> None:
    predictions = generate_predictions(
        number_scores=_number_scores(),
        lottery_type="loto6",
        prediction_count=5,
        strategy="mixed_loto6",
        seed=123,
        history=_history(),
        target_draw=2000,
        history_limit=100,
    )

    assert len(predictions) == 5
    assert len({tuple(sorted(prediction)) for prediction in predictions}) == 5
    assert all(len(prediction) == 6 for prediction in predictions)
    assert all(len(set(prediction)) == 6 for prediction in predictions)
    assert all(1 <= number <= 43 for prediction in predictions for number in prediction)
