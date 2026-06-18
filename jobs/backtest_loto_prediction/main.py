"""バックテストツール: LOTO6/7 の予想戦略を事後検証する CLI。"""

from __future__ import annotations

# This CLI performs rolling backtests for LOTO6/LOTO7 strategies.
# It trains only on draws before each target draw and reports historical
# reference metrics for strategy/profile/history_limit/seed comparisons.
import argparse
import json
import os
import sys
from itertools import combinations
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parents[2]
sys.path.append(str(PROJECT_ROOT))

from src.domain.prediction import generate_predictions
from src.domain.scorers.pair_cooccurrence import PairConfig
from src.domain.statistics import (
    ScoreWeights,
    calculate_bonus_number_scores,
    calculate_main_number_scores,
)
from src.domain.strategies.ema_recency import EmaRecencyConfig
from src.domain.strategies.mixed_loto6 import (
    MIXED_LOTO6_PROFILES,
    PROFILE_ROLES as LOTO6_PROFILE_ROLES,
)
from src.domain.strategies.mixed_v2 import build_lane3_pair_weighted_scores
from src.domain.strategies.mixed_v3 import (
    MIXED_V3_PROFILES,
    PROFILE_ROLES,
)
from src.domain.strategies.triple_weighted import TripleWeightedConfig, build_triple_weighted_scores
from src.evaluation.expected_value import compute_expected_value
from src.evaluation.prize_tables import prize_table_for_draw


LOTTERY_SPECS = {
    "loto6": {
        "pick_count": 6,
        "bonus_count": 1,
        "bq_table_env": "BQ_TABLE_LOTO6_HISTORY",
        "default_table": "loto6_history",
    },
    "loto7": {
        "pick_count": 7,
        "bonus_count": 2,
        "bq_table_env": "BQ_TABLE_LOTO7_HISTORY",
        "default_table": "loto7_history",
    },
}


LOTO7_PROFILE_BY_TICKET_NO = {
    1: "main_hot",
    2: "main_balanced",
    3: "main_wide_bonus_hot",
    4: "main5_bonus2_balanced",
    5: "main5_bonus2_explore",
}

LOTO7_PROFILE_BY_TICKET_NO_MIXED_V2 = {
    1: "lane1_ema_hot_or_main_hot",
    2: "lane2_main_balanced_or_ema_balanced",
    3: "lane3_pair_weighted",
    4: "lane4_bonus2_balanced",
    5: "lane5_diverse_explore",
}

LOTO7_PROFILE_BY_TICKET_NO_MIXED_V3 = {
    index: profile
    for index, profile in enumerate(MIXED_V3_PROFILES, start=1)
}

LOTO7_PROFILE_BY_TICKET_NO_HIGH_TIER = {
    1: "high_main7_hot_core",
    2: "high_main7_balanced_100",
    3: "high_main6_bonus1",
    4: "high_main7_long_support",
    5: "high_main5_bonus2_cover",
}

LOTO6_PROFILE_BY_TICKET_NO_MIXED = {
    index: profile
    for index, profile in enumerate(MIXED_LOTO6_PROFILES, start=1)
}


def _normalize_lottery_type(lottery_type: str) -> str:
    normalized = str(lottery_type).strip().lower()
    if normalized not in LOTTERY_SPECS:
        raise ValueError("lottery_type must be loto6 or loto7")
    return normalized


def _parse_int_csv(value: str | None) -> list[int]:
    if not value:
        return []
    return [int(item.strip()) for item in value.split(",") if item.strip()]


def _load_jsonl_rows(path: str, lottery_type: str) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []

    with open(path, "r", encoding="utf-8") as file:
        for line_no, line in enumerate(file, start=1):
            text = line.strip()
            if not text:
                continue
            try:
                row = json.loads(text)
            except json.JSONDecodeError as exc:
                raise ValueError(f"invalid JSONL at line {line_no}: {exc}") from exc

            if str(row.get("lottery_type", "")).lower() == lottery_type:
                rows.append(row)

    return rows


def _load_bigquery_rows(
    *,
    project_id: str,
    dataset: str,
    table: str,
    lottery_type: str,
    min_target_draw_no: int,
    max_target_draw_no: int,
    max_history_limit: int,
) -> list[dict[str, Any]]:
    try:
        from google.cloud import bigquery
    except ImportError as exc:
        raise RuntimeError(
            "google-cloud-bigquery is required when --input-jsonl is not specified."
        ) from exc

    client = bigquery.Client(project=project_id)
    table_id = f"`{project_id}.{dataset}.{table}`"

    spec = LOTTERY_SPECS[lottery_type]
    pick_count = int(spec["pick_count"])
    bonus_count = int(spec["bonus_count"])

    number_columns = ", ".join(f"n{i}" for i in range(1, pick_count + 1))
    bonus_columns = ", ".join(f"b{i}" for i in range(1, bonus_count + 1))

    min_draw_no = max(1, min_target_draw_no - max_history_limit - 50)

    query = f"""
        SELECT
          lottery_type,
          draw_no,
          draw_date,
          {number_columns},
          {bonus_columns},
          source_url
        FROM {table_id}
        WHERE lottery_type = @lottery_type
          AND draw_no BETWEEN @min_draw_no AND @max_target_draw_no
        ORDER BY draw_no DESC
    """

    job_config = bigquery.QueryJobConfig(
        query_parameters=[
            bigquery.ScalarQueryParameter("lottery_type", "STRING", lottery_type),
            bigquery.ScalarQueryParameter("min_draw_no", "INT64", min_draw_no),
            bigquery.ScalarQueryParameter("max_target_draw_no", "INT64", max_target_draw_no),
        ]
    )

    result = client.query(query, job_config=job_config).result()
    return [dict(row) for row in result]


def _normalize_rows(rows: list[dict[str, Any]], lottery_type: str) -> list[dict[str, Any]]:
    spec = LOTTERY_SPECS[lottery_type]
    pick_count = int(spec["pick_count"])
    bonus_count = int(spec["bonus_count"])

    normalized: list[dict[str, Any]] = []

    for row in rows:
        if int(row.get("draw_no", 0)) <= 0:
            continue

        normalized_row = dict(row)
        normalized_row["lottery_type"] = lottery_type
        normalized_row["draw_no"] = int(normalized_row["draw_no"])

        for index in range(1, pick_count + 1):
            key = f"n{index}"
            if normalized_row.get(key) is None:
                raise ValueError(f"missing {key}: draw_no={normalized_row['draw_no']}")
            normalized_row[key] = int(normalized_row[key])

        for index in range(1, bonus_count + 1):
            key = f"b{index}"
            if normalized_row.get(key) is not None:
                normalized_row[key] = int(normalized_row[key])

        normalized.append(normalized_row)

    return sorted(normalized, key=lambda row: int(row["draw_no"]), reverse=True)


