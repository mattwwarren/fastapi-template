"""Comprehensive user endpoint tests.

Tests cover CRUD operations, validation, relationships, and error handling.
"""

from http import HTTPStatus

import pytest
from httpx import AsyncClient

# Test constants
NUM_TEST_USERS = 3
NONEXISTENT_UUID = "00000000-0000-0000-0000-000000000000"


class TestUserCRUD:
    """Test basic user CRUD operations."""

    @pytest.mark.asyncio
    async def test_create_user_success(self, client: AsyncClient) -> None:
        """Create a user with valid data."""
        response = await client.post(
            "/users",
            json={
                "name": "Jane Doe",
                "email": "jane@example.com",
            },
        )
        assert response.status_code == HTTPStatus.CREATED
        user = response.json()
        assert user["name"] == "Jane Doe"
        assert user["email"] == "jane@example.com"
        assert user["organizations"] == []
        assert "id" in user
        assert "created_at" in user
        assert "updated_at" in user

    @pytest.mark.asyncio
    async def test_create_user_with_duplicate_email(self, client: AsyncClient) -> None:
        """Creating user with duplicate email should fail gracefully."""
        payload = {
            "name": "Jane Doe",
            "email": "duplicate@example.com",
        }
        # Create first user
        response1 = await client.post("/users", json=payload)
        assert response1.status_code == HTTPStatus.CREATED

        # Try to create duplicate
        response2 = await client.post("/users", json=payload)
        # Should fail with 400 or 409 (database constraint violation)
        assert response2.status_code in (HTTPStatus.BAD_REQUEST, HTTPStatus.CONFLICT)

    @pytest.mark.asyncio
    async def test_read_user(self, client: AsyncClient) -> None:
        """Get a single user by ID."""
        # Create user
        create_response = await client.post(
            "/users",
            json={
                "name": "John Smith",
                "email": "john@example.com",
            },
        )
        user_id = create_response.json()["id"]

        # Read user
        get_response = await client.get(f"/users/{user_id}")
        assert get_response.status_code == HTTPStatus.OK
        user = get_response.json()
        assert user["id"] == user_id
        assert user["name"] == "John Smith"
        assert user["email"] == "john@example.com"

    @pytest.mark.asyncio
    async def test_update_user(self, client: AsyncClient) -> None:
        """Update user fields."""
        # Create user
        create_response = await client.post(
            "/users",
            json={
                "name": "Original Name",
                "email": "original@example.com",
            },
        )
        user_id = create_response.json()["id"]

        # Update user
        update_response = await client.patch(
            f"/users/{user_id}",
            json={"name": "Updated Name"},
        )
        assert update_response.status_code == HTTPStatus.OK
        updated_user = update_response.json()
        assert updated_user["name"] == "Updated Name"
        assert updated_user["email"] == "original@example.com"

    @pytest.mark.asyncio
    async def test_delete_user(self, client: AsyncClient) -> None:
        """Delete a user."""
        # Create user
        create_response = await client.post(
            "/users",
            json={
                "name": "To Delete",
                "email": "delete@example.com",
            },
        )
        user_id = create_response.json()["id"]

        # Delete user
        delete_response = await client.delete(f"/users/{user_id}")
        assert delete_response.status_code == HTTPStatus.NO_CONTENT

        # Verify deleted
        get_response = await client.get(f"/users/{user_id}")
        assert get_response.status_code == HTTPStatus.NOT_FOUND

    @pytest.mark.asyncio
    async def test_list_users(self, client: AsyncClient) -> None:
        """List users with pagination."""
        # Create multiple users
        for i in range(NUM_TEST_USERS):
            await client.post(
                "/users",
                json={
                    "name": f"User {i}",
                    "email": f"user{i}@example.com",
                },
            )

        # List users
        list_response = await client.get("/users")
        assert list_response.status_code == HTTPStatus.OK
        data = list_response.json()
        assert data["total"] == NUM_TEST_USERS
        assert len(data["items"]) == NUM_TEST_USERS
        assert data["page"] == 1
        assert data["size"] >= NUM_TEST_USERS


