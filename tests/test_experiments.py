"""Tests for experimental LOTO7 ranker utilities.

dataset作成・ranker学習/評価の補助関数が、最小データでも期待する形の入出力になることを確認します。
"""

from __future__ import annotations

from pathlib import Path

import pandas as pd

from experiments.build_loto7_dataset import (
    FEATURE_COLUMNS,
    build_number_level_dataset,
    build_time_series_folds,
    extract_loto7_draws,
    load_loto7_history_from_csv,
)


def test_load_sample_history_csv() -> None:
    sample_path = Path(__file__).resolve().parents[1] / "data_samples" / "loto7_history_sample.csv"
    history_df = load_loto7_history_from_csv(sample_path)
    assert "draw_number" in history_df.columns
    draws = extract_loto7_draws(history_df)
    assert len(draws) >= 2
    assert draws[0]["draw_no"] < draws[-1]["draw_no"]


def test_build_number_level_dataset_contains_expected_columns() -> None:
    sample_path = Path(__file__).resolve().parents[1] / "data_samples" / "loto7_history_sample.csv"
    history_df = load_loto7_history_from_csv(sample_path)
    dataset = build_number_level_dataset(history_df, history_limit=5, min_history_draws=1)
    assert not dataset.empty
    assert set(FEATURE_COLUMNS).issubset(set(dataset.columns))
    assert dataset["number"].between(1, 37).all()
    assert dataset["label_main"].isin([0, 1]).all()
    assert dataset["label_bonus"].isin([0, 1]).all()


def test_build_time_series_folds_returns_holdout_last() -> None:
    synthetic = pd.DataFrame(
        {
            "target_draw_no": [1, 2, 3, 4, 5, 6, 7, 8],
            "number": [1, 2, 3, 4, 5, 6, 7, 8],
            "label_main": [0, 0, 1, 0, 1, 0, 1, 0],
        }
    )
    folds = build_time_series_folds(synthetic, n_splits=4)
    assert len(folds) == 3
    assert folds[-1]["is_holdout"] is True
    assert folds[0]["train_draw_nos"] == [1, 2]
    assert folds[1]["train_draw_nos"] == [1, 2, 3, 4]
    assert folds[2]["train_draw_nos"] == [1, 2, 3, 4, 5, 6]
