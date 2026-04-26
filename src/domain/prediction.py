from __future__ import annotations

import math
import random
from itertools import islice


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
        number_int = int(number)
        score_float = float(score)
        if score_float < 0:
            continue
        normalized[number_int] = score_float
    return normalized


def _build_weights(
    number_min: int,
    number_max: int,
    score_map: dict[int, float],
) -> dict[int, float]:
    return {
        number: 1.0 + max(score_map.get(number, 0.0), 0.0)
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

    even_target = pick_count // 2
    odd_target = pick_count - even_target

    ticket = evens[:even_target] + odds[:odd_target]

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
            if number in ticket:
                continue
            ticket.append(number)
            if len(ticket) >= pick_count:
                break

    return ticket[:pick_count]


def _build_mixed_depth_ticket(ranked_numbers: list[int], pick_count: int) -> list[int]:
    head_count = max(2, pick_count // 3)
    head = ranked_numbers[:head_count]

    mid_start = head_count
    mid_end = min(len(ranked_numbers), mid_start + pick_count * 2)
    middle = ranked_numbers[mid_start:mid_end]

    tail = ranked_numbers[mid_end : min(len(ranked_numbers), mid_end + pick_count * 2)]

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
    base_weights = _build_weights(number_min, number_max, score_map)
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

    max_attempts = max(200, prediction_count * 200)
    attempts = 0

    while len(predictions) < prediction_count and attempts < max_attempts:
        attempts += 1
        ticket_weights = _build_ticket_weights(base_weights, len(predictions), number_usage)

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


def generate_loto7_second_prize_oriented_predictions(
    main_scores: list[tuple[int, float]],
    bonus_scores: list[tuple[int, float]],
    prediction_count: int,
    rng: random.Random | None = None,
    seed: int | None = None,
    excluded_combinations: set[tuple[int, ...]] | None = None,
) -> list[list[int]]:
    """
    LOTO7の2等条件を意識した生成。

    方針:
    - 本数字スコアから6個
    - ボーナス数字スコアから1個
    - 合計7個で1口
    """
    if prediction_count <= 0:
        raise ValueError("prediction_count must be greater than 0")

    random_source = rng if rng is not None else random.Random(seed)

    main_score_map = _normalize_scores(main_scores)
    bonus_score_map = _normalize_scores(bonus_scores)

    main_weights = _build_weights(1, 37, main_score_map)
    bonus_weights = _build_weights(1, 37, bonus_score_map)

    ranked_mains = _rank_numbers_by_weight(main_weights)
    ranked_bonuses = _rank_numbers_by_weight(bonus_weights)

    main_pool = ranked_mains[: min(24, len(ranked_mains))]
    bonus_pool = ranked_bonuses[: min(14, len(ranked_bonuses))]

    if len(main_pool) < 6:
        raise ValueError("main_pool must contain at least 6 numbers")

    predictions: list[list[int]] = []
    seen = set(excluded_combinations or set())

    max_attempts = max(500, prediction_count * 500)
    attempts = 0

    while len(predictions) < prediction_count and attempts < max_attempts:
        attempts += 1

        sampled_main = _weighted_sample_without_replacement(
            population=main_pool,
            weights=main_weights,
            sample_size=6,
            rng=random_source,
        )

        selectable_bonus_pool = [
            number for number in bonus_pool
            if number not in sampled_main
        ]

        if not selectable_bonus_pool:
            selectable_bonus_pool = [
                number for number in range(1, 38)
                if number not in sampled_main
            ]

        sampled_bonus = _weighted_sample_without_replacement(
            population=selectable_bonus_pool,
            weights=bonus_weights,
            sample_size=1,
            rng=random_source,
        )

        candidate = sampled_main + sampled_bonus
        key = tuple(sorted(candidate))

        if key in seen:
            continue

        display_weights = {
            number: main_weights.get(number, 1.0) + bonus_weights.get(number, 1.0) * 0.25
            for number in candidate
        }

        seen.add(key)
        predictions.append(_order_by_score(candidate, display_weights))

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
    """
    予想番号を生成する。

    strategy:
    - default: 既存方式
    - second_prize_oriented: LOTO7専用。本数字6個 + ボーナス寄り1個
    - mixed: LOTO7の場合、default と second_prize_oriented を混在
    """
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

        second_prize_count = max(1, int(round(prediction_count * 0.4)))
        default_count = prediction_count - second_prize_count

        predictions: list[list[int]] = []
        seen: set[tuple[int, ...]] = set()

        if default_count > 0:
            default_predictions = _generate_default_predictions(
                number_scores=number_scores,
                lottery_type=normalized_lottery_type,
                prediction_count=default_count,
                rng=rng,
                seed=seed,
                excluded_combinations=seen,
            )
            for prediction in default_predictions:
                predictions.append(prediction)
                seen.add(tuple(sorted(prediction)))

        if second_prize_count > 0:
            second_predictions = generate_loto7_second_prize_oriented_predictions(
                main_scores=number_scores,
                bonus_scores=bonus_scores,
                prediction_count=second_prize_count,
                rng=rng,
                seed=None if seed is None else seed + 10_000,
                excluded_combinations=seen,
            )
            for prediction in second_predictions:
                predictions.append(prediction)
                seen.add(tuple(sorted(prediction)))

        if len(predictions) != prediction_count:
            raise ValueError(
                f"mixed strategy failed: requested={prediction_count} generated={len(predictions)}"
            )

        return predictions

    raise ValueError(f"unsupported prediction strategy: {strategy}")