class TestUserValidation:
    """Test user input validation."""

    @pytest.mark.asyncio
    async def test_create_user_invalid_email(self, client: AsyncClient) -> None:
        """Creating user with malformed email should fail."""
        response = await client.post(
            "/users",
            json={
                "name": "Test User",
                "email": "not-an-email",
            },
        )
        assert response.status_code == HTTPStatus.UNPROCESSABLE_ENTITY

    @pytest.mark.asyncio
    async def test_create_user_empty_name(self, client: AsyncClient) -> None:
        """Creating user with empty name should fail."""
        response = await client.post(
            "/users",
            json={
                "name": "",
                "email": "test@example.com",
            },
        )
        assert response.status_code == HTTPStatus.UNPROCESSABLE_ENTITY

    @pytest.mark.asyncio
    async def test_create_user_whitespace_only_name(self, client: AsyncClient) -> None:
        """Creating user with whitespace-only name should fail."""
        response = await client.post(
            "/users",
            json={
                "name": "   ",
                "email": "test@example.com",
            },
        )
        # Should fail validation (min_length=1 should catch this)
        assert response.status_code == HTTPStatus.UNPROCESSABLE_ENTITY

    @pytest.mark.asyncio
    async def test_create_user_missing_email(self, client: AsyncClient) -> None:
        """Creating user without email should fail."""
        response = await client.post(
            "/users",
            json={
                "name": "Test User",
            },
        )
        assert response.status_code == HTTPStatus.UNPROCESSABLE_ENTITY

    @pytest.mark.asyncio
    async def test_create_user_missing_name(self, client: AsyncClient) -> None:
        """Creating user without name should fail."""
        response = await client.post(
            "/users",
            json={
                "email": "test@example.com",
            },
        )
        assert response.status_code == HTTPStatus.UNPROCESSABLE_ENTITY

    @pytest.mark.asyncio
    async def test_update_user_invalid_email(self, client: AsyncClient) -> None:
        """Updating user with invalid email should fail."""
        # Create user
        create_response = await client.post(
            "/users",
            json={
                "name": "Test User",
                "email": "valid@example.com",
            },
        )
        user_id = create_response.json()["id"]

        # Try to update with invalid email
        update_response = await client.patch(
            f"/users/{user_id}",
            json={"email": "invalid-email"},
        )
        assert update_response.status_code == HTTPStatus.UNPROCESSABLE_ENTITY


class TestUserOrganizationRelationship:
    """Test user-organization relationship expansion."""

    @pytest.mark.asyncio
    async def test_user_shows_organizations(self, client: AsyncClient) -> None:
        """User should show organizations after membership is created."""
        # Create user
        user_response = await client.post(
            "/users",
            json={
                "name": "Test User",
                "email": "user@example.com",
            },
        )
        user_id = user_response.json()["id"]

        # Create organization
        org_response = await client.post(
            "/organizations",
            json={"name": "Test Org"},
        )
        org_id = org_response.json()["id"]

        # Create membership
        await client.post(
            "/memberships",
            json={
                "user_id": user_id,
                "organization_id": org_id,
            },
        )

        # Get user and verify organizations
        get_response = await client.get(f"/users/{user_id}")
        assert get_response.status_code == HTTPStatus.OK
        user = get_response.json()
        assert "organizations" in user
        assert isinstance(user["organizations"], list)
        assert len(user["organizations"]) == 1
        assert user["organizations"][0]["id"] == org_id
        assert user["organizations"][0]["name"] == "Test Org"

    @pytest.mark.asyncio
    async def test_user_has_no_organizations(self, client: AsyncClient) -> None:
        """Fresh user should have empty organizations list."""
        response = await client.post(
            "/users",
            json={
                "name": "Lonely User",
                "email": "lonely@example.com",
            },
        )
        assert response.status_code == HTTPStatus.CREATED
        user = response.json()
        assert user["organizations"] == []

    @pytest.mark.asyncio
    async def test_delete_user_cascades_memberships(self, client: AsyncClient) -> None:
        """Deleting a user should cascade delete their memberships."""
        # Create user
        user_response = await client.post(
            "/users",
            json={
                "name": "Test User",
                "email": "cascade@example.com",
            },
        )
        user_id = user_response.json()["id"]

        # Create organization
        org_response = await client.post(
            "/organizations",
            json={"name": "Test Org"},
        )
        org_id = org_response.json()["id"]

        # Create membership
        membership_response = await client.post(
            "/memberships",
            json={
                "user_id": user_id,
                "organization_id": org_id,
            },
        )
        membership_id = membership_response.json()["id"]

        # Delete user
        delete_response = await client.delete(f"/users/{user_id}")
        assert delete_response.status_code == HTTPStatus.NO_CONTENT

        # Verify membership is deleted (cascade)
        membership_get = await client.delete(f"/memberships/{membership_id}")
        # Should get 404 since cascade delete already removed it
        assert membership_get.status_code == HTTPStatus.NOT_FOUND


class TestUserErrorHandling:
    """Test user error scenarios."""

    @pytest.mark.asyncio
    async def test_get_nonexistent_user(self, client: AsyncClient) -> None:
        """Getting nonexistent user should return 404."""
        response = await client.get(f"/users/{NONEXISTENT_UUID}")
        assert response.status_code == HTTPStatus.NOT_FOUND

    @pytest.mark.asyncio
    async def test_update_nonexistent_user(self, client: AsyncClient) -> None:
        """Updating nonexistent user should return 404."""
        response = await client.patch(
            f"/users/{NONEXISTENT_UUID}",
            json={"name": "Updated"},
        )
        assert response.status_code == HTTPStatus.NOT_FOUND

    @pytest.mark.asyncio
    async def test_delete_nonexistent_user(self, client: AsyncClient) -> None:
        """Deleting nonexistent user should return 404."""
        response = await client.delete(f"/users/{NONEXISTENT_UUID}")
        assert response.status_code == HTTPStatus.NOT_FOUND

    @pytest.mark.asyncio
    async def test_get_user_invalid_uuid(self, client: AsyncClient) -> None:
        """Getting user with invalid UUID should return 422."""
        response = await client.get("/users/not-a-uuid")
        assert response.status_code == HTTPStatus.UNPROCESSABLE_ENTITY
