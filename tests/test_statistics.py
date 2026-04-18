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
