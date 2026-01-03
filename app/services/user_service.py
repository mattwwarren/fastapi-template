from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import col

from app.models.membership import Membership
from app.models.organization import Organization
from app.models.user import User, UserCreate, UserUpdate


async def get_user(session: AsyncSession, user_id: int) -> User | None:
    result = await session.execute(select(User).where(col(User.id) == user_id))
    return result.scalar_one_or_none()


async def list_users(
    session: AsyncSession, offset: int = 0, limit: int = 100
) -> list[User]:
    result = await session.execute(select(User).offset(offset).limit(limit))
    return list(result.scalars().all())


async def create_user(session: AsyncSession, payload: UserCreate) -> User:
    user = User(**payload.model_dump())
    session.add(user)
    await session.commit()
    await session.refresh(user)
    return user


async def update_user(session: AsyncSession, user: User, payload: UserUpdate) -> User:
    updates = payload.model_dump(exclude_unset=True)
    for field, value in updates.items():
        setattr(user, field, value)
    session.add(user)
    await session.commit()
    await session.refresh(user)
    return user


async def delete_user(session: AsyncSession, user: User) -> None:
    await session.delete(user)
    await session.commit()


async def list_organizations_for_user(
    session: AsyncSession, user_id: int
) -> list[Organization]:
    result = await session.execute(
        select(Organization)
        .join(
            Membership,
            col(Membership.organization_id) == col(Organization.id),
        )
        .where(col(Membership.user_id) == user_id)
    )
    return list(result.scalars().all())
