"""Run a configured matrix of backtest commands.

YAMLに定義したstrategy/history/seed範囲を展開し、backtest CLIをまとめて実行します。
手作業のコマンド列を減らし、同条件比較を再現しやすくするためのジョブです。
"""

from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path
from typing import Any

import yaml

PROJECT_ROOT = Path(__file__).resolve().parents[2]
BACKTEST_CLI = PROJECT_ROOT / "jobs" / "backtest_loto_prediction" / "main.py"

STRATEGY_MAPPING: dict[str, str] = {
    "mixed": "mixed",
    "pair_weighted": "pair_weighted",
    "ema_recency": "ema_recency",
    "mixed_plus_diversity": "mixed",
    "mixed_v2": "mixed_v2",
}

DEFAULT_COHORT_NAME_TEMPLATE = "{from_draw}-{to_draw}"


def _load_yaml(path: str | Path) -> dict[str, Any]:
    config_path = Path(path)
    with config_path.open("r", encoding="utf-8") as file:
        config = yaml.safe_load(file)
    if not isinstance(config, dict):
        raise ValueError("experiment matrix config must be a YAML mapping")
    return config


def _resolve_path(path: str | None, base_dir: Path) -> Path:
    if path is None:
        raise ValueError("path cannot be None")
    resolved = Path(path)
    return resolved if resolved.is_absolute() else (base_dir / resolved)


def _to_cli_value(value: Any) -> str:
    if isinstance(value, bool):
        return "true" if value else "false"
    return str(value)


def _build_strategy_args(strategy: str, strategy_parameters: dict[str, Any] | None) -> list[str]:
    if strategy not in STRATEGY_MAPPING:
        raise ValueError(f"unsupported strategy: {strategy}")

    mapped_strategy = STRATEGY_MAPPING[strategy]
    args: list[str] = ["--strategy", mapped_strategy]

    if strategy == "mixed_plus_diversity":
        default_diversity_params = {
            "selector_max_overlap": 4,
            "selector_min_jaccard_distance": 0.43,
            "selector_candidate_pool_size": 20,
            "selector_diversity_weight": 0.25,
        }
        for key, value in default_diversity_params.items():
            if not strategy_parameters or key not in strategy_parameters:
                args.append(f"--{key.replace('_', '-')}")
                args.append(_to_cli_value(value))

    if strategy_parameters:
        for key, value in strategy_parameters.items():
            cli_key = f"--{key.replace('_', '-')}"
            args.append(cli_key)
            args.append(_to_cli_value(value))

    return args


def _build_backtest_command(
    lottery_type: str,
    input_jsonl: Path,
    target_from: int,
    target_to: int,
    history_limits: list[int],
    prediction_count: int,
    seed_from: int,
    seed_to: int,
    strategy: str,
    strategy_params: dict[str, Any] | None,
    output_jsonl: Path,
) -> list[str]:
    command = [sys.executable, str(BACKTEST_CLI)]
    command.extend(["--lottery-type", lottery_type])
    command.extend(["--target-draw-from", str(target_from)])
    command.extend(["--target-draw-to", str(target_to)])
    command.extend(["--history-limits", ",".join(str(value) for value in history_limits)])
    command.extend(["--prediction-count", str(prediction_count)])
    command.extend(["--seed-from", str(seed_from)])
    command.extend(["--seed-to", str(seed_to)])
    command.extend(["--input-jsonl", str(input_jsonl)])
    command.extend(["--output-jsonl", str(output_jsonl)])
    command.extend(_build_strategy_args(strategy, strategy_params))
    return command


def run_experiment_matrix(config_path: str | Path) -> None:
    config_path = Path(config_path)
    base_dir = config_path.parent
    config = _load_yaml(config_path)

    lottery_type = str(config["lottery_type"]).strip()
    input_jsonl = _resolve_path(str(config["input_jsonl"]), base_dir)
    output_root = _resolve_path(str(config.get("output_root", "./local_storage/backtest/experiments")), base_dir)
    report_root = _resolve_path(str(config.get("report_root", "./local_storage/backtest/reports")), base_dir)

    strategies = [str(strategy) for strategy in config.get("strategies", [])]
    if not strategies:
        raise ValueError("config must include at least one strategy")

    cohorts = config.get("target_draw_ranges", [])
    if not cohorts:
        raise ValueError("config must include at least one target_draw_ranges entry")

    history_limits = [int(limit) for limit in config.get("history_limits", [100])]
    prediction_count = int(config.get("prediction_count", 5))
    seed_from = int(config.get("seed_from", 1))
    seed_to = int(config.get("seed_to", 1))
    strategy_parameters = config.get("strategy_parameters", {}) or {}

    if not input_jsonl.exists():
        raise FileNotFoundError(f"input_jsonl not found: {input_jsonl}")

    output_root.mkdir(parents=True, exist_ok=True)
    report_root.mkdir(parents=True, exist_ok=True)

    for cohort_config in cohorts:
        cohort_name = str(cohort_config.get("name") or DEFAULT_COHORT_NAME_TEMPLATE.format(
            from_draw=int(cohort_config["from"]),
            to_draw=int(cohort_config["to"]),
        ))
        cohort_dir = output_root / cohort_name
        cohort_dir.mkdir(parents=True, exist_ok=True)

        target_from = int(cohort_config["from"])
        target_to = int(cohort_config["to"])

        for strategy in strategies:
            strategy_params = strategy_parameters.get(strategy, {})
            output_jsonl = cohort_dir / f"{strategy}.jsonl"
            command = _build_backtest_command(
                lottery_type=lottery_type,
                input_jsonl=input_jsonl,
                target_from=target_from,
                target_to=target_to,
                history_limits=history_limits,
                prediction_count=prediction_count,
                seed_from=seed_from,
                seed_to=seed_to,
                strategy=strategy,
                strategy_params=strategy_params,
                output_jsonl=output_jsonl,
            )

            print(f"Running cohort={cohort_name} strategy={strategy} -> {output_jsonl}")
            result = subprocess.run(command, check=False, text=True, capture_output=True)
            if result.returncode != 0:
                raise RuntimeError(
                    f"Backtest command failed for cohort={cohort_name} strategy={strategy}:"
                    f"\nstdout={result.stdout}\nstderr={result.stderr}"
                )

    print()
    print("experiment_matrix complete")
    print(f"experiment results: {output_root}")
    print(f"reports root: {report_root}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Run a reproducible backtest experiment matrix.")
    parser.add_argument("--config", required=True, help="Path to experiment matrix YAML config")
    args = parser.parse_args()
    run_experiment_matrix(args.config)
