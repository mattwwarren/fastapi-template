"""Tests for background task utilities.

Tests cover the fire-and-forget background task patterns used for
asynchronous operations that should not block API responses.
"""

from unittest.mock import AsyncMock, patch
from uuid import uuid4

import pytest

from fastapi_template.core.background_tasks import (
    archive_old_activity_logs_task,
    generate_activity_report_task,
    send_welcome_email_task,
)


class TestSendWelcomeEmailTask:
    """Tests for send_welcome_email_task background task."""

    @pytest.mark.asyncio
    async def test_logs_start_message_on_execution(self) -> None:
        """Task logs 'sending_welcome_email' when starting."""
        user_id = uuid4()
        email = "test@example.com"

        with patch("fastapi_template.core.background_tasks.logger") as mock_logger:
            await send_welcome_email_task(user_id, email)

            # Check that info was called with sending_welcome_email message
            calls = [call for call in mock_logger.info.call_args_list if "sending_welcome_email" in str(call)]
            assert len(calls) >= 1

    @pytest.mark.asyncio
    async def test_logs_success_on_completion(self) -> None:
        """Task logs 'welcome_email_sent' on successful completion."""
        user_id = uuid4()
        email = "test@example.com"

        with patch("fastapi_template.core.background_tasks.logger") as mock_logger:
            await send_welcome_email_task(user_id, email)

            # Check that info was called with welcome_email_sent message
            calls = [call for call in mock_logger.info.call_args_list if "welcome_email_sent" in str(call)]
            assert len(calls) >= 1

    @pytest.mark.asyncio
    async def test_logs_exception_on_failure(self) -> None:
        """Task logs exception when asyncio.sleep raises."""
        user_id = uuid4()
        email = "test@example.com"

        with (
            patch("fastapi_template.core.background_tasks.asyncio.sleep", new_callable=AsyncMock) as mock_sleep,
            patch("fastapi_template.core.background_tasks.logger") as mock_logger,
        ):
            mock_sleep.side_effect = RuntimeError("Simulated failure")

            await send_welcome_email_task(user_id, email)

            mock_logger.exception.assert_called_once()
            call_args = mock_logger.exception.call_args
            assert "Failed to send welcome email" in str(call_args)

    @pytest.mark.asyncio
    async def test_includes_user_context_in_start_log(self) -> None:
        """Verify user_id and email are included in log extra."""
        user_id = uuid4()
        email = "context-test@example.com"

        with patch("fastapi_template.core.background_tasks.logger") as mock_logger:
            await send_welcome_email_task(user_id, email)

            # Find the sending_welcome_email call
            start_call = next(
                (call for call in mock_logger.info.call_args_list if "sending_welcome_email" in str(call)),
                None,
            )
            assert start_call is not None
            extra = start_call.kwargs.get("extra", {})
            assert extra["user_id"] == str(user_id)
            assert extra["email"] == email

    @pytest.mark.asyncio
    async def test_includes_user_context_in_success_log(self) -> None:
        """Verify user_id and email are included in success log extra."""
        user_id = uuid4()
        email = "success-context@example.com"

        with patch("fastapi_template.core.background_tasks.logger") as mock_logger:
            await send_welcome_email_task(user_id, email)

            # Find the welcome_email_sent call
            success_call = next(
                (call for call in mock_logger.info.call_args_list if "welcome_email_sent" in str(call)),
                None,
            )
            assert success_call is not None
            extra = success_call.kwargs.get("extra", {})
            assert extra["user_id"] == str(user_id)
            assert extra["email"] == email


