import pytest
from src.infrastructure.bigquery_client import BigQueryClient

def test_merge_staging_to_main(monkeypatch):
    bq = BigQueryClient()
    monkeypatch.setattr(bq, 'client', type('Dummy', (), {'query': lambda self, sql: type('Q', (), {'result': lambda self: None})()})())
    result = bq.merge_staging_to_main('staging', 'main', ['draw_number'])
    assert result is not None
