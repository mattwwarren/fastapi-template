# Architecture

This document describes how the FastAPI template is put together: the layering
rules, the request lifecycle, the cross-cutting subsystems, and the invariants
that keep generated projects consistent. For "how do I run it" see
[README.md](README.md); for "how do I add a feature" see
[docs/howto_add_feature.rst](docs/howto_add_feature.rst).

## The template model: runnable-first

The repository is **directly runnable Python** on `main`. There is no Jinja
templating in the core source; Copier variables only shape config files and
which features ship enabled.

- `main` branch — runnable package (`fastapi_template/`), full test suite,
  instant edit-test loop.
- `copier` branch — generated artifact. `scripts/templatize.sh` (run by the
  `publish-template.yml` GitHub Actions workflow) rewrites `fastapi_template`
  to `{{ project_slug }}` and publishes.
- Production instances are generated with
  `copier copy gh:mattwwarren/fastapi-template --vcs-ref copier` and kept in
  sync via `copier update`.

Copier variables (`copier.yaml`) gate features rather than change
architecture: `auth_enabled`/`auth_provider` (Ory, Auth0, Keycloak, Cognito),
`multi_tenant`, `storage_provider` (local, S3, Azure, GCS),
`enable_metrics`, `enable_activity_logging`. In the runnable template the
auth and tenant middleware are present but commented out in `main.py`;
generation (or manual uncommenting) activates them.

## Layering

```
HTTP request
    │
    ▼
Middleware stack (logging → rate limit → [auth] → [tenant] → CORS)
    │
    ▼
api/          routers — HTTP concerns only: routing, status codes,
    │         serialization, pagination, transaction COMMIT
    ▼
services/     business logic and data access helpers — flush, never commit
    │
    ▼
models/       SQLModel tables + Pydantic schemas (Create/Read/Update)
    │
    ▼
db/           async engine, session dependency, Alembic model registry
    │
    ▼
Postgres 18 (asyncpg)
```

The dependency direction is strictly downward. Two rules carry most of the
weight:

1. **Endpoints own the transaction.** Services call `session.flush()` so IDs
   and constraint errors surface early; the endpoint calls `session.commit()`
   exactly once. `db/session.py:get_session` rolls back automatically on any
   exception.
2. **No business logic in `api/`.** Routers translate HTTP ↔ domain calls
   (including mapping `IntegrityError` to 409, validation to 422) and nothing
   else.

### Directory map

- `fastapi_template/main.py` — app factory, lifespan, middleware stack,
  global exception handlers
- `fastapi_template/api/` — one router per resource (`organizations`,
  `users`, `memberships`, `documents`, `health`, `ping`,
  `realtime_schemas`), composed in `api/routes.py`; `api/admin.py` is the
  internal-only `/_admin` surface
- `fastapi_template/services/` — CRUD/business helpers per resource
- `fastapi_template/models/` — SQLModel tables and schemas; `base.py`
  defines `TimestampedTable`; `shared.py` holds cross-resource schemas to
  break circular imports
- `fastapi_template/db/` — engine/session factories, retry decorator,
  `base.py` model registry for Alembic
- `fastapi_template/core/` — cross-cutting subsystems (auth, tenants,
  permissions, logging, metrics, storage, activity logging, background
  tasks, HTTP client, pagination)
- `fastapi_template/cache/` — Redis caching package
- `fastapi_template/realtime/` — Socket.IO server, event contracts
- `alembic/` — migrations (generated artifacts, never hand-edited)
- `k8s/`, `devspace.yaml`, `Dockerfile` — deployment surface

## Application lifecycle

`main.py` uses the lifespan context manager (not deprecated `on_event`):

1. **Validate configuration** — `settings.validate_config()` fails fast on
   misconfiguration, logs non-fatal warnings.
2. **Create DB engine + session maker into `app.state`** — pool settings come
   from `PoolConfig` (a frozen, validated Pydantic model). Connectivity is
   verified with `SELECT 1`; startup aborts if the database is unreachable.
3. **Mount Socket.IO** at `/ws` (`realtime/server.py`).
4. **Create Redis client** — optional; if `REDIS_URL` is unset or Redis is
   unreachable, cache operations degrade to silent no-ops.
5. On shutdown: dispose the engine pool, close Redis.

