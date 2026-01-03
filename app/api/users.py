from fastapi import APIRouter, HTTPException, status

from app.db.session import SessionDep
from app.models.shared import OrganizationInfo
from app.models.user import UserCreate, UserRead, UserUpdate
from app.services.user_service import (
    create_user,
    delete_user,
    get_user,
    list_organizations_for_user,
    list_users,
    update_user,
)

router = APIRouter(prefix="/users", tags=["users"])


@router.post("", response_model=UserRead, status_code=status.HTTP_201_CREATED)
async def create_user_endpoint(
    payload: UserCreate,
    session: SessionDep,
) -> UserRead:
    user = await create_user(session, payload)
    response = UserRead.model_validate(user)
    response.organizations = []
    return response


@router.get("", response_model=list[UserRead])
async def list_users_endpoint(
    session: SessionDep,
    offset: int = 0,
    limit: int = 100,
) -> list[UserRead]:
    users = await list_users(session, offset=offset, limit=limit)
    responses: list[UserRead] = []
    for user in users:
        if user.id is None:
            raise HTTPException(status_code=500, detail="User id missing")
        organizations = await list_organizations_for_user(session, user.id)
        response = UserRead.model_validate(user)
        response.organizations = [
            OrganizationInfo.model_validate(org) for org in organizations
        ]
        responses.append(response)
    return responses


@router.get("/{user_id}", response_model=UserRead)
async def get_user_endpoint(
    user_id: int,
    session: SessionDep,
) -> UserRead:
    user = await get_user(session, user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    if user.id is None:
        raise HTTPException(status_code=500, detail="User id missing")
    organizations = await list_organizations_for_user(session, user_id)
    response = UserRead.model_validate(user)
    response.organizations = [
        OrganizationInfo.model_validate(org) for org in organizations
    ]
    return response


@router.patch("/{user_id}", response_model=UserRead)
async def update_user_endpoint(
    user_id: int,
    payload: UserUpdate,
    session: SessionDep,
) -> UserRead:
    user = await get_user(session, user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    updated = await update_user(session, user, payload)
    organizations = await list_organizations_for_user(session, user_id)
    response = UserRead.model_validate(updated)
    response.organizations = [
        OrganizationInfo.model_validate(org) for org in organizations
    ]
    return response


@router.delete("/{user_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_user_endpoint(
    user_id: int,
    session: SessionDep,
) -> None:
    user = await get_user(session, user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    await delete_user(session, user)
