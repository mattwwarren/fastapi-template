# Backend Template - Python FastAPI Microservice

Claude Code configuration for Python FastAPI microservice development.

## What's Included

### Agents (`.claude/agents/`)
Backend-specific review and implementation agents:

**Implementation Agents:**
- **api-designer.md** - Design REST API endpoints following best practices
- **backend-implementer.md** - Implement backend features with proper patterns
- **migration-creator.md** - Create Alembic migrations via autogenerate (never hand-written)
- **test-writer.md** - Write comprehensive tests for backend code

**Review Agents:**
- **code-reviewer.md** - Python code quality and patterns
- **security-reviewer.md** - Security vulnerabilities, auth, validation
- **database-migration-reviewer.md** - Database migrations and schema changes
- **async-patterns-reviewer.md** - Async/await patterns, N+1 queries, performance
- **observability-reviewer.md** - Logging, metrics, tracing, monitoring

### Skills (`.claude/skills/`)

- **implement** - Implement a feature from requirements (`/implement`)
- **follow-logs** - Follow service logs via DevSpace (`/follow-logs`)

### Shared Documentation (`.claude/shared/`)

- **testing-philosophy.md** - Backend testing best practices (pytest)
- **edge-cases.md** - Common edge cases to test
- **output-formats.md** - Standard review output formats

## Tech Stack

This template assumes:
- **Language**: Python 3.11+
- **Framework**: FastAPI
- **Database**: PostgreSQL with SQLAlchemy/SQLModel
- **Testing**: pytest, pytest-asyncio
- **Linting**: ruff, mypy
- **Container**: Docker, Kubernetes
- **Cloud**: Generic cloud provider (Azure, AWS, GCP)

## Project Structure

```
fastapi-template/
├── fastapi_template/        # Runnable Python package (main branch)
│   ├── api/                # API endpoints
│   ├── models/             # Database models
│   ├── services/           # Business logic
│   └── main.py             # FastAPI app
├── tests/                   # Test suite
│   ├── unit/               # Unit tests
│   ├── integration/        # Integration tests
│   └── conftest.py         # Shared fixtures
├── scripts/
│   ├── templatize.sh       # Generate template from runnable code
│   └── ...
├── copier.yaml              # Copier configuration
├── _tasks.py                # Post-generation tasks
├── pyproject.toml           # Python dependencies
└── .claude/                 # Claude Code configuration
```

## How to Use

### 1. Copy to Your Backend Project

```bash
cp -r backend-template/.claude /path/to/your/backend/
```

### 2. Customize for Your Project

Edit paths and project-specific details:
- Replace generic paths in commands
- Add your specific database models/services
- Include business domain patterns
- Configure cloud provider specifics (if not generic)

### 3. Use the Agents

```bash
# In Claude Code chat
/implement Add user authentication
/security-review
/review-thorough
```

### 4. Create Project-Specific CLAUDE.md

```bash
# /path/to/your/backend/CLAUDE.md
# Point to universal patterns
See [PYTHON-PATTERNS.md](../PYTHON-PATTERNS.md) for coding standards

# Add project-specific patterns
## Database Schema
- users table: id, email, password_hash
- sessions table: id, user_id, token, expires_at

## Business Domain
- User roles: admin, user, viewer
- Permissions: read, write, delete
```

## Development Workflow

### Runnable-First Architecture

This template uses a **runnable-first** architecture:

- **Main branch** contains runnable Python code (`fastapi_template/`)
- **`copier` branch** contains the Copier template (auto-generated on release)
- Template variables (`{{ project_slug }}`) are generated at release time via GitHub Actions

```bash
# Development happens directly on the template (use --directory flag, no cd needed)
uv --directory /path/to/fastapi-template sync
uv --directory /path/to/fastapi-template run pytest
uv --directory /path/to/fastapi-template run ruff check .
uv --directory /path/to/fastapi-template run mypy .
```

**Key benefits:**
- No Copier generation step for development iteration
- Instant feedback loop: edit, test, repeat
- Git worktrees enable parallel feature development
- Template is always in a working state

### Parallel Development with Git Worktrees

Use git worktrees to develop multiple features simultaneously:

```bash
# Create worktrees for parallel feature development
git worktree add ../fastapi-template-feature-auth feature/auth
git worktree add ../fastapi-template-fix-pagination fix/pagination

# Each worktree is immediately runnable
cd ../fastapi-template-feature-auth
uv sync && uv run pytest  # Works immediately!

# Work on features in parallel (separate Claude Code sessions)
# Terminal 1: cd ../fastapi-template-feature-auth
# Terminal 2: cd ../fastapi-template-fix-pagination
```

**Worktree advantages:**
- Multiple Claude Code sessions can work simultaneously
- Each worktree has its own branch and working directory
- No git conflicts between parallel development efforts
- Clean merge back to main when features complete

### Worktree Management Skills

Use the built-in skills for worktree management:

| Skill | Purpose |
|-------|---------|
| `/worktree-create` | Create worktree for parallel development |
| `/worktree-list` | List worktrees for current repo |
| `/worktree-status` | Check status of all worktrees |
| `/worktree-remove` | Remove a worktree when done |

**Example workflow:**
```bash
# Create feature worktree
/worktree-create feature/new-endpoint

# Check all active worktrees
/worktree-status

# When feature is complete and merged
/worktree-remove feature/new-endpoint
```

### When to Use Copier

**Use Copier for production instances only:**

```bash
# Creating a new production project from the template
copier copy gh:mattwwarren/fastapi-template --vcs-ref copier /path/to/my-new-service

# Updating an existing production instance with template changes
cd /path/to/my-service
copier update
```

**Do NOT use Copier for:**
- Development iteration on the template itself
- Running tests during template development
- Quick prototyping of new features

