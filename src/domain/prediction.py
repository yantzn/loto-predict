from __future__ import annotations

import math
import random
from dataclasses import dataclass
from itertools import islice


@dataclass(frozen=True)
class Loto7Profile:
    name: str
    main_pool_size: int
    bonus_pool_size: int
    main_sample_count: int
    bonus_sample_count: int
    main_score_ratio: float
    bonus_score_ratio_for_main: float
    bonus_main_ratio: float
    bonus_score_ratio: float
    temperature: float


def _lottery_spec(lottery_type: str) -> tuple[int, int, int]:
    normalized = str(lottery_type).strip().lower()
    if normalized == "loto6":
        return 1, 43, 6
    if normalized == "loto7":
        return 1, 37, 7
    raise ValueError(f"unsupported lottery_type: {lottery_type}")


def _normalize_scores(number_scores: list[tuple[int, float]]) -> dict[int, float]:
    normalized: dict[int, float] = {}
    for number, score in number_scores:
        score_float = float(score)
        if score_float >= 0:
            normalized[int(number)] = score_float
    return normalized


def _scale_score_map(
    *,
    score_map: dict[int, float],
    number_min: int,
    number_max: int,
) -> dict[int, float]:
    values = [
        max(score_map.get(number, 0.0), 0.0)
        for number in range(number_min, number_max + 1)
    ]

    max_value = max(values, default=0.0)
    if max_value <= 0:
        return {number: 0.0 for number in range(number_min, number_max + 1)}

    return {
        number: max(score_map.get(number, 0.0), 0.0) / max_value
        for number in range(number_min, number_max + 1)
    }


def _build_weights(
    number_min: int,
    number_max: int,
    score_map: dict[int, float],
    *,
    temperature: float = 1.0,
) -> dict[int, float]:
    scaled = _scale_score_map(
        score_map=score_map,
        number_min=number_min,
        number_max=number_max,
    )
    temp = max(0.1, temperature)

    return {
        number: 1.0 + pow(scaled.get(number, 0.0), temp)
        for number in range(number_min, number_max + 1)
    }


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

    main_scaled = _scale_score_map(
        score_map=main_score_map,
        number_min=number_min,
        number_max=number_max,
    )
    bonus_scaled = _scale_score_map(
        score_map=bonus_score_map,
        number_min=number_min,
        number_max=number_max,
    )

    temp = max(0.1, temperature)

    return {
        number: 1.0
        + pow(
            max(
                main_scaled.get(number, 0.0) * main_ratio
                + bonus_scaled.get(number, 0.0) * bonus_ratio,
                0.0,
            ),
            temp,
        )
        for number in range(number_min, number_max + 1)
    }


def _build_ticket_weights(
    base_weights: dict[int, float],
    ticket_index: int,
    number_usage: dict[int, int],
) -> dict[int, float]:
    if ticket_index <= 0:
        return dict(base_weights)

    temperature = max(0.55, 1.0 - (0.1 * ticket_index))
    usage_penalty_strength = 0.35

    return {
        number: pow(weight, temperature)
        / (1.0 + number_usage.get(number, 0) * usage_penalty_strength)
        for number, weight in base_weights.items()
    }


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
        available_weights = [
            max(weights.get(number, 1.0), 0.000001)
            for number in available
        ]
        chosen = rng.choices(available, weights=available_weights, k=1)[0]
        selected.append(chosen)
        available.remove(chosen)

    return selected


def _order_by_score(selected: list[int], weights: dict[int, float]) -> list[int]:
    return sorted(selected, key=lambda number: (-weights.get(number, 1.0), number))


def _rank_numbers_by_weight(weights: dict[int, float]) -> list[int]:
    return [
        number
        for number, _ in sorted(weights.items(), key=lambda item: (-item[1], item[0]))
    ]


def _build_anchor_ticket(ranked_numbers: list[int], pick_count: int) -> list[int]:
    return list(islice(ranked_numbers, pick_count))


def _build_balanced_ticket(ranked_numbers: list[int], pick_count: int) -> list[int]:
    if len(ranked_numbers) <= pick_count:
        return list(ranked_numbers)

    upper_count = max(1, int(pick_count * 0.6))
    upper = ranked_numbers[:upper_count]
    middle_pool = ranked_numbers[upper_count : upper_count + pick_count * 2]
    return upper + middle_pool[: pick_count - len(upper)]


