from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
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


def create_app() -> FastAPI:
    """create fastapi app"""
    settings = get_settings()
    configure_logging(settings.log_level)

    app = FastAPI(
        title=settings.app_name,
        version=settings.app_version,
        debug=settings.debug,
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
    async def validation_exception_handler(request: Request, exc: RequestValidationError):
        print(f"Validation Error: {exc.errors()}", flush=True)
        return JSONResponse(status_code=422, content={"detail": exc.errors()})

    return app


app = create_app()
