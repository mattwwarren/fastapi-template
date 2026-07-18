"""Tests for the MembershipRole enum.

Tests cover:
- str()/format() output of MembershipRole (pinned after the enum.StrEnum rewrite)
"""

from __future__ import annotations

from fastapi_template.models.membership import MembershipRole


class TestMembershipRoleStrEnum:
    """Tests for MembershipRole's string behavior as an enum.StrEnum."""

    def test_str_returns_bare_value(self) -> None:
        """str() should return the bare value (e.g. 'owner'), not 'MembershipRole.OWNER'.

        MembershipRole is an enum.StrEnum, which overrides __str__/__format__ to
        return the plain value. This differs from the old `(str, enum.Enum)` mixin,
        which used Enum's default __str__ ("MembershipRole.OWNER"). No application
        source code relies on implicit str()/f-string formatting of this enum today
        (all call sites use `.value` or direct member comparison), but this test
        pins the intentional behavior so a future regression is caught.
        """
        assert str(MembershipRole.OWNER) == "owner"
        assert str(MembershipRole.ADMIN) == "admin"
        assert str(MembershipRole.MEMBER) == "member"

    def test_format_returns_bare_value(self) -> None:
        """f-string formatting should return the bare value, matching str()."""
        assert f"{MembershipRole.OWNER}" == "owner"

    def test_value_unchanged(self) -> None:
        """.value access is unaffected by the StrEnum rewrite."""
        assert MembershipRole.OWNER.value == "owner"
        assert MembershipRole.ADMIN.value == "admin"
        assert MembershipRole.MEMBER.value == "member"
