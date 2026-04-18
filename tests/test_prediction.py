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


def test_generate_predictions_loto6_unique_and_constraints() -> None:
    predictions = generate_predictions(
        history_rows=_history_rows("loto6"),
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
        history_rows=_history_rows("loto7"),
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
    history_rows = [
        {"draw_no": 1, "n1": 1, "n2": 1, "n3": 1, "n4": 2, "n5": 3, "n6": 4},
        {"draw_no": 2, "n1": 1, "n2": 2, "n3": 3, "n4": 4, "n5": 5, "n6": 6},
        {"draw_no": 3, "n1": 2, "n2": 3, "n3": 4, "n4": 5, "n5": 6, "n6": 7},
    ]
    predictions = generate_predictions(
        history_rows=history_rows,
        lottery_type="loto6",
        prediction_count=1,
        seed=9,
    )
    prediction = predictions[0]

    # この履歴では 1/2/3/4 の重みが高く、出力順も重み優先になる。
    if 1 in prediction and 6 in prediction:
        assert prediction.index(1) < prediction.index(6)


def test_generate_predictions_raises_for_invalid_prediction_count() -> None:
    try:
        generate_predictions(
            history_rows=_history_rows("loto6"),
            lottery_type="loto6",
            prediction_count=0,
        )
        assert False, "expected ValueError"
    except ValueError as exc:
        assert "prediction_count" in str(exc)


def test_generate_predictions_raises_for_unsupported_lottery_type() -> None:
    try:
        generate_predictions(
            history_rows=_history_rows("loto6"),
            lottery_type="mini-loto",
            prediction_count=1,
        )
        assert False, "expected ValueError"
    except ValueError as exc:
        assert "unsupported" in str(exc)
