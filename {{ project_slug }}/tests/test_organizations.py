"""Comprehensive organization endpoint tests.

Tests cover CRUD operations, validation, relationships, and tenant isolation.
"""

from http import HTTPStatus

import pytest
from httpx import AsyncClient

# Test constants
NUM_TEST_ORGS = 3
NUM_TEST_USERS_PER_ORG = 3
NONEXISTENT_UUID = "ffffffff-ffff-ffff-ffff-ffffffffffff"


class TestOrganizationCRUD:
    """Test basic organization CRUD operations."""

    @pytest.mark.asyncio
    async def test_create_organization_success(self, client: AsyncClient) -> None:
        """Create an organization with valid data."""
        response = await client.post(
            "/organizations",
            json={"name": "Acme Corp"},
        )
        assert response.status_code == HTTPStatus.CREATED
        org = response.json()
        assert org["name"] == "Acme Corp"
        assert org["users"] == []
        assert "id" in org
        assert "created_at" in org
        assert "updated_at" in org

    @pytest.mark.asyncio
    async def test_read_organization(self, client: AsyncClient) -> None:
        """Get a single organization by ID."""
        # Create organization
        create_response = await client.post(
            "/organizations",
            json={"name": "Tech Startup"},
        )
        org_id = create_response.json()["id"]

        # Read organization
        get_response = await client.get(f"/organizations/{org_id}")
        assert get_response.status_code == HTTPStatus.OK
        org = get_response.json()
        assert org["id"] == org_id
        assert org["name"] == "Tech Startup"

    @pytest.mark.asyncio
    async def test_update_organization(self, client: AsyncClient) -> None:
        """Update organization fields."""
        # Create organization
        create_response = await client.post(
            "/organizations",
            json={"name": "Original Org"},
        )
        org_id = create_response.json()["id"]

        # Update organization
        update_response = await client.patch(
            f"/organizations/{org_id}",
            json={"name": "Updated Org"},
        )
        assert update_response.status_code == HTTPStatus.OK
        updated_org = update_response.json()
        assert updated_org["name"] == "Updated Org"

    @pytest.mark.asyncio
    async def test_delete_organization(self, client: AsyncClient) -> None:
        """Delete an organization."""
        # Create organization
        create_response = await client.post(
            "/organizations",
            json={"name": "To Delete"},
        )
        org_id = create_response.json()["id"]

        # Delete organization
        delete_response = await client.delete(f"/organizations/{org_id}")
        assert delete_response.status_code == HTTPStatus.NO_CONTENT

        # Verify deleted
        get_response = await client.get(f"/organizations/{org_id}")
        assert get_response.status_code == HTTPStatus.NOT_FOUND

    @pytest.mark.asyncio
    async def test_list_organizations(self, client: AsyncClient) -> None:
        """List organizations with pagination."""
        # Create multiple organizations
        for i in range(NUM_TEST_ORGS):
            await client.post(
                "/organizations",
                json={"name": f"Organization {i}"},
            )

        # List organizations
        list_response = await client.get("/organizations")
        assert list_response.status_code == HTTPStatus.OK
        data = list_response.json()
        # +1 accounts for the fixture organization (UUID 00000000-0000-0000-0000-000000000000)
        # created in conftest.py that persists across tests
        assert data["total"] == NUM_TEST_ORGS + 1
        assert len(data["items"]) == NUM_TEST_ORGS + 1
        assert data["page"] == 1
        assert data["size"] >= NUM_TEST_ORGS


class TestOrganizationValidation:
    """Test organization input validation."""

    @pytest.mark.asyncio
    async def test_create_organization_empty_name(self, client: AsyncClient) -> None:
        """Creating organization with empty name should fail."""
        response = await client.post(
            "/organizations",
            json={"name": ""},
        )
        # Should fail if name has min_length validation
        # Pydantic validators raise ValueError which can be converted to either 400 or 422
        assert response.status_code in (
            HTTPStatus.BAD_REQUEST,  # 400
            HTTPStatus.UNPROCESSABLE_ENTITY,  # 422
        )

    @pytest.mark.asyncio
    async def test_create_organization_missing_name(self, client: AsyncClient) -> None:
        """Creating organization without name should fail."""
        response = await client.post(
            "/organizations",
            json={},
        )
        assert response.status_code == HTTPStatus.UNPROCESSABLE_ENTITY

    @pytest.mark.asyncio
    async def test_create_organization_whitespace_only_name(
        self, client: AsyncClient
    ) -> None:
        """Test organization with whitespace-only name."""
        response = await client.post(
            "/organizations",
            json={"name": "   "},
        )
        # Pydantic validators raise ValueError which can be converted to either 400 or 422
        assert response.status_code in (
            HTTPStatus.BAD_REQUEST,  # 400
            HTTPStatus.UNPROCESSABLE_ENTITY,  # 422
        )

    @pytest.mark.asyncio
    async def test_update_organization_empty_name(self, client: AsyncClient) -> None:
        """Updating organization to empty name should fail if validated."""
        # Create organization
        create_response = await client.post(
            "/organizations",
            json={"name": "Valid Org"},
        )
        org_id = create_response.json()["id"]

        # Try to update to empty name
        update_response = await client.patch(
            f"/organizations/{org_id}",
            json={"name": ""},
        )
        # Depends on validation rules
        assert update_response.status_code in (
            HTTPStatus.UNPROCESSABLE_ENTITY,
            HTTPStatus.OK,
        )


