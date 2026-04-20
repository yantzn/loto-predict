from __future__ import annotations

import argparse
import logging
import os
import sys
from datetime import datetime
from io import StringIO
from pathlib import Path
from typing import Any

CURRENT_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = CURRENT_DIR.parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.append(str(PROJECT_ROOT))

from src.config.settings import get_settings
from src.infrastructure.gcs.storage_factory import create_storage_client
from src.infrastructure.rakuten_loto import RakutenLotoClient
from src.infrastructure.serializer.loto_csv import serialize_results_to_csv

LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO").upper()
LOG_DIR = PROJECT_ROOT / "logs"
LOG_FILE = LOG_DIR / "backfill_loto_history.log"


def setup_logger() -> logging.Logger:
    """
    Backfill 実行時の状況をコンソールとファイルの両方に残す。
    取得失敗や 0 件時の切り分けをしやすくするため、stack trace も保存する。
    """
    LOG_DIR.mkdir(parents=True, exist_ok=True)

    logger = logging.getLogger("backfill_loto_history")
    logger.setLevel(LOG_LEVEL)

    if logger.handlers:
        return logger

    formatter = logging.Formatter(
        "%(asctime)s %(levelname)s %(name)s %(message)s"
    )

    stream_handler = logging.StreamHandler(sys.stdout)
    stream_handler.setLevel(LOG_LEVEL)
    stream_handler.setFormatter(formatter)

    file_handler = logging.FileHandler(LOG_FILE, encoding="utf-8")
    file_handler.setLevel(LOG_LEVEL)
    file_handler.setFormatter(formatter)

    logger.addHandler(stream_handler)
    logger.addHandler(file_handler)
    logger.propagate = False
    return logger


logger = setup_logger()


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Backfill loto history from Rakuten pages.")
    parser.add_argument("--lottery-type", required=True, choices=["loto6", "loto7"])
    parser.add_argument("--start-date", required=True, help="YYYY-MM-DD")
    parser.add_argument("--end-date", required=True, help="YYYY-MM-DD")
    parser.add_argument("--sleep-seconds", type=float, default=0.0)
    parser.add_argument("--output-path", required=True, help="Local path or gs:// URI")
    return parser.parse_args()


def _sample_results(results: list[Any], limit: int = 3) -> list[dict[str, Any]]:
    """
    ログ出力用に先頭数件だけを安全に整形する。
    オブジェクト構造が変わってもログで状況を追いやすいよう、主要属性のみ抜粋する。
    """
    samples: list[dict[str, Any]] = []

    for result in results[:limit]:
        samples.append(
            {
                "draw_no": getattr(result, "draw_no", None),
                "draw_date": str(getattr(result, "draw_date", None)),
                "main_numbers": getattr(result, "main_numbers", None),
                "bonus_numbers": getattr(result, "bonus_numbers", None),
            }
        )

    return samples


def save_results(results: list[Any], output_path: str, storage_client: Any) -> str:
    buffer = StringIO()
    serialize_results_to_csv(results, buffer)
    csv_text = buffer.getvalue()

    if output_path.startswith("gs://"):
        bucket_name, blob_name = output_path[len("gs://"):].split("/", 1)
        return storage_client.upload_bytes(
            bucket_name=bucket_name,
            blob_name=blob_name,
            payload=csv_text.encode("utf-8"),
            content_type="text/csv; charset=utf-8",
        )

    path = Path(output_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(csv_text, encoding="utf-8")
    return str(path.resolve())


def run_backfill(settings: Any, args: argparse.Namespace) -> str:
    start_date = datetime.strptime(args.start_date, "%Y-%m-%d").date()
    end_date = datetime.strptime(args.end_date, "%Y-%m-%d").date()

    if start_date > end_date:
        message = (
            f"Invalid date range. start_date={args.start_date} "
            f"end_date={args.end_date}"
        )
        logger.error(message)
        raise ValueError(message)

    logger.info(
        "Backfill started. lottery_type=%s start_date=%s end_date=%s sleep_seconds=%s output_path=%s",
        args.lottery_type,
        args.start_date,
        args.end_date,
        args.sleep_seconds,
        args.output_path,
    )

    client = RakutenLotoClient(sleep_seconds=args.sleep_seconds)
    results = client.fetch_history(
        lottery_type=args.lottery_type,
        start_date=start_date,
        end_date=end_date,
    )

    logger.info(
        "History fetched. lottery_type=%s count=%s sample=%s",
        args.lottery_type,
        len(results),
        _sample_results(results),
    )

    if not results:
        message = (
            f"No history found. lottery_type={args.lottery_type} "
            f"start_date={args.start_date} end_date={args.end_date}"
        )
        logger.error(message)
        raise ValueError(message)

    storage_client = create_storage_client(settings)
    output_uri = save_results(results, args.output_path, storage_client)

    logger.info(
        "Backfill completed. lottery_type=%s count=%s output=%s first_draw=%s last_draw=%s",
        args.lottery_type,
        len(results),
        output_uri,
        getattr(results[0], "draw_no", None),
        getattr(results[-1], "draw_no", None),
    )
    return output_uri


def main() -> int:
    args = parse_args()
    settings = get_settings()

    try:
        output_uri = run_backfill(settings, args)
        print(output_uri)
        logger.info("Backfill finished successfully. output_uri=%s", output_uri)
        return 0
    except Exception:
        logger.exception(
            "Backfill failed. lottery_type=%s start_date=%s end_date=%s output_path=%s",
            getattr(args, "lottery_type", None),
            getattr(args, "start_date", None),
            getattr(args, "end_date", None),
            getattr(args, "output_path", None),
        )
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
