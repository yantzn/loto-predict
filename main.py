from infrastructure.data_fetcher import CsvDrawResultFetcher
from usecases.data_sync_usecase import DataSyncRequest, DataSyncUseCase

# 既存コードの下に追加

def sync_entry_point(request):
    execution_id = begin_execution_context()

    try:
        payload = _extract_http_payload(request)
        lottery_type = _resolve_lottery_type(payload.get("lottery_type"))

        begin_execution_context(
            lottery_type=lottery_type.value,
            execution_id=execution_id,
        )

        log_start(
            logger,
            "cloud_function_sync_entry_point",
            trigger_type="http",
            lottery_type=lottery_type.value,
            payload=payload,
        )

        usecase = _build_data_sync_usecase()
        result = usecase.execute(
            DataSyncRequest(lottery_type=lottery_type)
        )

        response_body = {
            "status": "ok",
            "execution_id": execution_id,
            "lottery_type": result.lottery_type.value,
            "fetched_count": result.fetched_count,
            "inserted_count": result.inserted_count,
            "executed_at": result.executed_at.isoformat(),
        }

        log_success(
            logger,
            "cloud_function_sync_entry_point",
            trigger_type="http",
            lottery_type=lottery_type.value,
            inserted_count=result.inserted_count,
        )
        return response_body, 200

    except AppError as exc:
        log_failure(
            logger,
            "cloud_function_sync_entry_point",
            trigger_type="http",
            error_code=exc.error_code,
            details=exc.details,
            is_retryable=exc.is_retryable,
        )
        return {
            "status": "error",
            "execution_id": execution_id,
            "error_code": exc.error_code,
            "message": str(exc),
            "details": exc.details,
        }, 500

    except Exception as exc:
        log_failure(
            logger,
            "cloud_function_sync_entry_point",
            trigger_type="http",
            error_code="UNEXPECTED_ERROR",
            exception_type=type(exc).__name__,
            message=str(exc),
        )
        return {
            "status": "error",
            "execution_id": execution_id,
            "error_code": "UNEXPECTED_ERROR",
            "message": str(exc),
        }, 500

    finally:
        clear_execution_context()


def _build_data_sync_usecase() -> DataSyncUseCase:
    repository = BigQueryLotoRepository()
    fetcher = CsvDrawResultFetcher()
    return DataSyncUseCase(
        fetcher=fetcher,
        repository=repository,
    )
