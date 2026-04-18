from __future__ import annotations

import argparse
import logging
import os
import sys
from datetime import datetime
from io import StringIO
from pathlib import Path

CURRENT_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = CURRENT_DIR.parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.append(str(PROJECT_ROOT))

from src.config.settings import get_settings
from src.infrastructure.gcs.storage_factory import create_storage_client
from src.infrastructure.rakuten_loto import RakutenLotoClient
from src.infrastructure.serializer.loto_csv import serialize_results_to_csv

logging.basicConfig(level=os.getenv("LOG_LEVEL", "INFO"))
logger = logging.getLogger(__name__)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Backfill loto history from Rakuten pages.")
    parser.add_argument("--lottery-type", required=True, choices=["loto6", "loto7"])
    parser.add_argument("--start-date", required=True, help="YYYY-MM-DD")
    parser.add_argument("--end-date", required=True, help="YYYY-MM-DD")
    parser.add_argument("--sleep-seconds", type=float, default=0.0)
    parser.add_argument("--output-path", required=True, help="Local path or gs:// URI")
    return parser.parse_args()


def save_results(results, output_path: str, settings, storage_client) -> str:
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


def run_backfill(settings, args: argparse.Namespace) -> str:
    start_date = datetime.strptime(args.start_date, "%Y-%m-%d").date()
    end_date = datetime.strptime(args.end_date, "%Y-%m-%d").date()

    client = RakutenLotoClient(sleep_seconds=args.sleep_seconds)
    results = client.fetch_history(
        lottery_type=args.lottery_type,
        start_date=start_date,
        end_date=end_date,
    )
    if not results:
        raise ValueError(
            f"No history found. lottery_type={args.lottery_type} start_date={args.start_date} end_date={args.end_date}"
        )

    storage_client = create_storage_client(settings)
    output_uri = save_results(results, args.output_path, settings, storage_client)
    logger.info(
        "Backfill completed. lottery_type=%s count=%s output=%s first_draw=%s last_draw=%s",
        args.lottery_type,
        len(results),
        output_uri,
        results[0].draw_no,
        results[-1].draw_no,
    )
    return output_uri


def main() -> int:
    args = parse_args()
    settings = get_settings()
    output_uri = run_backfill(settings, args)
    print(output_uri)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
