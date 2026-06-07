"""Build tabular datasets for LOTO7 ranking experiments.

過去履歴から特徴量と教師ラベルを作り、学習/評価用のCSVへ変換する実験用スクリプトです。
本番予想ロジックではなく、profile selectorやranker検証の材料作成に使います。
"""

from __future__ import annotations

import argparse
from collections import Counter
from pathlib import Path
from statistics import mean
from typing import Any

import pandas as pd
from pandas import DataFrame

from src.domain.scorers.pair_cooccurrence import PairStats, build_pair_stats, compute_pair_lift
from src.domain.statistics import calculate_bonus_number_scores, calculate_main_number_scores

MAIN_NUMBER_COLUMNS = [f"number{i}" for i in range(1, 8)]
BONUS_NUMBER_COLUMNS = [f"bonus{i}" for i in range(1, 3)]
FEATURE_COLUMNS = [
    "number",
    "main_frequency",
    "main_recent_frequency",
    "main_recency",
    "main_absence",
    "main_repeat",
    "bonus_frequency",
    "bonus_recency",
    "bonus_absence",
    "bonus_repeat",
    "pair_count_sum",
    "pair_lift_avg",
    "main_baseline_score",
    "bonus_baseline_score",
]


def load_loto7_history_from_csv(path: str | Path) -> DataFrame:
    path_obj = Path(path)
    if not path_obj.exists():
        raise FileNotFoundError(f"Loto7 history file not found: {path}")

    df = pd.read_csv(path_obj)
    if "draw_number" not in df.columns:
        raise ValueError("CSV file must contain a draw_number column")

    return df


def extract_loto7_draws(rows: DataFrame) -> list[dict[str, Any]]:
    normalized: list[dict[str, Any]] = []

    for _, row in rows.iterrows():
        draw_no = int(row["draw_number"])
        draw_date = str(row.get("draw_date", ""))

        main_numbers: list[int] = []
        for column in MAIN_NUMBER_COLUMNS:
            value = row.get(column)
            try:
                number = int(value)
            except (TypeError, ValueError):
                continue
            if number > 0:
                main_numbers.append(number)

        bonus_numbers: list[int] = []
        for column in BONUS_NUMBER_COLUMNS:
            value = row.get(column)
            try:
                number = int(value)
            except (TypeError, ValueError):
                continue
            if number > 0:
                bonus_numbers.append(number)

        if len(main_numbers) < 7:
            raise ValueError(f"draw_no={draw_no} has fewer than 7 main numbers")

        normalized.append(
            {
                "draw_no": draw_no,
                "draw_date": draw_date,
                "main_numbers": sorted(set(main_numbers)),
                "bonus_numbers": sorted(set(bonus_numbers)),
            }
        )

    return sorted(normalized, key=lambda item: item["draw_no"])


def _describe_history(history: list[dict[str, Any]]) -> tuple[dict[int, int], dict[int, int], dict[int, int], dict[int, int], dict[int, int], dict[int, int], set[int], set[int]]:
    main_counts: Counter[int] = Counter()
    main_recent_counts: Counter[int] = Counter()
    main_latest_seen: dict[int, int] = {}
    bonus_counts: Counter[int] = Counter()
    bonus_latest_seen: dict[int, int] = {}
    bonus_recent_counts: Counter[int] = Counter()

    recent_window = max(1, int(len(history) * 0.3))
    latest_main_draw = set(history[0]["main_numbers"]) if history else set()
    latest_bonus_draw = set(history[0]["bonus_numbers"]) if history else set()

    for idx, entry in enumerate(history):
        for number in entry["main_numbers"]:
            main_counts[number] += 1
            main_latest_seen.setdefault(number, idx)
            if idx < recent_window:
                main_recent_counts[number] += 1

        for number in entry["bonus_numbers"]:
            bonus_counts[number] += 1
            bonus_latest_seen.setdefault(number, idx)
            if idx < recent_window:
                bonus_recent_counts[number] += 1

    return (
        dict(main_counts),
        dict(main_recent_counts),
        main_latest_seen,
        dict(bonus_counts),
        dict(bonus_recent_counts),
        bonus_latest_seen,
        latest_main_draw,
        latest_bonus_draw,
    )


def _build_pair_features(pair_stats: PairStats, number: int, laplace: float = 1.0) -> tuple[float, float]:
    pair_count_sum = 0.0
    lifts: list[float] = []

    for (left, right), pair_count in pair_stats.pair_counts.items():
        if number not in (left, right):
            continue

        other = right if left == number else left
        pair_count_sum += pair_count

        marginal_left = pair_stats.marginal_counts.get(number, 0.0) + laplace
        marginal_right = pair_stats.marginal_counts.get(other, 0.0) + laplace
        smoothed_draw_count = pair_stats.draw_count + laplace * pair_stats.max_number

        lift = compute_pair_lift(
            pair_count=pair_count + laplace,
            draw_count=smoothed_draw_count,
            marginal_i=marginal_left,
            marginal_j=marginal_right,
        )
        lifts.append(lift)

    average_pair_lift = float(mean(lifts)) if lifts else 1.0
    return pair_count_sum, average_pair_lift


