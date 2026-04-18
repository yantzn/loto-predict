from __future__ import annotations

import argparse
import logging
import os
import sys
from datetime import datetime
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


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Backfill loto history from Rakuten pages.")
    parser.add_argument("--lottery-type", required=True, choices=["loto6", "loto7"])
    parser.add_argument("--start-date", required=True, help="YYYY-MM-DD")
    parser.add_argument("--end-date", required=True, help="YYYY-MM-DD")
    parser.add_argument("--sleep-seconds", type=float, default=0.0)
    parser.add_argument("--output-prefix", default="backfill")
    return parser.parse_args()


    args = _parse_args()
    settings = get_settings()

    start_date = datetime.strptime(args.start_date, "%Y-%m-%d").date()
    end_date = datetime.strptime(args.end_date, "%Y-%m-%d").date()

    scraper = RakutenLotoClient(sleep_seconds=args.sleep_seconds)
    storage_client = create_storage_client(settings)

    results = scraper.fetch_history(
        lottery_type=args.lottery_type,
        start_date=start_date,
        end_date=end_date,
    )

    if not results:
        logger.warning(
            "No history found. lottery_type=%s start_date=%s end_date=%s",
            args.lottery_type,
            args.start_date,
            args.end_date,
        )
        return 1

    import io
    buf = io.StringIO()
    serialize_results_to_csv(results, buf)
    csv_text = buf.getvalue()
    filename = (
        f"{args.output_prefix}/{args.lottery_type}/"
        f"{args.lottery_type}_{args.start_date.replace('-', '')}_{args.end_date.replace('-', '')}.csv"
    )

    bucket_name = settings.gcp.raw_bucket_name or "local-backfill"
    uri = storage_client.upload_bytes(
        bucket_name=bucket_name,
        blob_name=filename,
        payload=csv_text.encode("utf-8"),
        content_type="text/csv; charset=utf-8",
    )

    logger.info(
        "Backfill completed. lottery_type=%s count=%s output=%s first_draw=%s last_draw=%s",
        args.lottery_type,
        len(results),
        uri,
        results[0].draw_no,
        results[-1].draw_no,
    )
    print(uri)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
