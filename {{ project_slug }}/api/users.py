"""User CRUD endpoints and membership expansion."""

from uuid import UUID

from fastapi import APIRouter, HTTPException, status
from fastapi_pagination import Page, create_page
from fastapi_pagination.ext.sqlalchemy import apaginate
from sqlalchemy import select

from {{ project_slug }}.core.activity_logging import ActivityAction, log_activity_decorator
from {{ project_slug }}.core.pagination import ParamsDep
from {{ project_slug }}.db.session import SessionDep
from {{ project_slug }}.models.shared import OrganizationInfo
from {{ project_slug }}.models.user import User, UserCreate, UserRead, UserUpdate
from {{ project_slug }}.services.user_service import (
    create_user,
    delete_user,
    get_user,
    list_organizations_for_user,
    list_organizations_for_users,
    update_user,
)

router = APIRouter(prefix="/users", tags=["users"])


@router.post("", response_model=UserRead, status_code=status.HTTP_201_CREATED)
@log_activity_decorator(ActivityAction.CREATE, "user")
async def create_user_endpoint(
    payload: UserCreate,
    session: SessionDep,
) -> UserRead:
    user = await create_user(session, payload)
    response = UserRead.model_validate(user)
    response.organizations = []
    return response


@router.get("", response_model=Page[UserRead])
async def list_users_endpoint(
    session: SessionDep,
    params: ParamsDep,
) -> Page[UserRead]:
    page = await apaginate(session, select(User).order_by(User.created_at), params)
    users = page.items
    user_ids = [user.id for user in users if user.id is not None]
    organizations_by_user = await list_organizations_for_users(session, user_ids)
    responses: list[UserRead] = []
    for user in users:
        if user.id is None:
            raise HTTPException(status_code=500, detail="User id missing")
        response = UserRead.model_validate(user)
        response.organizations = [
            OrganizationInfo.model_validate(org)
            for org in organizations_by_user.get(user.id, [])
        ]
        responses.append(response)
    return create_page(responses, total=page.total, params=params)


@router.get("/{user_id}", response_model=UserRead)
@log_activity_decorator(ActivityAction.READ, "user")
async def get_user_endpoint(
    user_id: UUID,
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
@log_activity_decorator(ActivityAction.UPDATE, "user")
async def update_user_endpoint(
    user_id: UUID,
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
@log_activity_decorator(ActivityAction.DELETE, "user")
async def delete_user_endpoint(
    user_id: UUID,
    session: SessionDep,
) -> None:
    user = await get_user(session, user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    await delete_user(session, user)