def _extract_main_draws(rows: list[dict[str, Any]], lottery_type: str) -> list[list[int]]:
    """過去の当せん結果から「本数」だけを抽出"""
    pick_count = int(LOTTERY_SPECS[lottery_type]["pick_count"])
    return [
        [int(row[f"n{index}"]) for index in range(1, pick_count + 1)]
        for row in rows
    ]


def _extract_bonus_draws(rows: list[dict[str, Any]], lottery_type: str) -> list[list[int]]:
    """過去の当せん結果から「ボーナス数」だけを抽出"""
    bonus_count = int(LOTTERY_SPECS[lottery_type]["bonus_count"])
    result: list[list[int]] = []

    for row in rows:
        bonuses: list[int] = []
        for index in range(1, bonus_count + 1):
            key = f"b{index}"
            if row.get(key) is not None:
                bonuses.append(int(row[key]))
        result.append(bonuses)

    return result


def _extract_target_numbers(
    target_row: dict[str, Any],
    lottery_type: str,
) -> tuple[set[int], set[int]]:
    pick_count = int(LOTTERY_SPECS[lottery_type]["pick_count"])
    bonus_count = int(LOTTERY_SPECS[lottery_type]["bonus_count"])

    target_main = {
        int(target_row[f"n{index}"])
        for index in range(1, pick_count + 1)
    }
    target_bonus = {
        int(target_row[f"b{index}"])
        for index in range(1, bonus_count + 1)
        if target_row.get(f"b{index}") is not None
    }

    return target_main, target_bonus


def _judge_loto6_prize(main_match: int, bonus_match: int) -> str:
    """LOTO6 の当選判定（6個マッチ=1等、5個+bonus=2等...）"""
    if main_match == 6:
        return "1等相当"
    if main_match == 5 and bonus_match >= 1:
        return "2等相当"
    if main_match == 5:
        return "3等相当"
    if main_match == 4:
        return "4等相当"
    if main_match == 3:
        return "5等相当"
    return "該当なし"


def _judge_loto7_prize(main_match: int, bonus_match: int) -> str:
    """LOTO7 の当選判定（7個マッチ=1等、6個+bonus=2等...）"""
    if main_match == 7:
        return "1等相当"
    if main_match == 6 and bonus_match >= 1:
        return "2等相当"
    if main_match == 6:
        return "3等相当"
    if main_match == 5:
        return "4等相当"
    if main_match == 4:
        return "5等相当"
    if main_match == 3 and bonus_match >= 1:
        return "6等相当"
    return "該当なし"


def _judge_prize(lottery_type: str, main_match: int, bonus_match: int) -> str:
    if lottery_type == "loto6":
        return _judge_loto6_prize(main_match, bonus_match)
    if lottery_type == "loto7":
        return _judge_loto7_prize(main_match, bonus_match)
    raise ValueError(f"unsupported lottery_type: {lottery_type}")


def _score_near_miss(lottery_type: str, main_match: int, bonus_match: int) -> int:
    if lottery_type == "loto7":
        if main_match == 7:
            return 5000
        if main_match == 6 and bonus_match >= 1:
            return 3000
        if main_match == 6:
            return 1500
        if main_match == 5 and bonus_match >= 1:
            return 800
        if main_match == 5:
            return 500
        if main_match == 4 and bonus_match >= 1:
            return 200
        if main_match == 4:
            return 100
        if main_match == 3 and bonus_match >= 1:
            return 50
        return 0

    if main_match == 6:
        return 5000
    if main_match == 5 and bonus_match >= 1:
        return 3000
    if main_match == 5:
        return 1500
    if main_match == 4:
        return 500
    if main_match == 3:
        return 100
    return 0


def _build_training_rows(
    rows: list[dict[str, Any]],
    target_draw_no: int,
    history_limit: int,
) -> list[dict[str, Any]]:
    train_rows = [
        row for row in rows
        if int(row["draw_no"]) < target_draw_no
    ]
    return sorted(train_rows, key=lambda row: int(row["draw_no"]), reverse=True)[:history_limit]


def _compute_diversity_metrics(predictions: list[list[int]]) -> tuple[float, float, int]:
    if not predictions:
        return 0.0, 0.0, 0

    pairwise_jaccard: list[float] = []
    pairwise_overlap: list[int] = []
    unique_numbers = set()

    for index_a, index_b in combinations(range(len(predictions)), 2):
        a = predictions[index_a]
        b = predictions[index_b]
        intersection = set(a) & set(b)
        union = set(a) | set(b)
        pairwise_jaccard.append(len(intersection) / len(union) if union else 0.0)
        pairwise_overlap.append(len(intersection))

    avg_jaccard = sum(pairwise_jaccard) / len(pairwise_jaccard) if pairwise_jaccard else 0.0
    avg_overlap = sum(pairwise_overlap) / len(pairwise_overlap) if pairwise_overlap else 0.0
    for ticket in predictions:
        unique_numbers.update(ticket)

    return avg_jaccard, avg_overlap, len(unique_numbers)


