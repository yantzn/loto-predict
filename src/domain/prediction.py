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
    # 未出現番号も選択候補に残しつつ、統計スコアが高いほど選ばれやすくする。
    # 最低重みを 1.0 に固定し、探索の多様性を担保する。
    return {
        number: 1.0 + max(score_map.get(number, 0.0), 0.0)
        for number in range(number_min, number_max + 1)
    }


def _build_ticket_weights(
    base_weights: dict[int, float],
    ticket_index: int,
    number_usage: dict[int, int],
) -> dict[int, float]:
    # 1口目は従来どおりの重みを使い、2口目以降は段階的にフラット化して
    # 似た組合せに偏り続けるのを抑える。
    if ticket_index <= 0:
        return dict(base_weights)

    temperature = max(0.55, 1.0 - (0.1 * ticket_index))
    usage_penalty_strength = 0.35
    return {
        number: pow(weight, temperature)
        / (1.0 + (number_usage.get(number, 0) * usage_penalty_strength))
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
        available_weights = [max(weights.get(number, 1.0), 0.000001) for number in available]
        chosen = rng.choices(available, weights=available_weights, k=1)[0]
        selected.append(chosen)
        available.remove(chosen)

    return selected


def _order_by_score(selected: list[int], weights: dict[int, float]) -> list[int]:
    # 抽選は重み付きランダムで多様性を維持しつつ、最終表示はスコア優先で並べる。
    # 同点時は数値昇順に固定して、表示順の揺れを避ける。
    return sorted(selected, key=lambda number: (-weights.get(number, 1.0), number))


def _rank_numbers_by_weight(weights: dict[int, float]) -> list[int]:
    return [
        number
        for number, _ in sorted(
            weights.items(),
            key=lambda item: (-item[1], item[0]),
        )
    ]


def _build_anchor_ticket(
    ranked_numbers: list[int],
    pick_count: int,
) -> list[int]:
    return list(islice(ranked_numbers, pick_count))


def _build_balanced_ticket(
    ranked_numbers: list[int],
    pick_count: int,
) -> list[int]:
    # 上位偏重だけだと口ごとの類似度が高くなるため、
    # 上位4割と中位帯を混ぜた1口を固定で持つ。
    if len(ranked_numbers) <= pick_count:
        return list(ranked_numbers)

    upper_count = max(1, int(pick_count * 0.6))
    upper = ranked_numbers[:upper_count]
    middle_start = upper_count
    middle_end = min(len(ranked_numbers), upper_count + (pick_count * 2))
    middle_pool = ranked_numbers[middle_start:middle_end]
    needed = pick_count - len(upper)
    middle = middle_pool[:needed]
    return upper + middle


def _build_even_odd_ticket(
    ranked_numbers: list[int],
    pick_count: int,
) -> list[int]:
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


def _build_spread_ticket(
    ranked_numbers: list[int],
    pick_count: int,
) -> list[int]:
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


def _build_mixed_depth_ticket(
    ranked_numbers: list[int],
    pick_count: int,
) -> list[int]:
    # 上位だけに寄せすぎず、中位・下位候補を混ぜる口を1つ作る。
    head = ranked_numbers[: max(2, pick_count // 3)]
    mid_start = max(2, pick_count // 3)
    mid_end = min(len(ranked_numbers), mid_start + (pick_count * 2))
    middle = ranked_numbers[mid_start:mid_end]
    tail = ranked_numbers[mid_end : min(len(ranked_numbers), mid_end + (pick_count * 2))]

    ticket = []
    ticket.extend(head[: max(2, pick_count // 3)])
    ticket.extend(middle[: max(2, pick_count // 3)])
    ticket.extend(tail[: pick_count - len(ticket)])

    if len(ticket) < pick_count:
        rest = [number for number in ranked_numbers if number not in ticket]
        ticket.extend(rest[: pick_count - len(ticket)])

    return ticket[:pick_count]


def _build_strategy_tickets(
    ranked_numbers: list[int],
    pick_count: int,
) -> list[list[int]]:
    strategies = [
        _build_anchor_ticket(ranked_numbers, pick_count),
        _build_balanced_ticket(ranked_numbers, pick_count),
        _build_even_odd_ticket(ranked_numbers, pick_count),
        _build_spread_ticket(ranked_numbers, pick_count),
        _build_mixed_depth_ticket(ranked_numbers, pick_count),
    ]
    return [ticket for ticket in strategies if len(ticket) == pick_count]


def generate_predictions(
    number_scores: list[tuple[int, float]],
    lottery_type: str,
    prediction_count: int,
    rng: random.Random | None = None,
    seed: int | None = None,
) -> list[list[int]]:
    """
    統計スコアを重みに使って、重複なしの予想組合せを生成する。

    Args:
        number_scores: 統計スコア計算後の (番号, スコア) 配列。
            history_rows ではなく、UseCase で統計化済みデータを渡す。
        lottery_type: loto6 / loto7 のみを受け付ける。
        prediction_count: 生成する口数。
        rng: テスト用に差し込める乱数生成器。
        seed: rng 未指定時に使う seed。

    Returns:
        1口ごとの番号リスト。1口内の順序はスコア降順で固定する。

    返却する1口内の順序は、当たりやすさの高い番号を先に見せるため、
    "重み降順・同点は数値昇順" で固定する。
    一方で重複判定は順序を無視して番号集合で行う。
    """
    number_min, number_max, pick_count = _lottery_spec(lottery_type)
    if prediction_count <= 0:
        raise ValueError("prediction_count must be greater than 0")

    population_size = number_max - number_min + 1
    if population_size < pick_count:
        raise ValueError("candidate count is smaller than required pick_count")

    max_unique_combinations = math.comb(population_size, pick_count)
    if prediction_count > max_unique_combinations:
        raise ValueError(
            "requested prediction_count exceeds maximum unique combinations"
        )

    population = list(range(number_min, number_max + 1))
    score_map = _normalize_scores(number_scores)
    base_weights = _build_weights(number_min, number_max, score_map)
    ranked_numbers = _rank_numbers_by_weight(base_weights)
    random_source = rng if rng is not None else random.Random(seed)

    predictions: list[list[int]] = []
    seen_combinations: set[tuple[int, ...]] = set()
    number_usage: dict[int, int] = {}

    # 先に戦略ポートフォリオで複数タイプの口を確保し、
    # その後に重み付きランダムで補完する。
    for strategy_ticket in _build_strategy_tickets(ranked_numbers, pick_count):
        if len(predictions) >= prediction_count:
            break

        ordered = _order_by_score(strategy_ticket, base_weights)
        ordered_key = tuple(sorted(ordered))
        if ordered_key in seen_combinations:
            continue

        seen_combinations.add(ordered_key)
        predictions.append(ordered)
        for number in ordered:
            number_usage[number] = number_usage.get(number, 0) + 1

    # 組合せ空間が大きいため、理論上の上限を毎回総当たりせず、
    # 生成済みの重複検知と試行回数上限で現実的に打ち切る。
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
        candidate_key = tuple(sorted(candidate))
        if candidate_key in seen_combinations:
            continue
        seen_combinations.add(candidate_key)
        predictions.append(candidate)
        for number in candidate:
            number_usage[number] = number_usage.get(number, 0) + 1

    if len(predictions) != prediction_count:
        raise ValueError(
            f"failed to generate enough unique predictions: requested={prediction_count} generated={len(predictions)}"
        )

    return predictions
