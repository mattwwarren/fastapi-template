from fastapi import APIRouter, HTTPException, status

from app.db.session import SessionDep
from app.models.organization import (
    OrganizationCreate,
    OrganizationRead,
    OrganizationUpdate,
)
from app.models.shared import UserInfo
from app.services.organization_service import (
    create_organization,
    delete_organization,
    get_organization,
    list_organizations,
    list_users_for_organization,
    update_organization,
)

router = APIRouter(prefix="/organizations", tags=["organizations"])


@router.post("", response_model=OrganizationRead, status_code=status.HTTP_201_CREATED)
async def create_org(
    payload: OrganizationCreate,
    session: SessionDep,
) -> OrganizationRead:
    organization = await create_organization(session, payload)
    response = OrganizationRead.model_validate(organization)
    response.users = []
    return response


@router.get("", response_model=list[OrganizationRead])
async def list_orgs(
    session: SessionDep,
    offset: int = 0,
    limit: int = 100,
) -> list[OrganizationRead]:
    organizations = await list_organizations(session, offset=offset, limit=limit)
    responses: list[OrganizationRead] = []
    for organization in organizations:
        if organization.id is None:
            raise HTTPException(status_code=500, detail="Organization id missing")
        users = await list_users_for_organization(session, organization.id)
        response = OrganizationRead.model_validate(organization)
        response.users = [UserInfo.model_validate(user) for user in users]
        responses.append(response)
    return responses


@router.get("/{organization_id}", response_model=OrganizationRead)
async def get_org(
    organization_id: int,
    session: SessionDep,
) -> OrganizationRead:
    organization = await get_organization(session, organization_id)
    if not organization:
        raise HTTPException(status_code=404, detail="Organization not found")
    if organization.id is None:
        raise HTTPException(status_code=500, detail="Organization id missing")
    users = await list_users_for_organization(session, organization_id)
    response = OrganizationRead.model_validate(organization)
    response.users = [UserInfo.model_validate(user) for user in users]
    return response


@router.patch("/{organization_id}", response_model=OrganizationRead)
async def update_org(
    organization_id: int,
    payload: OrganizationUpdate,
    session: SessionDep,
) -> OrganizationRead:
    organization = await get_organization(session, organization_id)
    if not organization:
        raise HTTPException(status_code=404, detail="Organization not found")
    if organization.id is None:
        raise HTTPException(status_code=500, detail="Organization id missing")
    updated = await update_organization(session, organization, payload)
    users = await list_users_for_organization(session, organization_id)
    response = OrganizationRead.model_validate(updated)
    response.users = [UserInfo.model_validate(user) for user in users]
    return response


@router.delete("/{organization_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_org(
    organization_id: int,
    session: SessionDep,
) -> None:
    organization = await get_organization(session, organization_id)
    if not organization:
        raise HTTPException(status_code=404, detail="Organization not found")
    await delete_organization(session, organization)