def _score_breakdown_for_ticket(
    *,
    strategy: str,
    profile_name: str,
    prediction: list[int],
    history: list[list[int]],
    main_score_map: dict[int, float],
    bonus_score_map: dict[int, float] | None = None,
    pair_config: PairConfig | None = None,
    triple_config: TripleWeightedConfig | None = None,
) -> dict[str, Any]:
    base_values = list(main_score_map.values())
    max_base = max(base_values, default=0.0)
    base = (
        sum(main_score_map.get(number, 0.0) for number in prediction)
        / (max_base * len(prediction))
        if max_base > 0 and prediction
        else 0.0
    )
    breakdown: dict[str, Any] = {
        "base": round(base, 6),
        "ema": 0.0,
        "pair": 0.0,
        "triple": 0.0,
        "pair_affinity": 0.0,
        "bonus_affinity": 0.0,
        "coverage_gap": 0.0,
        "combination_fit": 0.0,
        "diversity_penalty": 0.0,
        "fallback_used": False,
    }

    if strategy == "mixed_v2" and profile_name == "lane3_pair_weighted":
        selected: list[int] = []
        pair_rows: list[dict[str, float | bool]] = []
        for number in prediction:
            rows = build_lane3_pair_weighted_scores(
                history=history,
                main_score_map=main_score_map,
                selected=selected,
                config=pair_config or PairConfig(),
            )
            row = rows.get(number)
            if row is not None:
                pair_rows.append(row)
            selected.append(number)
        if pair_rows:
            breakdown.update(
                {
                    "base": round(sum(float(row["base"]) for row in pair_rows) / len(pair_rows), 6),
                    "ema": round(sum(float(row["ema"]) for row in pair_rows) / len(pair_rows), 6),
                    "pair": round(sum(float(row["pair"]) for row in pair_rows) / len(pair_rows), 6),
                    "triple": 0.0,
                    "diversity_penalty": 0.0,
                    "fallback_used": any(bool(row["fallback_used"]) for row in pair_rows),
                }
            )

    if strategy == "triple_weighted":
        selected = []
        triple_rows: list[dict[str, float | bool]] = []
        config = triple_config or TripleWeightedConfig()
        for number in prediction:
            rows = build_triple_weighted_scores(
                history=history,
                selected=selected,
                config=config,
            )
            row = rows.get(number)
            if row is not None:
                triple_rows.append(row)
            selected.append(number)
        if triple_rows:
            breakdown.update(
                {
                    "base": round(sum(float(row["base"]) for row in triple_rows) / len(triple_rows), 6),
                    "ema": round(sum(float(row["ema"]) for row in triple_rows) / len(triple_rows), 6),
                    "pair": round(sum(float(row["pair"]) for row in triple_rows) / len(triple_rows), 6),
                    "triple": round(sum(float(row["triple"]) for row in triple_rows) / len(triple_rows), 6),
                    "diversity_penalty": 0.0,
                    "fallback_used": any(bool(row["fallback_used"]) for row in triple_rows),
                }
            )

    if strategy == "mixed_v3":
        # Backtests can emit hundreds of thousands of ticket rows. Recomputing the
        # full profile scoring table for every emitted ticket makes JSONL output
        # dominate runtime, so this trace uses already computed score maps and
        # leaves generation-time scoring unchanged.
        bonus_score_map = bonus_score_map or {number: 0.0 for number in range(1, 38)}
        if prediction:
            max_bonus = max(bonus_score_map.values(), default=0.0)
            bonus_affinity = (
                sum(bonus_score_map.get(number, 0.0) for number in prediction)
                / (max_bonus * len(prediction))
                if max_bonus > 0
                else 0.0
            )
            breakdown["primary_frequency"] = breakdown["base"]
            breakdown["secondary_frequency"] = breakdown["base"]
            breakdown["recent_frequency"] = breakdown["base"]
            breakdown["ema_recent"] = breakdown["base"]
            breakdown["pair_affinity"] = 0.0
            breakdown["bonus_affinity"] = round(bonus_affinity, 6)
            breakdown["coverage_gap"] = 0.0
            breakdown["gap"] = 0.0
            breakdown["trend"] = 0.0
            breakdown["combination_fit"] = 0.0
            breakdown["ema"] = breakdown["base"]
            breakdown["pair"] = 0.0
            breakdown["triple"] = 0.0

    if strategy == "mixed_loto6":
        # Keep LOTO6 JSONL trace compatible with the LOTO7 strategy metadata.
        # Generation-time profile scoring lives in mixed_loto6.py; this lightweight
        # trace exposes the comparable high-level components without rerunning the
        # candidate search for every ticket.
        breakdown["primary_frequency"] = breakdown["base"]
        breakdown["secondary_frequency"] = breakdown["base"]
        breakdown["recent_frequency"] = breakdown["base"]
        breakdown["long_frequency"] = breakdown["base"]
        breakdown["gap"] = 0.0
        breakdown["trend"] = 0.0
        breakdown["combination_fit"] = 0.0
        breakdown["ema"] = breakdown["base"]

    return breakdown


