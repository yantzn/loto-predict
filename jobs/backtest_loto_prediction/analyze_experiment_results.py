"""Analyze backtest experiment outputs.

experiment matrixで生成した複数JSONLを読み、strategy/profile/historyごとの比較表を作ります。
profileの勝ち筋をseed単体ではなく集計指標で判断するための補助ジョブです。
"""

from __future__ import annotations

import argparse
import json
import math
import random
from collections.abc import Sequence
from pathlib import Path
from typing import Any

import pandas as pd

BASELINE_STRATEGY_DEFAULT = "mixed"
METRIC_COLUMNS = [
    "second_count",
    "third_count",
    "second_plus_third",
    "weighted_prize_score",
    "expected_value_per_ticket",
    "avg_best_score",
    "avg_pairwise_jaccard",
    "unique_number_coverage",
]


def load_result_set(paths: Sequence[str | Path]) -> pd.DataFrame:
    records: list[dict[str, Any]] = []

    for source_path in paths:
        source = Path(source_path)
        cohort = source.parent.name
        strategy = source.stem

        with source.open("r", encoding="utf-8") as file:
            for line in file:
                text = line.strip()
                if not text:
                    continue
                row = json.loads(text)

                tickets = row.get("tickets", [])
                second_count = sum(1 for ticket in tickets if ticket.get("prize") == "2等相当")
                third_count = sum(1 for ticket in tickets if ticket.get("prize") == "3等相当")
                fourth_count = sum(1 for ticket in tickets if ticket.get("prize") == "4等相当")
                weighted_prize_score = 100 * second_count + 10 * third_count + fourth_count

                records.append({
                    "strategy": strategy,
                    "cohort": cohort,
                    "lottery_type": row.get("lottery_type"),
                    "target_draw_no": row.get("target_draw_no"),
                    "history_limit": row.get("history_limit"),
                    "seed": row.get("seed"),
                    "best_near_miss_score": row.get("best_near_miss_score"),
                    "avg_pairwise_jaccard": row.get("avg_pairwise_jaccard"),
                    "unique_number_coverage": row.get("unique_number_coverage"),
                    "expected_value_per_ticket": row.get("expected_value_per_ticket"),
                    "expected_value_sum": row.get("expected_value_sum"),
                    "roi_proxy": row.get("roi_proxy"),
                    "second_count": second_count,
                    "third_count": third_count,
                    "fourth_count": fourth_count,
                    "second_plus_third": second_count + third_count,
                    "weighted_prize_score": weighted_prize_score,
                })

    return pd.DataFrame.from_records(records)


def bootstrap_diff(series_a: Sequence[float], series_b: Sequence[float], n_boot: int = 2000) -> dict[str, float]:
    if not series_a or not series_b:
        raise ValueError("Both series must contain at least one observation")

    random_state = random.Random(0)
    diffs: list[float] = []
    for _ in range(n_boot):
        sample_a = [random_state.choice(series_a) for _ in range(len(series_a))]
        sample_b = [random_state.choice(series_b) for _ in range(len(series_b))]
        diffs.append((sum(sample_a) / len(sample_a)) - (sum(sample_b) / len(sample_b)))

    diffs.sort()
    lower_index = int((0.025) * len(diffs))
    upper_index = int((0.975) * len(diffs)) - 1
    mean_diff = sum(diffs) / len(diffs)
    return {
        "diff_mean": round(mean_diff, 4),
        "ci_lower": round(diffs[max(0, lower_index)], 4),
        "ci_upper": round(diffs[min(len(diffs) - 1, upper_index)], 4),
    }


