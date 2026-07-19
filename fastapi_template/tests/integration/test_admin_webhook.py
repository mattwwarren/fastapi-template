"""Integration tests for the Kratos registration webhook.

Exercises ``handle_registration`` in ``api/admin.py`` end-to-end through the
mounted ``/_admin/webhooks/kratos/registration`` route. These tests pin the
current, correct behaviour (user/org/owner-membership creation and idempotency)
so the ``col()`` typing wraps applied to the handler's queries can be verified
as pure no-ops.

Uses the plain ``client`` fixture (not ``authenticated_client``): the handler
depends only on ``payload``/``session`` and the webhook path is not in the auth
allowlist, so the real auth middleware would 401 before reaching the handler.
"""

from http import HTTPStatus
from uuid import UUID, uuid4

import pytest
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import col

from fastapi_template.models.membership import Membership, MembershipRole
from fastapi_template.models.organization import Organization
from fastapi_template.models.user import User

REGISTRATION_URL = "/_admin/webhooks/kratos/registration"


def _payload(identity_id: str, email: str) -> dict[str, object]:
    return {
        "identity": {
            "id": identity_id,
            "traits": {
                "email": email,
                "name": {"first": "Jane", "last": "Doe"},
            },
        }
    }


class TestKratosRegistrationWebhook:
    """Test handle_registration end-to-end."""

    @pytest.mark.asyncio
    async def test_registration_creates_user_org_and_owner_membership(
        self, client: AsyncClient, session: AsyncSession
    ) -> None:
        """A fresh identity creates a user, an organization, and an OWNER membership."""
        identity_id = uuid4()
        email = f"webhook-{identity_id}@example.com"

        response = await client.post(REGISTRATION_URL, json=_payload(str(identity_id), email))

        assert response.status_code == HTTPStatus.OK
        body = response.json()
        assert body["status"] == "created"

        user = (await session.execute(select(User).where(col(User.kratos_identity_id) == identity_id))).scalar_one()
        assert str(user.id) == body["user_id"]
        assert user.email == email

        org = (
            await session.execute(select(Organization).where(col(Organization.id) == UUID(body["organization_id"])))
        ).scalar_one_or_none()
        assert org is not None
        assert str(org.id) == body["organization_id"]

        membership = (
            await session.execute(
                select(Membership).where(
                    col(Membership.user_id) == user.id,
                    col(Membership.organization_id) == org.id,
                )
            )
        ).scalar_one()
        assert membership.role == MembershipRole.OWNER

    @pytest.mark.asyncio
    async def test_registration_is_idempotent_for_existing_identity(
        self, client: AsyncClient, session: AsyncSession
    ) -> None:
        """Repeated registration for the same identity returns the same ids and no duplicates."""
        identity_id = uuid4()
        email = f"webhook-idem-{identity_id}@example.com"

        first = await client.post(REGISTRATION_URL, json=_payload(str(identity_id), email))
        assert first.status_code == HTTPStatus.OK
        first_body = first.json()
        assert first_body["status"] == "created"

        second = await client.post(REGISTRATION_URL, json=_payload(str(identity_id), email))
        assert second.status_code == HTTPStatus.OK
        second_body = second.json()

        assert second_body["status"] == "already_exists"
        assert second_body["user_id"] == first_body["user_id"]
        assert second_body["organization_id"] == first_body["organization_id"]

        users = (
            (await session.execute(select(User).where(col(User.kratos_identity_id) == identity_id))).scalars().all()
        )
        assert len(users) == 1

        memberships = (
            (await session.execute(select(Membership).where(col(Membership.user_id) == users[0].id))).scalars().all()
        )
        assert len(memberships) == 1
