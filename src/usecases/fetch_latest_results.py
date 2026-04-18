from __future__ import annotations

from datetime import datetime, timezone

from src.infrastructure.loto_csv import serialize_results_to_csv


class FetchLatestResultsUseCase:
    """
    ユースケース: 最新のロト抽選結果を取得し、CSV化してGCSへ保存する。
    - 責務: スクレイピング、CSV変換、GCSアップロードのオーケストレーション
    - 外部I/F: scraper(抽選結果取得), gcs_client(GCS操作), logger(ロギング)
    """

    def __init__(self, scraper, gcs_client, bucket_name: str, logger) -> None:
        """
        Args:
            scraper: ロト抽選結果取得用スクレイパー
            gcs_client: GCSクライアント
            bucket_name (str): 保存先バケット名
            logger: ロギング用
        """
        self.scraper = scraper
        self.gcs_client = gcs_client
        self.bucket_name = bucket_name
        self.logger = logger

    def execute(self, lottery_type: str) -> dict:
        """
        最新のロト抽選結果を取得し、CSVとしてGCSへ保存する。

        Args:
            lottery_type (str): 'loto6' または 'loto7'

        Returns:
            dict: 保存結果サマリ
        """
        # ロト種別を小文字化
        lottery_type = str(lottery_type).lower()

        # 最新結果を取得
        result = self.scraper.fetch_latest_result(lottery_type)
        self.logger.info(f"Fetched latest result: lottery_type={lottery_type} draw_no={getattr(result, 'draw_no', None)}")

        # CSVテキストへ変換
        csv_text = serialize_results_to_csv(
            lottery_type=lottery_type,
            results=[result],
        )

        # 保存先パスを組み立て
        now = datetime.now(timezone.utc)
        draw_no = getattr(result, "draw_no", None)
        draw_date = getattr(result, "draw_date", None)
        blob_name = f"raw/{lottery_type}/{now:%Y/%m/%d}/{lottery_type}_{draw_no}.csv"

        # GCSへアップロード
        gcs_uri = self.gcs_client.upload_bytes(
            bucket_name=self.bucket_name,
            blob_name=blob_name,
            payload=csv_text.encode("utf-8"),
            content_type="text/csv",
        )

        self.logger.info(f"Uploaded csv to GCS: {gcs_uri}")

        return {
            "lottery_type": lottery_type,
            "draw_no": draw_no,
            "draw_date": str(draw_date),
            "gcs_uri": gcs_uri,
            "gcs_object": blob_name,
        }
