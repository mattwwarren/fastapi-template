"""Pydantic models for Socket.IO event payloads.

These models define the contract between backend emitters (FastAPI, Worker)
and frontend consumers (React, Mobile). They are exposed in the OpenAPI spec
so ``openapi-typescript`` can generate TypeScript types automatically.
"""

from __future__ import annotations

from uuid import UUID

from pydantic import BaseModel

# Event name constants -- used as the first argument to ``sio.emit()``.
TASK_STATUS_CHANGED = "task_status_changed"
TASK_PROGRESS = "task_progress"
TASK_COMPLETED = "task_completed"
TASK_FAILED = "task_failed"


class TaskStatusEvent(BaseModel):
    """Emitted when a task's status changes."""

    task_id: UUID
    task_name: str
    status: str
    total_steps: int | None = None
    completed_steps: int = 0
    status_message: str | None = None
    error_detail: str | None = None
    tenant_id: UUID


class TaskProgressEvent(BaseModel):
    """Emitted on step completion within a running task."""

    task_id: UUID
    completed_steps: int
    total_steps: int | None = None
    status_message: str | None = None


class TaskCompletedEvent(BaseModel):
    """Emitted when a task finishes successfully."""

    task_id: UUID
    task_name: str
    result_url: str | None = None
    tenant_id: UUID


class TaskFailedEvent(BaseModel):
    """Emitted when a task fails permanently."""

    task_id: UUID
    task_name: str
    error_detail: str | None = None
    tenant_id: UUID
