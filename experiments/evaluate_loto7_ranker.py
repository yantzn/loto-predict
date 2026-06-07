"""Evaluate an experimental LOTO7 ranker.

学習済みrankerを過去データへ適用し、従来strategyと比較できる形で評価指標を出します。
学習済みprofileを本番へ直接反映する前の検証用途です。
"""

from __future__ import annotations

import argparse
import math
import pickle
from pathlib import Path
from typing import Any

import pandas as pd
from pandas import DataFrame

from experiments.build_loto7_dataset import (
    FEATURE_COLUMNS,
    build_number_level_dataset,
    build_time_series_folds,
    extract_loto7_draws,
    load_loto7_history_from_csv,
)
from src.domain.prediction import generate_loto7_second_prize_oriented_predictions, generate_predictions
from src.domain.statistics import calculate_bonus_number_scores
from src.evaluation.expected_value import compute_expected_value
from src.evaluation.prize_tables import prize_table_for_draw


def load_model(path: str | Path) -> Any:
    with Path(path).open("rb") as handle:
        return pickle.load(handle)


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


def _predict_main_scores(model: Any, feature_df: DataFrame) -> list[tuple[int, float]]:
    X = feature_df[FEATURE_COLUMNS].astype(float).to_numpy()
    probabilities = model.predict_proba(X)
    scores = probabilities[:, 1] if probabilities.shape[1] == 2 else probabilities[:, 0]
    return [(int(number), float(score)) for number, score in zip(feature_df["number"], scores)]


def _build_ticket_summary(predictions: list[list[int]], target_main: set[int], target_bonus: set[int], target_draw_no: int) -> tuple[dict[str, int], int, float]:
    prize_counts: dict[str, int] = {}
    best_main_match = 0
    best_bonus_match = 0
    best_prize = "該当なし"
    best_near_miss_score = 0.0

    for ticket in predictions:
        main_match = len(set(ticket) & target_main)
        bonus_match = len(set(ticket) & target_bonus)
        prize = _judge_loto7_prize(main_match, bonus_match)
        prize_counts[prize] = prize_counts.get(prize, 0) + 1

        near_miss_score = 0
        if main_match == 7:
            near_miss_score = 5000
        elif main_match == 6 and bonus_match >= 1:
            near_miss_score = 3000
        elif main_match == 6:
            near_miss_score = 1500
        elif main_match == 5 and bonus_match >= 1:
            near_miss_score = 800
        elif main_match == 5:
            near_miss_score = 500
        elif main_match == 4 and bonus_match >= 1:
            near_miss_score = 200
        elif main_match == 4:
            near_miss_score = 100
        elif main_match == 3 and bonus_match >= 1:
            near_miss_score = 50

        if near_miss_score > best_near_miss_score:
            best_near_miss_score = near_miss_score
            best_main_match = main_match
            best_bonus_match = bonus_match
            best_prize = prize

    return prize_counts, best_main_match, best_near_miss_score


def _evaluate_predictions(
    predictions: list[list[int]],
    target_main: set[int],
    target_bonus: set[int],
    target_draw_no: int,
) -> dict[str, float]:
    prize_counts, best_main_match, best_near_miss_score = _build_ticket_summary(
        predictions, target_main, target_bonus, target_draw_no
    )
    prize_table = prize_table_for_draw("loto7", target_draw_no)
    ev_metrics = compute_expected_value(prize_counts, prize_table)
    weighted_prize_score = (
        100 * prize_counts.get("2等相当", 0)
        + 10 * prize_counts.get("3等相当", 0)
        + prize_counts.get("4等相当", 0)
    )
    return {
        "expected_value_per_ticket": ev_metrics["expected_value_per_ticket"],
        "weighted_prize_score": float(weighted_prize_score),
        "best_main_match": float(best_main_match),
        "best_near_miss_score": float(best_near_miss_score),
    }


