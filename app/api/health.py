import asyncio

from fastapi import APIRouter, HTTPException, status
from sqlalchemy import text

from app.db.session import SessionDep

router = APIRouter()
HEALTH_DB_TIMEOUT_SECONDS = 2.0


@router.get("/health", tags=["health"])
async def health(session: SessionDep) -> dict[str, str]:
    try:
        await asyncio.wait_for(
            session.execute(text("SELECT 1")),
            timeout=HEALTH_DB_TIMEOUT_SECONDS,
        )
    except TimeoutError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Database timeout",
        ) from exc
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Database unavailable",
        ) from exc
    return {"status": "ok"}
