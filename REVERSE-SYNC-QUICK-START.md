# Reverse Sync Quick Start Guide

> **Deprecation Notice**: This workflow is **deprecated** with the runnable-first architecture.
> Changes are now made directly to `fastapi_template/` - no reverse sync needed.
> See [INSTANCES.md](INSTANCES.md) for the current deployment workflow.

---

## The Problem You're Solving

You fixed ruff/mypy errors in your test instance and don't want to lose those fixes when you delete the instance.

## The Solution in 3 Steps

### Step 1: Fix Errors in Test Instance

```bash
cd fastapi-template-test-instance

# Make your fixes here
# Test them
uv run ruff check .
uv run mypy .
uv run pytest

# Commit your fixes
git add .
git commit -m "Fix: remove unused imports"
```

### Step 2: Sync Fixes Back to Template

```bash
cd ../fastapi-template

# Run reverse sync (interactive mode)
./scripts/manage-test-instance.sh reverse-sync

# Or sync everything without prompts
./scripts/manage-test-instance.sh reverse-sync --auto
```

The script will:
- ✓ Show each changed file
- ✓ Ask if you want to sync it (interactive mode)
- ✓ Transform instance paths to template paths
- ✓ Apply changes to template
- ✓ Verify changes survive roundtrip (template → instance → template)
- ✓ Run quality checks
- ✓ Show you what to commit

### Step 3: Commit Template Changes

```bash
# Review what changed
git diff

# Commit (use git add -p for selective staging if needed)
git add .
git commit -m "Fix ruff/mypy errors from test instance"

# (Optional) Push to remote
git push
```

## Common Scenarios

### I Fixed Just One File

```bash
cd fastapi-template
./scripts/manage-test-instance.sh reverse-sync
# Say 'y' for the file you fixed
# Say 'n' or 'q' for others
```

### I Fixed Multiple Files

```bash
cd fastapi-template
./scripts/manage-test-instance.sh reverse-sync --auto
git diff
git commit -am "Apply multiple fixes from test instance"
```

### I Want to Review Each File First

```bash
cd fastapi-template
./scripts/manage-test-instance.sh reverse-sync
# Interactive prompts for each file
# Say 'y' or 'n' for each one
# Say 'q' to stop
```

## What It's Doing Behind the Scenes

1. **Finds** changed files in test instance
2. **Maps** instance paths to template paths (`fastapi_template_test/` → `fastapi_template/`)
3. **Creates patches** of the changes
4. **Applies** patches to template files
5. **Verifies roundtrip** - ensures changes survive template transformation
6. **Runs quality checks** - ruff, mypy, pytest
7. **Reports results** and suggests next git commands

## If Something Goes Wrong

### "Template has uncommitted changes"

```bash
git stash  # Or git commit -m "WIP"
# Then retry reverse-sync
```

### "Roundtrip failed"

This means the changes didn't survive the template transformation. Causes:
- Jinja2 variable handling issue
- Path mapping error
- Instance-specific code that shouldn't be in template

**Fix**: Review the error, manually fix the template, re-run

### "Quality checks failed"

This means ruff/mypy/pytest failed after roundtrip. You can:
- Answer 'n' to abort and fix issues
- Answer 'y' to proceed anyway (not recommended)

## Best Practices

1. **Commit changes in test instance** before reverse-sync
2. **Sync frequently** - don't let changes pile up
3. **Review template changes** with `git diff` before committing
4. **Run tests** - always verify after reverse-sync
5. **Keep it simple** - don't sync instance-specific code

## What Gets Synced

✅ **Safe to sync:**
- Unused imports removed
- Type annotations added
- Test improvements
- Bug fixes
- Linting fixes

❌ **Don't sync:**
- Instance configuration
- Service-specific business logic
- New required fields/parameters
- Changes that need template variables

## Next Steps

For more details, see: `docs/TEMPLATE-INSTANCE-SYNC.md` (Part 6: Automated Reverse Sync)

```bash
cd fastapi-template
./scripts/manage-test-instance.sh help  # Show all commands
```

## Still Have Questions?

The full documentation includes:
- Detailed workflows
- Troubleshooting guide
- Best practices
- When NOT to use reverse-sync

See: `docs/TEMPLATE-INSTANCE-SYNC.md`