### Testing Template Generation (Pre-Release)

Before releasing, test that template generation works:

```bash
# Generate templatized version
./scripts/templatize.sh

# Test generation locally
copier copy .templatized/ /tmp/test-project --trust
cd /tmp/test-project
uv run pytest
```

### Agent Guidance

**When working on this template:**

1. **Default approach:** Work directly on the template, run tests directly
2. **Use git worktrees:** For parallel feature development
3. **Use Copier only:** When testing generation or creating production instances

**Agent prompts should note:**

```
This template is directly runnable for development.

For development iteration:
- Run uv run pytest, ruff, mypy directly on the template
- Use git worktrees for parallel feature work

For production instance creation:
- Use copier copy gh:mattwwarren/fastapi-template --vcs-ref copier
- Use copier update to sync existing instances
```

### Why Runnable-First Works

- Template structure matches generated output structure
- No Jinja2 templating in core Python files (only in config files if needed)
- Development velocity: instant edit-test cycles
- Parallel development: multiple features simultaneously via worktrees

## Key Patterns Enforced

### Code Quality
- **Zero linter violations** - `ruff check` must pass
- **Zero type errors** - `mypy` must pass
- **100% test pass rate** - All tests must pass
- **No shortcuts** - Fix root causes, no suppressions

### Database Patterns
- Use async SQLAlchemy session management
- Alembic migrations for schema changes
- Proper transaction boundaries
- Index analysis before recommending new indexes

### API Patterns
- Service layer for business logic
- API layer only handles HTTP concerns
- Proper error handling and status codes
- Request/response validation with Pydantic

### Testing Patterns
- AAA pattern (Arrange-Act-Assert)
- Real database data, not mocks
- Test behavior, not implementation
- Security test coverage (20+ cases for validators)

### Async Patterns
- Parallelize with `asyncio.gather()`
- Avoid N+1 database queries
- Proper async context manager usage
- Session lifecycle management

### DevSpace Abstraction Layer

**All cluster operations go through DevSpace or the devspace-mcp server. Raw kubectl/k3d/docker/helm commands are blocked by `.claude/settings.json` deny rules.**

Full command map: [`.claude/domain/devspace-command-map.md`](.claude/domain/devspace-command-map.md)

| Task | DevSpace Command | MCP Tool |
|------|-----------------|----------|
| Check cluster status | `devspace run status` | `devspace_status` |
| View logs | `devspace logs -f` | `devspace_logs` |
| Health check | `devspace run health` | `devspace_health_check` |
| Enter container | `devspace enter --container api` | `devspace_container_exec` |
| Run migrations | `devspace run alembic-upgrade` | `devspace_alembic_upgrade` |
| Generate migration | `devspace run alembic-revision -- "msg"` | `devspace_alembic_revision` |
| psql shell | `devspace run db-shell` | — |
| Full diagnostics | `devspace run troubleshoot` | — |
| Create cluster | `devspace run cluster-up` | — |
| Tear down cluster | `devspace run k3d-down` | — |
| Restart service | `devspace restart` | `devspace_restart` |
| Rebuild & redeploy | `devspace deploy` | `devspace_redeploy` |

**Standard workflow pattern:** status → changes → health → tests → logs

### ORM-Exclusive Database Policy

All database schema management goes through the ORM. No exceptions without explicit user approval.

- All schema changes **MUST** go through SQLModel/SQLAlchemy model definitions
- Migrations **MUST** be generated via `alembic revision --autogenerate`, never hand-written
- Migration files in `alembic/versions/` are **generated artifacts** — agents must never Edit or Write them (enforced by `.claude/settings.json` deny rules)
- Use the **migration-creator** agent to generate migrations (handles DB availability, model registration, and validation)

**Escalation ladder** when autogenerate can't express a change:
1. Model change → autogenerate
2. Research SQLAlchemy extension packages (`sqlalchemy-utils`, `alembic-utils`, etc.)
3. Ask user for approval before any raw SQL

Raw `op.execute()` SQL is a **last resort** — only after exhausting ORM/extension approaches AND getting explicit user approval.

## Review Process

### Quick Review (<5 files)
```bash
/review-quick
```

### Standard Review (5-20 files)
```bash
# In parent CLAUDE.md or workspace CLAUDE.md
/review-standard
```

### Thorough Review (security, architecture)
```bash
# In parent CLAUDE.md or workspace CLAUDE.md
/review-thorough
```

## Agent Model Selection

- **haiku** - Simple searches, file reads, status checks
- **sonnet** - Default for implementation, reviews
- **opus** - Only when user explicitly requests complex reasoning

Agents inherit model from parent unless specified in frontmatter.

## Integration with Workspace Patterns

This template is designed to work with:
- **PYTHON-PATTERNS.md** - Universal Python coding standards
- **WORKSPACE-PATTERNS.md** - Development workflows and commands
- **CLAUDE.md** - Claude Code-specific configuration

Place all three at workspace level and reference from this template.

## Common Workflows

### Implement New Feature
1. `/implement Add password reset endpoint` (uses api-designer, backend-implementer, test-writer)
2. Review changes with `/review-standard`
3. Run tests: `pytest`
4. Run linters: `ruff check .` and `mypy .`

### Review Pull Request
1. `/review-quick` for small changes
2. `/review-standard` for medium changes
3. `/review-thorough` for security/architecture changes

### Debug Production Issue
1. `devspace run status` - Check pod health
2. `/follow-logs` or `devspace logs -f` - Stream logs
3. `devspace run health` - Verify endpoint
4. Write test to reproduce
5. Fix and verify

## Contributing Back

If you develop new agents or patterns, consider open-sourcing them! These templates benefit from community contributions.

## License

This is free and unencumbered software released into the public domain.

For more information, please refer to <http://unlicense.org/>
