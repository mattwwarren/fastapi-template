"""Membership CRUD endpoints for user-organization relationships."""

from uuid import UUID

from fastapi import APIRouter, HTTPException, status
from fastapi_pagination import Page
from fastapi_pagination.ext.sqlalchemy import apaginate
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from {{ project_slug }}.core.activity_logging import ActivityAction, log_activity_decorator
from {{ project_slug }}.core.pagination import ParamsDep
from {{ project_slug }}.db.session import SessionDep
from {{ project_slug }}.models.membership import Membership, MembershipCreate, MembershipRead
from {{ project_slug }}.services.membership_service import (
    create_membership,
    delete_membership,
    get_membership,
)
from {{ project_slug }}.services.organization_service import get_organization
from {{ project_slug }}.services.user_service import get_user

router = APIRouter(prefix="/memberships", tags=["memberships"])


@router.post("", response_model=MembershipRead, status_code=status.HTTP_201_CREATED)
@log_activity_decorator(ActivityAction.CREATE, "membership")
async def create_membership_endpoint(
    payload: MembershipCreate,
    session: SessionDep,
) -> MembershipRead:
    user = await get_user(session, payload.user_id)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="User does not exist",
        )
    organization = await get_organization(session, payload.organization_id)
    if not organization:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Organization does not exist",
        )
    try:
        membership = await create_membership(session, payload)
    except IntegrityError as e:
        if "uq_membership_user_org" in str(e):
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="User is already a member of this organization",
            ) from None
        raise
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
@log_activity_decorator(
    ActivityAction.DELETE, "membership", resource_id_param_name="membership_id"
)
async def delete_membership_endpoint(
    membership_id: UUID,
    session: SessionDep,
) -> None:
    membership = await get_membership(session, membership_id)
    if not membership:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Membership not found",
        )
    await delete_membership(session, membership)
