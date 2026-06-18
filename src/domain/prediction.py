from __future__ import annotations

import math
import random
from dataclasses import dataclass
from itertools import combinations, islice

from src.domain.scorers.pair_cooccurrence import PairConfig
from src.domain.selection.diversity import (
    TicketCandidate,
    jaccard_similarity,
    overlap_count,
    select_diverse_tickets,
)
from src.domain.strategies.ema_recency import EmaRecencyConfig, rank_ema_recency_candidates
from src.domain.strategies.loto6_mixed_v3 import Loto6MixedV3Strategy, build_default_loto6_mixed_v3_config
from src.domain.strategies.mixed_loto6 import MixedLoto6Strategy, build_default_mixed_loto6_config
from src.domain.strategies.mixed_v2 import MixedStrategyV2, build_default_mixed_v2_config
from src.domain.strategies.mixed_v3 import MixedStrategyV3, build_default_mixed_v3_config
from src.domain.strategies.pair_weighted import rank_pair_weighted_candidates
from src.domain.strategies.triple_weighted import (
    TripleWeightedConfig,
    rank_triple_weighted_candidates,
)


"""予想番号生成の中核ロジックをまとめたドメイン層。"""


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
    """
    スコアのリスト形式を辞書形式に正規化

    入力: [(1, 0.08), (2, 0.12), (3, 0.05), ...]  ← タプルリスト
    出力: {1: 0.08, 2: 0.12, 3: 0.05, ...}        ← 辞書型

    負のスコアは除外（アルゴリズムが正値を前提）
    """
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
    """
    スコアを相対的な優劣を保ちながら 0.0～1.0 の範囲に正規化

    【背景】
    異なる統計モデル・パラメータから得られたスコアは、
    スケール（絶対値の大きさ）が異なることがある。
    最大値で除算し「相対的な差」のみに注目することで、
    複数のスコアを公平に比較可能にする

    【計算例】
    元スコア: {1: 0.02, 2: 0.05, 3: 0.01}  → 最大値 = 0.05
    正規化後: {1: 0.4, 2: 1.0, 3: 0.2}      → 最大値 = 1.0

    【全番号対象】
    number_min～number_max の全範囲を対象
    未出現番号（スコア 0.0）も含めて返却
    """
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
    # スコアを重みに変換し、temperature で高スコア優先の強さを調整する。
    # 0 点の番号にも最小重みを残して、完全に選ばれない番号をなくす。
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
    # LOTO7 ではメインとボーナスの両方のスコアを使う。
    # main_ratio / bonus_ratio で重み付けし、用途に応じてどちらを優先するかを変える。
    # 例: メイン寄りなら main_ratio を大きく、ボーナス寄りなら bonus_ratio を大きくする。
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
    # 複数口で同じ番号が固まりすぎないよう、使用済み番号を減衰させる。
    # 口数が増えるほど temperature を下げて、後続の票を多様化しやすくする。
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
    # スコアに応じた確率で抽選し、重複なしで sample_size 個選ぶ。
    # 高スコアほど有利だが、固定順ではなくランダム性を残すことで多様性を確保する。
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
    # 出力を見やすくするため、スコア降順・同点は番号昇順に並べる。
    return sorted(selected, key=lambda number: (-weights.get(number, 1.0), number))


def _rank_numbers_by_weight(weights: dict[int, float]) -> list[int]:
    # 全番号をスコア降順で並べる。
    return [
        number
        for number, _ in sorted(weights.items(), key=lambda item: (-item[1], item[0]))
    ]


def _build_anchor_ticket(ranked_numbers: list[int], pick_count: int) -> list[int]:
    # 上位番号をそのまま採用する、最も保守的な戦略。
    return list(islice(ranked_numbers, pick_count))


def _build_balanced_ticket(ranked_numbers: list[int], pick_count: int) -> list[int]:
    # 上位を残しつつ中位層も混ぜて、確実性と多様性の両方を狙う。
    if len(ranked_numbers) <= pick_count:
        return list(ranked_numbers)

    upper_count = max(1, int(pick_count * 0.6))
    upper = ranked_numbers[:upper_count]
    middle_pool = ranked_numbers[upper_count : upper_count + pick_count * 2]
    return upper + middle_pool[: pick_count - len(upper)]


