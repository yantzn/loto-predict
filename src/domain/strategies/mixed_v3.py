"""LOTO7 mixed_v3 strategy.

650-679 validation resultsを受けて追加した5口profile型の予想戦略です。
各profileのhistory window、score weight、探索幅をこのファイルに集約し、
seed固定ではなくprofile/windowごとの傾向を比較できるようにしています。
"""

from __future__ import annotations

import random
from collections.abc import Sequence
from dataclasses import dataclass
from itertools import combinations
from statistics import mean
from typing import Any

from src.domain.scorers.pair_cooccurrence import PairConfig, PairCooccurrenceScorer
from src.domain.strategies.seed import stable_seed
from src.domain.statistics import ScoreWeights, calculate_main_number_scores

Draw = Sequence[int]

MIXED_V3_PROFILES = [
    "lane1_ema_hot_core",
    "lane2_pair_weighted_core",
    "lane3_long_200_balanced",
    "lane4_bonus_aware_balanced",
    "lane5_diversity_repair",
]


PROFILE_HISTORY_WINDOWS: dict[str, dict[str, int]] = {
    "lane1_ema_hot_core": {
        "primary": 100,
        "secondary": 200,
        "recent": 30,
        "short": 50,
        "medium": 150,
    },
    "lane2_pair_weighted_core": {
        "primary": 100,
        "secondary": 50,
        "long": 200,
        "recent": 30,
    },
    "lane3_long_200_balanced": {
        "primary": 100,
        "secondary": 200,
        "recent": 50,
        "medium": 150,
    },
    "lane4_bonus_aware_balanced": {
        "primary": 100,
        "secondary": 200,
        "recent": 50,
        "bonus_window": 200,
    },
    "lane5_diversity_repair": {
        "primary": 50,
        "secondary": 100,
        "long": 200,
        "recent": 30,
    },
}


PROFILE_SCORE_WEIGHTS: dict[str, dict[str, float]] = {
    "lane1_ema_hot_core": {
        "ema_recent": 0.30,
        "primary_frequency": 0.35,
        "secondary_frequency": 0.10,
        "short_frequency": 0.15,
        "medium_frequency": 0.05,
        "gap": 0.05,
    },
    "lane2_pair_weighted_core": {
        "pair_affinity": 0.05,
        "primary_frequency": 0.40,
        "secondary_frequency": 0.20,
        "ema_recent": 0.15,
        "recent_frequency": 0.15,
        "gap": 0.05,
    },
    "lane3_long_200_balanced": {
        "primary_frequency": 0.35,
        "secondary_frequency": 0.15,
        "recent_frequency": 0.15,
        "medium_frequency": 0.15,
        "gap": 0.10,
        "trend": 0.05,
        "combination_fit": 0.05,
    },
    "lane4_bonus_aware_balanced": {
        "primary_frequency": 0.42,
        "secondary_frequency": 0.18,
        "recent_frequency": 0.12,
        "bonus_affinity": 0.03,
        "gap": 0.08,
        "trend": 0.05,
        "combination_fit": 0.12,
    },
    "lane5_diversity_repair": {
        "coverage_gap": 0.18,
        "primary_frequency": 0.28,
        "secondary_frequency": 0.18,
        "long_frequency": 0.10,
        "recent_frequency": 0.16,
        "gap": 0.10,
    },
}


PROFILE_ROLES = {
    "lane1_ema_hot_core": "core hot profile using 100-draw frequency and 50-draw exploration",
    "lane2_pair_weighted_core": "frequency-first profile with pair affinity only as a weak tiebreaker",
    "lane3_long_200_balanced": "100-draw balanced profile with 200-draw long-term support",
    "lane4_bonus_aware_balanced": "hit4-oriented main-number profile with very weak bonus affinity",
    "lane5_diversity_repair": "light exploration and coverage repair profile",
}


PROFILE_TOP_K = {
    "lane1_ema_hot_core": 12,
    "lane2_pair_weighted_core": 16,
    "lane3_long_200_balanced": 14,
    "lane4_bonus_aware_balanced": 12,
    "lane5_diversity_repair": 18,
}


