"""Model imports for SQLModel metadata discovery.

Alembic autogenerate uses SQLModel.metadata. Importing this module registers all
table models by importing their modules, so keep new models listed here.
"""

from {{ project_slug }}.models.membership import Membership
from {{ project_slug }}.models.organization import Organization
from {{ project_slug }}.models.user import User

__all__ = ["Membership", "Organization", "User"]
