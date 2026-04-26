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


def _normalize_lottery_type(lottery_type: str) -> str:
    normalized = str(lottery_type).strip().lower()
    if normalized not in LOTTERY_SPECS:
        raise ValueError("lottery_type must be loto6 or loto7")
    return normalized


def _parse_history_limits(value: str | None, default_limit: int) -> list[int]:
    if not value:
        return [default_limit]

    limits = []
    for item in value.split(","):
        item = item.strip()
        if not item:
            continue
        parsed = int(item)
        if parsed <= 0:
            raise ValueError("history limit must be greater than 0")
        limits.append(parsed)

    return limits or [default_limit]


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

            if str(row.get("lottery_type", "")).lower() != lottery_type:
                continue

            rows.append(row)

    return rows


def _load_bigquery_rows(
    *,
    project_id: str,
    dataset: str,
    table: str,
    lottery_type: str,
    target_draw_no: int,
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

    min_draw_no = max(1, target_draw_no - max_history_limit - 50)

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
          AND draw_no <= @target_draw_no
          AND draw_no >= @min_draw_no
        ORDER BY draw_no DESC
    """

    job_config = bigquery.QueryJobConfig(
        query_parameters=[
            bigquery.ScalarQueryParameter("lottery_type", "STRING", lottery_type),
            bigquery.ScalarQueryParameter("target_draw_no", "INT64", target_draw_no),
            bigquery.ScalarQueryParameter("min_draw_no", "INT64", min_draw_no),
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
    return [[int(row[f"n{index}"]) for index in range(1, pick_count + 1)] for row in rows]


def _extract_bonus_draws(rows: list[dict[str, Any]], lottery_type: str) -> list[list[int]]:
    bonus_count = int(LOTTERY_SPECS[lottery_type]["bonus_count"])
    bonus_draws: list[list[int]] = []

    for row in rows:
        bonuses: list[int] = []
        for index in range(1, bonus_count + 1):
            key = f"b{index}"
            if row.get(key) is not None:
                bonuses.append(int(row[key]))
        bonus_draws.append(bonuses)

    return bonus_draws


def _extract_target_numbers(
    target_row: dict[str, Any],
    lottery_type: str,
) -> tuple[set[int], set[int]]:
    pick_count = int(LOTTERY_SPECS[lottery_type]["pick_count"])
    bonus_count = int(LOTTERY_SPECS[lottery_type]["bonus_count"])

    target_main = {int(target_row[f"n{index}"]) for index in range(1, pick_count + 1)}
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


def _resolve_rows(
    *,
    lottery_type: str,
    input_jsonl: str | None,
    target_draw_no: int,
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
        target_draw_no=target_draw_no,
        max_history_limit=max_history_limit,
    )


def _build_training_rows(
    rows: list[dict[str, Any]],
    target_draw_no: int,
    history_limit: int,
) -> list[dict[str, Any]]:
    train_rows = [row for row in rows if int(row["draw_no"]) < target_draw_no]
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
    target_row = next((row for row in rows if int(row["draw_no"]) == target_draw_no), None)
    if target_row is None:
        raise ValueError(f"target draw not found: {target_draw_no}")

    train_rows = _build_training_rows(rows, target_draw_no, history_limit)
    if not train_rows:
        raise ValueError("no training rows found before target draw")

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

    ticket_results: list[dict[str, Any]] = []
    best_main_match = 0
    best_bonus_match = 0
    best_prize = "該当なし"
    second_prize_found = False

    for index, prediction in enumerate(predictions, start=1):
        prediction_set = set(prediction)
        main_match = len(prediction_set & target_main)
        bonus_match = len(prediction_set & target_bonus)
        prize = _judge_prize(lottery_type, main_match, bonus_match)

        if prize == "2等相当":
            second_prize_found = True

        if (
            main_match > best_main_match
            or (main_match == best_main_match and bonus_match > best_bonus_match)
        ):
            best_main_match = main_match
            best_bonus_match = bonus_match
            best_prize = prize

        ticket_results.append(
            {
                "ticket_no": index,
                "prediction": prediction,
                "main_match": main_match,
                "bonus_match": bonus_match,
                "prize": prize,
            }
        )

    return {
        "lottery_type": lottery_type,
        "target_draw_no": target_draw_no,
        "target_main": sorted(target_main),
        "target_bonus": sorted(target_bonus),
        "history_limit": history_limit,
        "history_count": len(train_rows),
        "prediction_count": prediction_count,
        "strategy": strategy,
        "seed": seed,
        "tickets": ticket_results,
        "best_main_match": best_main_match,
        "best_bonus_match": best_bonus_match,
        "best_prize": best_prize,
        "second_prize_found": second_prize_found,
    }


def _print_single_result(result: dict[str, Any], source: str) -> None:
    print(f"lottery_type: {result['lottery_type']}")
    print(f"target_draw_no: {result['target_draw_no']}")
    print(f"target_main: {result['target_main']}")
    print(f"target_bonus: {result['target_bonus']}")
    print(f"history_count: {result['history_count']}")
    print(f"strategy: {result['strategy']}")
    print(f"seed: {result['seed']}")
    print(f"source: {source}")
    print("-" * 60)

    for ticket in result["tickets"]:
        print(f"{ticket['ticket_no']}口目: {' '.join(str(n) for n in ticket['prediction'])}")
        print(f"  main_match: {ticket['main_match']}")
        print(f"  bonus_match: {ticket['bonus_match']}")
        print(f"  prize: {ticket['prize']}")

    print("-" * 60)
    print(f"best_main_match: {result['best_main_match']}")
    print(f"best_bonus_match: {result['best_bonus_match']}")
    print(f"best_prize: {result['best_prize']}")
    print(f"second_prize_found: {str(result['second_prize_found']).lower()}")


def _print_batch_summary(results: list[dict[str, Any]]) -> None:
    total = len(results)
    second_prize_count = sum(1 for r in results if r["second_prize_found"])

    print("=" * 80)
    print("BATCH SUMMARY")
    print("=" * 80)
    print(f"total_runs: {total}")
    print(f"second_prize_count: {second_prize_count}")
    print(f"second_prize_rate: {second_prize_count / total:.4f}" if total else "second_prize_rate: 0")
    print()

    by_history: dict[int, list[dict[str, Any]]] = {}
    for result in results:
        by_history.setdefault(int(result["history_limit"]), []).append(result)

    print("history_limit summary")
    print("-" * 80)
    print("history_limit | runs | 2nd_count | 2nd_rate | best_main | best_bonus")
    for history_limit, group in sorted(by_history.items()):
        group_total = len(group)
        group_second = sum(1 for r in group if r["second_prize_found"])
        best = max(
            group,
            key=lambda r: (int(r["best_main_match"]), int(r["best_bonus_match"])),
        )
        print(
            f"{history_limit:13d} | "
            f"{group_total:4d} | "
            f"{group_second:9d} | "
            f"{group_second / group_total:8.4f} | "
            f"{best['best_main_match']:9d} | "
            f"{best['best_bonus_match']:10d}"
        )

    print()
    print("top results")
    print("-" * 80)
    top_results = sorted(
        results,
        key=lambda r: (
            bool(r["second_prize_found"]),
            int(r["best_main_match"]),
            int(r["best_bonus_match"]),
        ),
        reverse=True,
    )[:10]

    print("rank | history_limit | seed | best_main | best_bonus | best_prize | 2nd")
    for rank, result in enumerate(top_results, start=1):
        print(
            f"{rank:4d} | "
            f"{result['history_limit']:13d} | "
            f"{result['seed']:4d} | "
            f"{result['best_main_match']:9d} | "
            f"{result['best_bonus_match']:10d} | "
            f"{result['best_prize']} | "
            f"{str(result['second_prize_found']).lower()}"
        )


def _write_jsonl(path: str, results: list[dict[str, Any]]) -> None:
    output_path = Path(path)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    with output_path.open("w", encoding="utf-8") as file:
        for result in results:
            file.write(json.dumps(result, ensure_ascii=False) + "\n")


def main() -> None:
    parser = argparse.ArgumentParser(
        description=(
            "Backtest LOTO6/LOTO7 predictions. "
            "Local uses --input-jsonl. GCP uses BigQuery."
        )
    )
    parser.add_argument("--lottery-type", choices=["loto6", "loto7"], required=True)
    parser.add_argument("--target-draw-no", type=int, required=True)
    parser.add_argument("--history-limit", type=int, default=100)
    parser.add_argument(
        "--history-limits",
        type=str,
        default=None,
        help="Comma separated history limits for batch mode. Example: 50,100,150,200",
    )
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
    parser.add_argument(
        "--output-jsonl",
        type=str,
        default=None,
        help="Write batch results to JSONL.",
    )

    args = parser.parse_args()

    lottery_type = _normalize_lottery_type(args.lottery_type)

    if lottery_type == "loto6" and args.strategy in {"second_prize_oriented", "mixed"}:
        print("warning: strategy is for loto7 only. fallback to default for loto6.")
        args.strategy = "default"

    history_limits = _parse_history_limits(args.history_limits, args.history_limit)
    max_history_limit = max(history_limits)

    rows = _normalize_rows(
        _resolve_rows(
            lottery_type=lottery_type,
            input_jsonl=args.input_jsonl,
            target_draw_no=args.target_draw_no,
            max_history_limit=max_history_limit,
        ),
        lottery_type,
    )

    source = "jsonl" if args.input_jsonl else "bigquery"

    batch_mode = args.seed_from is not None or args.seed_to is not None or args.history_limits

    if not batch_mode:
        result = _evaluate_once(
            rows=rows,
            lottery_type=lottery_type,
            target_draw_no=args.target_draw_no,
            history_limit=args.history_limit,
            prediction_count=args.prediction_count,
            strategy=args.strategy,
            seed=args.seed,
        )
        _print_single_result(result, source)
        return

    seed_from = args.seed_from if args.seed_from is not None else args.seed
    seed_to = args.seed_to if args.seed_to is not None else seed_from

    if seed_to < seed_from:
        raise ValueError("--seed-to must be greater than or equal to --seed-from")

    results: list[dict[str, Any]] = []

    for history_limit in history_limits:
        for seed in range(seed_from, seed_to + 1):
            result = _evaluate_once(
                rows=rows,
                lottery_type=lottery_type,
                target_draw_no=args.target_draw_no,
                history_limit=history_limit,
                prediction_count=args.prediction_count,
                strategy=args.strategy,
                seed=seed,
            )
            results.append(result)

    _print_batch_summary(results)

    if args.output_jsonl:
        _write_jsonl(args.output_jsonl, results)
        print()
        print(f"output_jsonl: {args.output_jsonl}")


if __name__ == "__main__":
    main()
