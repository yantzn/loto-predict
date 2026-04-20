from src.domain.statistics import calculate_number_scores


def test_calculate_number_scores_counts_frequency() -> None:
    draws = [
        [1, 2, 3, 4, 5, 6],
        [1, 3, 5, 7, 9, 11],
        [2, 3, 5, 8, 13, 21],
    ]

    score_map = dict(calculate_number_scores(draws))

    assert score_map[1] == 2.0
    assert score_map[2] == 2.0
    assert score_map[3] == 3.0
    assert score_map[5] == 3.0
    assert score_map[21] == 1.0


def test_calculate_number_scores_returns_empty_for_empty_input() -> None:
    assert calculate_number_scores([]) == []


def test_calculate_number_scores_ignores_invalid_values() -> None:
    draws = [
        [1, 2, "3", None, -4],
        [2, "x", 5],
        "invalid-row",
    ]

    score_map = dict(calculate_number_scores(draws))

    assert score_map[1] == 1.0
    assert score_map[2] == 2.0
    assert score_map[3] == 1.0
    assert score_map[5] == 1.0
    assert -4 not in score_map
