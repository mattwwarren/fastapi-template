"""Model imports for SQLModel metadata discovery.

Alembic autogenerate uses SQLModel.metadata. Importing this module registers all
table models by importing their modules, so keep new models listed here.
"""

from fastapi_template.models.activity_log import ActivityLog, ActivityLogArchive
from fastapi_template.models.document import Document
from fastapi_template.models.membership import Membership
from fastapi_template.models.organization import Organization
from fastapi_template.models.user import User

__all__ = [
    "ActivityLog",
    "ActivityLogArchive",
    "Document",
    "Membership",
    "Organization",
    "User",
]
