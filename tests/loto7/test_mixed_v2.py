"""Tests for the LOTO7 mixed_v2 strategy.

mixed_v2のlane構成、pair fallback、5口重複回避、seed再現性を検証します。
mixed_v3比較のbaselineが壊れないようにするためのテストです。
"""

from src.domain.statistics import (
    ScoreWeights,
    calculate_bonus_number_scores,
    calculate_main_number_scores,
)
from src.domain.strategies.mixed_v2 import (
    MixedStrategyV2,
    SlotConfig,
    allocate_strategy_slots,
    build_lane3_pair_weighted_scores,
    build_default_mixed_v2_config,
)
from src.domain.prediction import generate_predictions


def _build_sample_history() -> list[list[int]]:
    return [
        [1, 2, 3, 4, 5, 6, 7],
        [8, 9, 10, 11, 12, 13, 14],
        [15, 16, 17, 18, 19, 20, 21],
        [22, 23, 24, 25, 26, 27, 28],
        [29, 30, 31, 32, 33, 34, 35],
        [2, 4, 6, 8, 10, 12, 14],
        [3, 5, 7, 9, 11, 13, 15],
    ]


def test_build_default_mixed_v2_config_has_five_slots() -> None:
    config = build_default_mixed_v2_config()

    assert len(config.slots) == 5
    assert config.slots[0].strategy == "ema_hot_or_main_hot"
    assert config.slots[3].strategy == "bonus2_balanced"
    assert any(slot.bonus_aware for slot in config.slots)


def test_allocate_strategy_slots_switches_based_on_history_limit() -> None:
    short_slots = allocate_strategy_slots(history_limit=100)
    long_slots = allocate_strategy_slots(history_limit=200)

    assert short_slots[0].strategy == "main_hot"
    assert short_slots[1].strategy == "main_balanced"
    assert short_slots[3].strategy == "bonus2_balanced"
    assert long_slots[0].strategy == "ema_hot"
    assert long_slots[1].strategy == "ema_balanced"


def test_mixed_v2_history_limit_100_is_primary_profile_axis() -> None:
    config = build_default_mixed_v2_config()

    assert config.history_threshold_for_ema == 200
    assert allocate_strategy_slots(history_limit=100)[0].strategy == "main_hot"
    assert allocate_strategy_slots(history_limit=100)[1].strategy == "main_balanced"


def test_mixed_v2_pair_and_explore_lanes_are_downweighted() -> None:
    config = build_default_mixed_v2_config()

    assert config.diverse_candidate_pool_size == 18
    assert config.diverse_main_ratio > config.diverse_bonus_ratio
    assert config.diverse_quality_weight < 0.001


def test_mixed_v2_generate_predictions_returns_five_unique_tickets() -> None:
    history = _build_sample_history()
    main_scores = calculate_main_number_scores(history, ScoreWeights())
    bonus_scores = calculate_bonus_number_scores(history, ScoreWeights())

    predictions = generate_predictions(
        number_scores=main_scores,
        bonus_scores=bonus_scores,
        lottery_type="loto7",
        prediction_count=5,
        strategy="mixed_v2",
        history=history,
        seed=42,
    )

    assert len(predictions) == 5
    assert len({tuple(prediction) for prediction in predictions}) == 5
    assert all(len(prediction) == 7 for prediction in predictions)


def test_mixed_v2_can_generate_fewer_than_five_tickets() -> None:
    history = _build_sample_history()
    main_scores = calculate_main_number_scores(history, ScoreWeights())
    bonus_scores = calculate_bonus_number_scores(history, ScoreWeights())

    predictions = generate_predictions(
        number_scores=main_scores,
        bonus_scores=bonus_scores,
        lottery_type="loto7",
        prediction_count=3,
        strategy="mixed_v2",
        history=history,
        seed=7,
    )

    assert len(predictions) == 3
    assert len({tuple(prediction) for prediction in predictions}) == 3


def test_lane3_pair_weighted_uses_fallback_when_pair_support_sparse() -> None:
    history = [
        [1, 2, 3, 4, 5, 6, 7],
        [8, 9, 10, 11, 12, 13, 14],
    ]
    main_scores = dict(calculate_main_number_scores(history, ScoreWeights()))

    rows = build_lane3_pair_weighted_scores(
        history=history,
        main_score_map=main_scores,
        selected=[1],
        config=build_default_mixed_v2_config().pair_config,
        min_pair_support=2.0,
    )

    assert rows[8]["fallback_used"] is True
    assert rows[8]["pair_support"] < 2.0


def test_lane3_pair_weighted_reduces_pair_weight_for_upper_hit_focus() -> None:
    history = [
        [1, 2, 3, 4, 5, 6, 7],
        [1, 2, 3, 8, 9, 10, 11],
        [1, 2, 4, 12, 13, 14, 15],
    ]
    main_scores = dict(calculate_main_number_scores(history, ScoreWeights()))

    rows = build_lane3_pair_weighted_scores(
        history=history,
        main_score_map=main_scores,
        selected=[1, 2],
        config=build_default_mixed_v2_config().pair_config,
        min_pair_support=0.0,
    )

    row = rows[3]
    expected = (
        0.62 * float(row["base"])
        + 0.25 * float(row["ema"])
        + 0.08 * float(row["pair"])
        + 0.05 * float(row["explore_bonus"])
    )
    assert abs(float(row["final"]) - expected) < 1e-9
