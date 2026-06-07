"""LOTO6 mixed strategy.

LOTO6専用の5口profileを定義し、100回窓を主軸にしながら150回の安定性、
50回の探索性、未出現間隔、組合せ補正を軽く混ぜて予想を生成します。
当選保証ではなく、過去データ上の参考評価を比較しやすくするためのstrategyです。
"""

from __future__ import annotations

import random
from collections.abc import Sequence
from dataclasses import dataclass

from src.domain.strategies.seed import stable_seed

Draw = Sequence[int]

LOTO6_NUMBER_MIN = 1
LOTO6_NUMBER_MAX = 43
LOTO6_PICK_COUNT = 6

MIXED_LOTO6_PROFILES = [
    "l6_hot_100_core",
    "l6_balanced_150",
    "l6_recent_50",
    "l6_gap_repair",
    "l6_diverse_explore",
]

PROFILE_HISTORY_WINDOWS: dict[str, dict[str, int]] = {
    "l6_hot_100_core": {"primary": 100, "secondary": 150, "recent": 30, "long": 200},
    "l6_balanced_150": {"primary": 150, "secondary": 100, "recent": 50, "long": 200},
    "l6_recent_50": {"primary": 50, "secondary": 100, "recent": 30, "long": 150},
    "l6_gap_repair": {"primary": 100, "secondary": 150, "recent": 50, "long": 200},
    "l6_diverse_explore": {"primary": 50, "secondary": 100, "recent": 30, "long": 200},
}

PROFILE_SCORE_WEIGHTS: dict[str, dict[str, float]] = {
    "l6_hot_100_core": {
        "primary_frequency": 0.45,
        "secondary_frequency": 0.20,
        "recent_frequency": 0.15,
        "long_frequency": 0.08,
        "gap": 0.07,
        "trend": 0.05,
    },
    "l6_balanced_150": {
        "primary_frequency": 0.35,
        "secondary_frequency": 0.25,
        "recent_frequency": 0.12,
        "long_frequency": 0.10,
        "gap": 0.12,
        "trend": 0.06,
    },
    "l6_recent_50": {
        "primary_frequency": 0.32,
        "secondary_frequency": 0.18,
        "recent_frequency": 0.25,
        "long_frequency": 0.05,
        "gap": 0.10,
        "trend": 0.10,
    },
    "l6_gap_repair": {
        "primary_frequency": 0.28,
        "secondary_frequency": 0.22,
        "recent_frequency": 0.10,
        "long_frequency": 0.08,
        "gap": 0.24,
        "trend": 0.08,
    },
    "l6_diverse_explore": {
        "primary_frequency": 0.25,
        "secondary_frequency": 0.15,
        "recent_frequency": 0.18,
        "long_frequency": 0.07,
        "gap": 0.20,
        "trend": 0.15,
    },
}

PROFILE_TOP_K = {
    "l6_hot_100_core": 14,
    "l6_balanced_150": 16,
    "l6_recent_50": 18,
    "l6_gap_repair": 20,
    "l6_diverse_explore": 24,
}

PROFILE_ROLES = {
    "l6_hot_100_core": "100-draw hot-number core profile",
    "l6_balanced_150": "150-draw balanced stability profile",
    "l6_recent_50": "50-draw recent-trend profile",
    "l6_gap_repair": "gap-aware profile that avoids excluding cold numbers",
    "l6_diverse_explore": "exploration profile that reduces overlap with earlier tickets",
}


@dataclass(frozen=True)
class MixedLoto6Config:
    min_weight: float = 0.0001
    candidate_attempts: int = 24
    combination_fit_weight: float = 0.16


def build_default_mixed_loto6_config() -> MixedLoto6Config:
    return MixedLoto6Config()


def _full_number_map(value: float = 0.0) -> dict[int, float]:
    return {
        number: value
        for number in range(LOTO6_NUMBER_MIN, LOTO6_NUMBER_MAX + 1)
    }


def _normalize(scores: dict[int, float]) -> dict[int, float]:
    values = [scores.get(number, 0.0) for number in range(LOTO6_NUMBER_MIN, LOTO6_NUMBER_MAX + 1)]
    max_value = max(values, default=0.0)
    min_value = min(values, default=0.0)
    if max_value == min_value:
        return _full_number_map(0.0)
    return {
        number: max(0.0, min(1.0, (scores.get(number, 0.0) - min_value) / (max_value - min_value)))
        for number in range(LOTO6_NUMBER_MIN, LOTO6_NUMBER_MAX + 1)
    }


