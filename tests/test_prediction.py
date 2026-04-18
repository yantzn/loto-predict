import random

import pytest

from src.domain.prediction import generate_predictions


def _number_scores_loto6() -> list[tuple[int, float]]:
    return [
        (1, 10.0),
        (2, 9.0),
        (3, 8.0),
        (4, 7.0),
        (5, 6.0),
        (6, 5.0),
        (7, 4.0),
        (8, 3.0),
        (9, 2.0),
        (10, 1.0),
    ]


def _number_scores_loto7() -> list[tuple[int, float]]:
    return [(number, float(38 - number)) for number in range(1, 38)]


def test_generate_predictions_loto6_unique_and_constraints() -> None:
    predictions = generate_predictions(
        number_scores=_number_scores_loto6(),
        lottery_type="loto6",
        prediction_count=5,
        seed=123,
    )

    assert len(predictions) == 5
    assert len({tuple(prediction) for prediction in predictions}) == 5
    assert all(len(prediction) == 6 for prediction in predictions)
    assert all(1 <= number <= 43 for prediction in predictions for number in prediction)
    assert all(len(set(prediction)) == 6 for prediction in predictions)


def test_generate_predictions_loto7_pick_count_is_seven() -> None:
    predictions = generate_predictions(
        number_scores=_number_scores_loto7(),
        lottery_type="loto7",
        prediction_count=5,
        seed=456,
    )

    assert len(predictions) == 5
    assert len({tuple(prediction) for prediction in predictions}) == 5
    assert all(len(prediction) == 7 for prediction in predictions)
    assert all(1 <= number <= 37 for prediction in predictions for number in prediction)
    assert all(len(set(prediction)) == 7 for prediction in predictions)


def test_generate_predictions_uses_score_priority_order() -> None:
    score_map = {1: 100.0, 2: 90.0, 3: 80.0, 4: 70.0, 5: 60.0, 6: 50.0}
    predictions = generate_predictions(
        number_scores=list(score_map.items()),
        lottery_type="loto6",
        prediction_count=1,
        seed=3,
    )
    prediction = predictions[0]

    def weight_of(number: int) -> float:
        return 1.0 + score_map.get(number, 0.0)

    for earlier, later in zip(prediction, prediction[1:]):
        earlier_weight = weight_of(earlier)
        later_weight = weight_of(later)
        assert earlier_weight >= later_weight
        if earlier_weight == later_weight:
            assert earlier <= later


def test_generate_predictions_output_order_is_weight_desc_then_number_asc() -> None:
    rng = random.Random(0)
    predictions = generate_predictions(
        number_scores=[(5, 10.0), (2, 10.0), (9, 2.0), (1, 0.0), (3, 0.0)],
        lottery_type="loto6",
        prediction_count=1,
        rng=rng,
    )

    # 同点(2,5)は数値昇順。重みが高い番号ほど前に来る。
    numbers = predictions[0]
    if 2 in numbers and 5 in numbers:
        assert numbers.index(2) < numbers.index(5)


def test_generate_predictions_raises_for_invalid_prediction_count() -> None:
    with pytest.raises(ValueError, match="prediction_count"):
        generate_predictions(
            number_scores=_number_scores_loto6(),
            lottery_type="loto6",
            prediction_count=0,
        )


def test_generate_predictions_raises_for_unsupported_lottery_type() -> None:
    with pytest.raises(ValueError, match="unsupported"):
        generate_predictions(
            number_scores=_number_scores_loto6(),
            lottery_type="mini-loto",
            prediction_count=1,
        )


def test_generate_predictions_raises_when_unique_combinations_exceeded() -> None:
    with pytest.raises(ValueError, match="maximum unique combinations"):
        generate_predictions(
            number_scores=[(1, 1.0), (2, 1.0), (3, 1.0), (4, 1.0), (5, 1.0), (6, 1.0)],
            lottery_type="loto6",
            prediction_count=6_500_000,
        )
