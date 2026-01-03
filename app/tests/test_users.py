from http import HTTPStatus

import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_user_crud(client: AsyncClient) -> None:
    create_response = await client.post(
        "/users",
        json={
            "name": "Jane Doe",
            "email": "jane@example.com",
        },
    )
    assert create_response.status_code == HTTPStatus.CREATED
    user = create_response.json()
    assert user["organizations"] == []

    user_id = user["id"]
    get_response = await client.get(f"/users/{user_id}")
    assert get_response.status_code == HTTPStatus.OK

    list_response = await client.get("/users")
    assert list_response.status_code == HTTPStatus.OK
    assert len(list_response.json()) == 1

    update_response = await client.patch(
        f"/users/{user_id}", json={"name": "Jane Updated"}
    )
    assert update_response.status_code == HTTPStatus.OK
    assert update_response.json()["name"] == "Jane Updated"

    delete_response = await client.delete(f"/users/{user_id}")
    assert delete_response.status_code == HTTPStatus.NO_CONTENT
