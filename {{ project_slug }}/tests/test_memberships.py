"""Comprehensive membership endpoint tests covering CRUD, constraints, cascade delete, and error handling."""

from http import HTTPStatus

import pytest
from httpx import AsyncClient


class TestMembershipCRUD:
    """Test basic membership CRUD operations."""

    @pytest.mark.asyncio
    async def test_create_membership_success(self, client: AsyncClient) -> None:
        """Create a membership with valid user and organization."""
        # Create organization
        org_response = await client.post("/organizations", json={"name": "Acme"})
        assert org_response.status_code == HTTPStatus.CREATED
        organization_id = org_response.json()["id"]

        # Create user
        user_response = await client.post(
            "/users",
            json={"name": "Jane Doe", "email": "jane@example.com"},
        )
        assert user_response.status_code == HTTPStatus.CREATED
        user_id = user_response.json()["id"]

        # Create membership
        create_response = await client.post(
            "/memberships",
            json={"user_id": user_id, "organization_id": organization_id},
        )
        assert create_response.status_code == HTTPStatus.CREATED
        membership = create_response.json()
        assert membership["user_id"] == user_id
        assert membership["organization_id"] == organization_id
        assert "id" in membership
        assert "created_at" in membership
        assert "updated_at" in membership

    @pytest.mark.asyncio
    async def test_delete_membership(self, client: AsyncClient) -> None:
        """Delete a membership."""
        # Create organization and user
        org_response = await client.post("/organizations", json={"name": "Acme"})
        organization_id = org_response.json()["id"]

        user_response = await client.post(
            "/users",
            json={"name": "Jane Doe", "email": "jane@example.com"},
        )
        user_id = user_response.json()["id"]

        # Create membership
        create_response = await client.post(
            "/memberships",
            json={"user_id": user_id, "organization_id": organization_id},
        )
        membership_id = create_response.json()["id"]

        # Delete membership
        delete_response = await client.delete(f"/memberships/{membership_id}")
        assert delete_response.status_code == HTTPStatus.NO_CONTENT

        # Verify user has no organizations
        user_get = await client.get(f"/users/{user_id}")
        assert user_get.status_code == HTTPStatus.OK
        assert user_get.json()["organizations"] == []

        # Verify organization has no users
        org_get = await client.get(f"/organizations/{organization_id}")
        assert org_get.status_code == HTTPStatus.OK
        assert org_get.json()["users"] == []

    @pytest.mark.asyncio
    async def test_list_memberships(self, client: AsyncClient) -> None:
        """List all memberships with pagination."""
        # Create organization
        org_response = await client.post("/organizations", json={"name": "Acme"})
        organization_id = org_response.json()["id"]

        # Create multiple users and memberships
        for i in range(3):
            user_response = await client.post(
                "/users",
                json={"name": f"User {i}", "email": f"user{i}@example.com"},
            )
            user_id = user_response.json()["id"]

            await client.post(
                "/memberships",
                json={"user_id": user_id, "organization_id": organization_id},
            )

        # List memberships
        list_response = await client.get("/memberships")
        assert list_response.status_code == HTTPStatus.OK
        data = list_response.json()
        assert data["total"] == 3
        assert len(data["items"]) == 3