`db/session.py` also keeps module-level `engine` / `async_session_maker`
globals. These exist for two consumers — fire-and-forget activity logging
(no request context) and test fixtures that swap in per-worker databases for
pytest-xdist. New code should reach for `app.state` / `SessionDep` instead.

## Request lifecycle

Middleware executes in reverse order of addition (last added runs first).
Verified request flow for the active stack:

1. **LoggingMiddleware** — extracts/generates `X-Request-ID`, stores
   `request_id` (and post-auth `user_id`/`org_id`) in ContextVars so every
   log line in the request — including in services — carries the context via
   `get_logging_context()`
2. **SlowAPIMiddleware** — per-IP rate limiting (default 100/min, 2000/hr).
   Note: the `Limiter` is constructed without a `storage_uri`, so limits are
   tracked **in-process, per worker** — not shared across replicas. Point it
   at Redis if you need cluster-wide limits.
3. **CORSMiddleware** — explicit method/header lists, configured origins
4. Route handler, with dependencies injected

**AuthMiddleware** (gated on `auth_enabled` — JWT validation for
Ory/Auth0/Keycloak/Cognito, populates `request.state.user`) and
**TenantIsolationMiddleware** (gated on `multi_tenant`, requires auth) ship
commented out in `main.py`; generation or manual uncommenting activates
them. Beware the reverse-execution rule when placing them: the narrative
comments in `main.py` describe the *intended* order (logging → auth →
tenant), which requires adding them in the opposite order.

### Standard endpoint dependencies

- `SessionDep` — request-scoped `AsyncSession`
- `CurrentUserDep` / `CurrentUserFromHeaders` — authenticated principal
- `TenantDep` — tenant context (see below)
- `ParamsDep` — pagination params (`fastapi-pagination`; list endpoints
  return `Page` with stable `created_at` ordering)

### Error contract

Global exception handlers in `main.py` guarantee a uniform error envelope:

```json
{ "status_code": 422, "error_code": "VALIDATION_ERROR", "message": "...", "details": [...] }
```

- `RequestValidationError` / Pydantic `ValidationError` → 422
- `ValueError` → 400 `INVALID_VALUE`; `TypeError` → 400 `INVALID_TYPE`
- Anything else → 500 `INTERNAL_ERROR`, fully logged server-side, sanitized
  message to the client

## Security model

Three layers, each fail-closed:

1. **Authentication** (`core/auth.py`) — JWT middleware + dependencies;
   provider-agnostic via configuration. In the Ory deployment variant,
   Oathkeeper terminates auth at the gateway and identity arrives via
   headers (`CurrentUserFromHeaders`).
2. **Tenant isolation** (`core/tenants.py`) — deny by default: endpoints
   opt into tenant context via `TenantDep`; services apply
   `add_tenant_filter` to queries; public endpoints must be explicitly
   listed. Missing tenant context returns 401/403, never data.
3. **RBAC** (`core/permissions.py`) — role hierarchy OWNER > ADMIN > MEMBER
   within an organization; `require_role(...)` dependency factory for
   dangerous operations.

The `/_admin` routers (webhooks for Kratos/Oathkeeper, internal lookups) are
**not** protected in-app — they must be blocked at the edge (Traefik /
Oathkeeper rules in `k8s/`). The same applies to `/metrics`.

Tenant scoping is threaded **explicitly** everywhere (cache keys, queries,
storage paths); there is deliberately no ambient/implicit tenant detection.

## Data layer

- **SQLModel** models double as tables and schemas, following the
  `ModelBase` → `Model(table=True)` / `ModelCreate` / `ModelRead` /
  `ModelUpdate` pattern (see `models/CLAUDE.md`).
- **`TimestampedTable`** (`models/base.py`) gives every table a
  server-generated UUID PK (`gen_random_uuid()`) and timezone-aware
  `created_at` / `updated_at`. `updated_at` is maintained by a Postgres
  trigger — never set from Python.
- **Migrations are ORM-exclusive.** Alembic autogenerate reads
  `SQLModel.metadata`; `db/base.py` imports every table module so metadata
  is complete — a new model that isn't imported there is invisible to
  autogenerate (and to tests). Files in `alembic/versions/` are generated
  artifacts. Hand-written SQL is an escalation, not a default.
- **Resilience:** `db/retry.py` provides `@db_retry` for transient failures
  (connection drops, deadlocks); the pool uses `pre_ping` plus recycling.
- **N+1 discipline:** relationship expansion happens as explicit follow-up
  queries (batch functions for lists), not ORM eager-loading.

