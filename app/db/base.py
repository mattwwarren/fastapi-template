"""Model imports for SQLModel metadata discovery.

Alembic autogenerate uses SQLModel.metadata. Importing this module registers all
table models by importing their modules, so keep new models listed here.
"""

from app.models.membership import Membership
from app.models.organization import Organization
from app.models.user import User

__all__ = ["Membership", "Organization", "User"]
