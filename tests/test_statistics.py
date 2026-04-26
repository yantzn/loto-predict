from src.domain.statistics import calculate_number_scores


def test_calculate_number_scores_counts_frequency_with_recency_bonus() -> None:
    draws = [
        [1, 2, 3, 4, 5, 6],
        [1, 3, 5, 7, 9, 11],
        [2, 3, 5, 8, 13, 21],
    ]

    score_map = dict(calculate_number_scores(draws))

    # 出現頻度3回の番号は、1回しか出ていない番号より高スコアになる。
    assert score_map[3] > score_map[21]
    assert score_map[5] > score_map[21]

    # 同頻度なら、より最近に出た番号のスコアが高くなる。
    # 7 と 21 はともに1回だが、7はより新しい回(index=1)で出ている。
    assert score_map[7] > score_map[21]


def test_calculate_number_scores_returns_empty_for_empty_input() -> None:
    assert calculate_number_scores([]) == []


def test_calculate_number_scores_ignores_invalid_values() -> None:
    draws = [
        [1, 2, "3", None, -4],
        [2, "x", 5],
        "invalid-row",
    ]

    score_map = dict(calculate_number_scores(draws))

    assert 1 in score_map
    assert 2 in score_map
    assert 3 in score_map
    assert 5 in score_map
    assert score_map[2] > score_map[1]
    assert -4 not in score_map
