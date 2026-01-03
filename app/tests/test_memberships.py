from http import HTTPStatus

import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_membership_create_and_delete(client: AsyncClient) -> None:
    org_response = await client.post("/organizations", json={"name": "Acme"})
    assert org_response.status_code == HTTPStatus.CREATED
    organization_id = org_response.json()["id"]

    user_response = await client.post(
        "/users",
        json={"name": "Jane Doe", "email": "jane@example.com"},
    )
    assert user_response.status_code == HTTPStatus.CREATED
    user_id = user_response.json()["id"]

    create_response = await client.post(
        "/memberships",
        json={"user_id": user_id, "organization_id": organization_id},
    )
    assert create_response.status_code == HTTPStatus.CREATED
    membership_id = create_response.json()["id"]

    list_response = await client.get("/memberships")
    assert list_response.status_code == HTTPStatus.OK
    assert len(list_response.json()) == 1

    user_get = await client.get(f"/users/{user_id}")
    assert user_get.status_code == HTTPStatus.OK
    assert len(user_get.json()["organizations"]) == 1

    org_get = await client.get(f"/organizations/{organization_id}")
    assert org_get.status_code == HTTPStatus.OK
    assert len(org_get.json()["users"]) == 1

    delete_response = await client.delete(f"/memberships/{membership_id}")
    assert delete_response.status_code == HTTPStatus.NO_CONTENT

    user_get = await client.get(f"/users/{user_id}")
    assert user_get.status_code == HTTPStatus.OK
    assert user_get.json()["organizations"] == []

    org_get = await client.get(f"/organizations/{organization_id}")
    assert org_get.status_code == HTTPStatus.OK
    assert org_get.json()["users"] == []