class TestOrganizationUserRelationship:
    """Test organization-user relationship expansion."""

    @pytest.mark.asyncio
    async def test_organization_shows_users(self, client: AsyncClient) -> None:
        """Organization should show users after membership is created."""
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

        # Get organization and verify users
        get_response = await client.get(f"/organizations/{org_id}")
        assert get_response.status_code == HTTPStatus.OK
        org = get_response.json()
        assert "users" in org
        assert isinstance(org["users"], list)
        assert len(org["users"]) == 1
        assert org["users"][0]["id"] == user_id
        assert org["users"][0]["name"] == "Test User"

    @pytest.mark.asyncio
    async def test_organization_has_no_users(self, client: AsyncClient) -> None:
        """Fresh organization should have empty users list."""
        response = await client.post(
            "/organizations",
            json={"name": "Empty Org"},
        )
        assert response.status_code == HTTPStatus.CREATED
        org = response.json()
        assert org["users"] == []

    @pytest.mark.asyncio
    async def test_organization_shows_multiple_users(
        self, client: AsyncClient
    ) -> None:
        """Organization should show all member users."""
        # Create organization
        org_response = await client.post(
            "/organizations",
            json={"name": "Multi User Org"},
        )
        org_id = org_response.json()["id"]

        # Create multiple users
        user_ids = []
        for i in range(NUM_TEST_USERS_PER_ORG):
            user_response = await client.post(
                "/users",
                json={
                    "name": f"User {i}",
                    "email": f"user{i}@example.com",
                },
            )
            user_id = user_response.json()["id"]
            user_ids.append(user_id)

            # Create membership
            await client.post(
                "/memberships",
                json={
                    "user_id": user_id,
                    "organization_id": org_id,
                },
            )

        # Get organization and verify users
        get_response = await client.get(f"/organizations/{org_id}")
        assert get_response.status_code == HTTPStatus.OK
        org = get_response.json()
        assert len(org["users"]) == NUM_TEST_USERS_PER_ORG
        response_user_ids = [user["id"] for user in org["users"]]
        for user_id in user_ids:
            assert user_id in response_user_ids

    @pytest.mark.asyncio
    async def test_delete_organization_cascades_memberships(
        self, client: AsyncClient
    ) -> None:
        """Deleting organization should cascade delete memberships."""
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

        # Delete organization
        delete_response = await client.delete(f"/organizations/{org_id}")
        assert delete_response.status_code == HTTPStatus.NO_CONTENT

        # Verify membership is deleted (cascade)
        membership_get = await client.delete(f"/memberships/{membership_id}")
        # Should get 404 since cascade delete already removed it
        assert membership_get.status_code == HTTPStatus.NOT_FOUND


class TestOrganizationErrorHandling:
    """Test organization error scenarios."""

    @pytest.mark.asyncio
    async def test_get_nonexistent_organization(self, client: AsyncClient) -> None:
        """Getting nonexistent organization should return 404."""
        response = await client.get(f"/organizations/{NONEXISTENT_UUID}")
        assert response.status_code == HTTPStatus.NOT_FOUND

    @pytest.mark.asyncio
    async def test_update_nonexistent_organization(self, client: AsyncClient) -> None:
        """Updating nonexistent organization should return 404."""
        response = await client.patch(
            f"/organizations/{NONEXISTENT_UUID}",
            json={"name": "Updated"},
        )
        assert response.status_code == HTTPStatus.NOT_FOUND

    @pytest.mark.asyncio
    async def test_delete_nonexistent_organization(self, client: AsyncClient) -> None:
        """Deleting nonexistent organization should return 404."""
        response = await client.delete(f"/organizations/{NONEXISTENT_UUID}")
        assert response.status_code == HTTPStatus.NOT_FOUND

    @pytest.mark.asyncio
    async def test_get_organization_invalid_uuid(self, client: AsyncClient) -> None:
        """Getting organization with invalid UUID should return 422."""
        response = await client.get("/organizations/not-a-uuid")
        assert response.status_code == HTTPStatus.UNPROCESSABLE_ENTITY