@dataclass(frozen=True)
class MixedV3Config:
    pair_config: PairConfig = PairConfig(top_pool_size=37, shrink_k=5.0)
    min_weight: float = 0.0001
    min_pair_support: float = 1.0
    top_k: int = 14
    candidate_attempts: int = 6


def build_default_mixed_v3_config() -> MixedV3Config:
    return MixedV3Config()


def _normalize(scores: dict[int, float]) -> dict[int, float]:
    if not scores:
        return {number: 0.0 for number in range(1, 38)}
    max_value = max(scores.values(), default=0.0)
    min_value = min(scores.values(), default=0.0)
    if max_value == min_value:
        return {number: 0.0 for number in scores}
    return {
        number: max(0.0, min(1.0, (score - min_value) / (max_value - min_value)))
        for number, score in scores.items()
    }


def _calculate_sum_percentiles(history: list[Draw]) -> dict[str, float]:
    sums = sorted(sum(draw[:7]) for draw in history if len(draw) >= 7)
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


def _calculate_frequency(history: list[Draw], window: int) -> dict[int, float]:
    counts = {number: 0.0 for number in range(1, 38)}
    target = history[:window] if window > 0 else history
    for draw in target:
        for number in set(int(value) for value in draw):
            if 1 <= number <= 37:
                counts[number] += 1.0
    return _normalize(counts)


def _ema_scores(history: list[Draw], alpha: float = 0.22, window: int = 0) -> dict[int, float]:
    target = history[:window] if window > 0 else history
    scores = {number: 0.0 for number in range(1, 38)}
    for draw in reversed(target):
        present = {int(number) for number in draw}
        for number in scores:
            observation = 1.0 if number in present else 0.0
            scores[number] = alpha * observation + (1.0 - alpha) * scores[number]
    return _normalize(scores)


def _gap_scores(history: list[Draw], window: int) -> dict[int, float]:
    target = history[:window] if window > 0 else history
    max_gap = max(1, len(target))
    gaps = {number: max_gap for number in range(1, 38)}
    for index, draw in enumerate(target):
        for number in set(int(value) for value in draw):
            if 1 <= number <= 37 and gaps[number] == max_gap:
                gaps[number] = index
    raw = {number: min(1.0, gap / max_gap) for number, gap in gaps.items()}
    return _normalize(raw)


def _trend_scores(recent: dict[int, float], baseline: dict[int, float]) -> dict[int, float]:
    return _normalize({
        number: max(0.0, recent.get(number, 0.0) - baseline.get(number, 0.0))
        for number in range(1, 38)
    })


def _bonus_affinity_scores(bonus_score_map: dict[int, float]) -> dict[int, float]:
    return _normalize({number: bonus_score_map.get(number, 0.0) for number in range(1, 38)})


def _coverage_gap_scores(existing_tickets: list[list[int]]) -> dict[int, float]:
    usage = {number: 0 for number in range(1, 38)}
    for ticket in existing_tickets:
        for number in ticket:
            if 1 <= number <= 37:
                usage[number] += 1
    raw = {
        number: 1.0 if count == 0 else 0.45 if count == 1 else 0.0
        for number, count in usage.items()
    }
    return raw


def _pair_affinity_scores(
    *,
    history: list[Draw],
    selected: list[int],
    config: PairConfig,
) -> dict[int, float]:
    if not selected:
        return {number: 0.0 for number in range(1, 38)}

    scorer = PairCooccurrenceScorer(config)
    scorer.score_numbers(history)
    stats = scorer._stats
    if stats is None:
        return {number: 0.0 for number in range(1, 38)}

    raw: dict[int, float] = {}
    for candidate in range(1, 38):
        if candidate in selected:
            raw[candidate] = 0.0
            continue

        pair_values: list[float] = []
        for chosen in selected:
            pair_key = (min(candidate, chosen), max(candidate, chosen))
            support = stats.pair_counts.get(pair_key, 0.0)
            support_scale = support / (support + config.shrink_k) if config.shrink_k > 0 else 1.0
            pair_values.append(max(0.0, min(1.0, support_scale)))
        raw[candidate] = mean(pair_values) if pair_values else 0.0
    return _normalize(raw)


