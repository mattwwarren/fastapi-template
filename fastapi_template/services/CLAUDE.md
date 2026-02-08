# Services Layer

Business logic as pure async functions. No classes.

## Function Signature Convention

```python
async def get_user(session: AsyncSession, user_id: UUID) -> User | None:
async def create_user(session: AsyncSession, payload: UserCreate) -> User:
async def list_users_for_org(session: AsyncSession, org_id: UUID, params: Params) -> list[User]:
```

Parameter order: `session` first, then IDs, then payload/params. Always explicit return types.

## Transaction Boundary Rule

Services use `flush()`, NEVER `commit()`. The API layer owns the transaction.

```python
# In service:
session.add(user)
await session.flush()
await session.refresh(user)  # Reload DB-generated fields (id, timestamps)
return user

# In API endpoint:
user = await create_user(session, payload)
await session.commit()  # Commit happens here
```

## Query Patterns

```python
from sqlmodel import col, select

# Use col() for column references
statement = select(User).where(col(User.org_id) == org_id)
result = await session.execute(statement)
user = result.scalar_one_or_none()       # Single result
users = result.scalars().all()            # Multiple results
```

## N+1 Prevention (Batch Queries)

```python
async def get_memberships_by_org_ids(
    session: AsyncSession, org_ids: list[UUID]
) -> dict[UUID, list[Membership]]:
    mapping: dict[UUID, list[Membership]] = {id: [] for id in org_ids}
    statement = select(Membership).where(col(Membership.org_id).in_(org_ids))
    for membership in (await session.execute(statement)).scalars().all():
        if membership.org_id in mapping:
            mapping[membership.org_id].append(membership)
    return mapping
```

## Structured Logging

```python
LOGGER = logging.getLogger(__name__)

context = get_logging_context()
LOGGER.info("creating_user", extra={**context, "email": payload.email})
# ... operation ...
LOGGER.info("user_created", extra={**context, "user_id": str(user.id)})
```

Event names use `snake_case` verbs: `creating_x`, `x_created`, `x_not_found`.

## Metrics

```python
start = time.perf_counter()
# ... operation ...
duration = time.perf_counter() - start
database_query_duration_seconds.labels(query_type="select").observe(duration)
users_created_total.labels(environment=settings.environment).inc()
```

Increment counters AFTER successful operations only.

## Security

Include tenant isolation requirements in docstrings. Services must never return data across tenant boundaries without explicit authorization checks.
