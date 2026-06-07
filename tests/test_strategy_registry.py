"""Strategy registry tests.

prediction entrypointとbacktest CLIで利用できるstrategy名の整合性を確認します。
"""

import pytest
from src.domain.prediction import generate_predictions

def test_registry_contains_mixed_variants():
    # Provide minimal mocks to ensure the factory dispatch works
    # We are testing that the registry doesn't raise "Unknown strategy"
    number_scores = [(i, 1.0) for i in range(1, 38)]
    bonus_scores = [(i, 1.0) for i in range(1, 38)]
    history = [[1, 2, 3, 4, 5, 6, 7]] * 10

    # mixed
    generate_predictions(
        number_scores=number_scores,
        bonus_scores=bonus_scores,
        lottery_type="loto7",
        prediction_count=1,
        strategy="mixed",
        seed=1,
    )

    # mixed_v2
    generate_predictions(
        number_scores=number_scores,
        bonus_scores=bonus_scores,
        lottery_type="loto7",
        prediction_count=1,
        strategy="mixed_v2",
        seed=1,
        history=history,
    )

    # triple_weighted
    generate_predictions(
        number_scores=number_scores,
        bonus_scores=bonus_scores,
        lottery_type="loto7",
        prediction_count=1,
        strategy="triple_weighted",
        seed=1,
        history=history,
    )

    # mixed_loto6
    generate_predictions(
        number_scores=[(i, 1.0) for i in range(1, 44)],
        lottery_type="loto6",
        prediction_count=1,
        strategy="mixed_loto6",
        seed=1,
        history=[[1, 2, 3, 4, 5, 6]] * 10,
    )

def test_unknown_strategy_fails_fast():
    number_scores = [(i, 1.0) for i in range(1, 38)]
    
    with pytest.raises(ValueError, match="Unknown strategy"):
        generate_predictions(
            number_scores=number_scores,
            lottery_type="loto7",
            prediction_count=1,
            strategy="invalid_strategy_name",
        )