class TestArchiveOldActivityLogsTask:
    """Tests for archive_old_activity_logs_task background task."""

    @pytest.mark.asyncio
    async def test_logs_start_message(self) -> None:
        """Task logs 'archiving_old_activity_logs' when starting."""
        org_id = uuid4()
        days_older_than = 90

        with patch("fastapi_template.core.background_tasks.logger") as mock_logger:
            await archive_old_activity_logs_task(org_id, days_older_than)

            calls = [call for call in mock_logger.info.call_args_list if "archiving_old_activity_logs" in str(call)]
            assert len(calls) >= 1

    @pytest.mark.asyncio
    async def test_logs_success_on_completion(self) -> None:
        """Task logs 'activity_logs_archived' on successful completion."""
        org_id = uuid4()
        days_older_than = 30

        with patch("fastapi_template.core.background_tasks.logger") as mock_logger:
            await archive_old_activity_logs_task(org_id, days_older_than)

            calls = [call for call in mock_logger.info.call_args_list if "activity_logs_archived" in str(call)]
            assert len(calls) >= 1

    @pytest.mark.asyncio
    async def test_logs_success_with_org_context(self) -> None:
        """Verify org_id and days_older_than are in log extra."""
        org_id = uuid4()
        days_older_than = 60

        with patch("fastapi_template.core.background_tasks.logger") as mock_logger:
            await archive_old_activity_logs_task(org_id, days_older_than)

            # Find the activity_logs_archived call
            success_call = next(
                (call for call in mock_logger.info.call_args_list if "activity_logs_archived" in str(call)),
                None,
            )
            assert success_call is not None
            extra = success_call.kwargs.get("extra", {})
            assert extra["org_id"] == str(org_id)
            assert extra["days_older_than"] == days_older_than

    @pytest.mark.asyncio
    async def test_handles_exception_gracefully(self) -> None:
        """Task logs exception and does not raise when failure occurs."""
        org_id = uuid4()
        days_older_than = 90

        with (
            patch("fastapi_template.core.background_tasks.asyncio.sleep", new_callable=AsyncMock) as mock_sleep,
            patch("fastapi_template.core.background_tasks.logger") as mock_logger,
        ):
            mock_sleep.side_effect = RuntimeError("Archival service unavailable")

            # Should not raise
            await archive_old_activity_logs_task(org_id, days_older_than)

            mock_logger.exception.assert_called_once()
            call_args = mock_logger.exception.call_args
            assert "Failed to archive activity logs" in str(call_args)

    @pytest.mark.asyncio
    async def test_includes_org_context_in_error_log(self) -> None:
        """Verify org_id and days_older_than are in error log extra."""
        org_id = uuid4()
        days_older_than = 45

        with (
            patch("fastapi_template.core.background_tasks.asyncio.sleep", new_callable=AsyncMock) as mock_sleep,
            patch("fastapi_template.core.background_tasks.logger") as mock_logger,
        ):
            mock_sleep.side_effect = RuntimeError("Test error")

            await archive_old_activity_logs_task(org_id, days_older_than)

            # Check exception was called with correct extra
            call_args = mock_logger.exception.call_args
            extra = call_args.kwargs.get("extra", {})
            assert extra["org_id"] == str(org_id)
            assert extra["days_older_than"] == days_older_than


