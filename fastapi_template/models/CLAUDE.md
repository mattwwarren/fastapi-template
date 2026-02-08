# Models Layer

SQLModel database models and Pydantic schemas.

## Inheritance Chain

Every database model follows this pattern:

```python
class UserBase(SQLModel):
    """Shared fields between create/read/update."""
    email: str = Field(max_length=255)

class User(TimestampedTable, UserBase, table=True):
    """Database table. TimestampedTable provides id, created_at, updated_at."""
    __tablename__ = "app_user"
```

- `TimestampedTable` (from `base.py`) provides `id: UUID`, `created_at`, `updated_at` - all DB-managed
- Domain base class (`UserBase`) contains business fields
- `table=True` marks it as a database table

## CRUD Schema Pattern

```
ModelBase        - Shared fields
  Model          - Database table (TimestampedTable + ModelBase, table=True)
  ModelCreate    - Creation schema with validators
  ModelRead      - Response schema (adds relationship fields via Field(default_factory=list))
  ModelUpdate    - Partial update (all fields Optional)
```

## UUID Primary Keys

Always use PostgreSQL-native UUIDs with server-side generation:

```python
from sqlalchemy.dialects.postgresql import UUID as PGUUID
id: UUID = Field(sa_column=Column(PGUUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")))
```

## Timestamps

DB-managed, never set in Python:

```python
created_at: datetime = Field(sa_column_kwargs={"server_default": sa.func.now()})
updated_at: datetime = Field(sa_column_kwargs={"server_default": sa.func.now(), "onupdate": sa.func.now()})
```

## Field Validators

```python
MAX_NAME_LENGTH = 100  # Constants at module level

@field_validator("name")
@classmethod
def validate_name(cls, value: str, _info: ValidationInfo) -> str:
    value = value.strip()
    if not value:
        msg = "Name cannot be empty"
        raise ValueError(msg)
    if len(value) > MAX_NAME_LENGTH:
        msg = f"Name must be {MAX_NAME_LENGTH} characters or less"
        raise ValueError(msg)
    return value
```

Rules:
- Always `@field_validator` + `@classmethod` (never `@validator`)
- Always include `ValidationInfo` parameter (prefix with `_` if unused)
- Extract max length to module-level constant
- Strip whitespace first, then validate empty, then check length
- Error messages in variables (EM101 compliance)

## ConfigDict

```python
model_config: ClassVar[ConfigDict] = ConfigDict(from_attributes=True)
```

## Table Constraints

```python
__table_args__ = (
    UniqueConstraint("email", name="uq_app_user_email"),
)
```

Always provide explicit constraint names for migration clarity.

## Shared Schemas

Cross-resource relationship schemas live in `shared.py` (e.g., `UserInfo`, `OrganizationInfo`) to avoid circular imports.