def _evaluate_once(
    *,
    rows: list[dict[str, Any]],
    lottery_type: str,
    target_draw_no: int,
    history_limit: int,
    prediction_count: int,
    strategy: str,
    seed: int,
    pair_config: PairConfig | None = None,
    triple_config: TripleWeightedConfig | None = None,
    ema_config: EmaRecencyConfig | None = None,
    selector_max_overlap: int | None = None,
    selector_min_jaccard_distance: float | None = None,
    selector_candidate_pool_size: int | None = None,
    selector_diversity_weight: float | None = None,
) -> dict[str, Any]:
    """
    単一の draw に対して、1 回の予想生成を実施

    【処理流れ】
    1. target_draw_no の実際の当せん番号を取得
    2. その draw より前の history_limit 件の履歴から統計計算
    3. 統計に基づいて prediction_count 口の予想を生成
    4. 5 票それぞれについて、マッチング数と当選等級を判定
    5. 最良スコア、1 等/2 等の出現有無を返却

    【output】
    {
        'lottery_type': 'loto7',
        'target_draw_no': 600,
        'tickets': [
            {
                'ticket_no': 1,
                'profile_name': 'main_hot',
                'main_match': 3,
                'bonus_match': 0,
                'prize': '4等相当',
                'near_miss_score': 500
            },
            ...
        ],
        'best_main_match': 4,
        'best_bonus_match': 1,
        'best_prize': '5等相当',
        'first_prize_found': false,
        'second_prize_found': true
    }
    """
    target_row = next(
        (row for row in rows if int(row["draw_no"]) == target_draw_no),
        None,
    )
    if target_row is None:
        raise ValueError(f"target draw not found: {target_draw_no}")

    train_rows = _build_training_rows(rows, target_draw_no, history_limit)
    if not train_rows:
        raise ValueError(f"no training rows found before target draw: {target_draw_no}")

    target_main, target_bonus = _extract_target_numbers(target_row, lottery_type)

    main_draws = _extract_main_draws(train_rows, lottery_type)
    bonus_draws = _extract_bonus_draws(train_rows, lottery_type)

    weights = ScoreWeights()
    main_scores = calculate_main_number_scores(main_draws, weights)
    bonus_scores = calculate_bonus_number_scores(bonus_draws, weights)

    strategy_history = main_draws
    if strategy == "ema_recency" and ema_config is not None and ema_config.include_bonus:
        strategy_history = [
            sorted(set(main + bonus))
            for main, bonus in zip(main_draws, bonus_draws)
        ]

    predictions = generate_predictions(
        number_scores=main_scores,
        bonus_scores=bonus_scores,
        lottery_type=lottery_type,
        prediction_count=prediction_count,
        strategy=strategy,
        seed=seed,
        target_draw=target_draw_no,
        history_limit=history_limit,
        history=strategy_history,
        pair_config=pair_config,
        triple_config=triple_config,
        ema_config=ema_config,
        selector_max_overlap=selector_max_overlap,
        selector_min_jaccard_distance=selector_min_jaccard_distance,
        selector_candidate_pool_size=selector_candidate_pool_size,
        selector_diversity_weight=selector_diversity_weight,
    )

    tickets: list[dict[str, Any]] = []
    best_main_match = 0
    best_bonus_match = 0
    best_prize = "該当なし"
    best_near_miss_score = 0
    second_prize_found = False
    first_prize_found = False

    for ticket_no, prediction in enumerate(predictions, start=1):
        prediction_set = set(prediction)
        main_match = len(prediction_set & target_main)
        bonus_match = len(prediction_set & target_bonus)
        prize = _judge_prize(lottery_type, main_match, bonus_match)
        near_miss_score = _score_near_miss(lottery_type, main_match, bonus_match)

        if prize == "1等相当":
            first_prize_found = True
        if prize == "2等相当":
            second_prize_found = True

        if (
            near_miss_score > best_near_miss_score
            or (
                near_miss_score == best_near_miss_score
                and (
                    main_match > best_main_match
                    or (
                        main_match == best_main_match
                        and bonus_match > best_bonus_match
                    )
                )
            )
        ):
            best_main_match = main_match
            best_bonus_match = bonus_match
            best_prize = prize
            best_near_miss_score = near_miss_score

        if lottery_type == "loto7":
            if strategy == "mixed_v3":
                profile_name = LOTO7_PROFILE_BY_TICKET_NO_MIXED_V3.get(ticket_no, f"lane_{ticket_no}")
            elif strategy == "high_tier_v1":
                profile_name = LOTO7_PROFILE_BY_TICKET_NO_HIGH_TIER.get(ticket_no, f"high_tier_{ticket_no}")
            elif strategy == "mixed_v2":
                profile_name = LOTO7_PROFILE_BY_TICKET_NO_MIXED_V2.get(ticket_no, f"lane_{ticket_no}")
            elif strategy == "triple_weighted":
                profile_name = f"triple_weighted_ticket_{ticket_no}"
            else:
                profile_name = LOTO7_PROFILE_BY_TICKET_NO.get(ticket_no, f"profile_{ticket_no}")
        elif strategy == "mixed_v3":
            profile_name = f"loto6_mixed_v3_ticket_{ticket_no}"
        elif strategy == "mixed_loto6":
            profile_name = LOTO6_PROFILE_BY_TICKET_NO_MIXED.get(ticket_no, f"l6_ticket_{ticket_no}")
        else:
            profile_name = f"ticket_{ticket_no}"

        score_breakdown = _score_breakdown_for_ticket(
            strategy=strategy,
            profile_name=profile_name,
            prediction=prediction,
            history=strategy_history,
            main_score_map=dict(main_scores),
            bonus_score_map=dict(bonus_scores),
            pair_config=pair_config,
            triple_config=triple_config,
        )
        score = round(
            float(score_breakdown["base"])
            + float(score_breakdown["ema"])
            + float(score_breakdown["pair"])
            + float(score_breakdown["triple"])
            - float(score_breakdown["diversity_penalty"]),
            6,
        )

        tickets.append(
            {
                "ticket_no": ticket_no,
                "profile_name": profile_name,
                "prediction": prediction,
                "score": score,
                "score_breakdown": score_breakdown,
                "main_match": main_match,
                "bonus_match": bonus_match,
                "prize": prize,
                "near_miss_score": near_miss_score,
            }
        )

    avg_pairwise_jaccard, avg_pairwise_overlap, unique_number_coverage = _compute_diversity_metrics(predictions)

    prize_counts: dict[str, int] = {}
    for ticket in tickets:
        prize = ticket["prize"]
        prize_counts[prize] = prize_counts.get(prize, 0) + 1

    if lottery_type == "loto7":
        prize_table = prize_table_for_draw(lottery_type, target_draw_no)
        ev_metrics = compute_expected_value(prize_counts, prize_table)
    else:
        ev_metrics = {
            "expected_value_sum": 0.0,
            "expected_value_per_ticket": 0.0,
            "roi_proxy": 0.0,
            "prize_table_version": "unsupported",
        }

    return {
        "lottery_type": lottery_type,
        "target_draw_no": target_draw_no,
        "target_draw_date": str(target_row.get("draw_date")),
        "target_main": sorted(target_main),
        "target_bonus": sorted(target_bonus),
        "history_limit": history_limit,
        "history_count": len(train_rows),
        "prediction_count": prediction_count,
        "strategy": strategy,
        "seed": seed,
        "tickets": tickets,
        "best_main_match": best_main_match,
        "best_bonus_match": best_bonus_match,
        "best_prize": best_prize,
        "best_near_miss_score": best_near_miss_score,
        "first_prize_found": first_prize_found,
        "second_prize_found": second_prize_found,
        "avg_pairwise_jaccard": round(avg_pairwise_jaccard, 4),
        "avg_pairwise_overlap": round(avg_pairwise_overlap, 4),
        "unique_number_coverage": unique_number_coverage,
        "expected_value_sum": ev_metrics["expected_value_sum"],
        "expected_value_per_ticket": ev_metrics["expected_value_per_ticket"],
        "roi_proxy": ev_metrics["roi_proxy"],
        "prize_table_version": ev_metrics["prize_table_version"],
    }


def _resolve_target_draws(args: argparse.Namespace) -> list[int]:
    """CLI から target draw no を解決（単一値、複数値、範囲対応）"""
    if args.target_draws:
        targets = _parse_int_csv(args.target_draws)
    else:
        targets = [args.target_draw_no]

    if args.target_draw_from is not None or args.target_draw_to is not None:
        if args.target_draw_from is None or args.target_draw_to is None:
            raise ValueError("--target-draw-from and --target-draw-to must be specified together")
        if args.target_draw_to < args.target_draw_from:
            raise ValueError("--target-draw-to must be greater than or equal to --target-draw-from")
        targets = list(range(args.target_draw_from, args.target_draw_to + 1))

    return sorted(set(targets))


def _resolve_history_limits(args: argparse.Namespace) -> list[int]:
    """CLI から history_limit を解決（単一値、複数値対応）"""
    if args.history_limits:
        limits = _parse_int_csv(args.history_limits)
    else:
        limits = [args.history_limit]

    for limit in limits:
        if limit <= 0:
            raise ValueError("history_limit must be greater than 0")

    return sorted(set(limits))


def _resolve_seed_range(args: argparse.Namespace) -> list[int]:
    """CLI から seed の範囲を解決（単一値、範囲対応）"""
    if args.seed_from is None and args.seed_to is None:
        return [args.seed]

    seed_from = args.seed if args.seed_from is None else args.seed_from
    seed_to = seed_from if args.seed_to is None else args.seed_to

    if seed_to < seed_from:
        raise ValueError("--seed-to must be greater than or equal to --seed-from")

    return list(range(seed_from, seed_to + 1))


