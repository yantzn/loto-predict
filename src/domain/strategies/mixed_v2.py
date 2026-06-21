"""LOTO7 mixed_v2 strategy.

既存mixed戦略を壊さず、EMA・pair・bonus-aware・diverse exploreの複数laneで
5口を生成するための戦略実装です。mixed_v3の比較baselineとしても使います。
"""

from __future__ import annotations

import random
from dataclasses import dataclass
from statistics import mean
from typing import Sequence

from src.domain.scorers.pair_cooccurrence import PairConfig, PairCooccurrenceScorer
from src.domain.strategies.ema_recency import EmaRecencyConfig, rank_ema_recency_candidates
from src.domain.strategies.seed import stable_seed
from src.domain.statistics import (
    ScoreWeights,
    calculate_bonus_number_scores,
    calculate_main_number_scores,
)

Draw = Sequence[int]


@dataclass(frozen=True)
class SlotConfig:
    name: str
    strategy: str
    description: str
    bonus_aware: bool = False


@dataclass(frozen=True)
class MixedV2Config:
    slots: list[SlotConfig]
    history_threshold_for_ema: int = 200
    diverse_candidate_pool_size: int = 18
    pair_config: PairConfig = PairConfig()
    ema_hot_config: EmaRecencyConfig = EmaRecencyConfig(
        alpha_short=0.30,
        alpha_mid=0.12,
        alpha_long=0.05,
        short_weight=0.55,
        mid_weight=0.30,
        long_weight=0.15,
        include_bonus=False,
    )
    min_pair_support: float = 2.0
    pair_top_k: int = 10
    diverse_main_ratio: float = 0.85
    diverse_bonus_ratio: float = 0.15
    diverse_quality_weight: float = 0.0005
    pair_base_weight: float = 0.62
    pair_ema_weight: float = 0.25
    pair_affinity_weight: float = 0.08
    pair_explore_weight: float = 0.05
    pair_fallback_base_weight: float = 0.74
    pair_fallback_ema_weight: float = 0.23
    pair_fallback_explore_weight: float = 0.03
    seed_namespace: str = "mixed_v2"
    ema_balanced_config: EmaRecencyConfig = EmaRecencyConfig(
        alpha_short=0.18,
        alpha_mid=0.12,
        alpha_long=0.08,
        short_weight=0.40,
        mid_weight=0.35,
        long_weight=0.25,
        include_bonus=False,
    )


def build_default_mixed_v2_config() -> MixedV2Config:
    return MixedV2Config(
        slots=[
            SlotConfig(
                name="lane1",
                strategy="ema_hot_or_main_hot",
                description=(
                    "Hot lane: use EMA when history is deep, otherwise preserve main_hot strength."
                ),
            ),
            SlotConfig(
                name="lane2",
                strategy="main_balanced_or_ema_balanced",
                description=(
                    "Balanced lane: preserve main_balanced for short history, use EMA-balanced for deeper history."
                ),
            ),
            SlotConfig(
                name="lane3",
                strategy="pair_weighted",
                description="Pair-weighted lane to capture co-occurrence structure for 3等狙い.",
            ),
            SlotConfig(
                name="lane4",
                strategy="bonus2_balanced",
                description="Bonus-aware lane with 5 main + 2 bonus for 2等狙い.",
                bonus_aware=True,
            ),
            SlotConfig(
                name="lane5",
                strategy="diverse_explore",
                description="Exploratory lane that prioritizes ticket diversity and coverage.",
            ),
        ]
    )


def build_tuned_mixed_v2_config() -> MixedV2Config:
    """本番mixed_v2を変えず、上位一致を狙う比較用の保守的な調整を返します。"""
    default = build_default_mixed_v2_config()
    return MixedV2Config(
        slots=default.slots,
        history_threshold_for_ema=default.history_threshold_for_ema,
        diverse_candidate_pool_size=24,
        pair_config=default.pair_config,
        ema_hot_config=default.ema_hot_config,
        min_pair_support=default.min_pair_support,
        pair_top_k=default.pair_top_k,
        diverse_main_ratio=0.90,
        diverse_bonus_ratio=0.10,
        diverse_quality_weight=0.025,
        ema_balanced_config=default.ema_balanced_config,
        pair_base_weight=0.68,
        pair_ema_weight=0.25,
        pair_affinity_weight=0.04,
        pair_explore_weight=0.03,
        pair_fallback_base_weight=0.78,
        pair_fallback_ema_weight=0.20,
        pair_fallback_explore_weight=0.02,
        seed_namespace="mixed_v2_tuned",
    )


