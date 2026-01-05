# Claude Code Configuration - Backend Template

Claude Code agents, commands, and documentation for Python FastAPI microservice development.

## What's Included

### Agents (`agents/`)

Specialized agents for Python FastAPI backend development:

- **api-designer.md** - FastAPI endpoint design, REST conventions, OpenAPI
- **backend-implementer.md** - Implements features following service layer patterns
- **security-reviewer.md** - Auth, validation, security vulnerabilities
- **test-writer.md** - Writes comprehensive pytest tests
- **database-migration-reviewer.md** - Alembic migration safety and correctness
- **async-patterns-reviewer.md** - Async/await, concurrency, session handling
- **code-reviewer.md** - Python code quality and FastAPI patterns
- **observability-reviewer.md** - Logging, metrics, tracing

### Commands (`commands/`)

Workflow automation for backend development:

- **follow-pod.md** - Stream Kubernetes pod logs for this service
- **implement.md** - Implement features following backend patterns

### Shared Documentation (`shared/`)

Backend-specific guidelines:

- **edge-cases.md** - Edge cases for FastAPI/SQLAlchemy testing
- **testing-philosophy.md** - pytest and FastAPI testing standards
- **output-formats.md** - Review output formats with backend examples

## How to Use

### Running Reviews

```bash
# Quick review for small changes
/review-quick

# Standard review with selective delegation
/review-standard

# Thorough review for major changes
/review-thorough
```

### Implementing Features

```bash
# Implement a new feature
/implement "Add user profile endpoints with avatar upload"
```

### Debugging Production

```bash
# Follow pod logs
/follow-pod app=backend-api
```

## Tech Stack

This configuration is optimized for:

- **Python 3.11+**
- **FastAPI** - Web framework
- **Pydantic** - Data validation
- **SQLAlchemy 2.0** - ORM with async support
- **Alembic** - Database migrations
- **pytest** - Testing framework
- **Ruff** - Linting
- **MyPy** - Type checking

## Project Structure

```
app/
├── api/v1/endpoints/    # API route handlers
├── models/              # Pydantic schemas
├── services/            # Business logic
├── db/models/           # SQLAlchemy models
└── core/                # Config, security, etc.

tests/
├── unit/                # Service unit tests
├── integration/         # API integration tests
└── conftest.py          # Shared fixtures

alembic/                 # Database migrations
```

## Standards Enforced

### Linting & Type Checking

**Zero violations required:**

```bash
ruff check .   # Must pass
mypy .         # Must pass
pytest         # 100% pass rate
```

### Code Patterns

- **Service layer** for business logic
- **Pydantic models** for validation
- **Async/await** throughout
- **Type annotations** on all functions (including `-> None`)
- **Error messages in variables** (EM101 rule)
- **No magic numbers** (extract to constants)

## Customization

This is a template project. Customize for your needs:

1. **Update paths** - Adjust file structure if different
2. **Add domain knowledge** - Include business-specific patterns
3. **Configure agents** - Adjust agent tools/models in frontmatter
4. **Extend shared docs** - Add project-specific guidelines

## Universal Patterns

For language-agnostic patterns, see:

- `../workspace-oss/agents/` - Universal review agents
- `../workspace-oss/commands/` - Worktree and feature commands
- `../workspace-oss/shared/` - General conventions and patterns

## License

This is free and unencumbered software released into the public domain.

For more information, please refer to <http://unlicense.org/>