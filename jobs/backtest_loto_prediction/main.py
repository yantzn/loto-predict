from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parents[2]
sys.path.append(str(PROJECT_ROOT))

from src.domain.prediction import generate_predictions
from src.domain.statistics import (
    ScoreWeights,
    calculate_bonus_number_scores,
    calculate_main_number_scores,
)


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
    pick_count = int(LOTTERY_SPECS[lottery_type]["pick_count"])
    return [
        [int(row[f"n{index}"]) for index in range(1, pick_count + 1)]
        for row in rows
    ]


def _extract_bonus_draws(rows: list[dict[str, Any]], lottery_type: str) -> list[list[int]]:
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


def _evaluate_once(
    *,
    rows: list[dict[str, Any]],
    lottery_type: str,
    target_draw_no: int,
    history_limit: int,
    prediction_count: int,
    strategy: str,
    seed: int,
) -> dict[str, Any]:
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

    predictions = generate_predictions(
        number_scores=main_scores,
        bonus_scores=bonus_scores,
        lottery_type=lottery_type,
        prediction_count=prediction_count,
        strategy=strategy,
        seed=seed,
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

        profile_name = (
            LOTO7_PROFILE_BY_TICKET_NO.get(ticket_no, f"profile_{ticket_no}")
            if lottery_type == "loto7"
            else f"ticket_{ticket_no}"
        )

        tickets.append(
            {
                "ticket_no": ticket_no,
                "profile_name": profile_name,
                "prediction": prediction,
                "main_match": main_match,
                "bonus_match": bonus_match,
                "prize": prize,
                "near_miss_score": near_miss_score,
            }
        )

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
    }


def _resolve_target_draws(args: argparse.Namespace) -> list[int]:
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
    if args.history_limits:
        limits = _parse_int_csv(args.history_limits)
    else:
        limits = [args.history_limit]

    for limit in limits:
        if limit <= 0:
            raise ValueError("history_limit must be greater than 0")

    return sorted(set(limits))


def _resolve_seed_range(args: argparse.Namespace) -> list[int]:
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


def _write_jsonl(path: str, results: list[dict[str, Any]]) -> None:
    output_path = Path(path)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    with output_path.open("w", encoding="utf-8") as file:
        for result in results:
            file.write(json.dumps(result, ensure_ascii=False) + "\n")


def main() -> None:
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
        choices=["default", "second_prize_oriented", "mixed"],
        default="mixed",
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

    if lottery_type == "loto6" and args.strategy in {"second_prize_oriented", "mixed"}:
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

    source = "jsonl" if args.input_jsonl else "bigquery"
    batch_mode = len(target_draws) > 1 or len(history_limits) > 1 or len(seeds) > 1

    results: list[dict[str, Any]] = []

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
