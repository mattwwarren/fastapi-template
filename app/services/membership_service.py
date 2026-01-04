"""Membership data access helpers for services and endpoints."""

from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import col

from app.models.membership import Membership, MembershipCreate


async def get_membership(
    session: AsyncSession, membership_id: UUID
) -> Membership | None:
    result = await session.execute(
        select(Membership).where(col(Membership.id) == membership_id)
    )
    return result.scalar_one_or_none()


async def list_memberships(
    session: AsyncSession, offset: int = 0, limit: int = 100
) -> list[Membership]:
    result = await session.execute(select(Membership).offset(offset).limit(limit))
    return list(result.scalars().all())


async def create_membership(
    session: AsyncSession, payload: MembershipCreate
) -> Membership:
    membership = Membership(**payload.model_dump())
    session.add(membership)
    await session.commit()
    await session.refresh(membership)
    return membership


async def delete_membership(session: AsyncSession, membership: Membership) -> None:
    await session.delete(membership)
    await session.commit()
