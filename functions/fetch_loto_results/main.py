from __future__ import annotations

import csv
import io
import logging
import os
import re
import uuid
from dataclasses import dataclass
from typing import Iterable

import requests
from bs4 import BeautifulSoup
from google.cloud import pubsub_v1, storage

from common.execution_log import log_and_write
from common.pubsub_message import to_pubsub_data
from common.time_utils import now_local_iso

logging.basicConfig(level=os.getenv("LOG_LEVEL", "INFO"))
logger = logging.getLogger(__name__)

PROJECT_ID = os.environ["GCP_PROJECT_ID"]
RAW_BUCKET_NAME = os.environ["RAW_BUCKET_NAME"]
IMPORT_TOPIC_NAME = os.environ["IMPORT_TOPIC_NAME"]

LOTO6_PAGE_URL = "https://www.mizuhobank.co.jp/takarakuji/check/loto/loto6/index.html"
LOTO7_PAGE_URL = "https://www.mizuhobank.co.jp/takarakuji/check/loto/loto7/index.html"

REQUEST_TIMEOUT_SECONDS = 60

storage_client = storage.Client(project=PROJECT_ID)
publisher = pubsub_v1.PublisherClient()
topic_path = publisher.topic_path(PROJECT_ID, IMPORT_TOPIC_NAME)


@dataclass(frozen=True)
class LotoResult:
    lottery_type: str
    draw_no: int
    draw_date: str
    main_numbers: list[int]
    bonus_numbers: list[int]


def _extract_request_json(request) -> dict:
    payload = request.get_json(silent=True)
    return payload or {}


def _page_url_for(lottery_type: str) -> str:
    if lottery_type == "LOTO6":
        return LOTO6_PAGE_URL
    if lottery_type == "LOTO7":
        return LOTO7_PAGE_URL
    raise ValueError(f"unsupported lottery_type: {lottery_type}")


def _normalize_text(html: str) -> str:
    soup = BeautifulSoup(html, "html.parser")
    text = soup.get_text("\n", strip=True)
    text = text.replace("\u3000", " ")
    return re.sub(r"[ \t]+", " ", text)


def _extract_draw_header(text: str, lottery_type: str) -> tuple[int, str]:
    pattern = rf"{lottery_type}\s*第(\d+)回\s*(\d{{4}})年(\d{{1,2}})月(\d{{1,2}})日抽せん"
    match = re.search(pattern, text)
    if not match:
        raise ValueError(f"failed to parse draw header for {lottery_type}")

    draw_no = int(match.group(1))
    yyyy = int(match.group(2))
    mm = int(match.group(3))
    dd = int(match.group(4))
    return draw_no, f"{yyyy:04d}-{mm:02d}-{dd:02d}"


def _iter_two_digit_numbers(text: str) -> Iterable[int]:
    for value in re.findall(r"(?<!\d)(\d{1,2})(?!\d)", text):
        yield int(value)


def _extract_number_blocks(text: str) -> tuple[list[int], list[int]]:
    lines = text.splitlines()
    main_numbers: list[int] | None = None
    bonus_numbers: list[int] | None = None

    for idx, line in enumerate(lines):
        normalized = line.strip()

        if normalized == "本数字":
            values: list[int] = []
            for next_line in lines[idx + 1 : idx + 8]:
                values.extend(list(_iter_two_digit_numbers(next_line)))
                if len(values) >= 7:
                    break
            main_numbers = values

        if normalized == "ボーナス数字":
            values = []
            for next_line in lines[idx + 1 : idx + 5]:
                values.extend(list(_iter_two_digit_numbers(next_line)))
                if len(values) >= 2:
                    break
            bonus_numbers = values

        if main_numbers is not None and bonus_numbers is not None:
            break

    if main_numbers is None or bonus_numbers is None:
        raise ValueError("failed to parse numbers")

    return main_numbers, bonus_numbers


def _parse_latest_result(html: str, lottery_type: str) -> LotoResult:
    text = _normalize_text(html)
    draw_no, draw_date = _extract_draw_header(text, lottery_type)
    main_numbers, bonus_numbers = _extract_number_blocks(text)

    if lottery_type == "LOTO6":
        main_numbers = main_numbers[:6]
        bonus_numbers = bonus_numbers[:1]
    else:
        main_numbers = main_numbers[:7]
        bonus_numbers = bonus_numbers[:2]

    return LotoResult(
        lottery_type=lottery_type,
        draw_no=draw_no,
        draw_date=draw_date,
        main_numbers=main_numbers,
        bonus_numbers=bonus_numbers,
    )