class TestGenerateActivityReportTask:
    """Tests for generate_activity_report_task background task."""

    @pytest.mark.asyncio
    async def test_logs_start_message(self) -> None:
        """Task logs 'generating_activity_report' when starting."""
        org_id = uuid4()
        period = "monthly"

        with patch("fastapi_template.core.background_tasks.logger") as mock_logger:
            await generate_activity_report_task(org_id, period)

            calls = [call for call in mock_logger.info.call_args_list if "generating_activity_report" in str(call)]
            assert len(calls) >= 1

    @pytest.mark.asyncio
    async def test_logs_success_on_completion(self) -> None:
        """Task logs 'activity_report_generated' on successful completion."""
        org_id = uuid4()
        period = "weekly"

        with patch("fastapi_template.core.background_tasks.logger") as mock_logger:
            await generate_activity_report_task(org_id, period)

            calls = [call for call in mock_logger.info.call_args_list if "activity_report_generated" in str(call)]
            assert len(calls) >= 1

    @pytest.mark.asyncio
    async def test_logs_with_org_and_period_context(self) -> None:
        """Verify org_id and period are in log extra."""
        org_id = uuid4()
        period = "quarterly"

        with patch("fastapi_template.core.background_tasks.logger") as mock_logger:
            await generate_activity_report_task(org_id, period)

            # Find the activity_report_generated call
            success_call = next(
                (call for call in mock_logger.info.call_args_list if "activity_report_generated" in str(call)),
                None,
            )
            assert success_call is not None
            extra = success_call.kwargs.get("extra", {})
            assert extra["org_id"] == str(org_id)
            assert extra["period"] == period

    @pytest.mark.asyncio
    async def test_handles_weekly_period(self) -> None:
        """Task handles 'weekly' period value."""
        org_id = uuid4()

        with patch("fastapi_template.core.background_tasks.logger") as mock_logger:
            await generate_activity_report_task(org_id, "weekly")

            # Find the activity_report_generated call
            success_call = next(
                (call for call in mock_logger.info.call_args_list if "activity_report_generated" in str(call)),
                None,
            )
            assert success_call is not None
            extra = success_call.kwargs.get("extra", {})
            assert extra["period"] == "weekly"

    @pytest.mark.asyncio
    async def test_handles_monthly_period(self) -> None:
        """Task handles 'monthly' period value."""
        org_id = uuid4()

        with patch("fastapi_template.core.background_tasks.logger") as mock_logger:
            await generate_activity_report_task(org_id, "monthly")

            # Find the activity_report_generated call
            success_call = next(
                (call for call in mock_logger.info.call_args_list if "activity_report_generated" in str(call)),
                None,
            )
            assert success_call is not None
            extra = success_call.kwargs.get("extra", {})
            assert extra["period"] == "monthly"

    @pytest.mark.asyncio
    async def test_handles_quarterly_period(self) -> None:
        """Task handles 'quarterly' period value."""
        org_id = uuid4()

        with patch("fastapi_template.core.background_tasks.logger") as mock_logger:
            await generate_activity_report_task(org_id, "quarterly")

            # Find the activity_report_generated call
            success_call = next(
                (call for call in mock_logger.info.call_args_list if "activity_report_generated" in str(call)),
                None,
            )
            assert success_call is not None
            extra = success_call.kwargs.get("extra", {})
            assert extra["period"] == "quarterly"

    @pytest.mark.asyncio
    async def test_handles_exception_gracefully(self) -> None:
        """Task logs exception and does not raise when failure occurs."""
        org_id = uuid4()
        period = "monthly"

        with (
            patch("fastapi_template.core.background_tasks.asyncio.sleep", new_callable=AsyncMock) as mock_sleep,
            patch("fastapi_template.core.background_tasks.logger") as mock_logger,
        ):
            mock_sleep.side_effect = RuntimeError("Report generation failed")

            # Should not raise
            await generate_activity_report_task(org_id, period)

            mock_logger.exception.assert_called_once()
            call_args = mock_logger.exception.call_args
            assert "Failed to generate activity report" in str(call_args)

    @pytest.mark.asyncio
    async def test_includes_context_in_error_log(self) -> None:
        """Verify org_id and period are in error log extra."""
        org_id = uuid4()
        period = "daily"

        with (
            patch("fastapi_template.core.background_tasks.asyncio.sleep", new_callable=AsyncMock) as mock_sleep,
            patch("fastapi_template.core.background_tasks.logger") as mock_logger,
        ):
            mock_sleep.side_effect = RuntimeError("Test error")

            await generate_activity_report_task(org_id, period)

            # Check exception was called with correct extra
            call_args = mock_logger.exception.call_args
            extra = call_args.kwargs.get("extra", {})
            assert extra["org_id"] == str(org_id)
            assert extra["period"] == period
