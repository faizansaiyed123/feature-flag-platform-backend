from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import Awaitable, Callable
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response
from starlette.middleware.trustedhost import TrustedHostMiddleware
from app.api.v1.router import api_router
from app.config import get_settings
from app.db import get_engine

settings = get_settings()

class SecurityMiddleware(BaseHTTPMiddleware):
    async def dispatch(
        self,
        request: Request,
        call_next: Callable[[Request], Awaitable[Response]],
    ) -> Response:
        if request.method in {"POST", "PUT", "PATCH", "DELETE"}:
            content_length = request.headers.get("content-length")
            if content_length:
                try:
                    too_large = int(content_length) > settings.max_request_body_bytes
                except ValueError:
                    too_large = False
                if too_large:
                    return JSONResponse({"detail": "Request body is too large"}, status_code=413)
            origin = request.headers.get("origin")
            cookie = request.headers.get("cookie", "")
            if ("access_token=" in cookie or "refresh_token=" in cookie) and origin and origin not in settings.cors_origin_list:
                return JSONResponse({"detail": "Request origin is not allowed"}, status_code=403)

        response = await call_next(request)
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["Referrer-Policy"] = "same-origin"
        response.headers["Permissions-Policy"] = "camera=(), microphone=(), geolocation=()"
        if settings.app_env.lower() == "production":
            response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
        return response

@asynccontextmanager
async def lifespan(_: FastAPI) -> AsyncIterator[None]:
    try:
        yield
    finally:
        await get_engine().dispose()

app = FastAPI(title=settings.app_name, version="0.1.0", lifespan=lifespan)
if settings.allowed_host_list:
    app.add_middleware(TrustedHostMiddleware, allowed_hosts=settings.allowed_host_list)
app.add_middleware(SecurityMiddleware)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
    allow_headers=["Content-Type", "Authorization", "X-Request-ID", "X-Feature-Key"],
)
app.include_router(api_router, prefix=settings.api_prefix)
