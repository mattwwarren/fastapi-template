from fastapi import APIRouter

from app.api import health, memberships, organizations, ping, users

router = APIRouter()
router.include_router(health.router)
router.include_router(ping.router)
router.include_router(organizations.router)
router.include_router(users.router)
router.include_router(memberships.router)
