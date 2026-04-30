"""
Backfill loto history job のテスト。

期待する動作:
1. 指定期間の結果を RakutenLotoClient から取得
2. CSV にシリアライズして GCS に保存
3. ログに成功メッセージ を出力
"""

import pytest
from unittest.mock import Mock, MagicMock, patch
from datetime import datetime
from io import StringIO

from jobs.backfill_loto_history.main import save_results, _sample_results


def test_sample_results_extracts_key_fields() -> None:
    """_sample_results が主要属性を正しく抽出することを検証。"""
    results = [
        Mock(draw_no=2094, draw_date="20260416", main_numbers=[3, 4, 7, 11, 24, 30], bonus_numbers=[16]),
        Mock(draw_no=2093, draw_date="20260413", main_numbers=[2, 10, 21, 26, 29, 38], bonus_numbers=[12]),
    ]

    samples = _sample_results(results, limit=2)

    assert len(samples) == 2
    assert samples[0]["draw_no"] == 2094
    assert samples[0]["draw_date"] == "20260416"
    assert samples[0]["main_numbers"] == [3, 4, 7, 11, 24, 30]


def test_sample_results_handles_limit() -> None:
    """_sample_results が limit パラメータを正しく使うことを検証。"""
    results = [Mock(draw_no=i, draw_date="2026-01-01", main_numbers=[], bonus_numbers=[]) for i in range(10)]

    samples = _sample_results(results, limit=3)

    assert len(samples) == 3


def test_save_results_to_gcs_path() -> None:
    """save_results が gs:// パスへ正しく保存することを検証。"""
    results = [
        Mock(draw_no=2094, draw_date="20260416", main_numbers=[3, 4, 7, 11, 24, 30], bonus_numbers=[16], lottery_type="loto6", source_url="https://example.com"),
    ]

    mock_storage_client = Mock()
    mock_storage_client.upload_bytes = Mock(return_value="gs://bucket/loto6_20260416.csv")

    result_path = save_results(
        results,
        output_path="gs://bucket/loto6_20260416.csv",
        storage_client=mock_storage_client,
    )

    mock_storage_client.upload_bytes.assert_called_once()
    assert result_path == "gs://bucket/loto6_20260416.csv"


def test_save_results_to_local_path() -> None:
    """save_results がローカルパスへ正しく保存することを検証。"""
    import tempfile
    from pathlib import Path

    results = [
        Mock(draw_no=2094, draw_date="20260416", main_numbers=[3, 4, 7, 11, 24, 30], bonus_numbers=[16], lottery_type="loto6", source_url="https://example.com"),
    ]

    with tempfile.TemporaryDirectory() as tmpdir:
        output_path = str(Path(tmpdir) / "loto6.csv")

        # ローカル保存なので storage_client は不要だが、ダミーを渡す
        mock_storage_client = Mock()

        result_path = save_results(
            results,
            output_path=output_path,
            storage_client=mock_storage_client,
        )

        # ローカルファイルが作成されたことを確認
        assert Path(result_path).exists()
        assert result_path == str(Path(output_path).resolve())
