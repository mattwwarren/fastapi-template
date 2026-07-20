Architecture
============

.. note::

   The authoritative architecture document is ``ARCHITECTURE.md`` at the
   repository root. This page is a quick orientation summary.

High-level flow:

- Requests enter FastAPI routes under ``fastapi_template/api/``.
- Route handlers call service helpers in ``fastapi_template/services/``.
- Services use the async SQLAlchemy session provided by ``fastapi_template/db/session.py``.
- SQLModel defines tables and schemas in ``fastapi_template/models/``.
- Alembic reads ``SQLModel.metadata`` for migrations.

Runtime components:

- Postgres 18 for persistence
- Prometheus metrics via ``/metrics``
- ECS JSON logs for structured logging
