# Quick Start Guide

Welcome! You've generated a production-ready FastAPI template. This guide walks you through initial setup and optional feature configuration.

## Prerequisites

- Python 3.11+
- Docker (for PostgreSQL)
- `uv` package manager (https://docs.astral.sh/uv/)

## Initial Setup (5 minutes)

### 1. Environment Configuration

Copy the example environment file and update it:

```bash
cp .env.example .env
# Edit .env - at minimum, set DATABASE_URL to your PostgreSQL connection
```

### 2. Install Dependencies

```bash
uv sync --dev
```

### 3. Database Setup

Run migrations to create schema:

```bash
uv run alembic upgrade head
```

### 4. Run Development Server

```bash
uv run fastapi dev {{ project_slug }}/main.py
# Opens http://localhost:{{ port }}
# API docs: http://localhost:{{ port }}/docs
```

Verify the server is running by visiting http://localhost:{{ port }}/health in your browser.

---

## Enabling Optional Features

By default, several features are disabled (commented out in code). Follow this checklist to enable the ones you need:

### Feature: Authentication

**Status**: DISABLED by default
**Why**: Allows local development without auth provider setup
**Enable**: Uncomment in `{{ project_slug }}/main.py` around line 35

```python
# Line 35: Uncomment to enable authentication
app.add_middleware(AuthMiddleware)
```

**Configuration**: Update `.env`:
- `AUTH_PROVIDER_TYPE=none` (local development, no auth)
- `AUTH_PROVIDER_TYPE=ory` (use Ory identity platform)
- `AUTH_PROVIDER_TYPE=auth0` (use Auth0)
- `AUTH_PROVIDER_TYPE=keycloak` (use Keycloak)
- `AUTH_PROVIDER_TYPE=cognito` (use AWS Cognito)

For provider-specific setup, see [CONFIGURATION-GUIDE.md](CONFIGURATION-GUIDE.md#authentication)

**Test without authentication**:
```bash
# These endpoints work without auth:
curl http://localhost:{{ port }}/health
curl http://localhost:{{ port }}/ping
curl http://localhost:{{ port }}/docs
```

---

### Feature: Multi-Tenant Isolation

**Status**: DISABLED by default
**Why**: Single-tenant apps don't need this complexity
**Enable**: Uncomment in `{{ project_slug }}/main.py` around line 45

```python
# Line 45: Uncomment to enable tenant isolation
# IMPORTANT: AuthMiddleware must be enabled first!
app.add_middleware(TenantIsolationMiddleware)
```

**Configuration**: Update `.env`:
- `ENFORCE_TENANT_ISOLATION=true` (default, recommended)
- `ENFORCE_TENANT_ISOLATION=false` (for single-tenant)

**What this does**:
- Prevents User A from accessing Organization B's data
- Enforces tenant context from JWT claims
- Applies WHERE clauses to all database queries
- Protects documents, users, memberships, and custom data

For details, see [docs/TENANT_ISOLATION.md](docs/TENANT_ISOLATION.md)

---

### Feature: Cloud Storage

**Status**: Local filesystem by default
**Why**: Works out-of-the-box, no external dependencies
**Configure**: Update `.env` for your provider

**Local storage** (development):
```bash
STORAGE_PROVIDER=local
STORAGE_LOCAL_PATH=./uploads
```

**AWS S3** (production):
```bash
STORAGE_PROVIDER=s3
STORAGE_AWS_BUCKET=my-bucket
STORAGE_AWS_REGION=us-east-1
STORAGE_AWS_ACCESS_KEY_ID=your-access-key
STORAGE_AWS_SECRET_ACCESS_KEY=your-secret-key
```

**Azure Blob Storage** (production):
```bash
STORAGE_PROVIDER=azure
STORAGE_AZURE_CONTAINER=my-container
STORAGE_AZURE_CONNECTION_STRING=DefaultEndpointsProtocol=https;...
```

**Google Cloud Storage** (production):
```bash
STORAGE_PROVIDER=gcs
STORAGE_GCS_BUCKET=my-bucket
STORAGE_GCS_PROJECT_ID=my-project
GOOGLE_APPLICATION_CREDENTIALS=/path/to/service-account-key.json
```

For setup guides, see [CONFIGURATION-GUIDE.md](CONFIGURATION-GUIDE.md#storage)

---

### Feature: Activity Logging

**Status**: ENABLED by default
**Why**: Audit trail for compliance and debugging
**Disable**: Update `.env` if not needed

```bash
ACTIVITY_LOGGING_ENABLED=false  # Disable if not needed
```

All create, read, update, and delete operations are logged with:
- Timestamp
- User ID and email
- Action type (CREATE, READ, UPDATE, DELETE)
- Resource type and ID
- Changes made (for UPDATE)

---

### Feature: Metrics (Prometheus)

**Status**: ENABLED by default
**Why**: Observability and monitoring
**Access**: http://localhost:{{ port }}/metrics

Metrics include:
- User operations (users_created_total, users_updated_total)
- Organization operations (organizations_created_total)
- Document uploads (documents_uploaded_total)
- Database query duration
- HTTP request latency

---

## Running Tests

```bash
# Run all tests
uv run pytest tests/ -v

# Run specific test file
uv run pytest tests/test_users.py -v

# Run specific test
uv run pytest tests/test_users.py::TestUserCRUD::test_create_user_success -v

# Run with coverage report
uv run pytest tests/ --cov={{ project_slug }} --cov-report=html
```

After running tests, open `htmlcov/index.html` to view coverage report.

---

## Code Quality

Verify your code meets production standards before committing:

```bash
# Lint violations
uv run ruff check .

# Type checking
uv run mypy .

# Run tests
uv run pytest tests/
```

All three must pass before pushing to repository.

---

## Next Steps

1. **Read the Architecture**: [docs/architecture.rst](docs/architecture.rst) explains the project structure
2. **Add Your First Endpoint**: Follow [docs/howto_add_feature.rst](docs/howto_add_feature.rst)
3. **Configure Features**: See [CONFIGURATION-GUIDE.md](CONFIGURATION-GUIDE.md) for detailed options
4. **Review Security**: See [docs/TENANT_ISOLATION.md](docs/TENANT_ISOLATION.md) if using multi-tenant

---

## Troubleshooting

### "Can't connect to PostgreSQL"

**Problem**: `psycopg.OperationalError: connection failed`

**Solution**:
1. Ensure Docker is running: `docker ps`
2. Check DATABASE_URL in `.env` matches your setup
3. Create a test database container:
   ```bash
   docker run -d \
     -e POSTGRES_PASSWORD=postgres \
     -e POSTGRES_DB=myapp \
     -p 5432:5432 \
     --name postgres \
     postgres:15
   ```
4. Update `.env`:
   ```bash
   DATABASE_URL=postgresql+asyncpg://postgres:postgres@localhost:5432/myapp
   ```

### "Port 8000 already in use"

**Problem**: `[Errno 98] Address already in use`

**Solution**:
```bash
# Use a different port
uv run fastapi dev {{ project_slug }}/main.py --port 8001

# Or kill the process using port 8000
lsof -i :8000 | grep LISTEN | awk '{print $2}' | xargs kill -9
```

### "ruff check fails"

**Problem**: Linting violations found

**Solution**:
```bash
# Auto-fix most violations
uv run ruff check --fix

# View remaining violations
uv run ruff check .

# See specific rule: .claude/RUFF-GUIDE.md
```

### "mypy reports type errors"

**Problem**: Type checking failures

**Solution**:
1. Check for missing type annotations on function parameters
2. Ensure all functions have return types (including `-> None`)
3. See type checking guide: [.claude/README.md](.claude/README.md)

### "Tests fail with 'No module named...'"

**Problem**: Import errors in tests

**Solution**:
```bash
# Reinstall with dependencies
uv sync --dev

# Verify Python path
uv run python -c "import {{ project_slug }}"

# Check package structure
ls -la {{ project_slug }}/
```

---

## Production Deployment Checklist

Before deploying to production, verify all items:

- [ ] Set `DEBUG=false` in `.env`
- [ ] Set `SECRET_KEY` to a random 32+ character value (don't commit to git)
- [ ] Enable authentication: uncomment AuthMiddleware
- [ ] Enable tenant isolation if using multi-tenant: uncomment TenantIsolationMiddleware
- [ ] Configure external PostgreSQL database (not local)
- [ ] Configure external storage (S3, Azure, GCS - not local filesystem)
- [ ] Set up SSL/TLS (use nginx reverse proxy)
- [ ] Configure logging level (info for production)
- [ ] Set up monitoring and alerting
- [ ] Run full test suite: `uv run pytest tests/`
- [ ] Run security checks: `uv run ruff check . && uv run mypy .`
- [ ] Review API documentation at /docs endpoint
- [ ] Test all enabled features in staging environment

---

## Additional Resources

- **Configuration Reference**: [CONFIGURATION-GUIDE.md](CONFIGURATION-GUIDE.md)
- **Tenant Isolation Details**: [docs/TENANT_ISOLATION.md](docs/TENANT_ISOLATION.md)
- **Activity Logging**: [docs/activity_logging.md](docs/activity_logging.md)
- **Deployment Guide**: [docs/deployment.md](docs/deployment.md)
- **Testing Patterns**: [.claude/TEMPLATE-TESTING.md](.claude/TEMPLATE-TESTING.md)
- **Contributing**: See [CONTRIBUTING.md](CONTRIBUTING.md) if developing on this template

---

## Getting Help

If you encounter issues:

1. Check this Quick Start guide first
2. See [CONFIGURATION-GUIDE.md](CONFIGURATION-GUIDE.md) for detailed setup
3. Check [docs/troubleshooting.rst](docs/troubleshooting.rst)
4. Review [.claude/README.md](.claude/README.md) for Claude Code integration
5. Check recent git commit messages: `git log --oneline -20`

---

## What's Next?

Your FastAPI application is ready. Start building! 🚀

1. Create your first endpoint in `{{ project_slug }}/api/`
2. Add your data models in `{{ project_slug }}/models/`
3. Implement business logic in `{{ project_slug }}/services/`
4. Write tests in `{{ project_slug }}/tests/`
5. Deploy with confidence knowing tests pass and code is clean
