from http import HTTPStatus

import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_organization_crud(client: AsyncClient) -> None:
    create_response = await client.post("/organizations", json={"name": "Acme"})
    assert create_response.status_code == HTTPStatus.CREATED
    organization = create_response.json()
    assert organization["name"] == "Acme"
    assert organization["users"] == []

    organization_id = organization["id"]
    get_response = await client.get(f"/organizations/{organization_id}")
    assert get_response.status_code == HTTPStatus.OK
    assert get_response.json()["id"] == organization_id

    list_response = await client.get("/organizations")
    assert list_response.status_code == HTTPStatus.OK
    assert len(list_response.json()) == 1

    update_response = await client.patch(
        f"/organizations/{organization_id}", json={"name": "Acme 2"}
    )
    assert update_response.status_code == HTTPStatus.OK
    assert update_response.json()["name"] == "Acme 2"

    delete_response = await client.delete(f"/organizations/{organization_id}")
    assert delete_response.status_code == HTTPStatus.NO_CONTENT

    missing_response = await client.get(f"/organizations/{organization_id}")
    assert missing_response.status_code == HTTPStatus.NOT_FOUND
