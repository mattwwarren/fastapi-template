---
name: test-instance
description: Manage FastAPI template test instance (generate, verify, sync, clean, shell)
---

# Test Instance Management Skill

Manages the persistent test instance for FastAPI template verification and development.

## Commands

- `/test-instance generate` - Create fresh test instance from template
- `/test-instance verify` - Run quality checks (ruff, mypy, pytest)
- `/test-instance sync` - Update test instance from template changes
- `/test-instance clean` - Remove test instance
- `/test-instance shell` - Open interactive debugging shell

## Workflow

### Setting up for the first time:
```bash
/test-instance generate
```

### After making template changes:
```bash
/test-instance sync        # Pull changes from template
/test-instance verify      # Run quality checks
```

### Debugging in test instance:
```bash
/test-instance shell       # Interactive bash in test instance
```

## Test Instance Location

`$HOME/workspace/meta-work/fastapi-template-test-instance/`

## Key Features

- **Persistent**: Instance persists between sessions
- **Git-tracked**: Copier's `update` command uses git three-way merge
- **Auto-approved**: Verification commands run without approval
- **Bidirectional sync**: Learn from both template changes and instance usage

## Implementation

```bash
#!/usr/bin/env bash
set -euo pipefail

SCRIPT="$HOME/workspace/meta-work/fastapi-template/scripts/manage-test-instance.sh"
COMMAND="${1:-help}"

exec "$SCRIPT" "$COMMAND"
```