def _build_even_odd_ticket(ranked_numbers: list[int], pick_count: int) -> list[int]:
    top_pool = ranked_numbers[: max(pick_count * 3, pick_count)]
    evens = [number for number in top_pool if number % 2 == 0]
    odds = [number for number in top_pool if number % 2 == 1]

    ticket = evens[: pick_count // 2] + odds[: pick_count - pick_count // 2]

    if len(ticket) < pick_count:
        rest = [number for number in top_pool if number not in ticket]
        ticket.extend(rest[: pick_count - len(ticket)])

    return ticket[:pick_count]


def _build_spread_ticket(ranked_numbers: list[int], pick_count: int) -> list[int]:
    top_pool = ranked_numbers[: max(pick_count * 3, pick_count)]
    ticket: list[int] = []

    for index in range(0, len(top_pool), 2):
        if len(ticket) >= pick_count:
            break
        ticket.append(top_pool[index])

    if len(ticket) < pick_count:
        for number in top_pool:
            if number not in ticket:
                ticket.append(number)
            if len(ticket) >= pick_count:
                break

    return ticket[:pick_count]


def _build_mixed_depth_ticket(ranked_numbers: list[int], pick_count: int) -> list[int]:
    head_count = max(2, pick_count // 3)
    head = ranked_numbers[:head_count]
    middle = ranked_numbers[head_count : head_count + pick_count * 2]
    tail = ranked_numbers[head_count + pick_count * 2 : head_count + pick_count * 4]

    ticket: list[int] = []
    ticket.extend(head[:head_count])
    ticket.extend(middle[:head_count])
    ticket.extend(tail[: pick_count - len(ticket)])

    if len(ticket) < pick_count:
        rest = [number for number in ranked_numbers if number not in ticket]
        ticket.extend(rest[: pick_count - len(ticket)])

    return ticket[:pick_count]


def _build_strategy_tickets(
    ranked_numbers: list[int],
    pick_count: int,
) -> list[list[int]]:
    candidates = [
        _build_anchor_ticket(ranked_numbers, pick_count),
        _build_balanced_ticket(ranked_numbers, pick_count),
        _build_even_odd_ticket(ranked_numbers, pick_count),
        _build_spread_ticket(ranked_numbers, pick_count),
        _build_mixed_depth_ticket(ranked_numbers, pick_count),
    ]
    return [ticket for ticket in candidates if len(ticket) == pick_count]


def _generate_default_predictions(
    number_scores: list[tuple[int, float]],
    lottery_type: str,
    prediction_count: int,
    rng: random.Random | None = None,
    seed: int | None = None,
    excluded_combinations: set[tuple[int, ...]] | None = None,
) -> list[list[int]]:
    number_min, number_max, pick_count = _lottery_spec(lottery_type)

    if prediction_count <= 0:
        raise ValueError("prediction_count must be greater than 0")

    population_size = number_max - number_min + 1
    if population_size < pick_count:
        raise ValueError("candidate count is smaller than required pick_count")

    if prediction_count > math.comb(population_size, pick_count):
        raise ValueError("requested prediction_count exceeds maximum unique combinations")

    population = list(range(number_min, number_max + 1))
    score_map = _normalize_scores(number_scores)

    base_weights = _build_weights(
        number_min,
        number_max,
        score_map,
        temperature=0.85,
    )

    ranked_numbers = _rank_numbers_by_weight(base_weights)
    random_source = rng if rng is not None else random.Random(seed)

    predictions: list[list[int]] = []
    seen = set(excluded_combinations or set())
    number_usage: dict[int, int] = {}

    for strategy_ticket in _build_strategy_tickets(ranked_numbers, pick_count):
        if len(predictions) >= prediction_count:
            break

        ordered = _order_by_score(strategy_ticket, base_weights)
        key = tuple(sorted(ordered))

        if key in seen:
            continue

        seen.add(key)
        predictions.append(ordered)

        for number in ordered:
            number_usage[number] = number_usage.get(number, 0) + 1

    max_attempts = max(300, prediction_count * 300)
    attempts = 0

    while len(predictions) < prediction_count and attempts < max_attempts:
        attempts += 1
        ticket_weights = _build_ticket_weights(
            base_weights=base_weights,
            ticket_index=len(predictions),
            number_usage=number_usage,
        )

        sampled = _weighted_sample_without_replacement(
            population=population,
            weights=ticket_weights,
            sample_size=pick_count,
            rng=random_source,
        )

        candidate = _order_by_score(sampled, ticket_weights)
        key = tuple(sorted(candidate))

        if key in seen:
            continue

        seen.add(key)
        predictions.append(candidate)

        for number in candidate:
            number_usage[number] = number_usage.get(number, 0) + 1

    if len(predictions) != prediction_count:
        raise ValueError(
            f"failed to generate enough unique predictions: "
            f"requested={prediction_count} generated={len(predictions)}"
        )

    return predictions


def _loto7_profiles(prediction_count: int) -> list[Loto7Profile]:
    profiles = [
        Loto7Profile(
            name="main_hot",
            main_pool_size=18,
            bonus_pool_size=37,
            main_sample_count=6,
            bonus_sample_count=1,
            main_score_ratio=0.94,
            bonus_score_ratio_for_main=0.06,
            bonus_main_ratio=0.30,
            bonus_score_ratio=0.70,
            temperature=0.75,
        ),
        Loto7Profile(
            name="main_balanced",
            main_pool_size=24,
            bonus_pool_size=37,
            main_sample_count=6,
            bonus_sample_count=1,
            main_score_ratio=0.88,
            bonus_score_ratio_for_main=0.12,
            bonus_main_ratio=0.35,
            bonus_score_ratio=0.65,
            temperature=0.95,
        ),
        Loto7Profile(
            name="main_wide_bonus_hot",
            main_pool_size=30,
            bonus_pool_size=37,
            main_sample_count=6,
            bonus_sample_count=1,
            main_score_ratio=0.82,
            bonus_score_ratio_for_main=0.18,
            bonus_main_ratio=0.22,
            bonus_score_ratio=0.78,
            temperature=1.05,
        ),
        Loto7Profile(
            name="main5_bonus2_balanced",
            main_pool_size=24,
            bonus_pool_size=37,
            main_sample_count=5,
            bonus_sample_count=2,
            main_score_ratio=0.90,
            bonus_score_ratio_for_main=0.10,
            bonus_main_ratio=0.25,
            bonus_score_ratio=0.75,
            temperature=0.95,
        ),
        Loto7Profile(
            name="main5_bonus2_explore",
            main_pool_size=30,
            bonus_pool_size=37,
            main_sample_count=5,
            bonus_sample_count=2,
            main_score_ratio=0.84,
            bonus_score_ratio_for_main=0.16,
            bonus_main_ratio=0.18,
            bonus_score_ratio=0.82,
            temperature=1.15,
        ),
    ]

    if prediction_count <= len(profiles):
        return profiles[:prediction_count]

    expanded: list[Loto7Profile] = []
    while len(expanded) < prediction_count:
        expanded.extend(profiles)

    return expanded[:prediction_count]


def _generate_loto7_profile_prediction(
    *,
    profile: Loto7Profile,
    main_score_map: dict[int, float],
    bonus_score_map: dict[int, float],
    rng: random.Random,
    seen: set[tuple[int, ...]],
    ticket_index: int,
) -> list[int]:
    main_weights = _build_blended_weights(
        number_min=1,
        number_max=37,
        main_score_map=main_score_map,
        bonus_score_map=bonus_score_map,
        main_ratio=profile.main_score_ratio,
        bonus_ratio=profile.bonus_score_ratio_for_main,
        temperature=profile.temperature,
    )

    bonus_weights = _build_blended_weights(
        number_min=1,
        number_max=37,
        main_score_map=main_score_map,
        bonus_score_map=bonus_score_map,
        main_ratio=profile.bonus_main_ratio,
        bonus_ratio=profile.bonus_score_ratio,
        temperature=profile.temperature,
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

    main_pool = ranked_main[: min(profile.main_pool_size, len(ranked_main))]
    bonus_pool = ranked_bonus[: min(profile.bonus_pool_size, len(ranked_bonus))]

    if len(main_pool) < profile.main_sample_count:
        raise ValueError("main_pool is smaller than main_sample_count")

    if profile.bonus_sample_count > 0 and len(bonus_pool) < profile.bonus_sample_count:
        raise ValueError("bonus_pool is smaller than bonus_sample_count")

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
            sample_size=profile.main_sample_count,
            rng=rng,
        )

        sampled_bonus: list[int] = []
        if profile.bonus_sample_count > 0:
            selectable_bonus_pool = [
                number for number in bonus_pool
                if number not in sampled_main
            ]

            if len(selectable_bonus_pool) < profile.bonus_sample_count:
                selectable_bonus_pool = [
                    number for number in range(1, 38)
                    if number not in sampled_main
                ]

            adjusted_bonus_weights = _build_ticket_weights(
                base_weights=bonus_weights,
                ticket_index=ticket_index + attempt // 100,
                number_usage=usage_penalty,
            )

            sampled_bonus = _weighted_sample_without_replacement(
                population=selectable_bonus_pool,
                weights=adjusted_bonus_weights,
                sample_size=profile.bonus_sample_count,
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

    raise ValueError(f"failed to generate unique prediction for profile={profile.name}")


def generate_loto7_second_prize_oriented_predictions(
    main_scores: list[tuple[int, float]],
    bonus_scores: list[tuple[int, float]],
    prediction_count: int,
    rng: random.Random | None = None,
    seed: int | None = None,
    excluded_combinations: set[tuple[int, ...]] | None = None,
) -> list[list[int]]:
    if prediction_count <= 0:
        raise ValueError("prediction_count must be greater than 0")

    random_source = rng if rng is not None else random.Random(seed)

    main_score_map = _normalize_scores(main_scores)
    bonus_score_map = _normalize_scores(bonus_scores)

    predictions: list[list[int]] = []
    seen = set(excluded_combinations or set())

    for ticket_index, profile in enumerate(_loto7_profiles(prediction_count)):
        prediction = _generate_loto7_profile_prediction(
            profile=profile,
            main_score_map=main_score_map,
            bonus_score_map=bonus_score_map,
            rng=random_source,
            seen=seen,
            ticket_index=ticket_index,
        )
        predictions.append(prediction)

    if len(predictions) != prediction_count:
        raise ValueError(
            f"failed to generate enough unique second-prize predictions: "
            f"requested={prediction_count} generated={len(predictions)}"
        )

    return predictions


def generate_predictions(
    number_scores: list[tuple[int, float]],
    lottery_type: str,
    prediction_count: int,
    rng: random.Random | None = None,
    seed: int | None = None,
    strategy: str = "default",
    bonus_scores: list[tuple[int, float]] | None = None,
) -> list[list[int]]:
    normalized_lottery_type = str(lottery_type).strip().lower()
    normalized_strategy = str(strategy).strip().lower()

    if normalized_strategy == "default":
        return _generate_default_predictions(
            number_scores=number_scores,
            lottery_type=normalized_lottery_type,
            prediction_count=prediction_count,
            rng=rng,
            seed=seed,
        )

    if normalized_strategy == "second_prize_oriented":
        if normalized_lottery_type != "loto7":
            raise ValueError("second_prize_oriented is only supported for loto7")
        if bonus_scores is None:
            raise ValueError("bonus_scores is required for second_prize_oriented")

        return generate_loto7_second_prize_oriented_predictions(
            main_scores=number_scores,
            bonus_scores=bonus_scores,
            prediction_count=prediction_count,
            rng=rng,
            seed=seed,
        )

    if normalized_strategy == "mixed":
        if normalized_lottery_type != "loto7" or bonus_scores is None:
            return _generate_default_predictions(
                number_scores=number_scores,
                lottery_type=normalized_lottery_type,
                prediction_count=prediction_count,
                rng=rng,
                seed=seed,
            )

        return generate_loto7_second_prize_oriented_predictions(
            main_scores=number_scores,
            bonus_scores=bonus_scores,
            prediction_count=prediction_count,
            rng=rng,
            seed=None if seed is None else seed + 10_000,
            excluded_combinations=None,
        )

    raise ValueError(f"unsupported prediction strategy: {strategy}")
