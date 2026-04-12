from __future__ import annotations

import argparse
import json
import logging
import os
import sys
import time
from datetime import date, datetime
from pathlib import Path
from typing import Any

CURRENT_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = CURRENT_DIR.parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.append(str(PROJECT_ROOT))

from src.config.settings import get_settings
from src.infrastructure.gcs.storage_factory import create_storage_client
from src.infrastructure.loto_csv import serialize_results_to_csv
from src.infrastructure.rakuten_loto import RakutenLotoClient
from src.infrastructure.repositories.repository_factory import create_loto_repository

logging.basicConfig(level=os.getenv("LOG_LEVEL", "INFO"))
logger = logging.getLogger(__name__)


def parse_args() -> argparse.Namespace:
    """
    コマンドライン引数をパースする。
    --lottery-type, --start-date, --end-date などを受け付ける。
    """
    parser = argparse.ArgumentParser(
        description="Backfill loto history from Rakuten into local JSONL or BigQuery."
    )
    parser.add_argument(
        "--lottery-type",
        required=True,
        choices=["loto6", "loto7", "all"],
        help="Target lottery type.",
    )
    parser.add_argument(
        "--start-date",
        required=True,
        help="Start date in YYYY-MM-DD.",
    )
    parser.add_argument(
        "--end-date",
        required=True,
        help="End date in YYYY-MM-DD.",
    )
    parser.add_argument(
        "--save-raw-csv",
        action="store_true",
        help="Also save fetched history as CSV files into storage.",
    )
    parser.add_argument(
        "--sleep-seconds",
        type=float,
        default=0.0,
        help="Sleep between lottery types to reduce access pressure.",
    )
    return parser.parse_args()


def parse_iso_date(value: str) -> date:
    """
    YYYY-MM-DD形式の文字列をdate型に変換。
    """
    return datetime.strptime(value, "%Y-%m-%d").date()


def result_to_row(lottery_type: str, result: Any, source_file_name: str) -> dict[str, Any]:
    """
    楽天ロトAPIの結果オブジェクトをBigQuery用のdictに変換。
    lottery_typeごとにカラム構造が異なるため分岐。
    """
    if lottery_type == "loto6":
        main_numbers = list(result.main_numbers)
        bonus_numbers = list(result.bonus_numbers)
        return {
            "draw_no": int(result.draw_no),
            "draw_date": str(result.draw_date),
            "number1": int(main_numbers[0]),
            "number2": int(main_numbers[1]),
            "number3": int(main_numbers[2]),
            "number4": int(main_numbers[3]),
            "number5": int(main_numbers[4]),
            "number6": int(main_numbers[5]),
            "bonus_number": int(bonus_numbers[0]) if bonus_numbers else None,
            "source_file_name": source_file_name,
        }
    if lottery_type == "loto7":
        main_numbers = list(result.main_numbers)
        bonus_numbers = list(result.bonus_numbers)
        return {
            "draw_no": int(result.draw_no),
            "draw_date": str(result.draw_date),
            "number1": int(main_numbers[0]),
            "number2": int(main_numbers[1]),
            "number3": int(main_numbers[2]),
            "number4": int(main_numbers[3]),
            "number5": int(main_numbers[4]),
            "number6": int(main_numbers[5]),
            "number7": int(main_numbers[6]),
            "bonus_number1": int(bonus_numbers[0]) if len(bonus_numbers) > 0 else None,
            "bonus_number2": int(bonus_numbers[1]) if len(bonus_numbers) > 1 else None,
            "source_file_name": source_file_name,
        }
    raise ValueError(f"unsupported lottery_type: {lottery_type}")


def save_raw_csv(storage_client, lottery_type: str, results: list[Any]) -> str:
    """
    取得した履歴をCSV化し、GCSへ保存。保存先パスは日付ごとに分ける。
    """
    csv_text = serialize_results_to_csv(lottery_type=lottery_type, results=results)
    today = datetime.now().strftime("%Y/%m/%d")
    blob_name = f"raw/backfill/{lottery_type}/{today}/{lottery_type}_history.csv"
    settings = get_settings()
    storage_uri = storage_client.upload_bytes(
        bucket_name=settings.gcs_bucket_raw,
        blob_name=blob_name,
        payload=csv_text.encode("utf-8"),
        content_type="text/csv",
    )
    return storage_uri