def _download_latest_result(lottery_type: str) -> LotoResult:
    response = requests.get(
        _page_url_for(lottery_type),
        timeout=REQUEST_TIMEOUT_SECONDS,
        headers={
            "User-Agent": "loto-predict/1.0 (+Cloud Functions Gen2)",
            "Accept-Language": "ja,en;q=0.8",
        },
    )
    response.raise_for_status()
    return _parse_latest_result(response.text, lottery_type)


def _to_csv(result: LotoResult) -> str:
    buffer = io.StringIO()
    writer = csv.writer(buffer)

    if result.lottery_type == "LOTO6":
        writer.writerow([
            "draw_no", "draw_date", "number1", "number2", "number3",
            "number4", "number5", "number6", "bonus_number"
        ])
        writer.writerow([
            result.draw_no, result.draw_date, *result.main_numbers, result.bonus_numbers[0]
        ])
    else:
        writer.writerow([
            "draw_no", "draw_date", "number1", "number2", "number3",
            "number4", "number5", "number6", "number7",
            "bonus_number1", "bonus_number2"
        ])
        writer.writerow([
            result.draw_no, result.draw_date, *result.main_numbers,
            result.bonus_numbers[0], result.bonus_numbers[1]
        ])

    return buffer.getvalue()


def _upload_csv(csv_text: str, object_name: str) -> None:
    blob = storage_client.bucket(RAW_BUCKET_NAME).blob(object_name)
    blob.upload_from_string(csv_text, content_type="text/csv; charset=utf-8")


def _publish_import_message(
    execution_id: str,
    lottery_type: str,
    gcs_object: str,
    draw_no: int,
    draw_date: str,
) -> str:
    message = {
        "event_type": "FETCH_COMPLETED",
        "execution_id": execution_id,
        "lottery_type": lottery_type,
        "gcs_bucket": RAW_BUCKET_NAME,
        "gcs_object": gcs_object,
        "draw_no": draw_no,
        "draw_date": draw_date,
        "fetched_at": now_local_iso(),
    }
    future = publisher.publish(topic_path, to_pubsub_data(message))
    return future.result()


def entry_point(request):
    execution_id = ""
    lottery_type = ""

    try:
        payload = _extract_request_json(request)
        lottery_type = payload.get("lottery_type")
        if lottery_type not in {"LOTO6", "LOTO7"}:
            return {"error": "lottery_type must be LOTO6 or LOTO7"}, 400

        execution_id = payload.get("execution_id") or str(uuid.uuid4())

        log_and_write(
            execution_id=execution_id,
            function_name="fetch_loto_results",
            lottery_type=lottery_type,
            stage="fetch",
            status="STARTED",
            message="fetch started",
        )

        result = _download_latest_result(lottery_type)
        csv_text = _to_csv(result)

        object_name = (
            f"{lottery_type.lower()}/draw_date={result.draw_date}/"
            f"draw_no={result.draw_no}/{execution_id}.csv"
        )

        _upload_csv(csv_text, object_name)
        message_id = _publish_import_message(
            execution_id=execution_id,
            lottery_type=lottery_type,
            gcs_object=object_name,
            draw_no=result.draw_no,
            draw_date=result.draw_date,
        )

        log_and_write(
            execution_id=execution_id,
            function_name="fetch_loto_results",
            lottery_type=lottery_type,
            stage="fetch",
            status="SUCCESS",
            message=f"fetch completed message_id={message_id}",
            gcs_bucket=RAW_BUCKET_NAME,
            gcs_object=object_name,
            draw_no=result.draw_no,
        )

        return {
            "status": "ok",
            "execution_id": execution_id,
            "gcs_bucket": RAW_BUCKET_NAME,
            "gcs_object": object_name,
            "draw_no": result.draw_no,
            "draw_date": result.draw_date,
        }, 200

    except Exception as exc:
        log_and_write(
            execution_id=execution_id or "UNKNOWN",
            function_name="fetch_loto_results",
            lottery_type=lottery_type or None,
            stage="fetch",
            status="FAILED",
            message="fetch failed",
            error_type=type(exc).__name__,
            error_detail=str(exc),
        )
        logger.exception("fetch_loto_results failed")
        return {"error": str(exc)}, 500
