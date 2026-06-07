"""EMA frequency scorer.

ロト履歴の直近傾向を指数移動平均でスコア化する低レベルscorerです。
単純頻度だけでは拾いにくい短期変化を、過度に尖らせず補助信号として扱います。
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Mapping, Sequence

Draw = Sequence[int]


def compute_ema_presence(
    draws: Sequence[Draw],
    max_number: int = 37,
    alpha: float = 0.15,
    include_bonus: bool = False,
) -> dict[int, float]:
    if alpha <= 0.0 or alpha > 1.0:
        raise ValueError("alpha must be between 0.0 and 1.0")

    if max_number <= 0:
        raise ValueError("max_number must be positive")

    if not draws:
        return {number: 0.0 for number in range(1, max_number + 1)}

    ema_scores: dict[int, float] = {number: 0.0 for number in range(1, max_number + 1)}

    for draw in draws:
        draw_numbers = {int(value) for value in draw if isinstance(value, int) and value > 0}
        for number in range(1, max_number + 1):
            observed = 1.0 if number in draw_numbers else 0.0
            ema_scores[number] = alpha * observed + (1.0 - alpha) * ema_scores[number]

        if not include_bonus:
            # 番号リストが main+bonus 混在の場合は caller が対処する。
            pass

    return ema_scores


def compute_last_seen_gap(
    draws: Sequence[Draw],
    max_number: int = 37,
) -> dict[int, int]:
    if max_number <= 0:
        raise ValueError("max_number must be positive")

    if not draws:
        return {number: 0 for number in range(1, max_number + 1)}

    gap_map = {number: len(draws) for number in range(1, max_number + 1)}

    for draw_index, draw in enumerate(draws):
        draw_numbers = {int(value) for value in draw if isinstance(value, int) and value > 0}
        for number in draw_numbers:
            if gap_map[number] == len(draws):
                gap_map[number] = draw_index

    return gap_map


def blend_scores(
    score_maps: Sequence[Mapping[int, float]],
    weights: Sequence[float],
) -> dict[int, float]:
    if len(score_maps) != len(weights):
        raise ValueError("score_maps and weights length must match")
    if not score_maps:
        return {}

    number_set = set()
    for score_map in score_maps:
        number_set.update(score_map.keys())

    result: dict[int, float] = {number: 0.0 for number in number_set}
    for score_map, weight in zip(score_maps, weights):
        for number in result:
            result[number] += float(score_map.get(number, 0.0)) * float(weight)

    return result


def _median(sorted_values: list[float]) -> float:
    length = len(sorted_values)
    if length == 0:
        return 0.0
    mid = length // 2
    if length % 2:
        return sorted_values[mid]
    return (sorted_values[mid - 1] + sorted_values[mid]) / 2.0


def _robust_scale(score_map: Mapping[int, float], max_number: int = 37) -> dict[int, float]:
    values = [float(score_map.get(number, 0.0)) for number in range(1, max_number + 1)]
    if not values:
        return {number: 0.0 for number in range(1, max_number + 1)}

    sorted_values = sorted(values)
    median = _median(sorted_values)
    q1_index = int(len(sorted_values) * 0.25)
    q3_index = int(len(sorted_values) * 0.75)
    q1 = sorted_values[q1_index]
    q3 = sorted_values[q3_index]
    iqr = q3 - q1

    if abs(iqr) < 1e-9:
        mean = sum(sorted_values) / len(sorted_values)
        variance = sum((value - mean) ** 2 for value in sorted_values) / len(sorted_values)
        scale = math.sqrt(variance) if variance > 1e-9 else 1.0
    else:
        scale = iqr

    scaled = [(value - median) / scale for value in values]
    minimum = min(scaled)
    shifted = [value - minimum for value in scaled]
    maximum = max(shifted)

    if maximum <= 1e-9:
        return {number: 0.0 for number in range(1, max_number + 1)}

    return {
        number: shifted[index] / maximum
        for index, number in enumerate(range(1, max_number + 1))
    }


@dataclass(frozen=True)
class EmaFrequencyScorer:
    alpha_short: float = 0.20
    alpha_mid: float = 0.10
    alpha_long: float = 0.05
    short_weight: float = 0.45
    mid_weight: float = 0.35
    long_weight: float = 0.20
    include_bonus: bool = False

    def score_numbers(self, history: Sequence[Draw]) -> dict[int, float]:
        if not history:
            return {number: 0.0 for number in range(1, 38)}

        max_number = 37
        short_scores = compute_ema_presence(
            history,
            max_number=max_number,
            alpha=self.alpha_short,
            include_bonus=self.include_bonus,
        )
        mid_scores = compute_ema_presence(
            history,
            max_number=max_number,
            alpha=self.alpha_mid,
            include_bonus=self.include_bonus,
        )
        long_scores = compute_ema_presence(
            history,
            max_number=max_number,
            alpha=self.alpha_long,
            include_bonus=self.include_bonus,
        )

        gap_map = compute_last_seen_gap(history, max_number=max_number)
        max_gap = max(gap_map.values(), default=1)
        gap_scores = {
            number: 1.0 - (gap_map[number] / max_gap)
            for number in range(1, max_number + 1)
        }

        scaled_short = _robust_scale(short_scores, max_number=max_number)
        scaled_mid = _robust_scale(mid_scores, max_number=max_number)
        scaled_long = _robust_scale(long_scores, max_number=max_number)
        scaled_gap = _robust_scale(gap_scores, max_number=max_number)

        support_weight = (self.short_weight + self.mid_weight + self.long_weight) * 0.15
        blended = blend_scores(
            [scaled_short, scaled_mid, scaled_long, scaled_gap],
            [self.short_weight, self.mid_weight, self.long_weight, support_weight],
        )

        return _robust_scale(blended, max_number=max_number)
