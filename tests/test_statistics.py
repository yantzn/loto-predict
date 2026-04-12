import pytest
from src.infrastructure.bigquery_client import BigQueryClient


def test_merge_staging_to_main(monkeypatch):
    """
    BigQueryClientのmerge_staging_to_mainが正常に呼ばれることを検証。
    クエリ実行部分はモック化。
    """
    bq = BigQueryClient()
    # クエリ実行をモック
    monkeypatch.setattr(bq, 'client', type('Dummy', (), {'query': lambda self, sql: type('Q', (), {'result': lambda self: None})()})())
    result = bq.merge_staging_to_main('staging', 'main', ['draw_number'])
    assert result is not None
