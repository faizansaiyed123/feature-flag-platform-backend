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
from app.security.rate_limit import auth_rate_limiter

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
            if origin and origin not in settings.cors_origin_list:
                return JSONResponse({"detail": "Request origin is not allowed"}, status_code=403)

            rate_limits = {
                f"{settings.api_prefix}/auth/login": settings.auth_login_rate_limit,
                f"{settings.api_prefix}/auth/signup": settings.auth_signup_rate_limit,
                f"{settings.api_prefix}/auth/refresh": settings.auth_refresh_rate_limit,
            }
            limit = rate_limits.get(request.url.path) if request.method == "POST" else None
            if limit is not None:
                client_host = request.client.host if request.client else "unknown"
                if settings.trust_proxy_headers:
                    forwarded = request.headers.get("x-forwarded-for", "")
                    if forwarded:
                        client_host = forwarded.split(",", 1)[0].strip() or client_host
                allowed, retry_after = auth_rate_limiter.check(
                    f"{request.url.path}:{client_host}",
                    limit,
                    settings.auth_rate_limit_window_seconds,
                )
                if not allowed:
                    return JSONResponse(
                        {"detail": "Too many authentication requests. Try again later."},
                        status_code=429,
                        headers={"Retry-After": str(retry_after)},
                    )

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