def _resolve_rows(
    *,
    lottery_type: str,
    input_jsonl: str | None,
    min_target_draw_no: int,
    max_target_draw_no: int,
    max_history_limit: int,
) -> list[dict[str, Any]]:
    if input_jsonl:
        return _load_jsonl_rows(input_jsonl, lottery_type)

    project_id = os.environ.get("GCP_PROJECT_ID")
    if not project_id:
        raise ValueError("GCP_PROJECT_ID is required when --input-jsonl is not specified.")

    dataset = os.environ.get("BQ_DATASET", "loto_predict")
    spec = LOTTERY_SPECS[lottery_type]
    table = os.environ.get(str(spec["bq_table_env"]), str(spec["default_table"]))

    return _load_bigquery_rows(
        project_id=project_id,
        dataset=dataset,
        table=table,
        lottery_type=lottery_type,
        min_target_draw_no=min_target_draw_no,
        max_target_draw_no=max_target_draw_no,
        max_history_limit=max_history_limit,
    )


def _print_single_result(result: dict[str, Any], source: str) -> None:
    print(f"lottery_type: {result['lottery_type']}")
    print(f"target_draw_no: {result['target_draw_no']}")
    print(f"target_draw_date: {result['target_draw_date']}")
    print(f"target_main: {result['target_main']}")
    print(f"target_bonus: {result['target_bonus']}")
    print(f"history_count: {result['history_count']}")
    print(f"strategy: {result['strategy']}")
    print(f"seed: {result['seed']}")
    print(f"source: {source}")
    print("-" * 100)

    for ticket in result["tickets"]:
        print(
            f"{ticket['ticket_no']}口目 "
            f"({ticket['profile_name']}): "
            f"{' '.join(str(n) for n in ticket['prediction'])}"
        )
        print(f"  main_match: {ticket['main_match']}")
        print(f"  bonus_match: {ticket['bonus_match']}")
        print(f"  prize: {ticket['prize']}")
        print(f"  near_miss_score: {ticket['near_miss_score']}")

    print("-" * 100)
    print(f"best_main_match: {result['best_main_match']}")
    print(f"best_bonus_match: {result['best_bonus_match']}")
    print(f"best_prize: {result['best_prize']}")
    print(f"best_near_miss_score: {result['best_near_miss_score']}")
    print(f"avg_pairwise_jaccard: {result.get('avg_pairwise_jaccard', 0.0)}")
    print(f"avg_pairwise_overlap: {result.get('avg_pairwise_overlap', 0.0)}")
    print(f"unique_number_coverage: {result.get('unique_number_coverage', 0)}")
    print(f"expected_value_sum: {result.get('expected_value_sum', 0.0)}")
    print(f"expected_value_per_ticket: {result.get('expected_value_per_ticket', 0.0)}")
    print(f"roi_proxy: {result.get('roi_proxy', 0.0)}")
    print(f"prize_table_version: {result.get('prize_table_version', 'unknown')}")
    print(f"first_prize_found: {str(result['first_prize_found']).lower()}")
    print(f"second_prize_found: {str(result['second_prize_found']).lower()}")


