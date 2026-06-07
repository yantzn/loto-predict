"""Tests for diverse ticket selection.

候補ticketからスコアと重複度を考慮して、似すぎない5口を選べることを確認します。
"""

from itertools import combinations

from src.domain.prediction import generate_predictions
from src.domain.selection.diversity import (
    TicketCandidate,
    jaccard_similarity,
    overlap_count,
    select_diverse_tickets,
)


def test_jaccard_similarity_computes_union_intersection() -> None:
    assert jaccard_similarity([], []) == 1.0
    assert jaccard_similarity([1, 2, 3], [4, 5, 6]) == 0.0
    assert jaccard_similarity([1, 2, 3], [3, 4, 5]) == 1 / 5


def test_overlap_count_returns_shared_numbers() -> None:
    assert overlap_count([1, 2, 3], [3, 4, 5]) == 1
    assert overlap_count([1, 2, 3], [4, 5, 6]) == 0


def test_select_diverse_tickets_prefers_dissimilar_candidates() -> None:
    candidates = [
        TicketCandidate(numbers=[1, 2, 3, 4, 5, 6, 7], score=10.0),
        TicketCandidate(numbers=[1, 2, 3, 4, 5, 6, 8], score=9.0),
        TicketCandidate(numbers=[9, 10, 11, 12, 13, 14, 15], score=8.0),
        TicketCandidate(numbers=[16, 17, 18, 19, 20, 21, 22], score=7.0),
    ]

    selected = select_diverse_tickets(
        candidates=candidates,
        prediction_count=3,
        max_overlap=4,
        min_jaccard_distance=0.4,
        diversity_weight=0.5,
    )

    assert len(selected) == 3
    assert any(8 in ticket.numbers for ticket in selected) is False
    assert all(overlap_count(selected[i].numbers, selected[j].numbers) <= 4 for i, j in combinations(range(3), 2))


def test_generate_predictions_with_selector_yields_diverse_tickets() -> None:
    number_scores = [(number, float(38 - number)) for number in range(1, 38)]

    predictions = generate_predictions(
        number_scores=number_scores,
        lottery_type="loto7",
        prediction_count=3,
        seed=123,
        strategy="default",
        selector_candidate_pool_size=12,
        selector_diversity_weight=0.5,
    )

    assert len(predictions) == 3
    assert len({tuple(prediction) for prediction in predictions}) == 3
    assert all(len(prediction) == 7 for prediction in predictions)
    assert all(overlap_count(a, b) <= 4 for a, b in combinations(predictions, 2))
    assert len({number for prediction in predictions for number in prediction}) >= 13
