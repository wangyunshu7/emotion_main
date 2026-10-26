import logging
import time
import uuid

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from sqlalchemy import text
from starlette.exceptions import HTTPException

from app.api import auth, care, insights, journals
from app.core.config import get_settings
from app.core.errors import AppError
from app.db import SessionLocal
from app.schemas import ErrorOut

settings = get_settings()
logging.basicConfig(
    level=settings.log_level, format="%(asctime)s %(levelname)s %(name)s %(message)s"
)
logging.getLogger("httpx").setLevel(logging.WARNING)
app = FastAPI(
    title="心晴日记 API",
    version="0.1.0",
    docs_url="/docs" if settings.app_env != "production" else None,
)
logger = logging.getLogger("emotion")


@app.middleware("http")
async def request_context(request: Request, call_next):
    request.state.request_id = uuid.uuid4().hex
    start = time.monotonic()
    try:
        response = await call_next(request)
    except Exception as exc:
        # Keep unexpected exceptions from exposing diary values through server tracebacks.
        logger.error(
            "request failed id=%s exception_type=%s", request.state.request_id, type(exc).__name__
        )
        response = error_response(
            request, 500, "INTERNAL_ERROR", "服务暂时无法完成请求，请稍后重试"
        )
    response.headers.update(
        {
            "X-Request-ID": request.state.request_id,
            "Cache-Control": "no-store",
            "X-Content-Type-Options": "nosniff",
            "Referrer-Policy": "same-origin",
        }
    )
    route = request.scope.get("route")
    logger.info(
        "request id=%s route=%s status=%s elapsed_ms=%d",
        request.state.request_id,
        getattr(route, "path", "unknown"),
        response.status_code,
        int((time.monotonic() - start) * 1000),
    )
    return response


def error_response(request, status, code, message, fields=None):
    headers = {"Cache-Control": "no-store"}
    if status == 429:
        headers["Retry-After"] = "60"
    return JSONResponse(
        status_code=status,
        content={
            "error": {
                "code": code,
                "message": message,
                "fields": fields or [],
                "request_id": getattr(request.state, "request_id", "unknown"),
            }
        },
        headers=headers,
    )


@app.exception_handler(AppError)
async def app_error(request: Request, exc: AppError):
    return error_response(request, exc.status, exc.code, exc.message, exc.fields)


@app.exception_handler(HTTPException)
async def http_error(request: Request, exc: HTTPException):
    return error_response(
        request,
        exc.status_code,
        "RESOURCE_NOT_FOUND" if exc.status_code == 404 else "HTTP_ERROR",
        "页面或接口不存在" if exc.status_code == 404 else "请求方法或状态不符合要求",
    )


@app.exception_handler(RequestValidationError)
async def validation_error(request: Request, exc: RequestValidationError):
    # Never include Pydantic's input/context, which can contain passwords or diary text.
    fields = [
        {"path": ".".join(map(str, e["loc"][1:])), "message": "字段格式或范围不符合要求"}
        for e in exc.errors()
    ]
    return error_response(request, 422, "VALIDATION_ERROR", "请检查输入内容", fields)


@app.exception_handler(Exception)
async def unhandled(request: Request, exc: Exception):
    logger.error(
        "request failed id=%s exception_type=%s", request.state.request_id, type(exc).__name__
    )
    return error_response(request, 500, "INTERNAL_ERROR", "服务暂时无法完成请求，请稍后重试")


@app.get("/health/live")
def live():
    return {"status": "ok"}


@app.get("/health/ready")
def ready():
    try:
        with SessionLocal() as db:
            revision = db.scalar(text("SELECT version_num FROM alembic_version"))
            if revision != "0001_initial":
                raise RuntimeError("migration mismatch")
        return {"status": "ready"}
    except Exception:
        raise AppError(503, "SERVICE_UNAVAILABLE", "数据库或迁移尚未就绪") from None


for router in (auth.router, journals.router, care.router, insights.router):
    app.include_router(
        router,
        prefix="/api/v1",
        responses={
            status: {"model": ErrorOut} for status in (401, 403, 404, 409, 422, 429, 500, 503)
        },
    )
