# Backend Template - Python FastAPI Microservice

Claude Code configuration for Python FastAPI microservice development.

## What's Included

### Agents (`.claude/agents/`)
Backend-specific review and implementation agents:

**Implementation Agents:**
- **api-designer.md** - Design REST API endpoints following best practices
- **backend-implementer.md** - Implement backend features with proper patterns
- **test-writer.md** - Write comprehensive tests for backend code

**Review Agents:**
- **code-reviewer.md** - Python code quality and patterns
- **security-reviewer.md** - Security vulnerabilities, auth, validation
- **database-migration-reviewer.md** - Database migrations and schema changes
- **async-patterns-reviewer.md** - Async/await patterns, N+1 queries, performance
- **observability-reviewer.md** - Logging, metrics, tracing, monitoring

### Commands (`.claude/commands/`)

- **implement.md** - Implement a feature from requirements
- **follow-pod.md** - Follow Kubernetes pod logs for debugging

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

## Project Structure Expected

```
project/
├── app/                    # Application code
│   ├── api/               # API endpoints
│   ├── models/            # Database models
│   ├── services/          # Business logic
│   └── main.py            # FastAPI app
├── tests/                 # Test suite
│   ├── unit/             # Unit tests
│   ├── integration/      # Integration tests
│   └── conftest.py       # Shared fixtures
├── alembic/              # Database migrations
├── pyproject.toml        # Python dependencies
└── .claude/              # This directory
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

This template is designed to be **directly runnable** without Copier generation:

```bash
# Development happens directly on the template
cd /path/to/fastapi-template
uv sync
uv run pytest          # Tests run immediately
uv run ruff check .    # Linting works directly
uv run mypy .          # Type checking works directly
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
copier copy /path/to/fastapi-template /path/to/my-new-service

# Updating an existing production instance with template changes
cd /path/to/my-service
copier update
```

**Do NOT use Copier for:**
- Development iteration on the template itself
- Running tests during template development
- Quick prototyping of new features

## Template Testing Protocol

**Updated approach:** This template is now directly runnable. Development and testing happen without Copier generation.

### Direct Development (Recommended)

```bash
# Development happens directly on the template
uv sync
uv run pytest          # Run tests directly
uv run ruff check .    # Lint directly
uv run mypy .          # Type check directly
```

### Copier Generation (Production Instances Only)

When creating production instances or testing Copier-specific features:

```bash
# Step 1: Generate project from template
copier copy /path/to/fastapi-template /path/to/generated-project

# Step 2: Verify generated instance
cd /path/to/generated-project
ruff check .
mypy .
pytest
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
- Use copier copy to generate new projects
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

## Test Instance Workflow

**Persistent test instance**: `$HOME/workspace/meta-work/fastapi-template-test-instance/`

### Quick Commands

```bash
# Via skill (recommended)
/test-instance generate   # Create fresh instance
/test-instance verify     # Check quality (ruff, mypy, pytest)
/test-instance sync       # Update from template changes

# Via script (direct)
./scripts/manage-test-instance.sh generate
./scripts/manage-test-instance.sh verify
```

### Workflow: Making Template Changes

1. Modify template source files
2. Run `/test-instance sync` to pull changes into test instance
3. Run `/test-instance verify` to check generated code
4. If passes: commit template changes
5. If fails: fix template, repeat

### Auto-Approved Commands

Claude Code auto-runs these in test instance without approval:
- `git status/diff/log/checkout` (read-only + branch switching)
- `uv run ruff check`
- `uv run mypy`
- `uv run pytest`
- `copier update`

### Why Git in Test Instance?

Copier's `update` mechanism uses git three-way merge to:
- Track which template version generated the instance
- Merge template changes with instance customizations
- Detect conflicts and preserve both sets of changes
- Enable true bidirectional learning between template and instances

See `docs/TEMPLATE-INSTANCE-SYNC.md` for comprehensive sync strategy.

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
1. `/follow-pod api-server-xyz` - Follow logs
2. Check observability (metrics, traces)
3. Write test to reproduce
4. Fix and verify

## Contributing Back

If you develop new agents or patterns, consider open-sourcing them! These templates benefit from community contributions.

## License

This is free and unencumbered software released into the public domain.

For more information, please refer to <http://unlicense.org/>
