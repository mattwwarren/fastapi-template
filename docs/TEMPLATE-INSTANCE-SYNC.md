# Template-Instance Sync Strategy

Comprehensive guide for bidirectional learning between the fastapi-template and its instances.

## Overview

This template uses **Copier's git-based update mechanism** to enable bidirectional learning:

- **Template → Instances** (automated): `copier update` pulls template improvements into existing instances
- **Instances → Template** (manual): Extract successful patterns from instances back into template

This document describes both workflows and best practices for managing multiple instances.

---

## Part 1: Copier Update Mechanism

### How Copier Update Works

Copier's `update` command performs a **three-way git merge**:

1. **Base** = Previous template version that generated this instance (stored in `.copier-answers.yml`)
2. **Theirs** = Current template version (HEAD)
3. **Ours** = Current instance version (what you've customized)

Copier merges these three versions intelligently:
- Applies template changes (Theirs)
- Preserves instance customizations (Ours)
- Detects conflicts where both sides changed the same code

### Example: Merging a Bug Fix

**Scenario**: The template has a bug in the user validation that you discovered and fixed in your production instance. The template maintainers then fix the same bug.

**Before**: Instance is customized, template is outdated
```
Base (old template):
  def validate_email(email):
    if not "@" in email:  # BUG: incorrect validation
      return False
    return True

Instance (your fix):
  def validate_email(email):
    if "@" not in email:  # You fixed this
      return False
    if email.count("@") != 1:  # You added this check too
      return False
    return True

Template (maintainer's fix):
  def validate_email(email):
    if "@" not in email:  # Fixed syntax
      return False
    return True
```

**After copier update**:
```
def validate_email(email):
  if "@" not in email:  # Template's fix applied
    return False
  if email.count("@") != 1:  # Your customization preserved!
    return False
  return True
```

Both the template's fix and your customization are preserved!

### `.copier-answers.yml` Tracking

Copier stores metadata about the instance:

```yaml
_src_path: ~/workspace/meta-work/fastapi-template
_commit: abc123def456  # Last template commit that was applied
project_name: FastAPI Template Test
project_slug: fastapi_template_test
description: Test instance for template verification
port: 8100
```

When you run `copier update`:
1. Copier reads `_commit: abc123def456`
2. Calculates diff: `template@abc123def456..template@HEAD`
3. Applies only the changes, not the full template
4. Updates `_commit` to current HEAD

---

## Part 2: Template → Instance Updates

### Workflow: Applying Template Changes

#### Step 1: Verify Template Changes Work

Always test in the persistent test instance first:

```bash
# Modify template source
cd ~/workspace/meta-work/fastapi-template
vim "{{ project_slug }}/services/user_service.py"

# Commit template change
git commit -m "Fix user email validation"

# Pull changes into test instance
/test-instance sync

# Verify everything still works
/test-instance verify
```

#### Step 2: Update Production Instances

Once verified in test instance, apply to production instances:

```bash
# For each production instance
cd /path/to/production-api
copier update --trust

# Test in production context
pytest
uv run mypy .
uv run ruff check .

# Commit the merge
git commit -m "Merge template improvements"
```

#### Step 3: Track Updates

Update `INSTANCES.md` registry:

```markdown
| Project | Location | Last Updated | Template Commit | Status |
|---------|----------|--------------|-----------------|--------|
| users-api | /projects/users-api | 2026-01-07 | abc123d | ✅ Up-to-date |
```

### Conflict Resolution

If `copier update` encounters conflicts:

```bash
cd /path/to/instance
copier update --trust
# Conflicts detected!

# Check status
git status
# Shows conflicted files with merge conflict markers

# Edit conflicted files
vim app/services/user_service.py
# Resolve <<<<<<<, =======, >>>>>>> markers

# Mark as resolved
git add app/services/user_service.py

# Complete merge
git commit -m "Merge template changes, resolve conflicts"

# Verify
pytest
```

### Type of Template Changes

**Safe to apply automatically:**
- ✅ Bug fixes (validation, logic errors)
- ✅ Security patches (authentication, validation)
- ✅ Performance improvements (indexing, queries)
- ✅ New utility functions (no breaking changes)
- ✅ Dependency upgrades with compatibility

**Require careful review:**
- ⚠️ API changes (breaking endpoint changes)
- ⚠️ Database schema changes (migrations)
- ⚠️ Major dependency upgrades
- ⚠️ Configuration changes
- ⚠️ New required parameters

**Should not apply automatically:**
- ❌ Business logic specific to template
- ❌ Refactoring that changes patterns significantly
- ❌ Removing features

### Breaking Change Handling

When a template change is breaking:

1. **Document migration path** in template CHANGELOG
2. **Test extensively** in test instance
3. **Release as version tag**: `git tag v2.0.0-breaking`
4. **Contact instance owners** with migration instructions
5. **Provide migration script** if possible

Example: SQLModel v1.0 upgrade requiring async session refactoring

```bash
# In template CHANGELOG.md
## v2.0.0 - Breaking Changes

### SQLModel 1.0.0 Upgrade

Requires session management refactoring:

```python
# OLD (v1.x)
session = SessionLocal()
user = session.exec(select(User)).first()

# NEW (v2.0+)
async with SessionLocal() as session:
    user = await session.exec(select(User)).first()
```

See `docs/MIGRATION-v1-to-v2.md` for detailed steps.
```

Then update instances:

```bash
cd /path/to/instance

# Read migration guide
cat /path/to/template/docs/MIGRATION-v1-to-v2.md

# Apply migration (manual refactoring or provided script)
./scripts/migrate-to-v2.0.sh

# Test thoroughly
pytest
uv run mypy .

# Update
copier update --trust

# Verify
pytest
```

---

## Part 3: Instance → Template Learning

### Identifying Patterns Worth Extracting

**Criteria for extraction into template:**

✅ **Extract if:**
- Pattern is repeated across multiple instances
- Solves a common problem (validation, permission checks, error handling)
- Improves security or performance
- Is a general best practice
- Works with template's architecture

❌ **Don't extract if:**
- Business logic specific to one domain
- Highly customized for specific use case
- Would add unnecessary complexity to template
- Breaking change for existing instances

### Example: Extracting a Validation Pattern

**Discovery**: Across 3 instances, you see identical email validation with UTF-8 support:

```python
# Instance 1 (users-api)
def validate_email(email: str) -> bool:
    if not email or "@" not in email:
        return False
    local, domain = email.rsplit("@", 1)
    if len(local) > 64 or len(domain) > 255:
        return False
    # UTF-8 support for international emails
    try:
        email.encode("ascii").decode("ascii")  # Check ASCII-compatible
    except (UnicodeEncodeError, UnicodeDecodeError):
        try:
            email.encode("utf-8").decode("utf-8")  # Check UTF-8
        except:
            return False
    return True
```

**Extraction Process**:

1. **Generalize** - Add to template as utility validator
2. **Jinja-templatize** - If it needs customization
3. **Test** - Verify with test instance
4. **Document** - Explain when to use
5. **Propagate** - Add to other instances

**Result** in template:

```python
# {{ project_slug }}/models/validators.py

from typing import Annotated

from pydantic import PlainValidator


def validate_email_with_international_support(email: str) -> str:
    """Validate email with UTF-8 support for international addresses.

    Args:
        email: Email address to validate

    Returns:
        Validated email

    Raises:
        ValueError: If email is invalid
    """
    if not email or "@" not in email:
        raise ValueError("Email must contain @")

    local, domain = email.rsplit("@", 1)
    if len(local) > 64 or len(domain) > 255:
        raise ValueError("Email parts exceed maximum length")

    # Support both ASCII and UTF-8
    try:
        email.encode("ascii").decode("ascii")
    except (UnicodeEncodeError, UnicodeDecodeError):
        try:
            email.encode("utf-8").decode("utf-8")
        except:
            raise ValueError("Email contains invalid characters")

    return email


Email = Annotated[str, PlainValidator(validate_email_with_international_support)]
```

Then use in models:

```python
# {{ project_slug }}/models/user.py

from pydantic import BaseModel
from .validators import Email


class UserCreate(BaseModel):
    email: Email
    password: str
```

**Test in test instance**:

```bash
/test-instance sync
/test-instance verify

# Manually test
cd fastapi-template-test-instance
python
>>> from fastapi_template_test.models.validators import validate_email_with_international_support
>>> validate_email_with_international_support("user@example.com")
'user@example.com'
>>> validate_email_with_international_support("user+tag@example.com")
'user+tag@example.com'
>>> validate_email_with_international_support("користувач@приклад.укр")
'користувач@приклад.укр'
```

**Propagate to other instances**:

```bash
# After merging into template
for instance in /projects/users-api /projects/orders-api; do
    cd "$instance"
    copier update --trust
    pytest
done
```

### Using Jinja2 for Customizable Patterns

Some patterns need customization per instance. Use Copier's Jinja2 templating:

**Template**:

```python
# {{ project_slug }}/models/validators.py

{% if auth_provider_type == "ory" %}
def validate_ory_user_id(user_id: str) -> str:
    """Validate Ory user ID format."""
    if not user_id.startswith("identity/"):
        raise ValueError("Ory user ID must start with 'identity/'")
    return user_id
{% elif auth_provider_type == "cognito" %}
def validate_cognito_user_id(user_id: str) -> str:
    """Validate AWS Cognito user ID format."""
    # Different validation for Cognito
    return user_id
{% endif %}
```

Instance-specific code is generated based on answers.

---

## Part 4: Multi-Instance Management

### Instance Registry

Track all instances for coordinated updates and maintenance.

**File**: `INSTANCES.md`

```markdown
# FastAPI Template Instances

| Project | Location | Team | Last Updated | Template Version | Status |
|---------|----------|------|--------------|------------------|--------|
| test-instance | /workspace/meta-work/ | Template Maintainers | 2026-01-07 | HEAD | ✅ Up-to-date |
| users-api | /projects/users-api | Platform Team | 2026-01-06 | abc123d | ✅ Up-to-date |
| orders-api | /projects/orders-api | Commerce Team | 2025-12-20 | e4f5a6b | ⚠️ 18 commits behind |
| payments-api | /projects/payments-api | Finance Team | 2025-11-01 | old_hash | 🔴 Major version behind |
```

### Drift Checking

Monitor which instances need updates:

**Script**: `scripts/check-instance-drift.sh`

```bash
#!/usr/bin/env bash
set -euo pipefail

INSTANCE_DIR="${1:?Usage: $0 <instance-path>}"
TEMPLATE_DIR="$(dirname "$0")/.."

TEMPLATE_COMMIT=$(git -C "$TEMPLATE_DIR" rev-parse HEAD)
INSTANCE_COMMIT=$(grep "_commit:" "$INSTANCE_DIR/.copier-answers.yml" | awk '{print $2}')

if [[ "$TEMPLATE_COMMIT" == "$INSTANCE_COMMIT" ]]; then
  echo "✅ Up-to-date"
  exit 0
fi

COMMITS_BEHIND=$(git -C "$TEMPLATE_DIR" rev-list --count "$INSTANCE_COMMIT".."$TEMPLATE_COMMIT")
echo "⚠️  Instance is $COMMITS_BEHIND commits behind template"
echo ""
echo "Recent template changes:"
git -C "$TEMPLATE_DIR" log --oneline --no-decorate "$INSTANCE_COMMIT".."$TEMPLATE_COMMIT"
echo ""
echo "To update: cd \"$INSTANCE_DIR\" && copier update --trust"
```

**Check all instances**:

```bash
#!/usr/bin/env bash
# check-all-drifts.sh

INSTANCES=(
  "/path/to/users-api"
  "/path/to/orders-api"
  "/path/to/payments-api"
)

for instance in "${INSTANCES[@]}"; do
  echo "Checking $instance"
  ./scripts/check-instance-drift.sh "$instance"
  echo ""
done
```

### Coordinated Update Strategy

For breaking changes affecting multiple instances:

1. **Announce** - Notify all instance owners
2. **Test** - Verify in test instance thoroughly
3. **Document** - Provide migration guide
4. **Schedule** - Coordinate update timeline
5. **Execute** - Update instances sequentially
6. **Verify** - Run full test suite in each
7. **Document** - Update INSTANCES.md

**Example**: Async migration affecting all instances

```bash
# Announce in #engineering
# "Template v2.0.0 upgrade available - requires async refactoring"

# Create migration docs
./docs/MIGRATION-v1-to-v2.md
git tag v2.0.0-breaking

# Notify instance teams
# "Your team should update within 2 weeks"
# "See docs/MIGRATION-v1-to-v2.md for steps"

# Update test instance first
/test-instance sync
/test-instance verify

# Stagger updates across teams
# Week 1: users-api, orders-api (non-critical path)
# Week 2: payments-api (careful, business-critical)

# For each instance:
cd /path/to/instance
copier update --trust
pytest
# Manual testing
git push
```

---

## Part 5: Best Practices

### Template Development

1. **Always test before committing**
   ```bash
   /test-instance sync
   /test-instance verify
   git commit  # Only if verify passes
   ```

2. **Provide migration guides for breaking changes**
   - Document what changed
   - Show before/after code
   - Provide automated migration script if possible
   - Test migration in instances

3. **Keep template DRY**
   - Extract repeated patterns from instances
   - Generalize with Jinja2 when needed
   - Add documentation and examples

4. **Version strategically**
   - Minor versions: backward-compatible improvements
   - Major versions: breaking changes
   - Tag releases: `git tag v1.2.3`
   - Update INSTANCES.md after releases

### Instance Management

1. **Keep instances reasonably close to template**
   - Update at least monthly
   - Don't defer breaking changes indefinitely
   - Set update policy for your team

2. **Minimize instance customization**
   - Extract customizations back to template when generic
   - Use instance-specific config, not hardcoded values
   - Document why customization is needed

3. **Test after updates**
   - Run full test suite
   - Manual smoke test of critical features
   - Check for deprecation warnings

4. **Track instance configuration**
   - `.copier-answers.yml` version-controlled
   - Document non-template customizations
   - Include in onboarding docs

### Conflict Resolution

1. **Prefer template changes when possible**
   - Template version often has best practices
   - Instance customization is usually less general

2. **Communicate with template maintainers**
   - If instance improvement is general, suggest upstreaming
   - If template change doesn't work, report issue
   - Share learnings to improve template

3. **Keep conflict markers until resolved**
   - Don't blindly accept one side
   - Merge intelligently (both changes often better)
   - Test thoroughly after resolving

---

## Part 6: Troubleshooting

### "Copier Update Fails"

**Problem**: `copier update` errors

**Solution**:
1. Check `.copier-answers.yml` exists
2. Verify `_commit` hash exists in template repo
3. Check for uncommitted changes: `git status`
4. Try: `copier update --trust --overwrite`

### "Merge Conflicts Too Complex"

**Problem**: Too many conflicts, hard to resolve

**Solution**:
1. Start over: `git merge --abort`
2. Consult template maintainers
3. Consider manual update:
   ```bash
   git checkout ours  # Keep current version
   git add .
   git commit -m "Keeping current version, will manually merge"
   ```

### "Instance Gets Out of Sync"

**Problem**: Instance is months behind template

**Solution**:
1. Check drift: `./scripts/check-instance-drift.sh`
2. Review what changed: `git -C /template log --oneline <commit>..<commit>`
3. Update incrementally if breaking changes
4. Or recreate from template if simpler

### "Template Change Breaks Instance"

**Problem**: After update, instance fails tests

**Solution**:
1. Don't panic - this is why we test!
2. Identify what broke: `pytest -vv`
3. Either:
   - Fix template bug and sync again
   - Resolve conflict manually and commit
4. Report issue to template maintainers
5. Update INSTANCES.md with status

---

## Summary

The template-instance sync strategy enables:

- **Efficient scaling** - Template improvements propagate automatically
- **Bidirectional learning** - Instances teach template, template improves instances
- **Conflict-free updates** - Git merge handles most conflicts intelligently
- **Version control** - Track exactly which template version generated each instance
- **Team coordination** - Registry and drift checker help manage multiple instances

**Key takeaway**: Think of template and instances as **two parts of the same ecosystem**, not separate concerns.
