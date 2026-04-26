from __future__ import annotations

from collections import Counter
from dataclasses import dataclass


@dataclass(frozen=True)
class ScoreWeights:
    frequency: float = 1.0
    recent: float = 2.0
    recency: float = 1.5
    absence: float = 0.8
    repeat_penalty: float = 0.4


def calculate_number_scores(
    draws: list[list[int]],
    weights: ScoreWeights | None = None,
) -> list[tuple[int, float]]:
    """
    番号ごとの統計スコアを算出する。

    前提:
    - draws は最新順
    - index=0 が最新回
    - 不正値は無視する

    スコア要素:
    - frequency: 全体出現頻度
    - recent: 直近30%での出現頻度
    - recency: 最後に出た回が近いほど加点
    - absence: 少し空いている番号を加点
    - repeat_penalty: 直近回に出た番号を少し減点
    """
    if not draws:
        return []

    score_weights = weights or ScoreWeights()

    counter: Counter[int] = Counter()
    recent_counter: Counter[int] = Counter()
    latest_seen_index: dict[int, int] = {}

    recent_window_size = max(1, int(len(draws) * 0.3))
    latest_draw_numbers = set(_normalize_draw(draws[0])) if draws else set()

    for draw_index, draw in enumerate(draws):
        numbers = _normalize_draw(draw)

        for number in numbers:
            counter[number] += 1

            if draw_index < recent_window_size:
                recent_counter[number] += 1

            if number not in latest_seen_index:
                latest_seen_index[number] = draw_index

    if not counter:
        return []

    number_min = min(counter.keys())
    number_max = max(counter.keys())

    max_frequency = max(counter.values(), default=1)
    max_recent = max(recent_counter.values(), default=1)
    max_seen_index = max(latest_seen_index.values(), default=1) or 1

    scores: list[tuple[int, float]] = []

    for number in range(number_min, number_max + 1):
        frequency = counter.get(number, 0)
        recent_frequency = recent_counter.get(number, 0)
        latest_index = latest_seen_index.get(number)

        frequency_ratio = frequency / max_frequency
        recent_ratio = recent_frequency / max_recent

        if latest_index is None:
            recency_ratio = 0.0
            absence_ratio = 1.0
        else:
            recency_ratio = 1.0 - (latest_index / max_seen_index)
            absence_ratio = min(latest_index / max_seen_index, 1.0)

        repeat_penalty = 1.0 if number in latest_draw_numbers else 0.0

        score = (
            frequency_ratio * score_weights.frequency
            + recent_ratio * score_weights.recent
            + recency_ratio * score_weights.recency
            + absence_ratio * score_weights.absence
            - repeat_penalty * score_weights.repeat_penalty
        )

        scores.append((number, max(score, 0.0)))

    return sorted(scores, key=lambda item: (-item[1], item[0]))


def calculate_main_number_scores(
    draws: list[list[int]],
    weights: ScoreWeights | None = None,
) -> list[tuple[int, float]]:
    """
    本数字用スコア。

    本数字は的中条件の中心なので、
    frequency / recent / recency をやや強めに使う。
    """
    base_weights = weights or ScoreWeights()

    main_weights = ScoreWeights(
        frequency=base_weights.frequency,
        recent=base_weights.recent,
        recency=base_weights.recency,
        absence=base_weights.absence,
        repeat_penalty=base_weights.repeat_penalty,
    )

    return calculate_number_scores(draws, main_weights)


def calculate_bonus_number_scores(
    bonus_draws: list[list[int]],
    weights: ScoreWeights | None = None,
) -> list[tuple[int, float]]:
    """
    ボーナス数字用スコア。

    ボーナスは出現頻度だけに寄せすぎると偏るため、
    absence と recency を少し効かせる。
    """
    base_weights = weights or ScoreWeights()

    bonus_weights = ScoreWeights(
        frequency=base_weights.frequency * 0.9,
        recent=base_weights.recent * 0.8,
        recency=base_weights.recency,
        absence=base_weights.absence * 1.2,
        repeat_penalty=base_weights.repeat_penalty * 0.5,
    )

    return calculate_number_scores(bonus_draws, bonus_weights)


def calculate_combined_scores(
    main_draws: list[list[int]],
    bonus_draws: list[list[int]],
    weights: ScoreWeights | None = None,
    main_weight: float = 0.8,
    bonus_weight: float = 0.2,
) -> list[tuple[int, float]]:
    """
    本数字スコアとボーナス数字スコアを合成する。

    prediction.py の profile型生成では、
    main_scores / bonus_scores を分離して渡すことを推奨。
    この関数は補助用途。
    """
    if main_weight < 0 or bonus_weight < 0:
        raise ValueError("main_weight and bonus_weight must be non-negative")

    main_scores = dict(calculate_main_number_scores(main_draws, weights))
    bonus_scores = dict(calculate_bonus_number_scores(bonus_draws, weights))

    numbers = set(main_scores.keys()) | set(bonus_scores.keys())

    combined = [
        (
            number,
            main_scores.get(number, 0.0) * main_weight
            + bonus_scores.get(number, 0.0) * bonus_weight,
        )
        for number in numbers
    ]

    return sorted(combined, key=lambda item: (-item[1], item[0]))


def _normalize_draw(draw: list[int]) -> list[int]:
    normalized: list[int] = []

    if not isinstance(draw, list):
        return normalized

    seen: set[int] = set()

    for value in draw:
        try:
            number = int(value)
        except (TypeError, ValueError):
            continue

        if number <= 0:
            continue

        if number in seen:
            continue

        seen.add(number)
        normalized.append(number)

    return normalized