def allocate_strategy_slots(
    history_limit: int,
    config: MixedV2Config | None = None,
) -> list[SlotConfig]:
    config = config or build_default_mixed_v2_config()
    use_ema = history_limit >= config.history_threshold_for_ema

    resolved: list[SlotConfig] = []
    for slot in config.slots:
        if slot.strategy == "ema_hot_or_main_hot":
            strategy = "ema_hot" if use_ema else "main_hot"
        elif slot.strategy == "main_balanced_or_ema_balanced":
            strategy = "ema_balanced" if use_ema else "main_balanced"
        else:
            strategy = slot.strategy

        resolved.append(
            SlotConfig(
                name=slot.name,
                strategy=strategy,
                description=slot.description,
                bonus_aware=slot.bonus_aware,
            )
        )

    return resolved


def _build_weights(
    *,
    number_min: int,
    number_max: int,
    score_map: dict[int, float],
    temperature: float = 1.0,
) -> dict[int, float]:
    values = [max(score_map.get(number, 0.0), 0.0) for number in range(number_min, number_max + 1)]
    max_value = max(values, default=0.0)
    if max_value <= 0:
        return {number: 0.0 for number in range(number_min, number_max + 1)}

    scaled = {
        number: max(score_map.get(number, 0.0), 0.0) / max_value
        for number in range(number_min, number_max + 1)
    }
    temp = max(0.1, temperature)
    return {number: 1.0 + pow(scaled[number], temp) for number in range(number_min, number_max + 1)}


def _build_blended_weights(
    *,
    number_min: int,
    number_max: int,
    main_score_map: dict[int, float],
    bonus_score_map: dict[int, float],
    main_ratio: float,
    bonus_ratio: float,
    temperature: float,
) -> dict[int, float]:
    if main_ratio < 0 or bonus_ratio < 0:
        raise ValueError("main_ratio and bonus_ratio must be non-negative")

    main_scaled = _scale_score_map(main_score_map, number_min, number_max)
    bonus_scaled = _scale_score_map(bonus_score_map, number_min, number_max)
    temp = max(0.1, temperature)

    return {
        number: 1.0 + pow(
            max(main_scaled.get(number, 0.0) * main_ratio + bonus_scaled.get(number, 0.0) * bonus_ratio, 0.0),
            temp,
        )
        for number in range(number_min, number_max + 1)
    }


def _scale_score_map(
    score_map: dict[int, float],
    number_min: int,
    number_max: int,
) -> dict[int, float]:
    values = [max(score_map.get(number, 0.0), 0.0) for number in range(number_min, number_max + 1)]
    max_value = max(values, default=0.0)
    if max_value <= 0:
        return {number: 0.0 for number in range(number_min, number_max + 1)}

    return {
        number: max(score_map.get(number, 0.0), 0.0) / max_value
        for number in range(number_min, number_max + 1)
    }


def _rank_numbers_by_weight(weights: dict[int, float]) -> list[int]:
    return [number for number, _ in sorted(weights.items(), key=lambda item: (-item[1], item[0]))]


def _order_by_score(selected: list[int], weights: dict[int, float]) -> list[int]:
    return sorted(selected, key=lambda number: (-weights.get(number, 1.0), number))


def _weighted_sample_without_replacement(
    population: list[int],
    weights: dict[int, float],
    sample_size: int,
    rng: random.Random,
) -> list[int]:
    if sample_size > len(population):
        raise ValueError("sample size is larger than population")

    available = list(population)
    selected: list[int] = []

    while len(selected) < sample_size:
        available_weights = [max(weights.get(number, 1.0), 0.000001) for number in available]
        chosen = rng.choices(available, weights=available_weights, k=1)[0]
        selected.append(chosen)
        available.remove(chosen)

    return selected


