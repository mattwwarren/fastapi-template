# FastAPI Template Instances

Track all instances of the fastapi-template for coordinated updates, maintenance, and drift monitoring.

## Instance Registry

| Project | Location | Last Updated | Template Commit | Status | Notes |
|---------|----------|--------------|-----------------|--------|-------|
| test-instance | `~/workspace/meta-work/fastapi-template-test-instance` | 2026-01-07 | HEAD | ✅ Up-to-date | Persistent test instance for template verification |

## Adding New Instance

When you create a new project from this template:

### 1. Generate from Template

```bash
copier copy ~/workspace/meta-work/fastapi-template /path/to/new-project \
  --data "project_name=My Project" \
  --trust
```

### 2. Initialize Git

```bash
cd /path/to/new-project
git init
git add .
git commit -m "Initial generation from fastapi-template"
```

### 3. Install Dependencies

```bash
uv sync
```

### 4. Run Initial Verification

```bash
uv run ruff check .
uv run mypy .
uv run pytest
```

### 5. Update This Registry

Add entry to table above:

```markdown
| my-project | /path/to/my-project | YYYY-MM-DD | <initial-commit> | ✅ Up-to-date | Initial generation |
```

### 6. Document Project

Create `docs/SETUP.md` or similar:
- What this project does
- How to set up locally
- How to run tests
- Deployment instructions

## Drift Checking

Monitor which instances are behind the template:

### Check Single Instance

```bash
./scripts/check-instance-drift.sh /path/to/instance
```

**Output** (up-to-date):
```
✅ Up-to-date
```

**Output** (behind):
```
⚠️  Instance is 5 commits behind template

Recent template changes:
abc123d Fix user email validation
def456e Add international email support
789abcd Security patch: input validation

To update: cd "/path/to/instance" && copier update --trust
```

### Check All Instances

```bash
#!/usr/bin/env bash
# check-all-drifts.sh

INSTANCES=(
  "/path/to/instance1"
  "/path/to/instance2"
)

for instance in "${INSTANCES[@]}"; do
  echo "=== $(basename $instance) ==="
  ./scripts/check-instance-drift.sh "$instance"
  echo ""
done
```

## Updating Instances

### Standard Update (Backward-Compatible Changes)

```bash
cd /path/to/instance

# Check current status
git status  # Should be clean

# Pull template changes
copier update --trust

# Run verification
uv run ruff check .
uv run mypy .
uv run pytest

# Commit the update
git commit -m "Merge template improvements"

# Update registry
# Edit INSTANCES.md with new commit hash and date
```

### Breaking Change Update (Major Version)

For major template updates, follow the migration guide:

```bash
cd /path/to/instance

# Read migration guide
cat /path/to/template/docs/MIGRATION-v*.md

# Manual refactoring or migration script
# (varies by breaking change)

# Update from template
copier update --trust

# Run full test suite
uv run pytest
uv run mypy .
uv run ruff check .

# Manual testing of critical features
# (application-specific)

# Commit
git commit -m "Migrate to template v2.0.0"

# Update registry
```

## Handling Conflicts

If `copier update` detects conflicts:

```bash
cd /path/to/instance
copier update --trust
# Conflict detected!

# Check status
git status

# Resolve conflicts
vim <conflicted-file>
# Edit conflict markers (<<<<<<<, =======, >>>>>>>)

# Mark as resolved
git add <conflicted-file>

# Complete merge
git commit -m "Merge template changes, resolve conflicts"

# Verify
uv run pytest
```

**Tips**:
- Template often has best practices - prefer template version
- Document why instance customization is needed
- Consider upstreaming customizations back to template
- Contact template maintainers if conflicts are complex

## Update Schedule

Recommended update cadence:

| Update Type | Frequency | Urgency | Example |
|-------------|-----------|---------|---------|
| Security patches | Within 1 week | 🔴 Critical | Auth bypass, SQL injection |
| Bug fixes | Within 2 weeks | 🟡 High | Validation bug, logic error |
| Features | Within 1 month | 🟢 Medium | New utility, performance improvement |
| Breaking changes | As needed | 🟠 High | Major dependency upgrade, API redesign |

## Monitoring Health

### Automated Checks

Add to CI/CD pipeline:

```bash
#!/bin/bash
# Check if instance is up-to-date

TEMPLATE_COMMIT=$(git -C /path/to/template rev-parse HEAD)
INSTANCE_COMMIT=$(grep "_commit:" /path/to/instance/.copier-answers.yml | awk '{print $2}')

if [[ "$TEMPLATE_COMMIT" != "$INSTANCE_COMMIT" ]]; then
  echo "WARNING: Instance is behind template"
  COMMITS_BEHIND=$(git -C /path/to/template rev-list --count "$INSTANCE_COMMIT".."$TEMPLATE_COMMIT")
  echo "Commits behind: $COMMITS_BEHIND"
  exit 1
fi
```

### Manual Quarterly Review

Once per quarter:
1. Check all instances: `./check-all-drifts.sh`
2. Plan updates for instances > 1 month behind
3. Schedule coordinated updates for breaking changes
4. Update this registry with latest status

## Template Versions

Track major template versions and instance compatibility:

| Instance | v1.0 | v1.1 | v1.2 | v2.0 | Notes |
|----------|------|------|------|------|-------|
| test-instance | ✅ | ✅ | ✅ | ✅ | Always on HEAD |
| my-project | ✅ | ✅ | ❌ | - | v1.2, planning v2.0 migration |

## Contributing Back

If you discover a bug or pattern in your instance that would help others:

1. **Verify it's general** - Not specific to your business domain
2. **Extract to template** - Generalize and use Jinja2 if needed
3. **Test in test-instance** - Verify with `verify` command
4. **Submit to template** - Create PR or contact maintainers
5. **Share learning** - Document the pattern

Example: If you improve email validation, consider extracting it:

```bash
# Your instance version
def validate_email(email: str) -> bool:
    """Handle international domains and plus-addressing."""
    # ... your implementation

# Extract to template
# {{ project_slug }}/models/validators.py
# With Jinja2 customization if needed
```

## Resources

- **Setup Guide**: See template [README.md](README.md)
- **Sync Strategy**: See [docs/TEMPLATE-INSTANCE-SYNC.md](docs/TEMPLATE-INSTANCE-SYNC.md)
- **Testing**: See [.claude/TEMPLATE-TESTING.md](.claude/TEMPLATE-TESTING.md)
- **Workflow**: See [CLAUDE.md](CLAUDE.md) - Test Instance Workflow section
