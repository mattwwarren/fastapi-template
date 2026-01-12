# Quick Start Guide

Welcome! You've generated a production-ready FastAPI template with automated setup.

## Prerequisites

- Python 3.11+
- Docker (for PostgreSQL)
- `uv` package manager (https://docs.astral.sh/uv/)

## What Was Automated

During project generation, the following tasks were completed automatically:

✅ Environment file (`.env`) created from template
✅ Dependencies installed via `uv sync --dev` (if uv available)
✅ Database migrations attempted via `alembic upgrade head` (if database configured)

## Quick Start (2 minutes)

### 1. Configure Database Connection

The `.env` file was created automatically. Edit it to set your database connection:

```bash
# Edit .env and update this line:
DATABASE_URL=postgresql+asyncpg://app:app@localhost:5432/app
```

### 2. Run Database Migrations (if not already done)

If the automated migration failed during generation, run it manually:

```bash
uv run alembic upgrade head
```

### 3. Start Development Server

```bash
uv run fastapi dev {{ project_slug }}/main.py
# Opens http://localhost:{{ port }}
# API docs: http://localhost:{{ port }}/docs
```

Verify the server is running by visiting http://localhost:{{ port }}/health in your browser.

---

## Your Configuration

During generation, you configured the following features:

{% if auth_enabled -%}
### Authentication: ENABLED ({{ auth_provider }})

**Status**: ✅ Enabled in `{{ project_slug }}/main.py`
**Provider**: {{ auth_provider }}

**Configuration in `.env`**:
- `AUTH_PROVIDER_TYPE={{ auth_provider }}`
- Update `AUTH_PROVIDER_URL`, `AUTH_PROVIDER_ISSUER`, `JWT_PUBLIC_KEY` as needed

For provider-specific setup, see [CONFIGURATION-GUIDE.md](CONFIGURATION-GUIDE.md#authentication)
{% else -%}
### Authentication: DISABLED

**Status**: ❌ Disabled (public API mode)

To enable authentication later, regenerate the project with copier or manually:
1. Uncomment AuthMiddleware in `{{ project_slug }}/main.py`
2. Configure `.env` with your auth provider details

**Test endpoints without authentication**:
```bash
curl http://localhost:{{ port }}/health
curl http://localhost:{{ port }}/ping
curl http://localhost:{{ port }}/docs
```
{% endif -%}

---

{% if multi_tenant and auth_enabled -%}
### Multi-Tenant Isolation: ENABLED

**Status**: ✅ Enabled in `{{ project_slug }}/main.py`

**Configuration in `.env`**:
- `ENFORCE_TENANT_ISOLATION=true`

**What this does**:
- Prevents User A from accessing Organization B's data
- Enforces tenant context from JWT claims
- Applies WHERE clauses to all database queries
- Protects documents, users, memberships, and custom data

For details, see [docs/TENANT_ISOLATION.md](docs/TENANT_ISOLATION.md)
{% elif multi_tenant and not auth_enabled -%}
### Multi-Tenant Isolation: DISABLED (requires authentication)

**Status**: ⚠️ Multi-tenant mode requires authentication to be enabled

To enable:
1. Enable authentication (see above)
2. Middleware will automatically enforce tenant isolation
{% else -%}
### Multi-Tenant Isolation: DISABLED

**Status**: ❌ Disabled (single-tenant mode)

**Configuration in `.env`**:
- `ENFORCE_TENANT_ISOLATION=false`

To enable later, regenerate with copier or manually uncomment TenantIsolationMiddleware.
{% endif -%}

---

### Storage Provider: {{ storage_provider }}

**Configuration in `.env`**:
- `STORAGE_PROVIDER={{ storage_provider }}`
{% if storage_provider == 'local' -%}
- `STORAGE_LOCAL_PATH=./uploads`

**Note**: Local storage is suitable for development. For production, consider cloud storage (S3, Azure, GCS).
{% elif storage_provider == 's3' -%}
- `STORAGE_AWS_BUCKET=my-bucket` (update with your bucket name)
- `STORAGE_AWS_REGION=us-east-1` (update with your region)

Configure AWS credentials via `~/.aws/credentials` or IAM role.
{% elif storage_provider == 'azure' -%}
- `STORAGE_AZURE_CONTAINER=documents` (update with your container name)
- `STORAGE_AZURE_CONNECTION_STRING=...` (update with your connection string)

Get connection string from Azure Portal → Storage Account → Access Keys.
{% elif storage_provider == 'gcs' -%}
- `STORAGE_GCS_BUCKET=my-bucket` (update with your bucket name)
- `STORAGE_GCS_PROJECT_ID=my-project` (update with your project ID)
- `GOOGLE_APPLICATION_CREDENTIALS=/path/to/service-account-key.json`

Get service account key from GCP Console → IAM → Service Accounts.
{% endif -%}

For setup guides, see [CONFIGURATION-GUIDE.md](CONFIGURATION-GUIDE.md#storage)

---

### Activity Logging: {{ 'ENABLED' if enable_activity_logging else 'DISABLED' }}

**Configuration in `.env`**:
- `ACTIVITY_LOGGING_ENABLED={{ 'true' if enable_activity_logging else 'false' }}`

{% if enable_activity_logging -%}
All create, read, update, and delete operations are logged with:
- Timestamp
- User ID and email
- Action type (CREATE, READ, UPDATE, DELETE)
- Resource type and ID
- Changes made (for UPDATE)
{% else -%}
To enable, update `.env` and set `ACTIVITY_LOGGING_ENABLED=true`.
{% endif -%}

---

### Metrics (Prometheus): {{ 'ENABLED' if enable_metrics else 'DISABLED' }}

**Configuration in `.env`**:
- `ENABLE_METRICS={{ 'true' if enable_metrics else 'false' }}`

{% if enable_metrics -%}
**Access**: http://localhost:{{ port }}/metrics

Metrics include:
- User operations (users_created_total, users_updated_total)
- Organization operations (organizations_created_total)
- Document uploads (documents_uploaded_total)
- Database query duration
- HTTP request latency
{% else -%}
To enable, update `.env` and set `ENABLE_METRICS=true`.
{% endif -%}

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

## Background Tasks: Implementation Required ⚠️

This template includes **placeholder background tasks** that require implementation before production use.

### Placeholder Functions

The following background tasks are **stubs** and do not perform actual operations:

1. **Email Service** (`{{ project_slug }}/core/background_tasks.py:send_welcome_email_task`)
   - **Current**: Logs "welcome_email_sent" but doesn't send emails
   - **Action Required**: Implement email integration
   - **Guide**: [docs/implementing_email_service.md](docs/implementing_email_service.md)

2. **Log Archival** (`{{ project_slug }}/core/background_tasks.py:archive_old_activity_logs_task`)
   - **Current**: Logs "activity_logs_archived" but doesn't archive anything
   - **Action Required**: Implement archival strategy
   - **Guide**: [docs/implementing_log_archival.md](docs/implementing_log_archival.md)

3. **Report Generation** (`{{ project_slug }}/core/background_tasks.py:generate_activity_report_task`)
   - **Current**: Logs "activity_report_generated" but doesn't generate reports
   - **Action Required**: Implement report generation and delivery
   - **Guide**: [docs/implementing_reports.md](docs/implementing_reports.md)

### HTTP Client Examples

The file `{{ project_slug }}/core/http_client.py` contains **commented example patterns** (lines 61-253):
- These are reference implementations, not production code
- Uncomment and adapt when integrating with external services
- See [docs/service_integration_patterns.md](docs/service_integration_patterns.md) for integration guides

### Before Production Deployment

**Verify all placeholder implementations are replaced or removed:**

```bash
# Search for placeholder markers
grep -r "asyncio.sleep(0.1)" {{ project_slug }}/

# If this returns results, you have unimplemented features
```

---

## What's Next?

Your FastAPI application is ready. Start building! 🚀

1. Create your first endpoint in `{{ project_slug }}/api/`
2. Add your data models in `{{ project_slug }}/models/`
3. Implement business logic in `{{ project_slug }}/services/`
4. Write tests in `{{ project_slug }}/tests/`
5. Deploy with confidence knowing tests pass and code is clean