def _calculate_frequency(history: list[Draw], window: int) -> dict[int, float]:
    counts = _full_number_map(0.0)
    target = history[:window] if window > 0 else history
    for draw in target:
        for number in set(int(value) for value in draw):
            if LOTO6_NUMBER_MIN <= number <= LOTO6_NUMBER_MAX:
                counts[number] += 1.0
    return _normalize(counts)


def _gap_scores(history: list[Draw], window: int) -> dict[int, float]:
    target = history[:window] if window > 0 else history
    max_gap = max(1, len(target))
    gaps = {number: max_gap for number in range(LOTO6_NUMBER_MIN, LOTO6_NUMBER_MAX + 1)}
    for index, draw in enumerate(target):
        for number in set(int(value) for value in draw):
            if LOTO6_NUMBER_MIN <= number <= LOTO6_NUMBER_MAX and gaps[number] == max_gap:
                gaps[number] = index
    raw = {number: min(1.0, gap / max_gap) for number, gap in gaps.items()}
    return _normalize(raw)


def _trend_scores(recent: dict[int, float], baseline: dict[int, float]) -> dict[int, float]:
    return _normalize({
        number: max(0.0, recent.get(number, 0.0) - baseline.get(number, 0.0))
        for number in range(LOTO6_NUMBER_MIN, LOTO6_NUMBER_MAX + 1)
    })


def _calculate_sum_percentiles(history: list[Draw]) -> dict[str, float]:
    sums = sorted(sum(int(number) for number in draw[:LOTO6_PICK_COUNT]) for draw in history if len(draw) >= LOTO6_PICK_COUNT)
    if not sums:
        return {"p10": 0.0, "p25": 0.0, "p50": 0.0, "p75": 0.0, "p90": 0.0}
    last = len(sums) - 1
    return {
        "p10": float(sums[min(last, max(0, int(len(sums) * 0.10)))]),
        "p25": float(sums[min(last, max(0, int(len(sums) * 0.25)))]),
        "p50": float(sums[min(last, max(0, int(len(sums) * 0.50)))]),
        "p75": float(sums[min(last, max(0, int(len(sums) * 0.75)))]),
        "p90": float(sums[min(last, max(0, int(len(sums) * 0.90)))]),
    }


def _consecutive_pairs(numbers: list[int]) -> int:
    sorted_numbers = sorted(numbers)
    return sum(1 for left, right in zip(sorted_numbers, sorted_numbers[1:]) if right - left == 1)


def _range_counts(numbers: list[int]) -> dict[str, int]:
    return {
        "low": sum(1 for number in numbers if 1 <= number <= 14),
        "mid": sum(1 for number in numbers if 15 <= number <= 29),
        "high": sum(1 for number in numbers if 30 <= number <= 43),
    }


def _combination_fit(
    numbers: list[int],
    *,
    existing_tickets: list[list[int]],
    sum_percentiles: dict[str, float],
    profile: str,
) -> float:
    score = 1.0
    odd_count = sum(1 for number in numbers if number % 2 == 1)
    if odd_count in {2, 3, 4}:
        score += 0.05
    elif odd_count in {1, 5}:
        score -= 0.12
    else:
        score -= 0.25

    total = sum(numbers)
    p10 = sum_percentiles.get("p10", 0.0)
    p25 = sum_percentiles.get("p25", 0.0)
    p75 = sum_percentiles.get("p75", 0.0)
    p90 = sum_percentiles.get("p90", 0.0)
    if p25 <= total <= p75:
        score += 0.08
    elif p10 and (total < p10 or total > p90):
        score -= 0.16

    consecutive_count = _consecutive_pairs(numbers)
    if consecutive_count >= 3:
        score -= 0.18
    elif consecutive_count <= 1:
        score += 0.03

    ranges = _range_counts(numbers)
    if all(value >= 1 for value in ranges.values()):
        score += 0.06
    if any(value >= 5 for value in ranges.values()):
        score -= 0.18

    for existing in existing_tickets:
        overlap = len(set(numbers) & set(existing))
        if overlap == LOTO6_PICK_COUNT:
            return 0.0
        if overlap >= 5:
            score -= 0.35
        elif overlap == 4 and profile == "l6_diverse_explore":
            score -= 0.12

    return max(0.0, min(1.0, score))


