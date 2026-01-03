from fastapi import APIRouter
from sqlalchemy import text

from app.db.session import SessionDep

router = APIRouter()


@router.get("/health", tags=["health"])
async def health(session: SessionDep) -> dict[str, str]:
    await session.execute(text("SELECT 1"))
    return {"status": "ok"}
