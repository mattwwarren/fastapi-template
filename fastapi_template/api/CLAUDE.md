# API Layer

HTTP endpoints. Handles routing, serialization, auth, and transaction commits. No business logic here.

## Router Registration

```python
# In domain router file:
router = APIRouter(prefix="/users", tags=["users"])

# In routes.py:
router.include_router(users.router)
```

## Dependency Injection

Standard dependencies available in endpoint signatures:

```python
@router.get("/", response_model=Page[UserRead])
async def list_users(
    session: SessionDep,                    # AsyncSession
    current_user: CurrentUserFromHeaders,   # Required auth
    tenant: TenantDep,                      # Tenant context
    params: ParamsDep,                      # Pagination params
) -> Page[UserRead]:
```

- `SessionDep` - async database session (from `db/session.py`)
- `CurrentUserFromHeaders` - required auth, reads Oathkeeper headers
- `TenantDep` - tenant/organization context
- `ParamsDep` - pagination parameters

## Transaction Commits

Endpoints own the transaction. Services only `flush()`.

```python
user = await create_user(session, payload)
await session.commit()
return user
```

## Response Models and Status Codes

Always specify both:

```python
@router.post("/", response_model=UserRead, status_code=status.HTTP_201_CREATED)
@router.delete("/{user_id}", status_code=status.HTTP_204_NO_CONTENT)
```

## Error Handling

IntegrityError for unique constraint violations:

```python
try:
    await session.commit()
except IntegrityError as e:
    error_str = str(e).lower()
    if "uq_app_user_email" in error_str or "unique" in error_str:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Email already exists",
        ) from None
    raise
```

## Activity Logging

```python
@router.post("/", ...)
@log_activity_decorator(ActivityAction.CREATE, "user")
async def create_user(...):
```

For delete endpoints, specify the ID parameter:
```python
@log_activity_decorator(ActivityAction.DELETE, "user", resource_id_param_name="user_id")
```

## Pagination

```python
page = await apaginate(session, select(User).order_by(col(User.created_at).desc()), params)
return create_page(page.items, total=page.total, params=params)
```

## Relationship Expansion

Query relationships separately after main operation to avoid eager loading complexity:

```python
user = await get_user(session, user_id)
user_orgs = await get_orgs_for_user(session, user.id)
response = UserRead.model_validate(user)
response.organizations = user_orgs
```

For lists, use batch query functions (see services/CLAUDE.md) to prevent N+1.

## Background Tasks

Fire-and-forget for non-blocking operations:

```python
asyncio.create_task(send_notification(user.id))  # noqa: RUF006
```
