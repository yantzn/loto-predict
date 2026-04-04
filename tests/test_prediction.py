import pytest
from src.usecases.loto_prediction_usecase import generate_and_notify_prediction

def test_generate_prediction_loto6(monkeypatch):
    # BigQuery, LINEをモック
    monkeypatch.setattr("src.infrastructure.bigquery_client.bq_client.fetch_history", lambda table, limit: [
        {'draw_number': 1, 'n1': 1, 'n2': 2, 'n3': 3, 'n4': 4, 'n5': 5, 'n6': 6}
    ])
    monkeypatch.setattr("src.infrastructure.line_client.line_client.notify", lambda msg: None)
    result = generate_and_notify_prediction('loto6')
    assert 'predictions' in result
    assert len(result['predictions']) == 5

def test_generate_prediction_loto7(monkeypatch):
    monkeypatch.setattr("src.infrastructure.bigquery_client.bq_client.fetch_history", lambda table, limit: [
        {'draw_number': 1, 'n1': 1, 'n2': 2, 'n3': 3, 'n4': 4, 'n5': 5, 'n6': 6, 'n7': 7}
    ])
    monkeypatch.setattr("src.infrastructure.line_client.line_client.notify", lambda msg: None)
    result = generate_and_notify_prediction('loto7')
    assert 'predictions' in result
    assert len(result['predictions']) == 5
