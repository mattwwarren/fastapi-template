from fastapi import APIRouter, HTTPException, status

from app.db.session import SessionDep
from app.models.membership import MembershipCreate, MembershipRead
from app.services.membership_service import (
    create_membership,
    delete_membership,
    get_membership,
    list_memberships,
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


@router.get("", response_model=list[MembershipRead])
async def list_memberships_endpoint(
    session: SessionDep,
    offset: int = 0,
    limit: int = 100,
) -> list[MembershipRead]:
    memberships = await list_memberships(session, offset=offset, limit=limit)
    return [MembershipRead.model_validate(item) for item in memberships]


@router.delete("/{membership_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_membership_endpoint(
    membership_id: int,
    session: SessionDep,
) -> None:
    membership = await get_membership(session, membership_id)
    if not membership:
        raise HTTPException(status_code=404, detail="Membership not found")
    await delete_membership(session, membership)
