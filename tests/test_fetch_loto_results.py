"""
Fetch loto results function のテスト。

期待する動作:
1. RakutenLotoClient から最新ロト結果を取得
2. CSV にシリアライズして GCS に保存
3. Pub/Sub へ import メッセージを publish
4. 実行ログを BigQuery に記録
"""

import pytest
from unittest.mock import Mock, patch, MagicMock
from datetime import datetime, date

from src.usecases.fetch_loto_results import FetchLotoResultsInput, FetchLotoResultsUseCase
from src.infrastructure.serializer.loto_csv import parse_csv_to_rows
from io import StringIO


class MockLotoResult:
    """Mock用のLotoResult クラス"""
    def __init__(self, draw_no, draw_date, lottery_type, main_numbers, bonus_numbers, source_url):
        self.draw_no = draw_no
        self.draw_date = draw_date
        self.lottery_type = lottery_type
        self.main_numbers = main_numbers
        self.bonus_numbers = bonus_numbers
        self.source_url = source_url


def test_fetch_loto_results_usecase_success() -> None:
    """FetchLotoResultsUseCase が正常に結果を返すことを検証。"""
    # モック設定
    mock_settings = Mock()
    mock_settings.is_local = False
    mock_settings.gcp.project_id = "test-project"
    mock_settings.gcp.raw_bucket_name = "test-bucket"

    mock_loto_client = Mock()
    mock_result = MockLotoResult(
        draw_no=2094,
        draw_date="20260416",
        lottery_type="loto6",
        main_numbers=[3, 4, 7, 11, 24, 30],
        bonus_numbers=[16],
        source_url="https://example.com/loto6",
    )
    mock_loto_client.fetch_latest_result = Mock(return_value=mock_result)

    mock_storage_client = Mock()
    mock_storage_client.upload_bytes = Mock(return_value="gs://test-bucket/loto6/latest/latest.csv")

    mock_publisher = Mock()
    mock_publisher.publish_json = Mock(return_value="message-id-123")

    # usecase 実行
    usecase = FetchLotoResultsUseCase(
        settings=mock_settings,
        loto_client=mock_loto_client,
        storage_client=mock_storage_client,
        publisher=mock_publisher,
    )

    result = usecase.execute(
        FetchLotoResultsInput(
            lottery_type="loto6",
            publish_import_message=True,
            execution_id="test-exec-123",
        )
    )

    # 検証
    assert result.execution_id == "test-exec-123"
    assert result.lottery_type == "loto6"
    assert result.draw_no == 2094
    assert result.output_uri == "gs://test-bucket/loto6/latest/latest.csv"
    mock_loto_client.fetch_latest_result.assert_called_once_with("loto6")
    mock_storage_client.upload_bytes.assert_called_once()
    mock_publisher.publish_json.assert_called_once()


def test_fetch_loto_results_publish_payload() -> None:
    """publish メッセージが正しいペイロードを含むことを検証。"""
    mock_settings = Mock()
    mock_settings.is_local = False
    mock_settings.gcp.project_id = "test-project"
    mock_settings.gcp.raw_bucket_name = "test-bucket"

    mock_result = MockLotoResult(
        draw_no=2094,
        draw_date="20260416",
        lottery_type="loto6",
        main_numbers=[3, 4, 7, 11, 24, 30],
        bonus_numbers=[16],
        source_url="https://example.com",
    )

    mock_loto_client = Mock()
    mock_loto_client.fetch_latest_result = Mock(return_value=mock_result)

    mock_storage_client = Mock()
    mock_storage_client.upload_bytes = Mock(return_value="gs://test-bucket/loto6/latest/latest.csv")

    mock_publisher = Mock()
    mock_publisher.publish_json = Mock()

    usecase = FetchLotoResultsUseCase(
        settings=mock_settings,
        loto_client=mock_loto_client,
        storage_client=mock_storage_client,
        publisher=mock_publisher,
    )

    result = usecase.execute(
        FetchLotoResultsInput(
            lottery_type="loto6",
            publish_import_message=True,
            execution_id="test-exec-123",
        )
    )

    # publish 呼び出しを検証
    mock_publisher.publish_json.assert_called_once()
    published_payload = mock_publisher.publish_json.call_args[0][0]

    assert published_payload["lottery_type"] == "loto6"
    assert published_payload["gcs_uri"] == "gs://test-bucket/loto6/latest/latest.csv"
    assert published_payload["draw_no"] == 2094
    assert published_payload["execution_id"] == "test-exec-123"


def test_fetch_loto_results_no_publish_when_disabled() -> None:
    """publish_import_message=False の場合、publish を呼ばないことを検証。"""
    mock_settings = Mock()
    mock_settings.is_local = False
    mock_settings.gcp.project_id = "test-project"
    mock_settings.gcp.raw_bucket_name = "test-bucket"

    mock_result = MockLotoResult(
        draw_no=2094,
        draw_date="20260416",
        lottery_type="loto6",
        main_numbers=[3, 4, 7, 11, 24, 30],
        bonus_numbers=[16],
        source_url="https://example.com",
    )

    mock_loto_client = Mock()
    mock_loto_client.fetch_latest_result = Mock(return_value=mock_result)

    mock_storage_client = Mock()
    mock_storage_client.upload_bytes = Mock(return_value="gs://test-bucket/loto6/latest/latest.csv")

    mock_publisher = Mock()

    usecase = FetchLotoResultsUseCase(
        settings=mock_settings,
        loto_client=mock_loto_client,
        storage_client=mock_storage_client,
        publisher=mock_publisher,
    )

    result = usecase.execute(
        FetchLotoResultsInput(
            lottery_type="loto6",
            publish_import_message=False,
            execution_id="test-exec-123",
        )
    )

    # publish が呼ばれていないことを確認
    mock_publisher.publish_json.assert_not_called()


def test_fetch_loto_results_loto7() -> None:
    """LOTO7 取得が正常に動作することを検証。"""
    mock_settings = Mock()
    mock_settings.is_local = False
    mock_settings.gcp.project_id = "test-project"
    mock_settings.gcp.raw_bucket_name = "test-bucket"

    mock_result = MockLotoResult(
        draw_no=673,
        draw_date="20260417",
        lottery_type="loto7",
        main_numbers=[6, 9, 10, 12, 16, 24, 32],
        bonus_numbers=[17, 19],
        source_url="https://example.com/loto7",
    )

    mock_loto_client = Mock()
    mock_loto_client.fetch_latest_result = Mock(return_value=mock_result)

    mock_storage_client = Mock()
    mock_storage_client.upload_bytes = Mock(return_value="gs://test-bucket/loto7/latest/latest.csv")

    mock_publisher = Mock()
    mock_publisher.publish_json = Mock()

    usecase = FetchLotoResultsUseCase(
        settings=mock_settings,
        loto_client=mock_loto_client,
        storage_client=mock_storage_client,
        publisher=mock_publisher,
    )

    result = usecase.execute(
        FetchLotoResultsInput(
            lottery_type="loto7",
            publish_import_message=True,
            execution_id="test-exec-456",
        )
    )

    assert result.lottery_type == "loto7"
    assert result.draw_no == 673
    assert result.output_uri == "gs://test-bucket/loto7/latest/latest.csv"
    mock_loto_client.fetch_latest_result.assert_called_once_with("loto7")
