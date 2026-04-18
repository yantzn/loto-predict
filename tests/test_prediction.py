from src.domain.prediction import generate_predictions


def _history_rows(lottery_type: str) -> list[dict[str, object]]:
    if lottery_type == "loto6":
        return [
            {"draw_no": 1, "n1": 1, "n2": 2, "n3": 3, "n4": 4, "n5": 5, "n6": 6},
            {"draw_no": 2, "n1": 1, "n2": 8, "n3": 13, "n4": 21, "n5": 34, "n6": 42},
            {"draw_no": 3, "n1": 2, "n2": 4, "n3": 6, "n4": 8, "n5": 10, "n6": 12},
        ]

    return [
        {"draw_no": 1, "n1": 1, "n2": 2, "n3": 3, "n4": 4, "n5": 5, "n6": 6, "n7": 7},
        {"draw_no": 2, "n1": 2, "n2": 4, "n3": 6, "n4": 8, "n5": 10, "n6": 12, "n7": 14},
        {"draw_no": 3, "n1": 7, "n2": 11, "n3": 13, "n4": 17, "n5": 19, "n6": 23, "n7": 29},
    ]


def test_generate_predictions_loto6_unique_and_sorted() -> None:
    predictions = generate_predictions(
        history_rows=_history_rows("loto6"),
        lottery_type="loto6",
        prediction_count=5,
        seed=123,
    )

    assert len(predictions) == 5
    assert len({tuple(prediction) for prediction in predictions}) == 5
    assert all(len(prediction) == 6 for prediction in predictions)
    assert all(prediction == sorted(prediction) for prediction in predictions)


def test_generate_predictions_loto7_pick_count_is_seven() -> None:
    predictions = generate_predictions(
        history_rows=_history_rows("loto7"),
        lottery_type="loto7",
        prediction_count=5,
        seed=456,
    )

    assert len(predictions) == 5
    assert len({tuple(prediction) for prediction in predictions}) == 5
    assert all(len(prediction) == 7 for prediction in predictions)
    assert all(1 <= number <= 37 for prediction in predictions for number in prediction)
