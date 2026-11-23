import logging
from collections.abc import Mapping
from uuid import uuid4

from fastapi import FastAPI, Request
from fastapi.encoders import jsonable_encoder
from fastapi.exceptions import RequestValidationError
from pydantic import BaseModel
from starlette.exceptions import HTTPException
from starlette.middleware.base import RequestResponseEndpoint
from starlette.responses import JSONResponse, Response

logger = logging.getLogger(__name__)


class SuccessEnvelope[T](BaseModel):
    success: bool = True
    data: T
    request_id: str


class APIError(Exception):
    def __init__(self, status: int, code: str, message: str) -> None:
        super().__init__(code)
        self.status = status
        self.code = code
        self.message = message


def success(request: Request, data: object, status: int = 200) -> JSONResponse:
    return JSONResponse(
        {"success": True, "data": jsonable_encoder(data), "request_id": request.state.request_id},
        status_code=status,
    )


def error(
    request: Request,
    status: int,
    code: str,
    message: str,
    details: dict[str, object] | None = None,
    headers: Mapping[str, str] | None = None,
) -> JSONResponse:
    return JSONResponse(
        {
            "success": False,
            "error": {"code": code, "message": message, "details": details or {}},
            "request_id": request.state.request_id,
        },
        status_code=status,
        headers=headers,
    )


def install_http_handlers(app: FastAPI) -> None:
    @app.middleware("http")
    async def request_context(request: Request, call_next: RequestResponseEndpoint) -> Response:
        request.state.request_id = str(uuid4())
        try:
            response = await call_next(request)
        except Exception as exc:
            # Exception text can contain SQL parameters or credentials from upstream libraries.
            logger.error("Request %s failed (%s)", request.state.request_id, type(exc).__name__)
            response = error(request, 500, "INTERNAL_ERROR", "服务暂时不可用")
        response.headers["X-Request-ID"] = request.state.request_id
        if request.url.path.startswith(("/api/v1/auth/", "/api/v1/members/")):
            response.headers["Cache-Control"] = "no-store"
        return response

    @app.exception_handler(APIError)
    async def api_error(request: Request, exc: APIError) -> JSONResponse:
        headers = {"WWW-Authenticate": "Bearer"} if exc.status == 401 else None
        return error(request, exc.status, exc.code, exc.message, headers=headers)

    @app.exception_handler(HTTPException)
    async def http_error(request: Request, exc: HTTPException) -> JSONResponse:
        code, message = {
            404: ("NOT_FOUND", "资源不存在"),
            405: ("METHOD_NOT_ALLOWED", "请求方法不受支持"),
        }.get(exc.status_code, ("HTTP_ERROR", "请求处理失败"))
        return error(request, exc.status_code, code, message, headers=exc.headers)

    @app.exception_handler(RequestValidationError)
    async def validation_error(request: Request, exc: RequestValidationError) -> JSONResponse:
        issues = exc.errors()
        if any(issue["type"] == "json_invalid" for issue in issues):
            return error(request, 400, "INVALID_REQUEST", "请求 JSON 格式无效")
        # Never echo Pydantic's input, context, or unknown field names.
        fields = {
            issue["loc"][1] if len(issue["loc"]) == 2
            and isinstance(issue["loc"][1], str) and issue["type"] != "extra_forbidden" else "request": "格式无效"
            for issue in issues
        }
        return error(request, 422, "VALIDATION_ERROR", "请求字段校验失败", {"fields": fields})
