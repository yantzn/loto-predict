"""Seed reproducibility tests.

同一seed・同一条件では同じ予想になり、異なるseedではmixed_v2/triple_weightedの予想が変化することを確認します。
"""

import pytest
import random
from src.domain.prediction import generate_predictions

def _generate_diverse_history():
    # To test that rng tie-breakers work, we need a history where many numbers
    # have the exact same scores (both base and triplet).
    history = []
    # 1..7, 8..14, 15..21, 22..28 all have exactly the same frequency (10)
    history.extend([list(range(1, 8))] * 10)
    history.extend([list(range(8, 15))] * 10)
    history.extend([list(range(15, 22))] * 10)
    history.extend([list(range(22, 29))] * 10)
    return history

def test_same_seed_same_predictions():
    number_scores = [(i, 1.0) for i in range(1, 38)]
    bonus_scores = [(i, 1.0) for i in range(1, 38)]
    history = _generate_diverse_history()

    # For mixed_v2
    preds1_mixed = generate_predictions(
        number_scores=number_scores,
        bonus_scores=bonus_scores,
        lottery_type="loto7",
        prediction_count=3,
        strategy="mixed_v2",
        seed=42,
        history=history,
        target_draw=100,
        history_limit=50,
    )
    
    preds2_mixed = generate_predictions(
        number_scores=number_scores,
        bonus_scores=bonus_scores,
        lottery_type="loto7",
        prediction_count=3,
        strategy="mixed_v2",
        seed=42,
        history=history,
        target_draw=100,
        history_limit=50,
    )
    assert preds1_mixed == preds2_mixed

    # For triple_weighted
    preds1_triple = generate_predictions(
        number_scores=number_scores,
        bonus_scores=bonus_scores,
        lottery_type="loto7",
        prediction_count=3,
        strategy="triple_weighted",
        seed=42,
        history=history,
        target_draw=100,
        history_limit=50,
    )

    preds2_triple = generate_predictions(
        number_scores=number_scores,
        bonus_scores=bonus_scores,
        lottery_type="loto7",
        prediction_count=3,
        strategy="triple_weighted",
        seed=42,
        history=history,
        target_draw=100,
        history_limit=50,
    )
    assert preds1_triple == preds2_triple

def test_different_seed_changes_predictions_for_mixed_v2():
    number_scores = [(i, 1.0) for i in range(1, 38)]
    bonus_scores = [(i, 1.0) for i in range(1, 38)]
    history = _generate_diverse_history()
    
    preds1 = generate_predictions(
        number_scores=number_scores,
        bonus_scores=bonus_scores,
        lottery_type="loto7",
        prediction_count=3,
        strategy="mixed_v2",
        seed=42,
        history=history,
    )
    
    preds2 = generate_predictions(
        number_scores=number_scores,
        bonus_scores=bonus_scores,
        lottery_type="loto7",
        prediction_count=3,
        strategy="mixed_v2",
        seed=43,
        history=history,
    )
    
    assert preds1 != preds2

def test_different_seed_changes_predictions_for_triple_weighted():
    number_scores = [(i, 1.0) for i in range(1, 38)]
    bonus_scores = [(i, 1.0) for i in range(1, 38)]
    history = _generate_diverse_history()
    
    preds1 = generate_predictions(
        number_scores=number_scores,
        bonus_scores=bonus_scores,
        lottery_type="loto7",
        prediction_count=3,
        strategy="triple_weighted",
        seed=42,
        history=history,
    )
    
    preds2 = generate_predictions(
        number_scores=number_scores,
        bonus_scores=bonus_scores,
        lottery_type="loto7",
        prediction_count=3,
        strategy="triple_weighted",
        seed=43,
        history=history,
    )
    
    assert preds1 != preds2
