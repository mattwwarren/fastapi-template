# Alembic Migrations

Database schema migrations for the backend.

## How Models Are Discovered

```python
from sqlmodel import SQLModel
target_metadata = SQLModel.metadata

# Side-effect import loads all models into SQLModel.metadata
from fastapi_template.db import base  # noqa: F401
```

The `base` module imports all model files. New models must be imported there to be discovered by Alembic.

## Async Engine

Migrations use `async_engine_from_config()` with `poolclass=pool.NullPool` (no connection pooling during migrations).

## Test Fixture Compatibility

`env.py` checks for `config.attributes.get("connection")` to reuse an existing connection from pytest fixtures instead of creating a new engine.

## Creating Migrations

```bash
# Generate migration from model changes
cd /path/to/fastapi-template
uv run alembic revision --autogenerate -m "add user email column"
```

- Use descriptive messages: `"add user email column"`, `"create documents table"`
- Review generated migration before committing - autogenerate doesn't catch everything
- Always test both upgrade AND downgrade paths

## Migration Safety

- Never drop columns in production without a multi-step migration (add new, migrate data, drop old)
- Add `NOT NULL` columns with a `server_default` first, then remove the default
- Index creation on large tables should use `CREATE INDEX CONCURRENTLY`