def _build_even_odd_ticket(ranked_numbers: list[int], pick_count: int) -> list[int]:
    # 偶数・奇数が偏りすぎないように並びを作る。
    top_pool = ranked_numbers[: max(pick_count * 3, pick_count)]
    evens = [number for number in top_pool if number % 2 == 0]
    odds = [number for number in top_pool if number % 2 == 1]

    ticket = evens[: pick_count // 2] + odds[: pick_count - pick_count // 2]

    if len(ticket) < pick_count:
        rest = [number for number in top_pool if number not in ticket]
        ticket.extend(rest[: pick_count - len(ticket)])

    return ticket[:pick_count]


def _build_spread_ticket(ranked_numbers: list[int], pick_count: int) -> list[int]:
    # 上位層を間引いて、広がりのある票を作る。
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
    # 上位・中位・下位を混ぜて、多様性を最大化する。
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
    # 5 種類の戦略で候補チケットを作る。
    candidates = [
        _build_anchor_ticket(ranked_numbers, pick_count),
        _build_balanced_ticket(ranked_numbers, pick_count),
        _build_even_odd_ticket(ranked_numbers, pick_count),
        _build_spread_ticket(ranked_numbers, pick_count),
        _build_mixed_depth_ticket(ranked_numbers, pick_count),
    ]
    return [ticket for ticket in candidates if len(ticket) == pick_count]


def _gap_scores_for_history(
    *,
    history: list[list[int]],
    number_min: int,
    number_max: int,
) -> dict[int, float]:
    # LOTO6 defaultの5口目だけに使う軽いgap補正。未出現間隔を0-1へ正規化し、
    # 低頻度数字を完全に捨てない探索要素として扱う。
    if not history:
        return {number: 0.0 for number in range(number_min, number_max + 1)}

    max_gap = max(1, len(history))
    gaps = {number: max_gap for number in range(number_min, number_max + 1)}
    for index, draw in enumerate(history):
        for value in draw:
            number = int(value)
            if number_min <= number <= number_max and gaps[number] == max_gap:
                gaps[number] = index

    return {
        number: min(1.0, gap / max_gap)
        for number, gap in gaps.items()
    }


def _build_loto6_gap_repair_ticket(
    *,
    base_weights: dict[int, float],
    history: list[list[int]],
    seen: set[tuple[int, ...]],
    rng: random.Random,
) -> list[int] | None:
    # 本線defaultを壊さないため、baseを強めに残しつつgapを薄く混ぜる。
    # 5口目だけseed差を持たせ、同じseedでは再現する探索枠にする。
    number_min, number_max, pick_count = _lottery_spec("loto6")
    gap_scores = _gap_scores_for_history(
        history=history,
        number_min=number_min,
        number_max=number_max,
    )
    max_base = max(base_weights.values(), default=1.0) or 1.0
    blended = {
        number: (
            (base_weights.get(number, 1.0) / max_base) * 0.68
            + gap_scores.get(number, 0.0) * 0.32
            + 0.01
        )
        for number in range(number_min, number_max + 1)
    }
    ranked = _rank_numbers_by_weight(blended)
    gap_ranked = sorted(
        range(number_min, number_max + 1),
        key=lambda number: (-gap_scores.get(number, 0.0), -base_weights.get(number, 1.0), number),
    )
    pool = list(dict.fromkeys(ranked[:18] + gap_ranked[:14]))

    best_ticket: list[int] | None = None
    best_score = -1.0
    for _ in range(40):
        sampled = _weighted_sample_without_replacement(
            population=pool,
            weights=blended,
            sample_size=pick_count,
            rng=rng,
        )
        key = tuple(sorted(sampled))
        if key in seen:
            continue
        score = sum(blended[number] for number in sampled)
        if score > best_score:
            best_score = score
            best_ticket = sampled

    if best_ticket is None:
        for start in range(0, len(ranked) - pick_count + 1):
            candidate = ranked[start : start + pick_count]
            if tuple(sorted(candidate)) not in seen:
                best_ticket = candidate
                break

    if best_ticket is None:
        return None

    return _order_by_score(best_ticket, blended)


def _generate_default_predictions(
    number_scores: list[tuple[int, float]],
    lottery_type: str,
    prediction_count: int,
    rng: random.Random | None = None,
    seed: int | None = None,
    excluded_combinations: set[tuple[int, ...]] | None = None,
    history: list[list[int]] | None = None,
) -> list[list[int]]:
    # 5 つの戦略をまず試し、足りなければランダム抽選で補う。
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

    strategy_tickets = _build_strategy_tickets(ranked_numbers, pick_count)
    normalized_lottery_type = str(lottery_type).strip().lower()

    gap_repair_added = False

    for strategy_ticket in strategy_tickets:
        if len(predictions) >= prediction_count:
            break
        if (
            normalized_lottery_type == "loto6"
            and history
            and not gap_repair_added
            and len(predictions) >= 4
        ):
            gap_ticket = _build_loto6_gap_repair_ticket(
                base_weights=base_weights,
                history=history,
                seen=seen,
                rng=random_source,
            )
            if gap_ticket is not None:
                strategy_ticket = gap_ticket
                gap_repair_added = True

        ordered = _order_by_score(strategy_ticket, base_weights)
        key = tuple(sorted(ordered))

        if key in seen:
            continue

        seen.add(key)
        predictions.append(ordered)

        for number in ordered:
            number_usage[number] = number_usage.get(number, 0) + 1

    if (
        normalized_lottery_type == "loto6"
        and history
        and not gap_repair_added
        and len(predictions) == prediction_count - 1
    ):
        gap_ticket = _build_loto6_gap_repair_ticket(
            base_weights=base_weights,
            history=history,
            seen=seen,
            rng=random_source,
        )
        if gap_ticket is not None:
            ordered = _order_by_score(gap_ticket, base_weights)
            key = tuple(sorted(ordered))
            if key not in seen:
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
    # LOTO7 では 5 種類の見方を持たせて、票ごとに異なる戦略を使う。
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


def _loto7_high_tier_profiles(prediction_count: int) -> list[Loto7Profile]:
    # 2等・3等相当を強く評価できるかを調べる実験用profileです。
    # mixed_v3は壊さず、上位一致を狙う比較戦略として本数字寄りの狭いpoolを多めにします。
    profiles = [
        Loto7Profile(
            name="high_main7_hot_core",
            main_pool_size=15,
            bonus_pool_size=37,
            main_sample_count=7,
            bonus_sample_count=0,
            main_score_ratio=0.97,
            bonus_score_ratio_for_main=0.03,
            bonus_main_ratio=0.30,
            bonus_score_ratio=0.70,
            temperature=0.62,
        ),
        Loto7Profile(
            name="high_main7_balanced_100",
            main_pool_size=18,
            bonus_pool_size=37,
            main_sample_count=7,
            bonus_sample_count=0,
            main_score_ratio=0.93,
            bonus_score_ratio_for_main=0.07,
            bonus_main_ratio=0.32,
            bonus_score_ratio=0.68,
            temperature=0.78,
        ),
        Loto7Profile(
            name="high_main6_bonus1",
            main_pool_size=18,
            bonus_pool_size=16,
            main_sample_count=6,
            bonus_sample_count=1,
            main_score_ratio=0.91,
            bonus_score_ratio_for_main=0.09,
            bonus_main_ratio=0.20,
            bonus_score_ratio=0.80,
            temperature=0.72,
        ),
        Loto7Profile(
            name="high_main7_long_support",
            main_pool_size=20,
            bonus_pool_size=37,
            main_sample_count=7,
            bonus_sample_count=0,
            main_score_ratio=0.90,
            bonus_score_ratio_for_main=0.10,
            bonus_main_ratio=0.35,
            bonus_score_ratio=0.65,
            temperature=0.86,
        ),
        Loto7Profile(
            name="high_main5_bonus2_cover",
            main_pool_size=22,
            bonus_pool_size=20,
            main_sample_count=5,
            bonus_sample_count=2,
            main_score_ratio=0.88,
            bonus_score_ratio_for_main=0.12,
            bonus_main_ratio=0.22,
            bonus_score_ratio=0.78,
            temperature=0.92,
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
    # プロフィールごとに重みとプールを変えて、同じ履歴から別の視点を作る。
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
    # 2 等を狙いやすいよう、LOTO7 専用の 5 プロフィールで予想する。
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


def generate_loto7_high_tier_predictions(
    main_scores: list[tuple[int, float]],
    bonus_scores: list[tuple[int, float]],
    prediction_count: int,
    rng: random.Random | None = None,
    seed: int | None = None,
    excluded_combinations: set[tuple[int, ...]] | None = None,
) -> list[list[int]]:
    # 2等・3等相当を強く意識する実験用生成関数です。
    # 5口全体の広さよりも、本数字5個以上に届きやすい狭めの上位poolを優先します。
    if prediction_count <= 0:
        raise ValueError("prediction_count must be greater than 0")

    random_source = rng if rng is not None else random.Random(seed)

    main_score_map = _normalize_scores(main_scores)
    bonus_score_map = _normalize_scores(bonus_scores)

    predictions: list[list[int]] = []
    seen = set(excluded_combinations or set())

    for ticket_index, profile in enumerate(_loto7_high_tier_profiles(prediction_count)):
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
            f"failed to generate enough high-tier predictions: "
            f"requested={prediction_count} generated={len(predictions)}"
        )

    return predictions


def _score_ticket(ticket: list[int], number_scores: dict[int, float]) -> float:
    return sum(number_scores.get(number, 0.0) for number in ticket)


def _generate_predictions_primitive(
    number_scores: list[tuple[int, float]],
    lottery_type: str,
    prediction_count: int,
    rng: random.Random | None = None,
    seed: int | None = None,
    strategy: str = "default",
    bonus_scores: list[tuple[int, float]] | None = None,
    history: list[list[int]] | None = None,
    pair_config: PairConfig | None = None,
    triple_config: TripleWeightedConfig | None = None,
    ema_config: EmaRecencyConfig | None = None,
    target_draw: int = 0,
    history_limit: int = 0,
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
            history=history,
        )

    if normalized_strategy == "mixed":
        if normalized_lottery_type != "loto7" or bonus_scores is None:
            return _generate_default_predictions(
                number_scores=number_scores,
                lottery_type=normalized_lottery_type,
                prediction_count=prediction_count,
                rng=rng,
                seed=seed,
                history=history,
            )

        return generate_loto7_second_prize_oriented_predictions(
            main_scores=number_scores,
            bonus_scores=bonus_scores,
            prediction_count=prediction_count,
            rng=rng,
            seed=None if seed is None else seed + 10_000,
            excluded_combinations=None,
        )

    if normalized_strategy == "high_tier_v1":
        if normalized_lottery_type != "loto7" or bonus_scores is None:
            raise ValueError("high_tier_v1 is only supported for loto7 with bonus_scores")

        return generate_loto7_high_tier_predictions(
            main_scores=number_scores,
            bonus_scores=bonus_scores,
            prediction_count=prediction_count,
            rng=rng,
            seed=None if seed is None else seed + 30_000,
            excluded_combinations=None,
        )

    if normalized_strategy == "mixed_loto6":
        if normalized_lottery_type != "loto6":
            raise ValueError("mixed_loto6 is only supported for loto6")
        if history is None:
            raise ValueError("history is required for mixed_loto6")

        config = build_default_mixed_loto6_config()
        strategy_impl = MixedLoto6Strategy(config)
        return strategy_impl.generate_predictions(
            history=history,
            prediction_count=prediction_count,
            seed=seed or 0,
            number_scores=number_scores,
            target_draw=target_draw,
            history_limit=history_limit,
        )

    if normalized_strategy == "pair_weighted":
        if normalized_lottery_type != "loto7":
            raise ValueError("pair_weighted is only supported for loto7")
        if history is None:
            raise ValueError("history is required for pair_weighted strategy")

        return rank_pair_weighted_candidates(
            history=history,
            prediction_count=prediction_count,
            seed=seed or 0,
            config=pair_config or PairConfig(),
        )

    if normalized_strategy == "ema_recency":
        if normalized_lottery_type != "loto7":
            raise ValueError("ema_recency is only supported for loto7")
        if history is None:
            raise ValueError("history is required for ema_recency strategy")

        return rank_ema_recency_candidates(
            history=history,
            prediction_count=prediction_count,
            seed=seed or 0,
            config=ema_config or EmaRecencyConfig(),
        )

    if normalized_strategy == "mixed_v2":
        if normalized_lottery_type != "loto7":
            raise ValueError("mixed_v2 is only supported for loto7")
        if bonus_scores is None:
            raise ValueError("bonus_scores is required for mixed_v2")
        if history is None:
            raise ValueError("history is required for mixed_v2")

        config = build_default_mixed_v2_config()
        strategy_impl = MixedStrategyV2(config)
        return strategy_impl.generate_predictions(
            history=history,
            prediction_count=prediction_count,
            seed=seed or 0,
            number_scores=number_scores,
            bonus_scores=bonus_scores,
            target_draw=target_draw,
            history_limit=history_limit,
        )

    if normalized_strategy == "mixed_v3":
        if normalized_lottery_type == "loto6":
            if history is None:
                raise ValueError("history is required for loto6 mixed_v3")
            config = build_default_loto6_mixed_v3_config()
            strategy_impl = Loto6MixedV3Strategy(config)
            return strategy_impl.generate_predictions(
                history=history,
                prediction_count=prediction_count,
                seed=seed or 0,
                target_draw=target_draw,
                history_limit=history_limit,
            )
        if normalized_lottery_type != "loto7":
            raise ValueError("mixed_v3 is only supported for loto6/loto7")
        if bonus_scores is None:
            raise ValueError("bonus_scores is required for mixed_v3")
        if history is None:
            raise ValueError("history is required for mixed_v3")

        config = build_default_mixed_v3_config()
        strategy_impl = MixedStrategyV3(config)
        return strategy_impl.generate_predictions(
            history=history,
            prediction_count=prediction_count,
            seed=seed or 0,
            number_scores=number_scores,
            bonus_scores=bonus_scores,
            target_draw=target_draw,
            history_limit=history_limit,
        )

    if normalized_strategy == "triple_weighted":
        if normalized_lottery_type != "loto7":
            raise ValueError("triple_weighted is only supported for loto7")
        if history is None:
            raise ValueError("history is required for triple_weighted strategy")

        config = triple_config or TripleWeightedConfig()
        return rank_triple_weighted_candidates(
            history=history,
            prediction_count=prediction_count,
            seed=seed or 0,
            config=config,
            target_draw=target_draw,
            history_limit=history_limit,
        )

    raise ValueError(
        f"Unknown strategy: {normalized_strategy}. Supported strategies are: "
        "default, mixed, mixed_loto6, mixed_v2, mixed_v3, high_tier_v1, pair_weighted, "
        "ema_recency, triple_weighted."
    )


def _build_candidate_pool(
    number_scores: list[tuple[int, float]],
    lottery_type: str,
    prediction_count: int,
    seed: int | None,
    strategy: str,
    bonus_scores: list[tuple[int, float]] | None,
    history: list[list[int]] | None,
    pair_config: PairConfig | None,
    triple_config: TripleWeightedConfig | None,
    ema_config: EmaRecencyConfig | None,
    candidate_pool_size: int,
    target_draw: int = 0,
    history_limit: int = 0,
) -> list[TicketCandidate]:
    score_map = _normalize_scores(number_scores)
    pool: list[TicketCandidate] = []
    seen: set[tuple[int, ...]] = set()
    seed_base = seed or 0
    attempts = 0
    max_attempts = max(10, candidate_pool_size * 2)

    while len(pool) < candidate_pool_size and attempts < max_attempts:
        batch_seed = seed_base + attempts
        predictions = _generate_predictions_primitive(
            number_scores=number_scores,
            lottery_type=lottery_type,
            prediction_count=prediction_count,
            rng=None,
            seed=batch_seed,
            strategy=strategy,
            bonus_scores=bonus_scores,
            history=history,
            pair_config=pair_config,
            triple_config=triple_config,
            ema_config=ema_config,
            target_draw=target_draw,
            history_limit=history_limit,
        )

        for prediction in predictions:
            key = tuple(sorted(prediction))
            if key in seen:
                continue
            seen.add(key)
            pool.append(
                TicketCandidate(
                    numbers=list(key),
                    score=_score_ticket(list(key), score_map),
                )
            )
            if len(pool) >= candidate_pool_size:
                break

        attempts += 1

    return pool


def _compute_diversity_metrics(predictions: list[list[int]]) -> tuple[float, float, int]:
    if not predictions:
        return 0.0, 0.0, 0

    pairwise_jaccard: list[float] = []
    pairwise_overlap: list[int] = []
    unique_numbers = set()

    for index_a, index_b in combinations(range(len(predictions)), 2):
        a = predictions[index_a]
        b = predictions[index_b]
        similarity = jaccard_similarity(a, b)
        pairwise_jaccard.append(similarity)
        pairwise_overlap.append(overlap_count(a, b))

    avg_jaccard = sum(pairwise_jaccard) / len(pairwise_jaccard) if pairwise_jaccard else 0.0
    avg_overlap = sum(pairwise_overlap) / len(pairwise_overlap) if pairwise_overlap else 0.0
    for ticket in predictions:
        unique_numbers.update(ticket)

    return avg_jaccard, avg_overlap, len(unique_numbers)


def generate_predictions(
    number_scores: list[tuple[int, float]],
    lottery_type: str,
    prediction_count: int,
    rng: random.Random | None = None,
    seed: int | None = None,
    strategy: str = "default",
    bonus_scores: list[tuple[int, float]] | None = None,
    history: list[list[int]] | None = None,
    pair_config: PairConfig | None = None,
    triple_config: TripleWeightedConfig | None = None,
    ema_config: EmaRecencyConfig | None = None,
    selector_max_overlap: int | None = None,
    selector_min_jaccard_distance: float | None = None,
    selector_candidate_pool_size: int | None = None,
    selector_diversity_weight: float | None = None,
    target_draw: int = 0,
    history_limit: int = 0,
) -> list[list[int]]:
    predictions = _generate_predictions_primitive(
        number_scores=number_scores,
        lottery_type=lottery_type,
        prediction_count=prediction_count,
        rng=rng,
        seed=seed,
        strategy=strategy,
        bonus_scores=bonus_scores,
        history=history,
        pair_config=pair_config,
        triple_config=triple_config,
        ema_config=ema_config,
        target_draw=target_draw,
        history_limit=history_limit,
    )

    if selector_candidate_pool_size is None or selector_candidate_pool_size <= prediction_count:
        return predictions

    candidate_pool = _build_candidate_pool(
        number_scores=number_scores,
        lottery_type=lottery_type,
        prediction_count=prediction_count,
        seed=seed,
        strategy=strategy,
        bonus_scores=bonus_scores,
        history=history,
        pair_config=pair_config,
        triple_config=triple_config,
        ema_config=ema_config,
        candidate_pool_size=selector_candidate_pool_size,
        target_draw=target_draw,
        history_limit=history_limit,
    )

    if not candidate_pool:
        return predictions

    selected_candidates = select_diverse_tickets(
        candidates=candidate_pool,
        prediction_count=prediction_count,
        max_overlap=selector_max_overlap or 4,
        min_jaccard_distance=selector_min_jaccard_distance or 0.43,
        diversity_weight=selector_diversity_weight or 0.25,
    )

    if len(selected_candidates) != prediction_count:
        return predictions

    return [candidate.numbers for candidate in selected_candidates]
