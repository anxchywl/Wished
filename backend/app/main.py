import logging

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.api.v1.auth.router import router as auth_router
from app.api.v1.media.router import router as media_router
from app.api.v1.me.router import router as me_router
from app.api.v1.router import api_v1_router
from app.api.v1.users.router import router as users_router
from app.api.v1.wishes.router import router as wishes_router
from app.api.v1.wishlists.router import router as wishlists_router
from app.core.config import get_settings
from app.core.logging import configure_logging
from app.db.session import dispose_db
from app.integrations.redis import close_redis

logger = logging.getLogger(__name__)


def create_app() -> FastAPI:
    """create fastapi app"""
    settings = get_settings()
    configure_logging(settings.log_level)

    if settings.app_env == "production":
        if settings.jwt_secret_key in ("change-me", ""):
            raise RuntimeError("JWT_SECRET_KEY must be set to a secure value in production")
        if settings.minio_secret_key in ("wished-password", ""):
            raise RuntimeError("MINIO_SECRET_KEY must be set to a secure value in production")
        if not settings.telegram_bot_token:
            raise RuntimeError("TELEGRAM_BOT_TOKEN must be set in production")

    app = FastAPI(
        title=settings.app_name,
        version=settings.app_version,
        debug=settings.debug,
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.allowed_origins,
        allow_credentials=True,
        allow_methods=["GET", "POST", "PATCH", "DELETE", "OPTIONS"],
        allow_headers=["Authorization", "Content-Type"],
    )

    app.include_router(api_v1_router, prefix=settings.api_v1_prefix)
    app.include_router(auth_router)
    app.include_router(media_router)
    app.include_router(me_router)
    app.include_router(users_router)
    app.include_router(wishes_router)
    app.include_router(wishlists_router)

    @app.on_event("shutdown")
    async def shutdown() -> None:
        """close shared connections"""
        await close_redis()
        await dispose_db()

    @app.exception_handler(RequestValidationError)
    async def validation_exception_handler(request: Request, exc: RequestValidationError) -> JSONResponse:
        # strip input values from error details to avoid leaking sensitive request data to logs
        safe_errors = [{"type": e["type"], "loc": e["loc"], "msg": e["msg"]} for e in exc.errors()]
        logger.warning("request validation error on %s %s", request.method, request.url.path)
        return JSONResponse(status_code=422, content={"detail": safe_errors})

    return app


app = create_app()
