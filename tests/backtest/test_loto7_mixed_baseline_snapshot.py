"""Snapshot-style tests for mixed strategy summaries.

baseline backtest JSONLを要約し、summary比較ロジックが既知の結果を返すことを確認します。
"""

import pytest
import json
from pathlib import Path
import sys

# Add tools dir to sys.path to import it
PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from tools.extract_backtest_summary import summarize_backtest_jsonl, compare_summary

def test_loto7_mixed_baseline():
    expected = {
        "total_runs": 90000,
        "total_tickets": 450000,
        "overall_prizes": {
            "2等相当": 1,
            "3等相当": 10,
            "4等相当": 421,
        },
        "profile_prizes": {
            "main_hot": {"3等相当": 4},
            "main_balanced": {"3等相当": 3},
            "main_wide_bonus_hot": {"3等相当": 0},
            "main5_bonus2_balanced": {"2等相当": 1},
            "main5_bonus2_explore": {"3等相当": 2},
        }
    }
    
    jsonl_path = PROJECT_ROOT / "local_storage" / "backtest" / "loto7_analysis_20260601.jsonl"
    if not jsonl_path.exists():
        pytest.skip(f"Baseline JSONL not found at {jsonl_path}. Run full backtest to verify.")

    with jsonl_path.open("r", encoding="utf-8") as file:
        first_row = json.loads(file.readline())
    if first_row.get("strategy") != "mixed":
        pytest.skip(f"Snapshot file is not baseline mixed output: {jsonl_path}")
        
    actual = summarize_backtest_jsonl(jsonl_path)
    diffs = compare_summary(actual, expected)
    
    assert not diffs, "Baseline snapshot mismatch:\n" + "\n".join(diffs)
