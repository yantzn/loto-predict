"""Train an experimental LOTO7 ranker.

`build_loto7_dataset.py` が作った特徴量データを使い、軽量なranker modelを学習する実験用スクリプトです。
本番採用前にvalidation/holdoutで劣化しないかを必ず確認します。
"""

from __future__ import annotations

import argparse
import os
import pickle
from pathlib import Path
from typing import Any

import pandas as pd
from pandas import DataFrame

from experiments.build_loto7_dataset import (
    FEATURE_COLUMNS,
    build_number_level_dataset,
    build_time_series_folds,
    load_loto7_history_from_csv,
)


def _safe_import_sklearn() -> Any:
    try:
        from sklearn.linear_model import LogisticRegression
        from sklearn.pipeline import Pipeline
        from sklearn.preprocessing import StandardScaler

        return LogisticRegression, Pipeline, StandardScaler
    except ModuleNotFoundError as exc:
        raise ModuleNotFoundError(
            "scikit-learn is required for training. Install it with `pip install -r requirements-experiments.txt`."
        ) from exc


def _safe_import_lightgbm() -> Any:
    try:
        from lightgbm import LGBMClassifier

        return LGBMClassifier
    except ModuleNotFoundError as exc:
        raise ModuleNotFoundError(
            "lightgbm is required for lightgbm training. Install it with `pip install -r requirements-experiments.txt`."
        ) from exc


def train_ranker(
    train_df: DataFrame,
    feature_columns: list[str],
    model_type: str = "logistic",
    random_state: int = 42,
) -> Any:
    if train_df.empty:
        raise ValueError("train_df must not be empty")

    X = train_df[feature_columns].astype(float).to_numpy()
    y = train_df["label_main"].astype(int).to_numpy()

    if model_type == "lightgbm":
        LGBMClassifier = _safe_import_lightgbm()
        model = LGBMClassifier(
            n_estimators=100,
            objective="binary",
            random_state=random_state,
            n_jobs=os.cpu_count() or 1,
        )
    else:
        LogisticRegression, Pipeline, StandardScaler = _safe_import_sklearn()
        model = Pipeline(
            [
                ("scaler", StandardScaler()),
                (
                    "classifier",
                    LogisticRegression(
                        penalty="l2",
                        solver="liblinear",
                        max_iter=1000,
                        random_state=random_state,
                    ),
                ),
            ]
        )

    model.fit(X, y)
    return model


def predict_main_probabilities(model: Any, dataset: DataFrame, feature_columns: list[str]) -> pd.Series:
    X = dataset[feature_columns].astype(float).to_numpy()
    probabilities = model.predict_proba(X)
    if probabilities.shape[1] == 2:
        return pd.Series(probabilities[:, 1], index=dataset.index)
    return pd.Series(probabilities[:, 0], index=dataset.index)


def compute_topk_recall(dataset: DataFrame, k: int = 7) -> float:
    draws = []
    for _, group in dataset.groupby("target_draw_no"):
        actual = set(group.loc[group["label_main"] == 1, "number"].tolist())
        predicted = group.sort_values("prob", ascending=False).head(k)["number"].tolist()
        draws.append(len(actual & set(predicted)) / max(1, len(actual)))
    return float(sum(draws) / len(draws)) if draws else 0.0


def evaluate_ranker(model: Any, val_df: DataFrame, feature_columns: list[str]) -> dict[str, float]:
    if val_df.empty:
        return {
            "roc_auc": 0.0,
            "top7_recall": 0.0,
            "top10_recall": 0.0,
            "top14_recall": 0.0,
        }

    val_df = val_df.copy()
    val_df["prob"] = predict_main_probabilities(model, val_df, feature_columns)
    metrics = {
        "top7_recall": compute_topk_recall(val_df, k=7),
        "top10_recall": compute_topk_recall(val_df, k=10),
        "top14_recall": compute_topk_recall(val_df, k=14),
        "roc_auc": 0.0,
    }

    try:
        from sklearn.metrics import roc_auc_score

        metrics["roc_auc"] = float(roc_auc_score(val_df["label_main"].astype(int), val_df["prob"]))
    except ModuleNotFoundError:
        pass

    return metrics


def save_model(model: Any, path: str | Path) -> None:
    path_obj = Path(path)
    path_obj.parent.mkdir(parents=True, exist_ok=True)
    with path_obj.open("wb") as handle:
        pickle.dump(model, handle)


def load_model(path: str | Path) -> Any:
    with Path(path).open("rb") as handle:
        return pickle.load(handle)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Train a learning-based Loto7 ranking model from historical data.")
    parser.add_argument("--input-csv", required=True, help="Path to Loto7 history CSV")
    parser.add_argument("--output-model", default="experiments/loto7_ranker.pkl", help="Output path for the trained model")
    parser.add_argument("--history-limit", type=int, default=180, help="Maximum number of prior draws to use for each training example")
    parser.add_argument("--min-history-draws", type=int, default=50, help="Minimum history draws required to build a training example")
    parser.add_argument("--n-splits", type=int, default=4, help="Time-aware split count, final fold is holdout")
    parser.add_argument("--model-type", choices=["logistic", "lightgbm"], default="logistic", help="Model class for the ranking experiment")
    parser.add_argument("--random-state", type=int, default=42, help="Random seed for training")
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
        raise RuntimeError("No training examples were produced from the provided history data.")

    folds = build_time_series_folds(dataset, n_splits=args.n_splits)
    print(f"Built dataset with {len(dataset)} examples and {len(dataset['target_draw_no'].unique())} target draws")

    for fold in folds:
        train_df = dataset[dataset["target_draw_no"].isin(fold["train_draw_nos"])]
        val_df = dataset[dataset["target_draw_no"].isin(fold["val_draw_nos"])]
        if train_df.empty or val_df.empty:
            print(f"Skipping fold {fold['fold_index']} because train or validation split is empty")
            continue

        model = train_ranker(train_df, FEATURE_COLUMNS, model_type=args.model_type, random_state=args.random_state)
        metrics = evaluate_ranker(model, val_df, FEATURE_COLUMNS)

        print(f"Fold {fold['fold_index']} (holdout={fold['is_holdout']})")
        print(f"  train_draws={len(fold['train_draw_nos'])} val_draws={len(fold['val_draw_nos'])}")
        print(f"  roc_auc={metrics['roc_auc']:.4f} top7_recall={metrics['top7_recall']:.4f} top10_recall={metrics['top10_recall']:.4f} top14_recall={metrics['top14_recall']:.4f}")

    holdout_fold = next((fold for fold in folds if fold["is_holdout"]), None)
    if holdout_fold is None:
        raise RuntimeError("No holdout fold was defined by the requested split configuration.")

    holdout_train_df = dataset[dataset["target_draw_no"] < min(holdout_fold["val_draw_nos"])]
    if holdout_train_df.empty:
        raise RuntimeError("Holdout training set is empty; reduce n_splits or lower min_history_draws")

    final_model = train_ranker(holdout_train_df, FEATURE_COLUMNS, model_type=args.model_type, random_state=args.random_state)
    save_model(final_model, args.output_model)
    print(f"Saved trained model to {args.output_model}")


if __name__ == "__main__":
    main()