## Cross-cutting subsystems (`core/`, `cache/`, `realtime/`)

- **Observability** — ECS JSON logging configured solely by
  `core/logging.yaml`; ContextVar-based request context; Prometheus metrics
  as a mounted ASGI app at `/metrics` with custom business metrics
  (counters/histograms recorded in services), designed to coexist with
  OpenTelemetry auto-instrumentation. Grafana dashboard and alerting rules
  ship in `k8s/` / `docs/`.
- **Caching** (`cache/`) — Redis with tenant-isolated key building
  (`build_cache_key(..., organization_id=...)`), explicit
  `cache_get`/`cache_set`/`cache_delete`, a `@cached` decorator, and
  serialization helpers. Optional by construction: no Redis → no-ops.
- **Realtime** (`realtime/`) — Socket.IO (JWT-authenticated) mounted at
  `/ws`; uses Redis pub/sub as the cross-process message manager when
  `REDIS_URL` is set, in-memory otherwise. Event payloads are typed
  contracts (`realtime/contracts.py`) and their JSON schemas are exposed via
  the `realtime_schemas` API for frontend codegen.
- **Storage** (`core/storage.py`, `core/storage_providers.py`) — provider
  abstraction (protocol + factory) over local/S3/Azure/GCS, selected by the
  `storage_provider` Copier variable; provider SDKs are optional
  dependencies. The `documents` API is the reference consumer.
- **Activity logging** (`core/activity_logging.py`) — audit trail via
  `@log_activity_decorator` on endpoints; transactional (joins the caller's
  session/commit) or fire-and-forget (own transaction via the module-level
  session maker).
- **Background work** (`core/background_tasks.py`) — fire-and-forget
  `asyncio.create_task` patterns with logging context; distributed queues
  (Celery/RQ) are documented but out of scope — that's what
  `worker-template` is for.
- **Cross-service HTTP** (`core/http_client.py`) — shared async httpx client
  factory; integration examples live as commented reference implementations
  with docs in `docs/service_integration_patterns.md`.

## Testing architecture

Tests live in `fastapi_template/tests/` and run against **real
infrastructure**, not mocks of our own code:

- `pytest-docker` starts Postgres from the repo-root `tests/docker-compose.yml`
  (a separate top-level directory from `fastapi_template/tests/`);
  migrations run via Alembic before tests.
- `pytest-alembic` guards against model/migration drift.
- pytest-xdist compatibility comes from the lifespan/`app.state` design:
  each worker's fixtures swap the engine/session maker to a worker-specific
  database.
- `tests/unit/` — pure logic (config, middleware, pagination, cache,
  retry…); `tests/integration/` — API + DB, including dedicated suites for
  tenant isolation, RBAC, SQL injection, XSS, and race conditions.
- Mocks exist only at boundaries we don't own: `tests/mocks/` fakes auth
  providers and storage providers.

## Deployment

- Non-root Docker image; `scripts/start.sh` launches uvicorn with
  `--log-config` (no ad-hoc log level overrides).
- Local Kubernetes is the default dev flow: k3d cluster + DevSpace
  (`devspace.yaml`); all cluster operations go through DevSpace commands
  (raw kubectl/k3d is blocked for agents by `.claude/settings.json`).
- `k8s/` carries Postgres StatefulSet manifests and the Ory stack config
  (Kratos identity schema, Oathkeeper rules) for the gateway-auth variant;
  see `docs/deployment_variants.md` and `docs/DEPLOYMENT.md`.

## Invariants (the short list)

1. Async-only, end to end — API, DB (asyncpg), HTTP client, cache.
2. Endpoints commit; services flush; `get_session` rolls back.
3. Every table extends `TimestampedTable`; UUIDs and timestamps are
   DB-generated.
4. Every new model is imported in `db/base.py`; every schema change goes
   through `alembic revision --autogenerate`.
5. Tenant scoping is explicit at every layer; isolation fails closed.
6. `core/logging.yaml` is the single source of logging truth; logs are ECS
   JSON with request context.
7. Errors leave the API only through the uniform error envelope.
8. Internal surfaces (`/_admin`, `/metrics`) are protected by the edge, and
   must be configured as such in any real deployment.
9. Optional infrastructure (Redis, storage SDKs) degrades gracefully or is
   feature-gated — the template boots with nothing but Postgres.
