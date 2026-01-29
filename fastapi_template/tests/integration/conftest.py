"""Conftest for integration tests.

Integration tests inherit all fixtures from the parent conftest.py including:
- database_url, engine, session, session_maker
- client, authenticated_client, client_bypass_auth
- test_user, test_organization, user_with_org
- reset_db, default_auth_user_in_org (autouse)

These tests require a running Postgres database (Docker or Kubernetes).
"""

# Re-export all fixtures from parent conftest
# Integration tests use the full database-backed fixture set
from fastapi_template.tests.conftest import *  # noqa: F401, F403