class MixedLoto6Strategy:
    def __init__(self, config: MixedLoto6Config | None = None) -> None:
        self.config = config or build_default_mixed_loto6_config()

    def generate_predictions(
        self,
        *,
        history: list[Draw],
        prediction_count: int,
        seed: int,
        number_scores: list[tuple[int, float]],
        target_draw: int = 0,
        history_limit: int = 0,
    ) -> list[list[int]]:
        if prediction_count > len(MIXED_LOTO6_PROFILES):
            raise ValueError(f"mixed_loto6 supports at most {len(MIXED_LOTO6_PROFILES)} tickets")
        if not history:
            raise ValueError("history is required for mixed_loto6")

        base_score_map = _normalize({number: score for number, score in number_scores})
        sum_percentiles = _calculate_sum_percentiles(history)

        predictions: list[list[int]] = []
        seen: set[tuple[int, ...]] = set()

        for index, profile in enumerate(MIXED_LOTO6_PROFILES[:prediction_count], start=1):
            rng = random.Random(stable_seed("mixed_loto6", target_draw, history_limit, seed, index, profile))
            number_score_map = self._score_numbers(profile, history, base_score_map)
            ticket = self._select_ticket(
                profile=profile,
                score_map=number_score_map,
                existing_tickets=predictions,
                seen=seen,
                sum_percentiles=sum_percentiles,
                rng=rng,
            )
            predictions.append(ticket)
            seen.add(tuple(sorted(ticket)))

        return predictions

    def _score_numbers(
        self,
        profile: str,
        history: list[Draw],
        base_score_map: dict[int, float],
    ) -> dict[int, float]:
        windows = PROFILE_HISTORY_WINDOWS[profile]
        weights = PROFILE_SCORE_WEIGHTS[profile]

        primary = _calculate_frequency(history, windows["primary"])
        secondary = _calculate_frequency(history, windows["secondary"])
        recent = _calculate_frequency(history, windows["recent"])
        long = _calculate_frequency(history, windows["long"])
        gap = _gap_scores(history, windows["long"])
        trend = _trend_scores(recent, primary)

        score_map = _full_number_map(self.config.min_weight)
        for number in score_map:
            score_map[number] += (
                primary[number] * weights["primary_frequency"]
                + secondary[number] * weights["secondary_frequency"]
                + recent[number] * weights["recent_frequency"]
                + long[number] * weights["long_frequency"]
                + gap[number] * weights["gap"]
                + trend[number] * weights["trend"]
                + base_score_map.get(number, 0.0) * 0.05
            )
        return score_map

    def _select_ticket(
        self,
        *,
        profile: str,
        score_map: dict[int, float],
        existing_tickets: list[list[int]],
        seen: set[tuple[int, ...]],
        sum_percentiles: dict[str, float],
        rng: random.Random,
    ) -> list[int]:
        top_k = PROFILE_TOP_K[profile]
        ranked = sorted(score_map, key=lambda number: (-score_map[number], number))
        pool = ranked[:top_k]
        best_ticket: list[int] | None = None
        best_score = -1.0

        for _ in range(self.config.candidate_attempts):
            ticket = self._weighted_sample(pool, score_map, rng)
            key = tuple(sorted(ticket))
            if key in seen:
                continue
            fit = _combination_fit(
                ticket,
                existing_tickets=existing_tickets,
                sum_percentiles=sum_percentiles,
                profile=profile,
            )
            total_score = sum(score_map[number] for number in ticket) + fit * self.config.combination_fit_weight
            if total_score > best_score:
                best_score = total_score
                best_ticket = ticket

        if best_ticket is None:
            for start in range(0, len(ranked) - LOTO6_PICK_COUNT + 1):
                ticket = ranked[start : start + LOTO6_PICK_COUNT]
                if tuple(sorted(ticket)) not in seen:
                    best_ticket = ticket
                    break

        if best_ticket is None:
            raise ValueError("failed to generate unique mixed_loto6 ticket")

        return sorted(best_ticket, key=lambda number: (-score_map.get(number, 0.0), number))

    def _weighted_sample(
        self,
        pool: list[int],
        score_map: dict[int, float],
        rng: random.Random,
    ) -> list[int]:
        available = list(pool)
        selected: list[int] = []
        while len(selected) < LOTO6_PICK_COUNT:
            weights = [max(score_map.get(number, 0.0), self.config.min_weight) for number in available]
            chosen = rng.choices(available, weights=weights, k=1)[0]
            selected.append(chosen)
            available.remove(chosen)
        return selected
