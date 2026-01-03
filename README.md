# fastapi-template

Async-only FastAPI template with SQLModel, Alembic, Postgres, Prometheus metrics, and k3d + DevSpace for local Kubernetes workflows.

## Requirements

- Python 3.13
- [uv](https://docs.astral.sh/uv/)
- Docker
- k3d, kubectl, and DevSpace (for the default local dev flow)

## Quickstart (local)

```bash
uv sync --dev
cp .env.example .env
uv run uvicorn app.main:app --reload --log-config app/core/logging.yaml
```

## Quickstart (k3d + DevSpace)

```bash
devspace dev -p dev
```

Defaults are defined in `devspace.yaml` and can be overridden via environment variables:

```bash
export CLUSTER_NAME=fastapi-template
export NAMESPACE=dev
export IMAGE_NAME=fastapi-template
export IMAGE_TAG=dev
export POSTGRES_DB=app
export POSTGRES_USER=app
export POSTGRES_PASSWORD=app
```

## Database migrations

```bash
alembic upgrade head
```

## Tests

Tests use `pytest-docker` to launch a Postgres container via `tests/docker-compose.yml`.

```bash
uv run pytest
```

## Endpoints

- `GET /health`
- `GET /ping`
- `GET /organizations`
- `POST /organizations`
- `PATCH /organizations/{organization_id}`
- `DELETE /organizations/{organization_id}`
- `GET /users`
- `POST /users`
- `PATCH /users/{user_id}`
- `DELETE /users/{user_id}`
- `GET /memberships`
- `POST /memberships`
- `DELETE /memberships/{membership_id}`
- `GET /metrics`
