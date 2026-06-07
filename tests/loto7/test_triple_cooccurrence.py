"""Tests for triple co-occurrence scoring.

triple supportの集計、support不足時のfallback、triple_weightedのseed差異を確認します。
"""

from src.domain.scorers.triple_cooccurrence import (
    TripletConfig,
    TripletStats,
    TripletCooccurrenceScorer,
    build_triplet_stats,
)
from contextlib import redirect_stdout
from io import StringIO

from src.domain.strategies.triple_weighted import (
    TripleWeightedConfig,
    build_triple_weighted_scores,
    rank_triple_weighted_candidates,
)
from jobs.backtest_loto_prediction.main import _print_triplet_holdout_summary


def test_build_triplet_stats_keeps_top_n() -> None:
    history = [
        [1, 2, 3, 4, 5, 6, 7],
        [1, 2, 3, 8, 9, 10, 11],
        [1, 2, 4, 8, 9, 10, 11],
    ]
    stats = build_triplet_stats(history, max_number=11, top_n=2, shrink_k=1.0)

    assert isinstance(stats, TripletStats)
    assert len(stats.triplet_counts) == 2
    assert stats.draw_count == 3.0
    assert stats.marginal_counts[1] > 0
    assert stats.marginal_counts[11] > 0


def test_triple_cooccurrence_scorer_prefers_frequent_triplets() -> None:
    history = [
        [1, 2, 3, 4, 5, 6, 7],
        [1, 2, 3, 8, 9, 10, 11],
        [1, 2, 4, 8, 9, 10, 11],
    ]
    scorer = TripletCooccurrenceScorer(
        TripletConfig(top_n=20, shrink_k=1.0, triplet_weight=1.0, laplace=1.0)
    )
    number_scores = scorer.score_numbers(history)
    score_123 = scorer.score_ticket([1, 2, 3, 12, 13, 14, 15])
    score_456 = scorer.score_ticket([4, 5, 6, 12, 13, 14, 15])

    assert score_123 > score_456
    assert score_123 >= 0.0
    assert score_456 >= 0.0


def test_print_triplet_holdout_summary_outputs_recommendation() -> None:
    comparisons = [
        {
            "pair_expected_value_per_ticket": 0.02,
            "triple_expected_value_per_ticket": 0.03,
        },
        {
            "pair_expected_value_per_ticket": 0.01,
            "triple_expected_value_per_ticket": 0.015,
        },
    ]
    buffer = StringIO()

    with redirect_stdout(buffer):
        _print_triplet_holdout_summary(comparisons)

    output = buffer.getvalue()
    assert "TRIPLET HOLDOUT SUMMARY" in output
    assert "Recommendation:" in output


def test_rank_triple_weighted_candidates_generates_unique_tickets() -> None:
    history = [
        [1, 2, 3, 4, 5, 6, 7],
        [1, 2, 3, 8, 9, 10, 11],
        [1, 2, 4, 8, 9, 10, 11],
    ]
    config = TripleWeightedConfig(top_n=20, shrink_k=1.0, triplet_weight=1.0, top_pool_size=10)
    predictions = rank_triple_weighted_candidates(history=history, prediction_count=3, seed=1, config=config)

    assert len(predictions) == 3
    assert len({tuple(ticket) for ticket in predictions}) == 3
    for ticket in predictions:
        assert len(ticket) == 7
        assert sorted(ticket) == ticket


def test_triple_weighted_falls_back_when_triple_support_sparse() -> None:
    history = [
        [1, 2, 3, 4, 5, 6, 7],
        [8, 9, 10, 11, 12, 13, 14],
    ]
    config = TripleWeightedConfig(min_triple_support=2.0)

    rows = build_triple_weighted_scores(
        history=history,
        selected=[1, 2],
        config=config,
    )

    assert rows[8]["fallback_used"] is True
    assert rows[8]["triple_support"] < 2.0
