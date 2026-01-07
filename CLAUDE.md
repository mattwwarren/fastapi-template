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

## Template Testing Protocol

**Critical prerequisite:** This is a Copier template, not runnable code. Before running any verification tools (ruff, mypy, pytest), you must generate a project from the template using Copier.

### Generation Required Before Testing

Templates themselves cannot be linted or tested directly. You must instantiate them first:

```bash
# Step 1: Generate project from template
copier copy /path/to/fastapi-template /path/to/generated-project

# Step 2: Only THEN run verification
cd /path/to/generated-project
ruff check .
mypy .
pytest
```

### Agent Guidance

**When working on this template:**

1. **Before modifying template files:** Generate a test instance
2. **After making changes:** Regenerate to verify template renders correctly
3. **Before running tools:** Always verify project was generated first

**Agent prompts should include:**

```
This is a Copier template, not runnable code.

Before running ruff/mypy/pytest:
1. Run: copier copy <template> <output>
2. cd into <output>
3. Then run verification commands on the generated project

Template itself may have {% jinja %} syntax that looks like code but isn't.
Only lint/test the generated output, not the template source.
```

### Why This Matters

- Templates contain Jinja2 templating syntax `{% if %} {{ var }}`, not valid Python
- Verification tools will fail on template syntax
- Generated projects are valid Python and can be linted/tested
- Any changes to template files must work when instantiated

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