def _ema_number_scores(history: Sequence[Draw], alpha: float = 0.16) -> dict[int, float]:
    scores = {number: 0.0 for number in range(1, 38)}
    for draw in reversed(history):
        present = {int(number) for number in draw}
        for number in scores:
            observation = 1.0 if number in present else 0.0
            scores[number] = alpha * observation + (1.0 - alpha) * scores[number]
    max_score = max(scores.values(), default=0.0)
    if max_score <= 0:
        return scores
    return {number: score / max_score for number, score in scores.items()}


def _support_normalized_pair_score(
    candidate: int,
    selected: Sequence[int],
    scorer: PairCooccurrenceScorer,
) -> tuple[float, float]:
    if scorer._stats is None or not selected:
        return 0.0, 0.0

    supports: list[float] = []
    lifts: list[float] = []
    for other in selected:
        pair_key = (min(candidate, other), max(candidate, other))
        raw_count = scorer._stats.pair_counts.get(pair_key, 0.0)
        supports.append(raw_count)
        lifts.append(scorer._average_pair_lift([candidate, other]))

    avg_support = sum(supports) / len(supports) if supports else 0.0
    support_scale = avg_support / (avg_support + scorer.config.shrink_k) if scorer.config.shrink_k > 0 else 1.0
    avg_lift = sum(lifts) / len(lifts) if lifts else 0.0
    normalized_score = max(0.0, min(1.0, ((avg_lift - 1.0) / 4.0 + 0.5) * support_scale))
    return normalized_score, avg_support


def build_lane3_pair_weighted_scores(
    *,
    history: Sequence[Draw],
    main_score_map: dict[int, float],
    selected: Sequence[int],
    config: PairConfig,
    min_pair_support: float = 2.0,
    base_weight: float = 0.62,
    ema_weight: float = 0.25,
    pair_weight: float = 0.08,
    explore_weight: float = 0.05,
    fallback_base_weight: float = 0.74,
    fallback_ema_weight: float = 0.23,
    fallback_explore_weight: float = 0.03,
) -> dict[int, dict[str, float | bool]]:
    scorer = PairCooccurrenceScorer(config)
    scorer.score_numbers(history)
    base_scaled = _scale_score_map(main_score_map, 1, 37)
    ema_scaled = _ema_number_scores(history)

    result: dict[int, dict[str, float | bool]] = {}
    for number in range(1, 38):
        if number in selected:
            continue

        base_score = base_scaled.get(number, 0.0)
        ema_score = ema_scaled.get(number, 0.0)
        pair_score, pair_support = _support_normalized_pair_score(number, selected, scorer)
        explore_bonus = max(0.0, 1.0 - base_score) * 0.35
        fallback_used = bool(selected) and pair_support < min_pair_support
        if fallback_used:
            final_score = (
                fallback_base_weight * base_score
                + fallback_ema_weight * ema_score
                + fallback_explore_weight * explore_bonus
            )
        else:
            final_score = (
                base_weight * base_score
                + ema_weight * ema_score
                + pair_weight * pair_score
                + explore_weight * explore_bonus
            )
        result[number] = {
            "base": base_score,
            "ema": ema_score,
            "pair": pair_score,
            "triple": 0.0,
            "diversity_penalty": 0.0,
            "explore_bonus": explore_bonus,
            "pair_support": pair_support,
            "fallback_used": fallback_used,
            "final": final_score,
        }

    return result


def _build_ticket_weights(
    base_weights: dict[int, float],
    ticket_index: int,
    number_usage: dict[int, int],
) -> dict[int, float]:
    if ticket_index <= 0:
        return dict(base_weights)

    temperature = max(0.55, 1.0 - (0.1 * ticket_index))
    penalty_strength = 0.35

    return {
        number: pow(weight, temperature) / (1.0 + number_usage.get(number, 0) * penalty_strength)
        for number, weight in base_weights.items()
    }


def _jaccard_similarity(a: Sequence[int], b: Sequence[int]) -> float:
    if not a and not b:
        return 1.0
    intersection = len(set(a) & set(b))
    union = len(set(a) | set(b))
    return intersection / union if union else 0.0


