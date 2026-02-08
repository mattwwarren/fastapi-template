# Database Layer

Session management and engine configuration.

## PEP 563 Warning

**NEVER use `from __future__ import annotations` in `session.py`.** It defines `SessionDep = Annotated[AsyncSession, Depends(get_session)]` which FastAPI evaluates at runtime.

## Session Dependency

```python
SessionDep = Annotated[AsyncSession, Depends(get_session)]
```

The `get_session` generator yields a session, rolls back on exception:

```python
async def get_session() -> AsyncGenerator[AsyncSession]:
    async with async_session_maker() as session:
        try:
            yield session
        except Exception:
            await session.rollback()
            raise
```

## Key Configuration

- `expire_on_commit=False` - prevents lazy-load errors after commit in async context
- Pool config via `PoolConfig(BaseModel, frozen=True)` with validation
- `pool_pre_ping=True` for connection health checks

## Engine Creation

```python
engine = create_async_engine(
    database_url,
    pool_size=pool_config.size,
    max_overflow=pool_config.max_overflow,
    pool_timeout=pool_config.timeout,
    pool_recycle=pool_config.recycle,
    pool_pre_ping=pool_config.pre_ping,
)
```

## Test Compatibility

Global `engine` and `async_session_maker` exist for test fixtures to swap in test databases. Test `conftest.py` replaces these with worker-specific instances.