def _build_feature_record(
    target_draw: dict[str, Any],
    history: list[dict[str, Any]],
    history_limit: int,
) -> list[dict[str, Any]]:
    history_newest_first = list(reversed(history))
    main_draws = [row["main_numbers"] for row in history_newest_first]
    bonus_draws = [row["bonus_numbers"] for row in history_newest_first]

    main_scores = dict(calculate_main_number_scores(main_draws))
    bonus_scores = dict(calculate_bonus_number_scores(bonus_draws))
    pair_stats = build_pair_stats([row["main_numbers"] for row in history_newest_first], max_number=37)

    (
        main_counts,
        main_recent_counts,
        main_latest_seen,
        bonus_counts,
        bonus_recent_counts,
        bonus_latest_seen,
        latest_main_draw,
        latest_bonus_draw,
    ) = _describe_history(history_newest_first)

    max_main_count = max(main_counts.values(), default=1)
    max_bonus_count = max(bonus_counts.values(), default=1)
    max_pair_sum = max(_build_pair_features(pair_stats, number)[0] for number in range(1, 38)) or 1.0
    max_pair_lift = max(_build_pair_features(pair_stats, number)[1] for number in range(1, 38)) or 1.0

    records: list[dict[str, Any]] = []
    target_main = set(target_draw["main_numbers"])
    target_bonus = set(target_draw["bonus_numbers"])

    for number in range(1, 38):
        pair_count_sum, pair_lift_avg = _build_pair_features(pair_stats, number)
        max_main_latest = max(1, max(main_latest_seen.values()) if main_latest_seen else 0)
        max_bonus_latest = max(1, max(bonus_latest_seen.values()) if bonus_latest_seen else 0)
        record = {
            "target_draw_no": target_draw["draw_no"],
            "target_draw_date": target_draw["draw_date"],
            "number": number,
            "main_frequency": main_counts.get(number, 0) / max_main_count,
            "main_recent_frequency": main_recent_counts.get(number, 0) / max(1, recent_window := max(1, int(len(history_newest_first) * 0.3))),
            "main_recency": 1.0 - (main_latest_seen[number] / max_main_latest) if number in main_latest_seen else 0.0,
            "main_absence": main_latest_seen.get(number, len(history_newest_first)) / max(1, max_main_latest),
            "main_repeat": int(number in latest_main_draw),
            "bonus_frequency": bonus_counts.get(number, 0) / max_bonus_count,
            "bonus_recency": 1.0 - (bonus_latest_seen[number] / max_bonus_latest) if number in bonus_latest_seen else 0.0,
            "bonus_absence": bonus_latest_seen.get(number, len(history_newest_first)) / max(1, max_bonus_latest),
            "bonus_repeat": int(number in latest_bonus_draw),
            "pair_count_sum": pair_count_sum / max_pair_sum,
            "pair_lift_avg": pair_lift_avg / max_pair_lift,
            "main_baseline_score": main_scores.get(number, 0.0),
            "bonus_baseline_score": bonus_scores.get(number, 0.0),
            "label_main": int(number in target_main),
            "label_bonus": int(number in target_bonus),
        }
        records.append(record)

    return records


def build_number_level_dataset(
    rows: DataFrame,
    history_limit: int = 200,
    min_history_draws: int = 50,
) -> DataFrame:
    draws = extract_loto7_draws(rows)
    if not draws:
        return DataFrame()

    records: list[dict[str, Any]] = []
    for index in range(len(draws)):
        if index < min_history_draws:
            continue

        history_window = draws[max(0, index - history_limit) : index]
        if len(history_window) < min_history_draws:
            continue

        target_draw = draws[index]
        records.extend(_build_feature_record(target_draw, history_window, history_limit))

    return DataFrame(records)


def build_time_series_folds(dataset: DataFrame, n_splits: int = 4) -> list[dict[str, Any]]:
    if n_splits < 2:
        raise ValueError("n_splits must be >= 2")

    unique_draws = sorted(dataset["target_draw_no"].astype(int).unique())
    if len(unique_draws) < n_splits:
        raise ValueError("not enough target draws to build time series folds")

    fold_size = len(unique_draws) // n_splits
    if fold_size == 0:
        raise ValueError("not enough unique draws for the requested number of splits")

    folds: list[dict[str, Any]] = []

    for fold_index in range(n_splits):
        start = fold_index * fold_size
        end = len(unique_draws) if fold_index == n_splits - 1 else (fold_index + 1) * fold_size
        val_draw_nos = unique_draws[start:end]

        if fold_index == 0:
            train_draw_nos: list[int] = []
        else:
            train_draw_nos = [draw_no for draw_no in unique_draws if draw_no < val_draw_nos[0]]

        folds.append(
            {
                "fold_index": fold_index,
                "train_draw_nos": train_draw_nos,
                "val_draw_nos": val_draw_nos,
                "is_holdout": fold_index == n_splits - 1,
            }
        )

    return folds[1:]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build a number-level dataset from Loto7 history CSV")
    parser.add_argument("--input-csv", required=True, help="Path to the Loto7 history CSV file")
    parser.add_argument("--output-csv", default=None, help="Optional path to write the generated dataset CSV")
    parser.add_argument("--history-limit", type=int, default=200, help="Maximum number of prior draws used for features")
    parser.add_argument("--min-history-draws", type=int, default=50, help="Minimum history draws required to build each example")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    history_df = load_loto7_history_from_csv(args.input_csv)
    dataset = build_number_level_dataset(
        history_df,
        history_limit=args.history_limit,
        min_history_draws=args.min_history_draws,
    )

    print(f"Built dataset with {len(dataset)} examples and {len(dataset['target_draw_no'].unique())} target draws")
    if args.output_csv:
        output_path = Path(args.output_csv)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        dataset.to_csv(output_path, index=False)
        print(f"Wrote dataset CSV to {output_path}")


if __name__ == "__main__":
    main()