def _pair_affinity_scores_from_stats(
    *,
    stats: Any,
    selected: list[int],
    shrink_k: float,
) -> dict[int, float]:
    if not selected or stats is None:
        return {number: 0.0 for number in range(1, 38)}

    raw: dict[int, float] = {}
    for candidate in range(1, 38):
        if candidate in selected:
            raw[candidate] = 0.0
            continue
        values: list[float] = []
        for chosen in selected:
            pair_key = (min(candidate, chosen), max(candidate, chosen))
            support = stats.pair_counts.get(pair_key, 0.0)
            values.append(support / (support + shrink_k) if shrink_k > 0 else support)
        raw[candidate] = mean(values) if values else 0.0
    return _normalize(raw)


def _combination_fit_seed() -> dict[int, float]:
    return {number: 0.5 for number in range(1, 38)}


def _build_profile_rows(
    *,
    profile_name: str,
    components: dict[str, dict[int, float]],
    min_weight: float,
) -> dict[int, dict[str, float]]:
    weights = PROFILE_SCORE_WEIGHTS[profile_name]
    rows: dict[int, dict[str, float]] = {}
    for number in range(1, 38):
        row = {name: maps.get(number, 0.0) for name, maps in components.items()}
        row["final"] = sum(row[name] * weight for name, weight in weights.items())
        row["final"] = max(row["final"], min_weight)
        rows[number] = row
    return rows