def _summarize_prizes(results: list[dict[str, Any]]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for result in results:
        for ticket in result["tickets"]:
            prize = str(ticket["prize"])
            counts[prize] = counts.get(prize, 0) + 1
    return counts


def _print_group_summary(title: str, groups: dict[Any, list[dict[str, Any]]]) -> None:
    print()
    print(title)
    print("-" * 120)
    print(
        "key | runs | 1st | 2nd | best_main | best_bonus | "
        "avg_best_score | best_prize"
    )

    for key, group in sorted(groups.items(), key=lambda item: item[0]):
        runs = len(group)
        first = sum(1 for result in group if result["first_prize_found"])
        second = sum(1 for result in group if result["second_prize_found"])
        best = max(
            group,
            key=lambda result: (
                int(result["best_near_miss_score"]),
                int(result["best_main_match"]),
                int(result["best_bonus_match"]),
            ),
        )
        avg_score = sum(int(result["best_near_miss_score"]) for result in group) / runs

        print(
            f"{str(key):>12} | "
            f"{runs:5d} | "
            f"{first:3d} | "
            f"{second:3d} | "
            f"{best['best_main_match']:9d} | "
            f"{best['best_bonus_match']:10d} | "
            f"{avg_score:14.2f} | "
            f"{best['best_prize']}"
        )


def _print_ticket_summary(results: list[dict[str, Any]]) -> None:
    ticket_groups: dict[str, list[dict[str, Any]]] = {}

    for result in results:
        for ticket in result["tickets"]:
            key = f"{ticket['ticket_no']}:{ticket['profile_name']}"
            ticket_groups.setdefault(key, []).append(ticket)

    print()
    print("ticket/profile summary")
    print("-" * 120)
    print(
        "ticket/profile | tickets | 1st | 2nd | 3rd | 4th | 5th | 6th | "
        "best_main | best_bonus | avg_score"
    )

    for key, tickets in sorted(ticket_groups.items()):
        prize_counts: dict[str, int] = {}
        for ticket in tickets:
            prize = str(ticket["prize"])
            prize_counts[prize] = prize_counts.get(prize, 0) + 1

        best = max(
            tickets,
            key=lambda ticket: (
                int(ticket["near_miss_score"]),
                int(ticket["main_match"]),
                int(ticket["bonus_match"]),
            ),
        )
        avg_score = sum(int(ticket["near_miss_score"]) for ticket in tickets) / len(tickets)

        print(
            f"{key:28} | "
            f"{len(tickets):7d} | "
            f"{prize_counts.get('1等相当', 0):3d} | "
            f"{prize_counts.get('2等相当', 0):3d} | "
            f"{prize_counts.get('3等相当', 0):3d} | "
            f"{prize_counts.get('4等相当', 0):3d} | "
            f"{prize_counts.get('5等相当', 0):3d} | "
            f"{prize_counts.get('6等相当', 0):3d} | "
            f"{best['main_match']:9d} | "
            f"{best['bonus_match']:10d} | "
            f"{avg_score:9.2f}"
        )


def _print_hit_examples(results: list[dict[str, Any]]) -> None:
    hit_tickets: list[dict[str, Any]] = []

    for result in results:
        for ticket in result["tickets"]:
            enriched = {
                **ticket,
                "target_draw_no": result["target_draw_no"],
                "history_limit": result["history_limit"],
                "seed": result["seed"],
                "target_main": result["target_main"],
                "target_bonus": result["target_bonus"],
            }
            if ticket["prize"] in {"1等相当", "2等相当", "3等相当"}:
                hit_tickets.append(enriched)

    print()
    print("1st/2nd/3rd examples")
    print("-" * 120)

    if not hit_tickets:
        print("none")
        return

    hit_tickets = sorted(
        hit_tickets,
        key=lambda ticket: (
            int(ticket["near_miss_score"]),
            int(ticket["main_match"]),
            int(ticket["bonus_match"]),
        ),
        reverse=True,
    )

    for ticket in hit_tickets[:30]:
        print(
            f"draw={ticket['target_draw_no']} "
            f"history={ticket['history_limit']} "
            f"seed={ticket['seed']} "
            f"ticket={ticket['ticket_no']} "
            f"profile={ticket['profile_name']} "
            f"main={ticket['main_match']} "
            f"bonus={ticket['bonus_match']} "
            f"prize={ticket['prize']} "
            f"prediction={ticket['prediction']}"
        )


def _print_batch_summary(results: list[dict[str, Any]]) -> None:
    """複数 draw/history/seed のバッチ実行結果を統計的に集計・表示"""
    total_runs = len(results)
    total_tickets = sum(len(result["tickets"]) for result in results)
    prize_counts = _summarize_prizes(results)

    first_count = sum(1 for result in results if result["first_prize_found"])
    second_count = sum(1 for result in results if result["second_prize_found"])

    print("=" * 120)
    print("BATCH SUMMARY")
    print("=" * 120)
    print(f"total_runs: {total_runs}")
    print(f"total_tickets: {total_tickets}")
    print(f"first_prize_runs: {first_count}")
    print(f"second_prize_runs: {second_count}")
    print(f"second_prize_rate_by_run: {second_count / total_runs:.8f}" if total_runs else "0")
    print()

    print("ticket prize counts")
    print("-" * 120)
    for prize in ["1等相当", "2等相当", "3等相当", "4等相当", "5等相当", "6等相当", "該当なし"]:
        print(f"{prize}: {prize_counts.get(prize, 0)}")

    by_target: dict[int, list[dict[str, Any]]] = {}
    by_history: dict[int, list[dict[str, Any]]] = {}
    by_seed: dict[int, list[dict[str, Any]]] = {}

    for result in results:
        by_target.setdefault(int(result["target_draw_no"]), []).append(result)
        by_history.setdefault(int(result["history_limit"]), []).append(result)
        by_seed.setdefault(int(result["seed"]), []).append(result)

    _print_group_summary("target_draw summary", by_target)
    _print_group_summary("history_limit summary", by_history)
    _print_ticket_summary(results)
    _print_hit_examples(results)

    print()
    print("top run results")
    print("-" * 120)
    print("rank | target | history | seed | best_main | best_bonus | best_prize | score | 1st | 2nd")

    top_results = sorted(
        results,
        key=lambda result: (
            bool(result["first_prize_found"]),
            bool(result["second_prize_found"]),
            int(result["best_near_miss_score"]),
            int(result["best_main_match"]),
            int(result["best_bonus_match"]),
        ),
        reverse=True,
    )[:30]

    for rank, result in enumerate(top_results, start=1):
        print(
            f"{rank:4d} | "
            f"{result['target_draw_no']:6d} | "
            f"{result['history_limit']:7d} | "
            f"{result['seed']:4d} | "
            f"{result['best_main_match']:9d} | "
            f"{result['best_bonus_match']:10d} | "
            f"{result['best_prize']:8} | "
            f"{result['best_near_miss_score']:5d} | "
            f"{str(result['first_prize_found']).lower():5} | "
            f"{str(result['second_prize_found']).lower():5}"
        )

    lottery_type = str(results[0].get("lottery_type", "loto7")) if results else "loto7"
    strategy = str(results[0].get("strategy", "")) if results else ""
    if lottery_type == "loto6":
        candidate_strategy = strategy or "mixed_v3"
        comparison_hint = {
            "strategy_comparison_hint": {
                "baseline_strategy": "default",
                "candidate_strategy": candidate_strategy,
                "primary_metric": "avg_best_score",
                "secondary_metrics": [
                    "third_prize_count",
                    "fourth_prize_count",
                    "fifth_prize_count",
                    "score_stddev",
                ],
                "adoption_rule": (
                    "Adopt the LOTO6 candidate only if it improves upper-prize counts, "
                    "avg_best_score, or five-ticket coverage without relying on a single seed or draw."
                ),
            }
        }
        adoption = {
            "adoption_recommendation": {
                "candidate_strategy": candidate_strategy,
                "baseline_strategy": "default",
                "should_adopt": candidate_strategy == "mixed_v3",
                "reason": (
                    "mixed_v3 is the LOTO6 LINE default after validation improved coverage and "
                    "upper-prize-equivalent counts; keep monitoring holdout results."
                    if candidate_strategy == "mixed_v3"
                    else "Use validation and holdout comparison before treating this strategy as production default."
                ),
            }
        }
    else:
        candidate_strategy = strategy or "mixed_v3"
        is_high_tier_experiment = candidate_strategy == "high_tier_v1"
        comparison_hint = {
            "strategy_comparison_hint": {
                "baseline_strategy": "mixed_v2",
                "candidate_strategy": candidate_strategy,
                "primary_metric": "avg_best_score",
                "secondary_metrics": [
                    "third_prize_count",
                    "fourth_prize_count",
                    "hit4_or_more_rate",
                    "hit5_or_more_rate",
                    "second_prize_runs",
                ],
                "adoption_rule": (
                    "Treat high_tier_v1 as experimental. Adopt a LOTO7 candidate only if it improves "
                    "2nd/3rd/4th prize counts or avg_best_score without eliminating bonus-aware upside."
                ),
            }
        }
        adoption = {
            "adoption_recommendation": {
                "candidate_strategy": candidate_strategy,
                "baseline_strategy": "mixed_v2_fix",
                "should_adopt": False,
                "reason": (
                    "high_tier_v1 is experimental only; keep mixed_v3 unchanged and compare on holdout before adoption."
                    if is_high_tier_experiment
                    else "Adopt only after 600-674 validation and 650-679 validation improve key metrics."
                ),
            }
        }

    print()
    print("strategy_comparison_hint:")
    print(json.dumps(comparison_hint, ensure_ascii=False, indent=2))

    print()
    print("adoption_recommendation:")
    print(json.dumps(adoption, ensure_ascii=False, indent=2))


def _print_triplet_holdout_summary(comparisons: list[dict[str, Any]]) -> None:
    if not comparisons:
        print("No holdout comparisons were performed.")
        return

    total_runs = len(comparisons)
    pair_total = sum(comp["pair_expected_value_per_ticket"] for comp in comparisons)
    triple_total = sum(comp["triple_expected_value_per_ticket"] for comp in comparisons)
    avg_pair = pair_total / total_runs
    avg_triple = triple_total / total_runs
    avg_delta = avg_triple - avg_pair

    improved_runs = sum(
        1 for comp in comparisons
        if comp["triple_expected_value_per_ticket"] > comp["pair_expected_value_per_ticket"]
    )
    tied_runs = sum(
        1 for comp in comparisons
        if comp["triple_expected_value_per_ticket"] == comp["pair_expected_value_per_ticket"]
    )
    worse_runs = total_runs - improved_runs - tied_runs

    percent_improved = improved_runs / total_runs * 100.0
    percent_worse = worse_runs / total_runs * 100.0
    percent_tied = tied_runs / total_runs * 100.0

    print()
    print("TRIPLET HOLDOUT SUMMARY")
    print("=" * 120)
    print(f"runs: {total_runs}")
    print(f"pair_weighted avg EV per ticket: {avg_pair:.6f}")
    print(f"triple_weighted avg EV per ticket: {avg_triple:.6f}")
    print(f"avg delta: {avg_delta:.6f}")
    print(f"improved: {improved_runs} ({percent_improved:.1f}%)")
    print(f"tied: {tied_runs} ({percent_tied:.1f}%)")
    print(f"worse: {worse_runs} ({percent_worse:.1f}%)")

    relative_uplift = (
        abs(avg_delta / avg_pair)
        if abs(avg_pair) > 1e-9
        else float("inf") if avg_delta > 0 else 0.0
    )
    adopt_recommended = avg_delta > 0 and percent_improved >= 50.0 and relative_uplift >= 0.01
    if adopt_recommended:
        print("Recommendation: adopt triple_weighted in holdout; it shows a positive uplift.")
    else:
        print("Recommendation: keep triple_weighted behind a feature flag until the holdout improvement is stronger.")
    print("Note: triple_weighted is feature-flag safe by default because --triplet-weight defaults to 0.0.")


def _write_jsonl(path: str, results: list[dict[str, Any]]) -> None:
    output_path = Path(path)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    with output_path.open("w", encoding="utf-8") as file:
        for result in results:
            for ticket in result["tickets"]:
                # Flatten the ticket into its own row for detailed traceability
                row = {
                    "strategy": result["strategy"],
                    "strategy_version": "1.0",
                    "profile": ticket["profile_name"],
                    "profile_learning_key": (
                        f"{result['strategy']}:{ticket['profile_name']}:"
                        f"history{result['history_limit']}:draw{result['target_draw_no']}"
                    ),
                    "profile_learning_candidate": result["strategy"] in {"mixed_loto6", "mixed_v2", "mixed_v3"},
                    "profile_role": {
                        **LOTO6_PROFILE_ROLES,
                        **PROFILE_ROLES,
                    }.get(ticket["profile_name"], ""),
                    "seed_optimization_used": False,
                    "target_draw": result["target_draw_no"],
                    "history_limit": result["history_limit"],
                    "seed": result["seed"],
                    "ticket_index": ticket["ticket_no"],
                    "prediction": ticket["prediction"],
                    "score": ticket.get("score", 0.0),
                    "score_breakdown": ticket.get(
                        "score_breakdown",
                        {
                            "base": 0.0,
                            "ema": 0.0,
                            "pair": 0.0,
                            "triple": 0.0,
                            "diversity_penalty": 0.0,
                            "fallback_used": False,
                        },
                    ),
                    "matched_main": ticket["main_match"],
                    "matched_bonus": ticket["bonus_match"],
                    "prize_equivalent": ticket["prize"],
                    
                    # Backward compatibility fields for analyze_experiment_results.py
                    "lottery_type": result["lottery_type"],
                    "target_draw_no": result["target_draw_no"],
                    "best_near_miss_score": result["best_near_miss_score"],
                    "avg_pairwise_jaccard": result.get("avg_pairwise_jaccard", 0.0),
                    "unique_number_coverage": result.get("unique_number_coverage", 0),
                    "expected_value_per_ticket": result.get("expected_value_per_ticket", 0.0),
                    "expected_value_sum": result.get("expected_value_sum", 0.0),
                    "roi_proxy": result.get("roi_proxy", 0.0),
                    "tickets": [ticket], # Single-ticket array so second_count logic works
                }
                file.write(json.dumps(row, ensure_ascii=False) + "\n")


def main() -> None:
    """
    CLI エントリーポイント

    【処理】
    1. コマンドライン引数をパース
    2. target_draws, history_limits, seeds を解決
    3. ローカル JSONL または BigQuery から履歴データを取得
    4. target_draw_no ごと、history_limit ごと、seed ごとに評価
    5. 結果を stdout に出力、または --output-jsonl に保存
    """
    parser = argparse.ArgumentParser(
        description="Backtest LOTO6/LOTO7 predictions. Local uses JSONL. GCP uses BigQuery."
    )
    parser.add_argument("--lottery-type", choices=["loto6", "loto7"], required=True)

    parser.add_argument("--target-draw-no", type=int, default=None)
    parser.add_argument("--target-draws", type=str, default=None)
    parser.add_argument("--target-draw-from", type=int, default=None)
    parser.add_argument("--target-draw-to", type=int, default=None)

    parser.add_argument("--history-limit", type=int, default=100)
    parser.add_argument("--history-limits", type=str, default=None)

    parser.add_argument("--prediction-count", type=int, default=5)
    parser.add_argument(
        "--strategy",
        choices=[
            "default",
            "mixed",
            "mixed_loto6",
            "mixed_v2",
            "mixed_v3",
            "high_tier_v1",
            "triple_weighted",
        ],
        default="mixed",
        help=(
            "Prediction strategy to use. Available: default, mixed, mixed_loto6, "
            "mixed_v2, mixed_v3, high_tier_v1 (experimental), triple_weighted"
        ),
    )

    parser.add_argument("--pair-weight", type=float, default=1.0)
    parser.add_argument("--pair-laplace", type=float, default=1.0)
    parser.add_argument("--pair-shrink-k", type=float, default=5.0)
    parser.add_argument("--pair-decay", type=float, default=0.0)

    parser.add_argument("--ema-alpha-short", type=float, default=0.20)
    parser.add_argument("--ema-alpha-mid", type=float, default=0.10)
    parser.add_argument("--ema-alpha-long", type=float, default=0.05)
    parser.add_argument("--ema-short-weight", type=float, default=0.45)
    parser.add_argument("--ema-mid-weight", type=float, default=0.35)
    parser.add_argument("--ema-long-weight", type=float, default=0.20)
    parser.add_argument(
        "--ema-include-bonus",
        choices=["true", "false"],
        default="false",
        help="Whether to include bonus numbers when computing EMA recency scores.",
    )

    parser.add_argument("--selector-max-overlap", type=int, default=4)
    parser.add_argument("--selector-min-jaccard-distance", type=float, default=0.43)
    parser.add_argument("--selector-candidate-pool-size", type=int, default=0)
    parser.add_argument("--selector-diversity-weight", type=float, default=0.25)

    parser.add_argument("--triplet-top-n", type=int, default=500)
    parser.add_argument("--triplet-shrink-k", type=float, default=10.0)
    parser.add_argument("--triplet-weight", type=float, default=0.0)
    parser.add_argument("--triplet-laplace", type=float, default=1.0)
    parser.add_argument("--triplet-decay", type=float, default=0.0)
    parser.add_argument("--triplet-top-pool-size", type=int, default=20)
    parser.add_argument("--triplet-holdout", action="store_true", default=False,
        help="Compare pair_weighted and triple_weighted on the same holdout set."
    )

    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--seed-from", type=int, default=None)
    parser.add_argument("--seed-to", type=int, default=None)

    parser.add_argument("--input-jsonl", type=str, default=None)
    parser.add_argument("--output-jsonl", type=str, default=None)

    args = parser.parse_args()

    lottery_type = _normalize_lottery_type(args.lottery_type)

    if args.target_draw_no is None and not args.target_draws and args.target_draw_from is None:
        raise ValueError(
            "Specify one of --target-draw-no, --target-draws, or --target-draw-from/--target-draw-to."
        )

    if lottery_type == "loto6" and args.strategy in {
        "mixed_v2",
        "triple_weighted",
        "pair_weighted",
        "ema_recency",
    }:
        print("warning: strategy is for loto7 only. fallback to default for loto6.")
        args.strategy = "default"

    target_draws = _resolve_target_draws(args)
    history_limits = _resolve_history_limits(args)
    seeds = _resolve_seed_range(args)

    rows = _normalize_rows(
        _resolve_rows(
            lottery_type=lottery_type,
            input_jsonl=args.input_jsonl,
            min_target_draw_no=min(target_draws),
            max_target_draw_no=max(target_draws),
            max_history_limit=max(history_limits),
        ),
        lottery_type,
    )

    existing_draw_nos = {int(row["draw_no"]) for row in rows}
    requested_target_draws = list(target_draws)
    missing_target_draws = [
        draw_no
        for draw_no in requested_target_draws
        if draw_no not in existing_draw_nos
    ]
    target_draws = [
        draw_no
        for draw_no in requested_target_draws
        if draw_no in existing_draw_nos
    ]
    if not target_draws:
        raise ValueError("no requested target draws exist in the input history")
    if missing_target_draws:
        print(
            "missing target draws skipped: "
            f"count={len(missing_target_draws)} "
            f"first={missing_target_draws[:20]}"
        )

    source = "jsonl" if args.input_jsonl else "bigquery"
    batch_mode = len(target_draws) > 1 or len(history_limits) > 1 or len(seeds) > 1

    results: list[dict[str, Any]] = []

    pair_config = None
    triple_config = None
    ema_config = None
    if args.strategy == "pair_weighted" or args.triplet_holdout:
        pair_config = PairConfig(
            pair_weight=float(args.pair_weight),
            laplace=float(args.pair_laplace),
            shrink_k=float(args.pair_shrink_k),
            decay=float(args.pair_decay) if args.pair_decay > 0 else None,
        )

    if args.strategy == "triple_weighted" or args.triplet_holdout:
        triple_config = TripleWeightedConfig(
            top_n=int(args.triplet_top_n),
            shrink_k=float(args.triplet_shrink_k),
            triplet_weight=float(args.triplet_weight),
            laplace=float(args.triplet_laplace),
            decay=float(args.triplet_decay) if args.triplet_decay > 0 else None,
            top_pool_size=int(args.triplet_top_pool_size),
        )

    if args.strategy == "ema_recency":
        ema_config = EmaRecencyConfig(
            alpha_short=float(args.ema_alpha_short),
            alpha_mid=float(args.ema_alpha_mid),
            alpha_long=float(args.ema_alpha_long),
            short_weight=float(args.ema_short_weight),
            mid_weight=float(args.ema_mid_weight),
            long_weight=float(args.ema_long_weight),
            include_bonus=args.ema_include_bonus == "true",
        )

    if args.triplet_holdout:
        if lottery_type != "loto7":
            raise ValueError("holdout comparison is only supported for loto7")

        comparisons: list[dict[str, Any]] = []
        holdout_results: list[dict[str, Any]] = []

        for target_draw_no in target_draws:
            for history_limit in history_limits:
                for seed in seeds:
                    pair_result = _evaluate_once(
                        rows=rows,
                        lottery_type=lottery_type,
                        target_draw_no=target_draw_no,
                        history_limit=history_limit,
                        prediction_count=args.prediction_count,
                        strategy="pair_weighted",
                        seed=seed,
                        pair_config=pair_config,
                        triple_config=triple_config,
                        ema_config=ema_config,
                        selector_max_overlap=args.selector_max_overlap,
                        selector_min_jaccard_distance=args.selector_min_jaccard_distance,
                        selector_candidate_pool_size=args.selector_candidate_pool_size,
                        selector_diversity_weight=args.selector_diversity_weight,
                    )
                    triple_result = _evaluate_once(
                        rows=rows,
                        lottery_type=lottery_type,
                        target_draw_no=target_draw_no,
                        history_limit=history_limit,
                        prediction_count=args.prediction_count,
                        strategy="triple_weighted",
                        seed=seed,
                        pair_config=pair_config,
                        triple_config=triple_config,
                        ema_config=ema_config,
                        selector_max_overlap=args.selector_max_overlap,
                        selector_min_jaccard_distance=args.selector_min_jaccard_distance,
                        selector_candidate_pool_size=args.selector_candidate_pool_size,
                        selector_diversity_weight=args.selector_diversity_weight,
                    )
                    comparisons.append(
                        {
                            "target_draw_no": target_draw_no,
                            "history_limit": history_limit,
                            "seed": seed,
                            "pair_expected_value_per_ticket": pair_result["expected_value_per_ticket"],
                            "triple_expected_value_per_ticket": triple_result["expected_value_per_ticket"],
                        }
                    )
                    holdout_results.extend([pair_result, triple_result])

        _print_triplet_holdout_summary(comparisons)

        if args.output_jsonl:
            _write_jsonl(args.output_jsonl, holdout_results)
            print()
            print(f"output_jsonl: {args.output_jsonl}")
        return

    for target_draw_no in target_draws:
        for history_limit in history_limits:
            for seed in seeds:
                result = _evaluate_once(
                    rows=rows,
                    lottery_type=lottery_type,
                    target_draw_no=target_draw_no,
                    history_limit=history_limit,
                    prediction_count=args.prediction_count,
                    strategy=args.strategy,
                    seed=seed,
                    pair_config=pair_config,
                    triple_config=triple_config,
                    ema_config=ema_config,
                    selector_max_overlap=args.selector_max_overlap,
                    selector_min_jaccard_distance=args.selector_min_jaccard_distance,
                    selector_candidate_pool_size=args.selector_candidate_pool_size,
                    selector_diversity_weight=args.selector_diversity_weight,
                )
                results.append(result)

    if batch_mode:
        _print_batch_summary(results)
    else:
        _print_single_result(results[0], source)

    if args.output_jsonl:
        _write_jsonl(args.output_jsonl, results)
        print()
        print(f"output_jsonl: {args.output_jsonl}")


if __name__ == "__main__":
    main()
