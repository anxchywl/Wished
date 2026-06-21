from fastapi import APIRouter

from app.api.v1.admin.router import router as admin_router
from app.api.v1.auth.router import router as auth_router
from app.api.v1.health.router import router as health_router
from app.api.v1.marketplace.router import router as marketplace_router
from app.api.v1.media.router import router as media_router
from app.api.v1.me.router import router as me_router
from app.api.v1.reservations.router import router as reservations_router
from app.api.v1.users.router import router as users_router
from app.api.v1.wishes.router import router as wishes_router
from app.api.v1.wishlists.router import router as wishlists_router

api_v1_router = APIRouter()
api_v1_router.include_router(admin_router)
api_v1_router.include_router(auth_router)
api_v1_router.include_router(health_router, tags=["health"])
api_v1_router.include_router(marketplace_router)
api_v1_router.include_router(media_router)
api_v1_router.include_router(me_router)
api_v1_router.include_router(reservations_router)
api_v1_router.include_router(users_router)
api_v1_router.include_router(wishes_router)
api_v1_router.include_router(wishlists_router)
