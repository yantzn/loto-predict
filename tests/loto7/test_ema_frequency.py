"""Tests for EMA frequency scoring.

直近傾向をEMAでスコア化する処理と、ema_recency strategyの基本挙動を確認します。
"""

import pytest

from src.domain.prediction import generate_predictions
from src.domain.scorers.ema_frequency import (
    EmaFrequencyScorer,
    blend_scores,
    compute_ema_presence,
    compute_last_seen_gap,
)
from src.domain.strategies.ema_recency import EmaRecencyConfig


def test_compute_ema_presence_applies_exponential_decay() -> None:
    draws = [[1, 2], [2, 3], [1, 4]]
    presence = compute_ema_presence(draws, max_number=5, alpha=0.5)

    assert presence[1] > presence[4]
    assert presence[4] > presence[3]
    assert presence[5] == 0.0


def test_compute_last_seen_gap_returns_most_recent_index() -> None:
    draws = [[1, 2], [2, 3], [1, 4]]
    gap = compute_last_seen_gap(draws, max_number=5)

    assert gap[1] == 0
    assert gap[2] == 0
    assert gap[3] == 1
    assert gap[5] == 3


def test_blend_scores_combines_weighted_maps() -> None:
    score_maps = [
        {1: 1.0, 2: 0.0},
        {1: 0.0, 2: 1.0},
    ]
    blended = blend_scores(score_maps, [0.5, 0.5])

    assert blended[1] == 0.5
    assert blended[2] == 0.5


def test_ema_frequency_scorer_returns_scores_for_all_numbers() -> None:
    history = [[1, 2, 3], [2, 3, 4], [3, 4, 5]]
    scorer = EmaFrequencyScorer()
    number_scores = scorer.score_numbers(history)

    assert set(number_scores.keys()) == set(range(1, 38))
    assert number_scores[3] > number_scores[5]
    assert 0.0 <= number_scores[1] <= 1.0


def test_generate_predictions_ema_recency_requires_history() -> None:
    with pytest.raises(ValueError, match="history is required for ema_recency"):
        generate_predictions(
            number_scores=[(i, 1.0) for i in range(1, 38)],
            lottery_type="loto7",
            prediction_count=1,
            strategy="ema_recency",
            seed=1,
        )
