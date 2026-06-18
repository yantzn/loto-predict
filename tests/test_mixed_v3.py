"""Tests for the LOTO7 mixed_v3 strategy.

profile定義、weight/windowの調整方針、組合せ補正、5口生成の基本不変条件を守るためのテストです。
650-679 validation結果を受けた再調整が意図せず戻らないようにします。
"""

import pytest
import random

from src.domain.strategies.mixed_v3 import (
    PROFILE_HISTORY_WINDOWS,
    PROFILE_SCORE_WEIGHTS,
    PROFILE_TOP_K,
    MixedStrategyV3,
    build_default_mixed_v3_config,
    _calculate_sum_percentiles,
    _normalize,
    MIXED_V3_PROFILES
)

def test_mixed_v3_profiles_count():
    assert len(MIXED_V3_PROFILES) == 5
    assert "lane1_ema_hot_core" in MIXED_V3_PROFILES
    assert "lane2_pair_weighted_core" in MIXED_V3_PROFILES
    assert "lane3_long_200_balanced" in MIXED_V3_PROFILES
    assert "lane4_bonus_aware_balanced" in MIXED_V3_PROFILES
    assert "lane5_diversity_repair" in MIXED_V3_PROFILES


def test_mixed_v3_weights_follow_validation_adjustment():
    for profile in MIXED_V3_PROFILES:
        assert sum(PROFILE_SCORE_WEIGHTS[profile].values()) == pytest.approx(1.0)

    assert PROFILE_HISTORY_WINDOWS["lane1_ema_hot_core"]["primary"] == 100
    assert PROFILE_HISTORY_WINDOWS["lane2_pair_weighted_core"]["primary"] == 100
    assert PROFILE_HISTORY_WINDOWS["lane5_diversity_repair"]["primary"] == 50

    assert PROFILE_SCORE_WEIGHTS["lane2_pair_weighted_core"]["pair_affinity"] <= 0.05
    assert PROFILE_SCORE_WEIGHTS["lane4_bonus_aware_balanced"]["bonus_affinity"] <= 0.05
    assert 0.20 <= PROFILE_SCORE_WEIGHTS["lane5_diversity_repair"]["coverage_gap"] <= 0.25
    assert PROFILE_TOP_K["lane1_ema_hot_core"] < PROFILE_TOP_K["lane5_diversity_repair"]
    assert PROFILE_TOP_K["lane4_bonus_aware_balanced"] < PROFILE_TOP_K["lane5_diversity_repair"]
    assert build_default_mixed_v3_config().candidate_attempts >= 8

def test_mixed_v3_normalization():
    # Empty scores
    assert _normalize({}) == {n: 0.0 for n in range(1, 38)}
    # Same scores
    assert _normalize({1: 5.0, 2: 5.0}) == {1: 0.0, 2: 0.0}
    # Normal scores
    scores = {1: 10.0, 2: 0.0, 3: 5.0}
    norm = _normalize(scores)
    assert norm[1] == 1.0
    assert norm[2] == 0.0
    assert norm[3] == 0.5

def test_mixed_v3_sum_percentiles():
    # Construct history to have known sums
    history = [
        [1, 2, 3, 4, 5, 6, 7], # sum 28
        [10, 11, 12, 13, 14, 15, 16], # sum 91
        [20, 21, 22, 23, 24, 25, 26], # sum 161
        [31, 32, 33, 34, 35, 36, 37], # sum 238
    ]
    p = _calculate_sum_percentiles(history)
    assert p["p10"] == 28
    assert p["p25"] == 91
    assert p["p50"] == 161
    assert p["p75"] == 238
    assert p["p90"] == 238

def test_mixed_v3_combination_evaluation():
    config = build_default_mixed_v3_config()
    strategy = MixedStrategyV3(config)
    base_weights = {n: 0.1 for n in range(1, 38)}
    sum_percentiles = {"p10": 50, "p25": 100, "p50": 140, "p75": 180, "p90": 220}
    existing_tickets = [[1, 2, 3, 4, 5, 6, 7]]
    
    # Eval completely disjoint ticket with good properties
    ticket = [8, 15, 22, 29, 30, 31, 35] # sum: 170 (p25-p75), 4 odds, range: low(1), mid(2), high(4)
    # consecutives: 29,30,31 (3 numbers => 2 pairs)
    score1 = strategy._evaluate_combination(
        ticket, base_weights, existing_tickets, sum_percentiles, "lane1_ema_hot_core"
    )
    
    # 5 overlaps
    ticket2 = [1, 2, 3, 4, 5, 30, 31]
    score2 = strategy._evaluate_combination(
        ticket2, base_weights, existing_tickets, sum_percentiles, "lane1_ema_hot_core"
    )
    
    assert score1 > score2
    
    # diversity_repair 4 overlap
    ticket3 = [1, 2, 3, 4, 20, 21, 22]
    score3_lane1 = strategy._evaluate_combination(
        ticket3, base_weights, existing_tickets, sum_percentiles, "lane1_ema_hot_core"
    )
    score3_lane5 = strategy._evaluate_combination(
        ticket3, base_weights, existing_tickets, sum_percentiles, "lane5_diversity_repair"
    )
    assert score3_lane5 < score3_lane1

def test_mixed_v3_generate_predictions():
    config = build_default_mixed_v3_config()
    strategy = MixedStrategyV3(config)
    history = [
        [1, 2, 3, 4, 5, 6, 7]
    ] * 210
    bonus_scores = [(n, 0.1) for n in range(1, 38)]
    predictions = strategy.generate_predictions(
        history=history,
        prediction_count=5,
        seed=42,
        bonus_scores=bonus_scores
    )
    assert len(predictions) == 5
    for p in predictions:
        assert len(p) == 7
        assert len(set(p)) == 7
