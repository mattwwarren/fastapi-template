"""API router composition for the service."""

from fastapi import APIRouter

from fastapi_template.api import (
    documents,
    health,
    memberships,
    organizations,
    ping,
    realtime_schemas,
    users,
)

router = APIRouter()
router.include_router(health.router)
router.include_router(ping.router)
router.include_router(organizations.router)
router.include_router(users.router)
router.include_router(memberships.router)
router.include_router(documents.router)
router.include_router(realtime_schemas.router)