def _build_loto7_ticket(
    *,
    main_score_map: dict[int, float],
    bonus_score_map: dict[int, float],
    profile: dict[str, float],
    rng: random.Random,
    seen: set[tuple[int, ...]],
    ticket_index: int,
) -> list[int]:
    main_weights = _build_blended_weights(
        number_min=1,
        number_max=37,
        main_score_map=main_score_map,
        bonus_score_map=bonus_score_map,
        main_ratio=profile["main_score_ratio"],
        bonus_ratio=profile["bonus_score_ratio_for_main"],
        temperature=profile["temperature"],
    )
    bonus_weights = _build_blended_weights(
        number_min=1,
        number_max=37,
        main_score_map=main_score_map,
        bonus_score_map=bonus_score_map,
        main_ratio=profile["bonus_main_ratio"],
        bonus_ratio=profile["bonus_score_ratio"],
        temperature=profile["temperature"],
    )
    display_weights = _build_blended_weights(
        number_min=1,
        number_max=37,
        main_score_map=main_score_map,
        bonus_score_map=bonus_score_map,
        main_ratio=0.75,
        bonus_ratio=0.25,
        temperature=1.0,
    )

    ranked_main = _rank_numbers_by_weight(main_weights)
    ranked_bonus = _rank_numbers_by_weight(bonus_weights)
    main_pool = ranked_main[: min(int(profile["main_pool_size"]), len(ranked_main))]
    bonus_pool = ranked_bonus[: min(int(profile["bonus_pool_size"]), len(ranked_bonus))]
    usage_penalty: dict[int, int] = {}
    max_attempts = 500

    for attempt in range(max_attempts):
        adjusted_main_weights = _build_ticket_weights(
            base_weights=main_weights,
            ticket_index=ticket_index + attempt // 100,
            number_usage=usage_penalty,
        )
        sampled_main = _weighted_sample_without_replacement(
            population=main_pool,
            weights=adjusted_main_weights,
            sample_size=int(profile["main_sample_count"]),
            rng=rng,
        )
        sampled_bonus: list[int] = []
        if int(profile["bonus_sample_count"]) > 0:
            selectable_bonus_pool = [n for n in bonus_pool if n not in sampled_main]
            if len(selectable_bonus_pool) < int(profile["bonus_sample_count"]):
                selectable_bonus_pool = [n for n in range(1, 38) if n not in sampled_main]
            adjusted_bonus_weights = _build_ticket_weights(
                base_weights=bonus_weights,
                ticket_index=ticket_index + attempt // 100,
                number_usage=usage_penalty,
            )
            sampled_bonus = _weighted_sample_without_replacement(
                population=selectable_bonus_pool,
                weights=adjusted_bonus_weights,
                sample_size=int(profile["bonus_sample_count"]),
                rng=rng,
            )

        candidate = sampled_main + sampled_bonus
        key = tuple(sorted(candidate))
        if key in seen:
            for number in candidate:
                usage_penalty[number] = usage_penalty.get(number, 0) + 1
            continue

        seen.add(key)
        return _order_by_score(candidate, display_weights)

    raise ValueError("failed to generate unique loto7 profile ticket")


def _build_default_profile(profile_name: str) -> dict[str, float]:
    profiles = {
        "main_hot": {
            "main_pool_size": 18,
            "bonus_pool_size": 37,
            "main_sample_count": 6,
            "bonus_sample_count": 1,
            "main_score_ratio": 0.94,
            "bonus_score_ratio_for_main": 0.06,
            "bonus_main_ratio": 0.30,
            "bonus_score_ratio": 0.70,
            "temperature": 0.75,
        },
        "main_balanced": {
            "main_pool_size": 24,
            "bonus_pool_size": 37,
            "main_sample_count": 6,
            "bonus_sample_count": 1,
            "main_score_ratio": 0.88,
            "bonus_score_ratio_for_main": 0.12,
            "bonus_main_ratio": 0.35,
            "bonus_score_ratio": 0.65,
            "temperature": 0.95,
        },
        "bonus2_balanced": {
            "main_pool_size": 24,
            "bonus_pool_size": 37,
            "main_sample_count": 5,
            "bonus_sample_count": 2,
            "main_score_ratio": 0.90,
            "bonus_score_ratio_for_main": 0.10,
            "bonus_main_ratio": 0.25,
            "bonus_score_ratio": 0.75,
            "temperature": 0.95,
        },
        "explore": {
            "main_pool_size": 30,
            "bonus_pool_size": 37,
            "main_sample_count": 5,
            "bonus_sample_count": 2,
            "main_score_ratio": 0.84,
            "bonus_score_ratio_for_main": 0.16,
            "bonus_main_ratio": 0.18,
            "bonus_score_ratio": 0.82,
            "temperature": 1.15,
        },
    }
    if profile_name not in profiles:
        raise ValueError(f"unsupported profile_name: {profile_name}")
    return profiles[profile_name]