def render_markdown_report(df: pd.DataFrame, output_path: str | Path) -> None:
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    lines: list[str] = []
    lines.append("# LOTO7 Experiment Matrix Report")
    lines.append("")
    lines.append("This report summarizes `mixed`, `pair_weighted`, `ema_recency`, `mixed_plus_diversity`, and `mixed_v2` strategies across the requested cohorts.")
    lines.append("")

    if df.empty:
        lines.append("No experiment data was available.")
        output_path.write_text("\n".join(lines), encoding="utf-8")
        return

    if {"runs", "avg_best_score"}.issubset(df.columns):
        summary_df = df.copy()
    else:
        grouped = df.groupby("cohort")
        summary_rows: list[dict[str, Any]] = []
        for (cohort_name, strategy), group in df.groupby(["cohort", "strategy"]):
            summary_rows.append({
                "cohort": cohort_name,
                "strategy": strategy,
                "runs": int(len(group)),
                "second_count": int(group["second_count"].sum()),
                "third_count": int(group["third_count"].sum()),
                "second_plus_third": int(group["second_plus_third"].sum()),
                "weighted_prize_score": float(group["weighted_prize_score"].mean()),
                "expected_value_per_ticket": float(group["expected_value_per_ticket"].mean()),
                "avg_best_score": float(group["best_near_miss_score"].mean()),
                "avg_pairwise_jaccard": float(group["avg_pairwise_jaccard"].mean()),
                "unique_number_coverage": float(group["unique_number_coverage"].mean()),
            })
        summary_df = pd.DataFrame.from_records(summary_rows)

    cohort_groups = summary_df.groupby("cohort")
    for cohort_name, cohort_df in cohort_groups:
        lines.append(f"## Cohort: {cohort_name}")
        lines.append("")

        summary = cohort_df.copy()
        if "weighted_rank" not in summary.columns:
            summary["weighted_rank"] = summary["weighted_prize_score"].rank(method="min", ascending=False).astype(int)
        if "ev_rank" not in summary.columns:
            summary["ev_rank"] = summary["expected_value_per_ticket"].rank(method="min", ascending=False).astype(int)

        summary = summary.sort_values(["weighted_rank", "ev_rank", "strategy"])

        columns = [
            "strategy",
            "runs",
            "second_count",
            "third_count",
            "second_plus_third",
            "weighted_prize_score",
            "expected_value_per_ticket",
            "avg_best_score",
            "avg_pairwise_jaccard",
            "unique_number_coverage",
            "weighted_rank",
            "ev_rank",
        ]

        lines.append("| " + " | ".join(columns) + " |")
        lines.append("| " + " | ".join(["---"] * len(columns)) + " |")

        for _, row in summary.iterrows():
            formatted = [
                str(row["strategy"]),
                str(int(row["runs"])),
                str(int(row["second_count"])),
                str(int(row["third_count"])),
                str(int(row["second_plus_third"])),
                f"{row['weighted_prize_score']:.2f}",
                f"{row['expected_value_per_ticket']:.2f}",
                f"{row['avg_best_score']:.2f}",
                f"{row['avg_pairwise_jaccard']:.4f}",
                f"{row['unique_number_coverage']:.2f}",
                str(int(row["weighted_rank"])),
                str(int(row["ev_rank"])),
            ]
            lines.append("| " + " | ".join(formatted) + " |")

        lines.append("")

    output_path.write_text("\n".join(lines), encoding="utf-8")


def analyze_experiment_results(input_dir: str | Path, output_md: str | Path) -> None:
    input_dir = Path(input_dir)
    output_md = Path(output_md)
    files = sorted(input_dir.rglob("*.jsonl"))
    if not files:
        raise FileNotFoundError(f"No JSONL files found under {input_dir}")

    df = load_result_set(files)
    if df.empty:
        raise ValueError("No experiment results were loaded")

    all_output_dir = output_md.parent
    all_output_dir.mkdir(parents=True, exist_ok=True)

    runs_csv_path = all_output_dir / "loto7_experiment_matrix_runs.csv"
    df.to_csv(runs_csv_path, index=False)

    summary_rows: list[dict[str, Any]] = []
    baseline_strategy = BASELINE_STRATEGY_DEFAULT

    for (cohort, strategy), group in df.groupby(["cohort", "strategy"]):
        baseline_group = df[(df["cohort"] == cohort) & (df["strategy"] == baseline_strategy)]
        row = {
            "cohort": cohort,
            "strategy": strategy,
            "runs": len(group),
            "second_count": int(group["second_count"].sum()),
            "third_count": int(group["third_count"].sum()),
            "second_plus_third": int(group["second_plus_third"].sum()),
            "weighted_prize_score": round(float(group["weighted_prize_score"].mean()), 4),
            "expected_value_per_ticket": round(float(group["expected_value_per_ticket"].mean()), 4),
            "avg_best_score": round(float(group["best_near_miss_score"].mean()), 4),
            "avg_pairwise_jaccard": round(float(group["avg_pairwise_jaccard"].mean()), 6),
            "unique_number_coverage": round(float(group["unique_number_coverage"].mean()), 4),
        }

        if not baseline_group.empty and strategy != baseline_strategy:
            for metric in [
                "weighted_prize_score",
                "expected_value_per_ticket",
                "avg_best_score",
                "avg_pairwise_jaccard",
                "unique_number_coverage",
            ]:
                diff = bootstrap_diff(
                    list(group[metric].astype(float)),
                    list(baseline_group[metric].astype(float)),
                    n_boot=2000,
                )
                row[f"{metric}_delta_mean"] = diff["diff_mean"]
                row[f"{metric}_delta_ci_lower"] = diff["ci_lower"]
                row[f"{metric}_delta_ci_upper"] = diff["ci_upper"]
        else:
            for metric in [
                "weighted_prize_score",
                "expected_value_per_ticket",
                "avg_best_score",
                "avg_pairwise_jaccard",
                "unique_number_coverage",
            ]:
                row[f"{metric}_delta_mean"] = 0.0
                row[f"{metric}_delta_ci_lower"] = 0.0
                row[f"{metric}_delta_ci_upper"] = 0.0

        summary_rows.append(row)

    summary_df = pd.DataFrame.from_records(summary_rows)
    summary_csv_path = all_output_dir / "loto7_experiment_matrix_summary.csv"
    summary_df.to_csv(summary_csv_path, index=False)

    render_markdown_report(summary_df, output_md)

    print(f"wrote runs CSV: {runs_csv_path}")
    print(f"wrote summary CSV: {summary_csv_path}")
    print(f"wrote markdown report: {output_md}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Analyze experiment matrix results and generate CSV/Markdown reports.")
    parser.add_argument("--input-dir", required=True, help="Directory containing experiment JSONL outputs")
    parser.add_argument("--output-md", required=True, help="Path to output Markdown report")
    args = parser.parse_args()
    analyze_experiment_results(args.input_dir, args.output_md)