def run_backfill_for_type(
    *,
    lottery_type: str,
    start_date: date,
    end_date: date,
    save_raw_csv_flag: bool,
) -> dict[str, Any]:
    """
    指定ロト種別・期間で楽天ロトから履歴を取得し、GCS/BigQueryへ保存。
    ローカル/GCP両対応。取得件数0件時は早期return。
    """
    settings = get_settings()
    logger.info(
        "Start backfill. lottery_type=%s start_date=%s end_date=%s app_env=%s",
        lottery_type,
        start_date,
        end_date,
        settings.env,
    )
    scraper = RakutenLotoClient()
    storage_client = create_storage_client()
    if settings.env == "local":
        bq_client = None
    else:
        from src.infrastructure.bigquery.bigquery_client import BigQueryClient
        bq_client = BigQueryClient(project_id=settings.gcp.project_id)
    repository = create_loto_repository(bq_client=bq_client)
    results = scraper.fetch_history(
        lottery_type=lottery_type,
        start_date=start_date,
        end_date=end_date,
    )
    if not results:
        logger.info("No results found. lottery_type=%s", lottery_type)
        return {
            "lottery_type": lottery_type,
            "fetched_results": 0,
            "inserted_rows": 0,
            "raw_csv_uri": None,
        }
    results = sorted(results, key=lambda x: int(x.draw_no))
    raw_csv_uri = None
    if save_raw_csv_flag:
        raw_csv_uri = save_raw_csv(storage_client, lottery_type, results)
        logger.info("Saved raw csv. lottery_type=%s storage_uri=%s", lottery_type, raw_csv_uri)
    rows = []
    for result in results:
        # GCS保存時のファイル名を記録（ローカル時はfile://対応）
        source_file_name = (
            Path(raw_csv_uri.replace("file://", "")).name
            if raw_csv_uri and raw_csv_uri.startswith("file://")
            else Path(raw_csv_uri).name if raw_csv_uri else "backfill"
        )
        rows.append(result_to_row(lottery_type, result, source_file_name))
    import_result = repository.import_rows(lottery_type=lottery_type, rows=rows)
    summary = {
        "lottery_type": lottery_type,
        "fetched_results": len(results),
        "inserted_rows": import_result.get("inserted_rows", 0),
        "draw_no_first": rows[0]["draw_no"] if rows else None,
        "draw_no_last": rows[-1]["draw_no"] if rows else None,
        "raw_csv_uri": raw_csv_uri,
        "import_result": import_result,
    }
    logger.info("Backfill completed. summary=%s", json.dumps(summary, ensure_ascii=False))
    return summary


def main() -> int:
    """
    コマンドライン引数を受け取り、ロト6/ロト7の履歴バックフィルを実行。
    --lottery-type=all指定時は両方を順次処理。sleep_secondsで間隔調整可。
    """
    args = parse_args()
    start_date = parse_iso_date(args.start_date)
    end_date = parse_iso_date(args.end_date)
    if start_date > end_date:
        raise ValueError("start-date must be <= end-date")
    lottery_types = ["loto6", "loto7"] if args.lottery_type == "all" else [args.lottery_type]
    all_results: list[dict[str, Any]] = []
    for idx, lottery_type in enumerate(lottery_types):
        result = run_backfill_for_type(
            lottery_type=lottery_type,
            start_date=start_date,
            end_date=end_date,
            save_raw_csv_flag=args.save_raw_csv,
        )
        all_results.append(result)
        # 両ロト連続実行時はsleepでアクセス負荷を下げる
        if idx < len(lottery_types) - 1 and args.sleep_seconds > 0:
            time.sleep(args.sleep_seconds)
    print(json.dumps({"status": "ok", "results": all_results}, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