def _assemble_scores_and_predict(
    model: Any,
    feature_df: DataFrame,
    history_main: list[list[int]],
    history_bonus: list[list[int]],
    prediction_count: int = 5,
    seed: int | None = None,
) -> tuple[list[list[int]], list[list[int]]]:
    main_scores = _predict_main_scores(model, feature_df)
    bonus_scores = calculate_bonus_number_scores(history_bonus)

    learner_predictions = generate_loto7_second_prize_oriented_predictions(
        main_scores=main_scores,
        bonus_scores=bonus_scores,
        prediction_count=prediction_count,
        seed=seed,
    )

    mixed_v2_predictions = generate_predictions(
        lottery_type="loto7",
        strategy="mixed_v2",
        number_scores=main_scores,
        bonus_scores=bonus_scores,
        history=history_main,
        prediction_count=prediction_count,
        seed=seed,
    )

    return learner_predictions, mixed_v2_predictions


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Evaluate a trained Loto7 ranker against mixed_v2 on a holdout period.")
    parser.add_argument("--input-csv", required=True, help="Path to Loto7 history CSV")
    parser.add_argument("--model-path", required=True, help="Path to the trained model file")
    parser.add_argument("--history-limit", type=int, default=180, help="Maximum number of prior draws to use for each evaluation step")
    parser.add_argument("--min-history-draws", type=int, default=50, help="Minimum history draws required to evaluate a target draw")
    parser.add_argument("--n-splits", type=int, default=4, help="Number of time series folds used to define the final holdout range")
    parser.add_argument("--prediction-count", type=int, default=5, help="Number of tickets to generate per draw")
    parser.add_argument("--seed", type=int, default=42, help="Random seed for ticket generation")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    history_df = load_loto7_history_from_csv(args.input_csv)
    dataset = build_number_level_dataset(
        history_df,
        history_limit=args.history_limit,
        min_history_draws=args.min_history_draws,
    )

    if dataset.empty:
        raise RuntimeError("No evaluation data could be assembled from the provided history CSV.")

    folds = build_time_series_folds(dataset, n_splits=args.n_splits)
    holdout_fold = next((fold for fold in folds if fold["is_holdout"]), None)
    if holdout_fold is None:
        raise RuntimeError("Failed to find a holdout fold from the dataset folds.")

    model = load_model(args.model_path)
    draws = extract_loto7_draws(history_df)
    draw_map = {draw["draw_no"]: draw for draw in draws}
    heldout_draw_nos = set(holdout_fold["val_draw_nos"])

    results: list[dict[str, float]] = []
    for target_draw_no in sorted(heldout_draw_nos):
        target_draw = draw_map.get(target_draw_no)
        if target_draw is None:
            continue

        history_window = [draw for draw in draws if draw["draw_no"] < target_draw_no]
        if len(history_window) < args.min_history_draws:
            continue
        history_window = history_window[-args.history_limit :]
        history_newest_first = list(reversed(history_window))
        history_main = [entry["main_numbers"] for entry in history_newest_first]
        history_bonus = [entry["bonus_numbers"] for entry in history_newest_first]

        target_features = dataset[dataset["target_draw_no"] == target_draw_no]
        if target_features.empty:
            continue

        learner_tickets, mixed_v2_tickets = _assemble_scores_and_predict(
            model=model,
            feature_df=target_features,
            history_main=history_main,
            history_bonus=history_bonus,
            prediction_count=args.prediction_count,
            seed=args.seed,
        )

        learner_metrics = _evaluate_predictions(
            learner_tickets,
            set(target_draw["main_numbers"]),
            set(target_draw["bonus_numbers"]),
            target_draw_no,
        )
        mixed_v2_metrics = _evaluate_predictions(
            mixed_v2_tickets,
            set(target_draw["main_numbers"]),
            set(target_draw["bonus_numbers"]),
            target_draw_no,
        )

        results.append(
            {
                "target_draw_no": float(target_draw_no),
                "learner_ev": learner_metrics["expected_value_per_ticket"],
                "mixed_v2_ev": mixed_v2_metrics["expected_value_per_ticket"],
                "learner_weighted_prize_score": learner_metrics["weighted_prize_score"],
                "mixed_v2_weighted_prize_score": mixed_v2_metrics["weighted_prize_score"],
            }
        )

    if not results:
        raise RuntimeError("No holdout draws were evaluated. Check the input history range and split parameters.")

    summary = {
        "learner_avg_ev": sum(item["learner_ev"] for item in results) / len(results),
        "mixed_v2_avg_ev": sum(item["mixed_v2_ev"] for item in results) / len(results),
        "learner_avg_weighted_prize_score": sum(item["learner_weighted_prize_score"] for item in results) / len(results),
        "mixed_v2_avg_weighted_prize_score": sum(item["mixed_v2_weighted_prize_score"] for item in results) / len(results),
        "evaluated_draws": len(results),
    }

    print("Holdout comparison results")
    print(f"  evaluated_draws={summary['evaluated_draws']}")
    print(f"  learner_avg_ev={summary['learner_avg_ev']:.4f}")
    print(f"  mixed_v2_avg_ev={summary['mixed_v2_avg_ev']:.4f}")
    print(f"  learner_avg_weighted_prize_score={summary['learner_avg_weighted_prize_score']:.4f}")
    print(f"  mixed_v2_avg_weighted_prize_score={summary['mixed_v2_avg_weighted_prize_score']:.4f}")

    if summary["learner_avg_ev"] > summary["mixed_v2_avg_ev"]:
        print("Learner model outperforms mixed_v2 on expected value in holdout.")
    else:
        print("mixed_v2 remains stronger on expected value in holdout.")

    if summary["learner_avg_weighted_prize_score"] > summary["mixed_v2_avg_weighted_prize_score"]:
        print("Learner model outperforms mixed_v2 on weighted prize score in holdout.")
    else:
        print("mixed_v2 remains stronger on weighted prize score in holdout.")


if __name__ == "__main__":
    main()
