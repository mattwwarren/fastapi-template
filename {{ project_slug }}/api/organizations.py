"""Organization CRUD endpoints and membership expansion."""

from uuid import UUID

from fastapi import APIRouter, HTTPException, status
from fastapi_pagination import Page, create_page
from fastapi_pagination.ext.sqlalchemy import apaginate
from sqlalchemy import select

from {{ project_slug }}.core.activity_logging import ActivityAction, log_activity_decorator
from {{ project_slug }}.core.pagination import ParamsDep
from {{ project_slug }}.db.session import SessionDep
from {{ project_slug }}.models.organization import (
    Organization,
    OrganizationCreate,
    OrganizationRead,
    OrganizationUpdate,
)
from {{ project_slug }}.models.shared import UserInfo
from {{ project_slug }}.services.organization_service import (
    create_organization,
    delete_organization,
    get_organization,
    list_users_for_organization,
    list_users_for_organizations,
    update_organization,
)

router = APIRouter(prefix="/organizations", tags=["organizations"])


@router.post("", response_model=OrganizationRead, status_code=status.HTTP_201_CREATED)
@log_activity_decorator(ActivityAction.CREATE, "organization")
async def create_org(
    payload: OrganizationCreate,
    session: SessionDep,
) -> OrganizationRead:
    organization = await create_organization(session, payload)
    response = OrganizationRead.model_validate(organization)
    response.users = []
    return response


@router.get("", response_model=Page[OrganizationRead])
async def list_orgs(
    session: SessionDep,
    params: ParamsDep,
) -> Page[OrganizationRead]:
    page = await apaginate(
        session, select(Organization).order_by(Organization.created_at), params
    )
    organizations = page.items
    organization_ids = [org.id for org in organizations]
    users_by_org = await list_users_for_organizations(session, organization_ids)
    items: list[OrganizationRead] = []
    for organization in organizations:
        response = OrganizationRead.model_validate(organization)
        response.users = [
            UserInfo.model_validate(user)
            for user in users_by_org.get(organization.id, [])
        ]
        items.append(response)
    return create_page(items, total=page.total, params=params)


@router.get("/{organization_id}", response_model=OrganizationRead)
@log_activity_decorator(ActivityAction.READ, "organization")
async def get_org(
    organization_id: UUID,
    session: SessionDep,
) -> OrganizationRead:
    organization = await get_organization(session, organization_id)
    if not organization:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Organization not found")
    users = await list_users_for_organization(session, organization_id)
    response = OrganizationRead.model_validate(organization)
    response.users = [UserInfo.model_validate(user) for user in users]
    return response


@router.patch("/{organization_id}", response_model=OrganizationRead)
@log_activity_decorator(ActivityAction.UPDATE, "organization")
async def update_org(
    organization_id: UUID,
    payload: OrganizationUpdate,
    session: SessionDep,
) -> OrganizationRead:
    organization = await get_organization(session, organization_id)
    if not organization:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Organization not found")
    updated = await update_organization(session, organization, payload)
    users = await list_users_for_organization(session, organization_id)
    response = OrganizationRead.model_validate(updated)
    response.users = [UserInfo.model_validate(user) for user in users]
    return response


@router.delete("/{organization_id}", status_code=status.HTTP_204_NO_CONTENT)
@log_activity_decorator(
    ActivityAction.DELETE, "organization", resource_id_param_name="organization_id"
)
async def delete_org(
    organization_id: UUID,
    session: SessionDep,
) -> None:
    organization = await get_organization(session, organization_id)
    if not organization:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Organization not found")
    await delete_organization(session, organization)
