"""Tests for experiment matrix jobs.

YAML設定からbacktestコマンドを展開する処理と、複数JSONLの分析処理を確認します。
"""

import json
import subprocess
from pathlib import Path
from tempfile import TemporaryDirectory

import pandas as pd
import yaml

from jobs.backtest_loto_prediction.analyze_experiment_results import (
    bootstrap_diff,
    load_result_set,
    render_markdown_report,
)
from jobs.backtest_loto_prediction.run_experiment_matrix import run_experiment_matrix


def test_load_result_set_parses_jsonl_and_computes_derived_metrics(tmp_path: Path) -> None:
    sample_path = tmp_path / "600-612" / "mixed.jsonl"
    sample_path.parent.mkdir(parents=True)
    data = {
        "lottery_type": "loto7",
        "target_draw_no": 600,
        "history_limit": 100,
        "seed": 1,
        "best_near_miss_score": 500,
        "avg_pairwise_jaccard": 0.12,
        "unique_number_coverage": 20,
        "expected_value_per_ticket": 150.0,
        "expected_value_sum": 900.0,
        "roi_proxy": 0.5,
        "tickets": [
            {"prize": "2等相当"},
            {"prize": "3等相当"},
            {"prize": "4等相当"},
            {"prize": "該当なし"},
            {"prize": "該当なし"},
        ],
    }
    sample_path.write_text(json.dumps(data, ensure_ascii=False) + "\n", encoding="utf-8")

    df = load_result_set([sample_path])

    assert df.shape[0] == 1
    assert df.loc[0, "strategy"] == "mixed"
    assert df.loc[0, "cohort"] == "600-612"
    assert df.loc[0, "second_count"] == 1
    assert df.loc[0, "third_count"] == 1
    assert df.loc[0, "second_plus_third"] == 2
    assert df.loc[0, "weighted_prize_score"] == 100 * 1 + 10 * 1 + 1 * 1
    assert df.loc[0, "expected_value_per_ticket"] == 150.0


def test_bootstrap_diff_returns_ci_for_two_series() -> None:
    series_a = [1.0, 2.0, 3.0, 4.0]
    series_b = [2.0, 3.0, 4.0, 5.0]

    result = bootstrap_diff(series_a, series_b, n_boot=200)

    assert isinstance(result, dict)
    assert result["ci_lower"] <= result["diff_mean"] <= result["ci_upper"]
    assert result["diff_mean"] < 0


def test_render_markdown_report_writes_markdown(tmp_path: Path) -> None:
    df = pd.DataFrame(
        [
            {
                "strategy": "mixed",
                "cohort": "600-612",
                "runs": 1,
                "second_count": 0,
                "third_count": 0,
                "second_plus_third": 0,
                "weighted_prize_score": 0.0,
                "expected_value_per_ticket": 0.0,
                "avg_best_score": 0.0,
                "avg_pairwise_jaccard": 0.0,
                "unique_number_coverage": 0.0,
                "weighted_rank": 1,
                "ev_rank": 1,
            }
        ]
    )
    output_md = tmp_path / "report.md"
    render_markdown_report(df, output_md)

    text = output_md.read_text(encoding="utf-8")
    assert "LOTO7 Experiment Matrix Report" in text
    assert "strategy" in text
    assert "mixed" in text


def test_run_experiment_matrix_invokes_backtest_cli(tmp_path: Path, monkeypatch) -> None:
    config_path = tmp_path / "loto7_experiment_matrix.yaml"
    experiment_root = tmp_path / "local_storage" / "backtest" / "experiments"
    report_root = tmp_path / "local_storage" / "backtest" / "reports"

    config = {
        "lottery_type": "loto7",
        "input_jsonl": "./local_storage/imported/loto7_history.jsonl",
        "output_root": str(experiment_root),
        "report_root": str(report_root),
        "history_limits": [100],
        "prediction_count": 5,
        "seed_from": 1,
        "seed_to": 1,
        "target_draw_ranges": [{"name": "600-612", "from": 600, "to": 612}],
        "strategies": ["mixed"],
    }
    config_path.write_text(yaml.safe_dump(config), encoding="utf-8")

    input_jsonl_path = tmp_path / "local_storage" / "imported" / "loto7_history.jsonl"
    input_jsonl_path.parent.mkdir(parents=True)
    input_jsonl_path.write_text("{}\n", encoding="utf-8")

    captured_commands: list[list[str]] = []

    class DummyCompletedProcess:
        def __init__(self) -> None:
            self.returncode = 0
            self.stdout = ""
            self.stderr = ""

    def fake_run(cmd, check=False, text=True, capture_output=True):
        captured_commands.append(cmd)
        output_path = Path(cmd[cmd.index("--output-jsonl") + 1])
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text("{}\n", encoding="utf-8")
        return DummyCompletedProcess()

    monkeypatch.setattr(subprocess, "run", fake_run)

    run_experiment_matrix(config_path)

    assert len(captured_commands) == 1
    assert "--strategy" in captured_commands[0]
    assert "mixed" in captured_commands[0]
    assert (experiment_root / "600-612" / "mixed.jsonl").exists()
