"""Activity logging decorator for centralizing audit trail recording."""

from collections.abc import Callable
from functools import wraps
from typing import Any
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from {{ project_slug }}.core.config import settings
from {{ project_slug }}.models.activity_log import ActivityAction, ActivityLog


async def log_activity(
    session: AsyncSession,
    action: ActivityAction,
    resource_type: str,
    resource_id: UUID | None = None,
    details: dict[str, Any] | None = None,
) -> None:
    """Log an activity to the audit trail.

    This is a best-effort function that will not raise exceptions if logging
    fails. Logging failures are silently ignored to avoid disrupting the
    primary request flow.

    Args:
        session: AsyncSession for database operations
        action: ActivityAction enum for the audit log
        resource_type: String identifier for resource type (e.g., "user", "organization")
        resource_id: UUID of the resource being acted upon (optional)
        details: Additional context to store as JSON (optional)
    """
    if not settings.activity_logging_enabled:
        return

    try:
        activity = ActivityLog(
            action=action,
            resource_type=resource_type,
            resource_id=resource_id,
            details=details or {},
        )
        session.add(activity)
        # Note: Don't commit here - let caller manage transaction
    except Exception:
        # Best-effort logging: never raise exceptions
        pass


def log_activity_decorator(
    action: ActivityAction, resource_type: str
) -> Callable[[Callable[..., Any]], Callable[..., Any]]:
    """Decorator to automatically log API endpoint activity.

    Wraps an endpoint to record activity after successful execution.
    Handles response model inspection to extract resource IDs automatically.

    IMPORTANT: The decorator logs activity AFTER endpoint execution but BEFORE
    response serialization. Callers are responsible for ensuring session.commit()
    is called within the endpoint to persist the activity log alongside the
    primary operation.

    Args:
        action: ActivityAction enum for the audit log
        resource_type: String identifier for resource type (e.g., "user", "organization")

    Returns:
        Decorator function for API endpoints

    Example:
        @router.post("", response_model=UserRead, status_code=201)
        @log_activity_decorator(ActivityAction.CREATE, "user")
        async def create_user_endpoint(
            payload: UserCreate,
            session: SessionDep,
        ) -> UserRead:
            user = await create_user(session, payload)
            # Activity log is recorded with the transaction
            response = UserRead.model_validate(user)
            return response
    """

    def decorator(func: Callable[..., Any]) -> Callable[..., Any]:
        """Inner decorator that wraps the endpoint function.

        Args:
            func: The endpoint function to wrap

        Returns:
            Wrapped function with activity logging
        """

        @wraps(func)
        async def wrapper(*args: Any, **kwargs: Any) -> Any:
            """Execute endpoint and log activity on success.

            Args:
                *args: Positional arguments passed to endpoint
                **kwargs: Keyword arguments passed to endpoint

            Returns:
                Result from wrapped endpoint function
            """
            # Extract session dependency from kwargs
            session = kwargs.get("session")

            # Execute endpoint function
            result = await func(*args, **kwargs)

            # Extract resource_id if present in result
            resource_id: UUID | None = None
            if result is not None:
                if hasattr(result, "id"):
                    resource_id = result.id
                elif isinstance(result, dict) and "id" in result:
                    resource_id = result["id"]

            # Log activity (best-effort, doesn't fail request)
            if session is not None:
                try:
                    await log_activity(
                        session=session,
                        action=action,
                        resource_type=resource_type,
                        resource_id=resource_id,
                    )
                except Exception:
                    # Best-effort: log failures don't affect response
                    pass

            return result

        return wrapper

    return decorator