class TestMembershipConstraints:
    """Test membership database constraints."""

    @pytest.mark.asyncio
    async def test_duplicate_membership_fails(self, client: AsyncClient) -> None:
        """Creating duplicate membership (same user+org) should fail."""
        # Create organization and user
        org_response = await client.post("/organizations", json={"name": "Acme"})
        organization_id = org_response.json()["id"]

        user_response = await client.post(
            "/users",
            json={"name": "Jane Doe", "email": "jane@example.com"},
        )
        user_id = user_response.json()["id"]

        # Create first membership
        create_response1 = await client.post(
            "/memberships",
            json={"user_id": user_id, "organization_id": organization_id},
        )
        assert create_response1.status_code == HTTPStatus.CREATED

        # Try to create duplicate membership
        create_response2 = await client.post(
            "/memberships",
            json={"user_id": user_id, "organization_id": organization_id},
        )
        # Should fail with unique constraint violation
        assert create_response2.status_code in (
            HTTPStatus.BAD_REQUEST,
            HTTPStatus.CONFLICT,
        )

    @pytest.mark.asyncio
    async def test_create_membership_nonexistent_user(
        self, client: AsyncClient
    ) -> None:
        """Creating membership with nonexistent user should fail."""
        # Create organization
        org_response = await client.post("/organizations", json={"name": "Acme"})
        organization_id = org_response.json()["id"]

        # Try to create membership with fake user
        create_response = await client.post(
            "/memberships",
            json={
                "user_id": "00000000-0000-0000-0000-000000000000",
                "organization_id": organization_id,
            },
        )
        assert create_response.status_code == HTTPStatus.BAD_REQUEST

    @pytest.mark.asyncio
    async def test_create_membership_nonexistent_organization(
        self, client: AsyncClient
    ) -> None:
        """Creating membership with nonexistent organization should fail."""
        # Create user
        user_response = await client.post(
            "/users",
            json={"name": "Jane Doe", "email": "jane@example.com"},
        )
        user_id = user_response.json()["id"]

        # Try to create membership with fake organization
        create_response = await client.post(
            "/memberships",
            json={
                "user_id": user_id,
                "organization_id": "00000000-0000-0000-0000-000000000000",
            },
        )
        assert create_response.status_code == HTTPStatus.BAD_REQUEST


class TestMembershipCascadeDelete:
    """Test cascade delete behavior for memberships."""

    @pytest.mark.asyncio
    async def test_cascade_delete_organization(self, client: AsyncClient) -> None:
        """Deleting organization should cascade delete memberships."""
        # Create organization and user
        org_response = await client.post("/organizations", json={"name": "Acme"})
        organization_id = org_response.json()["id"]

        user_response = await client.post(
            "/users",
            json={"name": "Jane Doe", "email": "jane@example.com"},
        )
        user_id = user_response.json()["id"]

        # Create membership
        await client.post(
            "/memberships",
            json={"user_id": user_id, "organization_id": organization_id},
        )

        # Delete organization
        delete_org = await client.delete(f"/organizations/{organization_id}")
        assert delete_org.status_code == HTTPStatus.NO_CONTENT

        # Verify membership is cascade deleted
        list_response = await client.get("/memberships")
        assert list_response.status_code == HTTPStatus.OK
        assert list_response.json()["items"] == []

        # Verify user still exists
        user_get = await client.get(f"/users/{user_id}")
        assert user_get.status_code == HTTPStatus.OK

    @pytest.mark.asyncio
    async def test_cascade_delete_user(self, client: AsyncClient) -> None:
        """Deleting user should cascade delete memberships."""
        # Create organization and user
        org_response = await client.post("/organizations", json={"name": "Acme"})
        organization_id = org_response.json()["id"]

        user_response = await client.post(
            "/users",
            json={"name": "Jane Doe", "email": "jane@example.com"},
        )
        user_id = user_response.json()["id"]

        # Create membership
        await client.post(
            "/memberships",
            json={"user_id": user_id, "organization_id": organization_id},
        )

        # Delete user
        delete_user = await client.delete(f"/users/{user_id}")
        assert delete_user.status_code == HTTPStatus.NO_CONTENT

        # Verify membership is cascade deleted
        list_response = await client.get("/memberships")
        assert list_response.status_code == HTTPStatus.OK
        assert list_response.json()["items"] == []

        # Verify organization still exists
        org_get = await client.get(f"/organizations/{organization_id}")
        assert org_get.status_code == HTTPStatus.OK


class TestMembershipErrorHandling:
    """Test membership error scenarios."""

    @pytest.mark.asyncio
    async def test_delete_nonexistent_membership(self, client: AsyncClient) -> None:
        """Deleting nonexistent membership should return 404."""
        response = await client.delete(
            "/memberships/00000000-0000-0000-0000-000000000000"
        )
        assert response.status_code == HTTPStatus.NOT_FOUND

    @pytest.mark.asyncio
    async def test_create_membership_invalid_uuid(self, client: AsyncClient) -> None:
        """Creating membership with invalid UUIDs should fail."""
        # Create valid organization
        org_response = await client.post("/organizations", json={"name": "Acme"})
        organization_id = org_response.json()["id"]

        # Try to create with invalid user UUID
        response = await client.post(
            "/memberships",
            json={
                "user_id": "not-a-uuid",
                "organization_id": organization_id,
            },
        )
        assert response.status_code == HTTPStatus.UNPROCESSABLE_ENTITY