class MixedStrategyV2:
    def __init__(self, config: MixedV2Config) -> None:
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
        if prediction_count > len(self.config.slots):
            raise ValueError("mixed_v2 supports at most 5 tickets")
        if bonus_scores is None:
            raise ValueError("bonus_scores is required for mixed_v2")

        main_score_map = (
            dict(number_scores) if number_scores is not None else dict(calculate_main_number_scores(list(history), ScoreWeights()))
        )
        bonus_score_map = dict(bonus_scores)
        slots = allocate_strategy_slots(len(history), self.config)[:prediction_count]
        selected: list[list[int]] = []
        seen: set[tuple[int, ...]] = set()

        for slot_index, slot in enumerate(slots):
            rng_seed = stable_seed(
                self.config.seed_namespace,
                target_draw,
                history_limit,
                seed,
                slot_index,
            )
            ticket = self._generate_slot_ticket(
                slot=slot,
                rng=random.Random(rng_seed),
                main_score_map=main_score_map,
                bonus_score_map=bonus_score_map,
                history=list(history),
                seen=seen,
                slot_index=slot_index,
            )
            seen.add(tuple(ticket))
            selected.append(ticket)

        return selected

    def _generate_slot_ticket(
        self,
        *,
        slot: SlotConfig,
        rng: random.Random,
        main_score_map: dict[int, float],
        bonus_score_map: dict[int, float],
        history: list[Draw],
        seen: set[tuple[int, ...]],
        slot_index: int,
    ) -> list[int]:
        strategy = slot.strategy

        if strategy == "main_hot":
            profile = _build_default_profile("main_hot")
            return _build_loto7_ticket(
                main_score_map=main_score_map,
                bonus_score_map=bonus_score_map,
                profile=profile,
                rng=rng,
                seen=seen,
                ticket_index=slot_index,
            )

        if strategy == "main_balanced":
            profile = _build_default_profile("main_balanced")
            return _build_loto7_ticket(
                main_score_map=main_score_map,
                bonus_score_map=bonus_score_map,
                profile=profile,
                rng=rng,
                seen=seen,
                ticket_index=slot_index,
            )

        if strategy == "ema_hot":
            return rank_ema_recency_candidates(
                history=history,
                prediction_count=1,
                seed=rng.randint(0, 2**32 - 1),
                config=self.config.ema_hot_config,
            )[0]

        if strategy == "ema_balanced":
            return rank_ema_recency_candidates(
                history=history,
                prediction_count=1,
                seed=rng.randint(0, 2**32 - 1),
                config=self.config.ema_balanced_config,
            )[0]

        if strategy == "pair_weighted":
            return self._generate_pair_weighted_ticket(
                main_score_map=main_score_map,
                history=history,
                existing_tickets=[list(ticket) for ticket in [*seen]],
                rng=rng,
            )

        if strategy == "bonus2_balanced":
            profile = _build_default_profile("bonus2_balanced")
            return _build_loto7_ticket(
                main_score_map=main_score_map,
                bonus_score_map=bonus_score_map,
                profile=profile,
                rng=rng,
                seen=seen,
                ticket_index=slot_index,
            )

        if strategy == "diverse_explore":
            return self._generate_diverse_explore_ticket(
                main_score_map=main_score_map,
                bonus_score_map=bonus_score_map,
                history=history,
                existing_tickets=[list(ticket) for ticket in [*seen]],
                rng=rng,
            )

        raise ValueError(f"unsupported mixed_v2 slot strategy: {strategy}")

    def _generate_pair_weighted_ticket(
        self,
        *,
        main_score_map: dict[int, float],
        history: list[Draw],
        existing_tickets: list[list[int]],
        rng: random.Random,
    ) -> list[int]:
        selected: list[int] = []
        usage_penalty: dict[int, int] = {}
        candidate_pool = list(range(1, 38))

        while len(selected) < 7:
            score_rows = build_lane3_pair_weighted_scores(
                history=history,
                main_score_map=main_score_map,
                selected=selected,
                config=self.config.pair_config,
                min_pair_support=self.config.min_pair_support,
                base_weight=self.config.pair_base_weight,
                ema_weight=self.config.pair_ema_weight,
                pair_weight=self.config.pair_affinity_weight,
                explore_weight=self.config.pair_explore_weight,
                fallback_base_weight=self.config.pair_fallback_base_weight,
                fallback_ema_weight=self.config.pair_fallback_ema_weight,
                fallback_explore_weight=self.config.pair_fallback_explore_weight,
            )
            scored: list[tuple[float, int]] = []
            for number in candidate_pool:
                if number in selected:
                    continue
                row = score_rows[number]
                overlap_penalty = usage_penalty.get(number, 0) * 0.04
                score = max(float(row["final"]) - overlap_penalty, 0.000001)
                scored.append((score, number))

            scored.sort(key=lambda item: (-item[0], item[1]))
            top_items = scored[: max(1, self.config.pair_top_k)]
            weights = [max(score, 0.000001) for score, _ in top_items]
            chosen = rng.choices([number for _, number in top_items], weights=weights, k=1)[0]
            selected.append(chosen)

        ticket = sorted(selected, key=lambda number: (-main_score_map.get(number, 0.0), number))
        if ticket in existing_tickets:
            ticket = sorted(rng.sample(candidate_pool, 7), key=lambda number: (-main_score_map.get(number, 0.0), number))
        for number in ticket:
            usage_penalty[number] = usage_penalty.get(number, 0) + 1
        return ticket

    def _generate_diverse_explore_ticket(
        self,
        *,
        main_score_map: dict[int, float],
        bonus_score_map: dict[int, float],
        history: list[Draw],
        existing_tickets: list[list[int]],
        rng: random.Random,
    ) -> list[int]:
        combined_score_map = {
            number: (
                main_score_map.get(number, 0.0) * self.config.diverse_main_ratio
                + bonus_score_map.get(number, 0.0) * self.config.diverse_bonus_ratio
            )
            for number in range(1, 38)
        }
        base_weights = _build_weights(
            number_min=1,
            number_max=37,
            score_map=combined_score_map,
            temperature=1.0,
        )
        explore_pool = _rank_numbers_by_weight(base_weights)[:26]
        candidate_pool: list[list[int]] = []

        for candidate_index in range(self.config.diverse_candidate_pool_size):
            ticket_weights = _build_ticket_weights(
                base_weights={number: base_weights[number] for number in explore_pool},
                ticket_index=candidate_index,
                number_usage={},
            )
            ticket = _weighted_sample_without_replacement(
                population=explore_pool,
                weights=ticket_weights,
                sample_size=7,
                rng=rng,
            )
            candidate_pool.append(_order_by_score(ticket, base_weights))

        best_ticket = None
        best_score = -1.0
        for candidate in candidate_pool:
            if candidate in existing_tickets:
                continue
            similarity_scores = [1.0 - _jaccard_similarity(candidate, existing) for existing in existing_tickets] if existing_tickets else [1.0]
            distance = mean(similarity_scores) if similarity_scores else 1.0
            quality = sum(main_score_map.get(number, 0.0) for number in candidate)
            score = distance + self.config.diverse_quality_weight * quality
            if score > best_score:
                best_score = score
                best_ticket = candidate

        if best_ticket is None:
            return _order_by_score(
                rng.sample(list(range(1, 38)), 7),
                base_weights,
            )

        return best_ticket
