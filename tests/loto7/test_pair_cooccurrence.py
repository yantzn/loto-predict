"""Tests for pair co-occurrence scoring.

pair supportの正規化、疎な履歴でのfallback、pair_weighted strategyの基本挙動を確認します。
"""

import pytest
from pathlib import Path
from src.domain.scorers.pair_cooccurrence import (
    PairConfig,
    PairCooccurrenceScorer,
    build_pair_stats,
    compute_pair_lift,
)
from src.domain.strategies.pair_weighted import rank_pair_weighted_candidates


def test_build_pair_stats_counts_pairs_and_marginals() -> None:
    draws = [[1, 2, 3], [1, 3, 4]]
    stats = build_pair_stats(draws, max_number=5, decay=None, laplace=1.0)

    assert stats.draw_count == 2.0
    assert stats.marginal_counts[1] == 2.0
    assert stats.marginal_counts[2] == 1.0
    assert stats.marginal_counts[3] == 2.0
    assert stats.pair_counts[(1, 3)] == 2.0
    assert stats.pair_counts[(1, 2)] == 1.0
    assert stats.pair_counts[(3, 4)] == 1.0


def test_compute_pair_lift_returns_expected_value() -> None:
    lift = compute_pair_lift(pair_count=2.0, draw_count=10.0, marginal_i=3.0, marginal_j=4.0)
    assert pytest.approx(lift, rel=1e-6) == (0.2 / ((0.3) * (0.4)))


def test_pair_cooccurrence_scorer_scores_ticket_with_pair_lift() -> None:
    history = [[1, 2, 3], [1, 3, 4], [2, 3, 5]]
    config = PairConfig(pair_weight=1.0, laplace=1.0, shrink_k=1.0, decay=None, top_pool_size=10)
    scorer = PairCooccurrenceScorer(config)
    number_scores = scorer.score_numbers(history)

    ticket = [1, 3, 5, 6, 7, 8, 9]
    score = scorer.score_ticket(ticket, number_scores)

    assert score > sum(number_scores.get(n, 0.0) for n in ticket)
    assert isinstance(score, float)


def test_rank_pair_weighted_candidates_returns_unique_tickets() -> None:
    history = [list(range(1, 8)), list(range(2, 9)), list(range(3, 10))]
    config = PairConfig(pair_weight=1.0, laplace=1.0, shrink_k=1.0, decay=None, top_pool_size=12)

    predictions = rank_pair_weighted_candidates(
        history=history,
        prediction_count=3,
        seed=42,
        config=config,
    )

    assert len(predictions) == 3
    assert all(len(ticket) == 7 for ticket in predictions)
    assert len({tuple(ticket) for ticket in predictions}) == 3
    assert all(sorted(ticket) == ticket for ticket in predictions)


def test_pair_weighted_strategy_requires_history() -> None:
    from src.domain.prediction import generate_predictions

    with pytest.raises(ValueError, match="history is required for pair_weighted"):
        generate_predictions(
            number_scores=[(1, 1.0), (2, 0.5)],
            lottery_type="loto7",
            prediction_count=1,
            strategy="pair_weighted",
            seed=1,
        )
