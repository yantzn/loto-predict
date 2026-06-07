"""Backtest JSONL observability tests.

strategy/profile/seed/score_breakdownなど、後続分析に必要なmetadataがJSONLに出ることを確認します。
"""

import json
import pytest
from pathlib import Path

def test_output_jsonl_contains_strategy_metadata(tmp_path):
    from jobs.backtest_loto_prediction.main import _write_jsonl
    
    output_path = tmp_path / "test.jsonl"
    results = [{
        "strategy": "mixed_v2",
        "target_draw_no": 674,
        "history_limit": 200,
        "seed": 42,
        "lottery_type": "loto7",
        "best_near_miss_score": 100,
        "tickets": [{
            "ticket_no": 1,
            "profile_name": "lane1",
            "prediction": [1, 2, 3, 4, 5, 6, 7],
            "main_match": 3,
            "bonus_match": 0,
            "prize": "4等相当"
        }]
    }]
    
    _write_jsonl(str(output_path), results)
    
    rows = [json.loads(line) for line in output_path.read_text("utf-8").splitlines()]
    assert len(rows) == 1
    
    req_keys = {
        "strategy",
        "profile",
        "profile_learning_key",
        "profile_learning_candidate",
        "seed_optimization_used",
        "seed",
        "history_limit",
        "prediction",
        "score",
        "score_breakdown",
    }
    assert req_keys.issubset(rows[0].keys())
    assert rows[0]["strategy"] == "mixed_v2"
    assert rows[0]["profile"] == "lane1"
    assert rows[0]["profile_learning_candidate"] is True
    assert rows[0]["seed_optimization_used"] is False
    assert rows[0]["seed"] == 42
    assert rows[0]["history_limit"] == 200

def test_output_jsonl_score_breakdown_is_object(tmp_path):
    from jobs.backtest_loto_prediction.main import _write_jsonl
    
    output_path = tmp_path / "test2.jsonl"
    results = [{
        "strategy": "mixed_v2",
        "target_draw_no": 674,
        "history_limit": 200,
        "seed": 42,
        "lottery_type": "loto7",
        "best_near_miss_score": 100,
        "tickets": [{
            "ticket_no": 1,
            "profile_name": "lane1",
            "prediction": [1, 2, 3, 4, 5, 6, 7],
            "main_match": 3,
            "bonus_match": 0,
            "prize": "4等相当"
        }]
    }]
    
    _write_jsonl(str(output_path), results)
    rows = [json.loads(line) for line in output_path.read_text("utf-8").splitlines()]
    assert isinstance(rows[0]["score_breakdown"], dict)
    assert "base" in rows[0]["score_breakdown"]

def test_output_jsonl_prediction_length_is_7(tmp_path):
    from jobs.backtest_loto_prediction.main import _write_jsonl
    
    output_path = tmp_path / "test3.jsonl"
    results = [{
        "strategy": "mixed_v2",
        "target_draw_no": 674,
        "history_limit": 200,
        "seed": 42,
        "lottery_type": "loto7",
        "best_near_miss_score": 100,
        "tickets": [{
            "ticket_no": 1,
            "profile_name": "lane1",
            "prediction": [1, 2, 3, 4, 5, 6, 7],
            "main_match": 3,
            "bonus_match": 0,
            "prize": "4等相当"
        }]
    }]
    
    _write_jsonl(str(output_path), results)
    rows = [json.loads(line) for line in output_path.read_text("utf-8").splitlines()]
    assert len(rows[0]["prediction"]) == 7
