"""Tests for the LOTO6 mixed_v3 strategy.

LOTO6 mixed_v3のpair affinity、EMA直近傾向、5口coverage、
seed再現性を確認するためのテストです。
"""

from __future__ import annotations

from src.domain.prediction import generate_predictions
from src.domain.strategies.loto6_mixed_v3 import (
    DEFAULT_CANDIDATE_ATTEMPTS,
    TARGET_UNIQUE_MAX,
    TARGET_UNIQUE_MIN,
    _coverage_score,
    build_default_loto6_mixed_v3_config,
    ema_recency_scores,
    pair_affinity_scores,
)


def _history() -> list[list[int]]:
    base = [
        [6, 11, 19, 31, 38, 41],
        [6, 11, 19, 24, 30, 41],
        [8, 11, 19, 31, 35, 42],
        [1, 6, 19, 27, 31, 41],
    ]
    return [base[index % len(base)] for index in range(140)]


def test_loto6_mixed_v3_pair_affinity_scores_pairs() -> None:
    scores = pair_affinity_scores(_history(), 100)

    assert scores[(11, 19)] > 0
    assert scores[(6, 31)] > 0


def test_loto6_mixed_v3_default_tuning_values_are_in_operating_range() -> None:
    config = build_default_loto6_mixed_v3_config()

    assert 0.30 <= config.pair_affinity_weight <= 0.34
    assert 4 <= config.candidate_attempts <= 8
    assert config.candidate_attempts == DEFAULT_CANDIDATE_ATTEMPTS
    assert config.coverage_weight > 0.22


def test_loto6_mixed_v3_ema_scores_available_with_short_history() -> None:
    scores = ema_recency_scores(_history()[:8])

    assert set(scores) == set(range(1, 44))
    assert all(0.0 <= score <= 1.0 for score in scores.values())


def test_loto6_mixed_v3_coverage_rewards_target_band_and_softens_over_spread() -> None:
    usage_under_target = {number: 0 for number in range(1, 44)}
    for number in range(1, TARGET_UNIQUE_MIN - 3):
        usage_under_target[number] = 1

    usage_over_target = {number: 0 for number in range(1, 44)}
    for number in range(1, TARGET_UNIQUE_MAX + 1):
        usage_over_target[number] = 1

    ticket = [38, 39, 40, 41, 42, 43]

    assert _coverage_score(ticket, usage_under_target) > _coverage_score(ticket, usage_over_target)


def test_loto6_mixed_v3_generates_reproducible_diverse_tickets() -> None:
    kwargs = {
        "number_scores": [(number, 1.0) for number in range(1, 44)],
        "lottery_type": "loto6",
        "prediction_count": 5,
        "strategy": "mixed_v3",
        "seed": 2109,
        "history": _history(),
        "target_draw": 2110,
        "history_limit": 100,
    }

    predictions1 = generate_predictions(**kwargs)
    predictions2 = generate_predictions(**kwargs)

    assert predictions1 == predictions2
    assert len(predictions1) == 5
    assert len({tuple(sorted(prediction)) for prediction in predictions1}) == 5
    assert all(len(prediction) == 6 for prediction in predictions1)
    assert len({number for prediction in predictions1 for number in prediction}) >= 20


def test_loto6_mixed_v3_different_seed_changes_prediction() -> None:
    common = {
        "number_scores": [(number, 1.0) for number in range(1, 44)],
        "lottery_type": "loto6",
        "prediction_count": 5,
        "strategy": "mixed_v3",
        "history": _history(),
        "target_draw": 2110,
        "history_limit": 100,
    }

    predictions1 = generate_predictions(**common, seed=1)
    predictions2 = generate_predictions(**common, seed=2)

    assert predictions1 != predictions2
