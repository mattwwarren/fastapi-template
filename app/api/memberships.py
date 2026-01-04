from uuid import UUID

from fastapi import APIRouter, HTTPException, status
from fastapi_pagination import Page
from fastapi_pagination.ext.sqlalchemy import apaginate
from sqlalchemy import select

from app.core.pagination import ParamsDep
from app.db.session import SessionDep
from app.models.membership import Membership, MembershipCreate, MembershipRead
from app.services.membership_service import (
    create_membership,
    delete_membership,
    get_membership,
)
from app.services.organization_service import get_organization
from app.services.user_service import get_user

router = APIRouter(prefix="/memberships", tags=["memberships"])


@router.post("", response_model=MembershipRead, status_code=status.HTTP_201_CREATED)
async def create_membership_endpoint(
    payload: MembershipCreate,
    session: SessionDep,
) -> MembershipRead:
    user = await get_user(session, payload.user_id)
    if not user:
        raise HTTPException(status_code=400, detail="User does not exist")
    organization = await get_organization(session, payload.organization_id)
    if not organization:
        raise HTTPException(status_code=400, detail="Organization does not exist")
    membership = await create_membership(session, payload)
    return MembershipRead.model_validate(membership)


@router.get("", response_model=Page[MembershipRead])
async def list_memberships_endpoint(
    session: SessionDep,
    params: ParamsDep,
) -> Page[MembershipRead]:
    return await apaginate(
        session, select(Membership).order_by(Membership.created_at), params
    )


@router.delete("/{membership_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_membership_endpoint(
    membership_id: UUID,
    session: SessionDep,
) -> None:
    membership = await get_membership(session, membership_id)
    if not membership:
        raise HTTPException(status_code=404, detail="Membership not found")
    await delete_membership(session, membership)