class MixedStrategyV3:
    def __init__(self, config: MixedV3Config) -> None:
        self.config = config

    def generate_predictions(
        self,
        history: Sequence[Draw],
        prediction_count: int,
        seed: int,
        number_scores: list[tuple[int, float]] | None = None,
        bonus_scores: list[tuple[int, float]] | None = None,
        target_draw: int = 0,
        history_limit: int = 0,
    ) -> list[list[int]]:
        if prediction_count <= 0:
            raise ValueError("prediction_count must be greater than 0")
        if prediction_count > len(MIXED_V3_PROFILES):
            raise ValueError(f"mixed_v3 supports at most {len(MIXED_V3_PROFILES)} tickets")
        if bonus_scores is None:
            raise ValueError("bonus_scores is required for mixed_v3")

        history_list = [list(draw) for draw in history]
        main_score_map = (
            dict(number_scores)
            if number_scores is not None
            else dict(calculate_main_number_scores(history_list, ScoreWeights()))
        )
        bonus_score_map = dict(bonus_scores)
        sum_percentiles = _calculate_sum_percentiles(history_list)

        tickets: list[list[int]] = []
        seen: set[tuple[int, ...]] = set()
        for index, profile_name in enumerate(MIXED_V3_PROFILES[:prediction_count]):
            rng = random.Random(stable_seed("mixed_v3", target_draw, history_limit, seed, index))
            ticket = self._generate_ticket_for_profile(
                profile_name=profile_name,
                history=history_list,
                main_score_map=main_score_map,
                bonus_score_map=bonus_score_map,
                existing_tickets=tickets,
                seen=seen,
                sum_percentiles=sum_percentiles,
                rng=rng,
            )
            seen.add(tuple(sorted(ticket)))
            tickets.append(ticket)
        return tickets

    def profile_number_breakdown(
        self,
        *,
        profile_name: str,
        history: list[Draw],
        bonus_score_map: dict[int, float],
        selected: list[int] | None = None,
        existing_tickets: list[list[int]] | None = None,
    ) -> dict[int, dict[str, float]]:
        selected = selected or []
        existing_tickets = existing_tickets or []
        windows = PROFILE_HISTORY_WINDOWS[profile_name]

        freq_primary = _calculate_frequency(history, windows.get("primary", 0))
        freq_secondary = _calculate_frequency(history, windows.get("secondary", 0))
        freq_short = _calculate_frequency(history, windows.get("short", windows.get("primary", 0)))
        freq_medium = _calculate_frequency(history, windows.get("medium", windows.get("secondary", 0)))
        freq_long = _calculate_frequency(history, windows.get("long", windows.get("secondary", 0)))
        freq_recent = _calculate_frequency(history, windows.get("recent", 30))
        ema_recent = _ema_scores(history, alpha=0.28, window=windows.get("primary", 100))
        gap = _gap_scores(history, windows.get("primary", 100))
        trend = _trend_scores(freq_recent, freq_primary)
        pair_affinity = _pair_affinity_scores(
            history=history[: windows.get("secondary", 100)],
            selected=selected,
            config=self.config.pair_config,
        )
        bonus_affinity = _bonus_affinity_scores(bonus_score_map)
        coverage_gap = _coverage_gap_scores(existing_tickets)
        combination_fit = _combination_fit_seed()

        components = {
            "primary_frequency": freq_primary,
            "secondary_frequency": freq_secondary,
            "short_frequency": freq_short,
            "medium_frequency": freq_medium,
            "long_frequency": freq_long,
            "recent_frequency": freq_recent,
            "ema_recent": ema_recent,
            "pair_affinity": pair_affinity,
            "bonus_affinity": bonus_affinity,
            "coverage_gap": coverage_gap,
            "gap": gap,
            "trend": trend,
            "combination_fit": combination_fit,
        }

        return _build_profile_rows(
            profile_name=profile_name,
            components=components,
            min_weight=self.config.min_weight,
        )

    def _generate_ticket_for_profile(
        self,
        *,
        profile_name: str,
        history: list[Draw],
        main_score_map: dict[int, float],
        bonus_score_map: dict[int, float],
        existing_tickets: list[list[int]],
        seen: set[tuple[int, ...]],
        sum_percentiles: dict[str, float],
        rng: random.Random,
    ) -> list[int]:
        best_ticket: list[int] | None = None
        best_score = -999.0
        static_rows = self.profile_number_breakdown(
            profile_name=profile_name,
            history=history,
            bonus_score_map=bonus_score_map,
            selected=[],
            existing_tickets=existing_tickets,
        )
        pair_weight = PROFILE_SCORE_WEIGHTS[profile_name].get("pair_affinity", 0.0)
        pair_history = history[: PROFILE_HISTORY_WINDOWS[profile_name].get("secondary", 100)]
        top_k = PROFILE_TOP_K.get(profile_name, self.config.top_k)
        pair_stats = None
        if pair_weight > 0:
            scorer = PairCooccurrenceScorer(self.config.pair_config)
            scorer.score_numbers(pair_history)
            pair_stats = scorer._stats

        for attempt in range(self.config.candidate_attempts):
            selected: list[int] = []
            while len(selected) < 7:
                rows = static_rows
                dynamic_pair = None
                if pair_weight > 0 and selected:
                    dynamic_pair = _pair_affinity_scores_from_stats(
                        stats=pair_stats,
                        selected=selected,
                        shrink_k=self.config.pair_config.shrink_k,
                    )
                available = [number for number in range(1, 38) if number not in selected]
                scored: list[tuple[float, int]] = []
                for number in available:
                    score = rows[number]["final"]
                    if dynamic_pair is not None:
                        score = (
                            score
                            - pair_weight * rows[number].get("pair_affinity", 0.0)
                            + pair_weight * dynamic_pair.get(number, 0.0)
                        )
                    scored.append((max(score, self.config.min_weight), number))
                scored.sort(key=lambda item: (-item[0], item[1]))
                top = scored[: max(1, top_k)]
                numbers = [number for _, number in top]
                weights = [max(score, self.config.min_weight) for score, _ in top]
                selected.append(rng.choices(numbers, weights=weights, k=1)[0])

            ticket = sorted(selected)
            key = tuple(ticket)
            if key in seen:
                continue

            adjustment = self.evaluate_combination_adjustment(
                ticket=ticket,
                existing_tickets=existing_tickets,
                sum_percentiles=sum_percentiles,
                profile_name=profile_name,
            )
            quality = sum(main_score_map.get(number, 0.0) for number in ticket) / max(1, len(ticket))
            candidate_score = quality * 0.01 + float(adjustment["fit_score"])
            if candidate_score > best_score:
                best_score = candidate_score
                best_ticket = ticket
            if candidate_score >= 0.95 and attempt >= 10:
                break

        if best_ticket is not None:
            return best_ticket

        while True:
            fallback = sorted(rng.sample(list(range(1, 38)), 7))
            if tuple(fallback) not in seen:
                return fallback

    def evaluate_combination_adjustment(
        self,
        *,
        ticket: list[int],
        existing_tickets: list[list[int]],
        sum_percentiles: dict[str, float],
        profile_name: str,
    ) -> dict[str, Any]:
        odd_count = sum(1 for number in ticket if number % 2 == 1)
        ticket_sum = sum(ticket)
        consecutive_pairs = sum(
            1 for left, right in zip(ticket, ticket[1:], strict=False) if right - left == 1
        )
        range_counts = {
            "low": sum(1 for number in ticket if 1 <= number <= 12),
            "mid": sum(1 for number in ticket if 13 <= number <= 25),
            "high": sum(1 for number in ticket if 26 <= number <= 37),
        }
        overlaps = [len(set(ticket) & set(existing)) for existing in existing_tickets]
        max_overlap = max(overlaps, default=0)

        penalty = 0.0
        bonus = 0.0
        if odd_count in {3, 4}:
            bonus += 0.12
        elif odd_count in {0, 1, 6, 7}:
            penalty += 0.30

        if sum_percentiles["p25"] <= ticket_sum <= sum_percentiles["p75"]:
            bonus += 0.16 if profile_name == "lane4_bonus_aware_balanced" else 0.12
        elif ticket_sum < sum_percentiles["p10"] or ticket_sum > sum_percentiles["p90"]:
            penalty += 0.30

        if consecutive_pairs >= 3:
            penalty += 0.25
        elif consecutive_pairs <= 2:
            bonus += 0.05

        if all(count > 0 for count in range_counts.values()):
            bonus += 0.14 if profile_name == "lane4_bonus_aware_balanced" else 0.10
        if any(count >= 5 for count in range_counts.values()):
            penalty += 0.25

        duplicate = any(overlap == 7 for overlap in overlaps)
        if duplicate:
            penalty += 5.0
        elif max_overlap >= 5:
            penalty += 0.70 if profile_name == "lane5_diversity_repair" else 0.60
        elif max_overlap == 4 and profile_name == "lane5_diversity_repair":
            penalty += 0.30

        fit_score = max(0.0, min(1.0, 0.65 + bonus - penalty))
        return {
            "odd_count": odd_count,
            "sum": ticket_sum,
            "sum_percentiles": sum_percentiles,
            "consecutive_pairs": consecutive_pairs,
            "range_counts": range_counts,
            "max_overlap": max_overlap,
            "duplicate": duplicate,
            "penalty": round(penalty, 6),
            "bonus": round(bonus, 6),
            "fit_score": round(fit_score, 6),
        }

    def _evaluate_combination(
        self,
        ticket: list[int],
        base_weights: dict[int, float],
        existing_tickets: list[list[int]],
        sum_percentiles: dict[str, float],
        profile_name: str,
    ) -> float:
        adjustment = self.evaluate_combination_adjustment(
            ticket=ticket,
            existing_tickets=existing_tickets,
            sum_percentiles=sum_percentiles,
            profile_name=profile_name,
        )
        quality = sum(base_weights.get(number, 0.0) for number in ticket) / max(1, len(ticket))
        return quality * 0.05 + float(adjustment["fit_score"])
