from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import col

from app.models.membership import Membership
from app.models.organization import Organization, OrganizationCreate, OrganizationUpdate
from app.models.user import User


async def get_organization(
    session: AsyncSession, organization_id: UUID
) -> Organization | None:
    result = await session.execute(
        select(Organization).where(col(Organization.id) == organization_id)
    )
    return result.scalar_one_or_none()


async def list_organizations(
    session: AsyncSession, offset: int = 0, limit: int = 100
) -> list[Organization]:
    result = await session.execute(select(Organization).offset(offset).limit(limit))
    return list(result.scalars().all())


async def create_organization(
    session: AsyncSession, payload: OrganizationCreate
) -> Organization:
    organization = Organization(**payload.model_dump())
    session.add(organization)
    await session.commit()
    await session.refresh(organization)
    return organization


async def update_organization(
    session: AsyncSession, organization: Organization, payload: OrganizationUpdate
) -> Organization:
    updates = payload.model_dump(exclude_unset=True)
    for field, value in updates.items():
        setattr(organization, field, value)
    session.add(organization)
    await session.commit()
    await session.refresh(organization)
    return organization


async def delete_organization(
    session: AsyncSession, organization: Organization
) -> None:
    await session.delete(organization)
    await session.commit()


async def list_users_for_organization(
    session: AsyncSession, organization_id: UUID
) -> list[User]:
    result = await session.execute(
        select(User)
        .join(Membership, col(Membership.user_id) == col(User.id))
        .where(col(Membership.organization_id) == organization_id)
    )
    return list(result.scalars().all())


async def list_users_for_organizations(
    session: AsyncSession, organization_ids: list[UUID]
) -> dict[UUID, list[User]]:
    if not organization_ids:
        return {}
    result = await session.execute(
        select(Membership.organization_id, User)
        .join(User, col(Membership.user_id) == col(User.id))
        .where(col(Membership.organization_id).in_(organization_ids))
    )
    mapping: dict[UUID, list[User]] = {org_id: [] for org_id in organization_ids}
    for organization_id, user in result.all():
        if organization_id in mapping:
            mapping[organization_id].append(user)
    return mapping
