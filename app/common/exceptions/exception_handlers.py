import logging

from fastapi import Request, status
from fastapi.exceptions import RequestValidationError, HTTPException
from fastapi.responses import JSONResponse

from app.common.schemas.response_schema import ApiResponse

logger = logging.getLogger(__name__)


async def http_exception_handler(request: Request, exc: HTTPException):
    """Xử lý các lỗi HTTPException được raise trong code"""
    return JSONResponse(
        status_code=exc.status_code,
        content=ApiResponse.error(
            message=exc.detail if isinstance(exc.detail, str) else str(exc.detail),
        ).model_dump()
    )

async def validation_exception_handler(request: Request, exc: RequestValidationError):
    """Xử lý các lỗi validate dữ liệu đầu vào (Pydantic Validation)"""
    errors = exc.errors()
    error_messages = []

    for err in errors:
        loc = " -> ".join(str(x) for x in err["loc"])
        msg = err["msg"]
        error_messages.append(f"{loc}: {msg}")

    combined_message = "; ".join(error_messages)

    return JSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        content=ApiResponse.error(
            message=f"Validation Error: {combined_message}",
        ).model_dump()
    )


async def global_exception_handler(request: Request, exc: Exception):
    """Bắt và ghi log tất cả các lỗi hệ thống không mong muốn (Lỗi 500)"""
    logger.exception(
        "Unhandled exception | %s %s",
        request.method,
        request.url.path,
        exc_info=exc,
    )

    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content=ApiResponse.error(
            message="Internal Server Error. Please try again later.",
        ).model_dump()
    )
