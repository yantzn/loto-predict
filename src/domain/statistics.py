from __future__ import annotations

from collections import Counter
from dataclasses import dataclass


@dataclass(frozen=True)
class ScoreWeights:
    frequency: float = 1.0
    recent: float = 2.0
    recency: float = 1.5


def calculate_number_scores(
    draws: list[list[int]],
    weights: ScoreWeights | None = None,
) -> list[tuple[int, float]]:
    """
    番号ごとの統計スコアを算出する。

    前提:
    - draws は最新順。index が小さいほど新しい抽選回。
    - 異常値、0以下、数値化できない値は無視する。
    """
    if not draws:
        return []

    score_weights = weights or ScoreWeights()

    counter: Counter[int] = Counter()
    latest_seen_index: dict[int, int] = {}
    recent_counter: Counter[int] = Counter()

    recent_window_size = max(1, int(len(draws) * 0.3))

    for draw_index, draw in enumerate(draws):
        if not isinstance(draw, list):
            continue

        for number in draw:
            try:
                parsed = int(number)
            except (TypeError, ValueError):
                continue

            if parsed <= 0:
                continue

            counter[parsed] += 1

            if parsed not in latest_seen_index:
                latest_seen_index[parsed] = draw_index

            if draw_index < recent_window_size:
                recent_counter[parsed] += 1

    if not counter:
        return []

    max_recent = max(recent_counter.values(), default=1)
    max_latest_seen_index = max(latest_seen_index.values(), default=1) or 1

    scores: list[tuple[int, float]] = []

    for number, frequency in counter.items():
        recent_ratio = recent_counter.get(number, 0) / max_recent

        latest_index = latest_seen_index.get(number, max_latest_seen_index)
        recency_ratio = 1.0 - (latest_index / max_latest_seen_index)

        score = (
            float(frequency) * score_weights.frequency
            + recent_ratio * score_weights.recent
            + recency_ratio * score_weights.recency
        )
        scores.append((number, score))

    return sorted(scores, key=lambda item: (-item[1], item[0]))


def calculate_main_number_scores(
    draws: list[list[int]],
    weights: ScoreWeights | None = None,
) -> list[tuple[int, float]]:
    """本数字 n1..n7 / n1..n6 のスコアを算出する。"""
    return calculate_number_scores(draws, weights)


def calculate_bonus_number_scores(
    bonus_draws: list[list[int]],
    weights: ScoreWeights | None = None,
) -> list[tuple[int, float]]:
    """ボーナス数字 b1,b2 / b1 のスコアを算出する。"""
    return calculate_number_scores(bonus_draws, weights)


def calculate_combined_scores(
    main_draws: list[list[int]],
    bonus_draws: list[list[int]],
    weights: ScoreWeights | None = None,
    main_weight: float = 0.8,
    bonus_weight: float = 0.2,
) -> list[tuple[int, float]]:
    """
    本数字スコアとボーナス数字スコアを合成する。

    LOTO7の2等狙いでは、基本は main_scores と bonus_scores を
    分離したまま使う。これは補助的な合成スコア用途。
    """
    if main_weight < 0 or bonus_weight < 0:
        raise ValueError("main_weight and bonus_weight must be non-negative")

    main_scores = dict(calculate_main_number_scores(main_draws, weights))
    bonus_scores = dict(calculate_bonus_number_scores(bonus_draws, weights))

    numbers = set(main_scores) | set(bonus_scores)
    combined = [
        (
            number,
            main_scores.get(number, 0.0) * main_weight
            + bonus_scores.get(number, 0.0) * bonus_weight,
        )
        for number in numbers
    ]

    return sorted(combined, key=lambda item: (-item[1], item[0]))
