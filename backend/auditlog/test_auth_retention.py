"""Database-free tests for authentication audit retention."""

from contextlib import nullcontext
from datetime import datetime, timedelta, timezone as dt_timezone
from io import StringIO
from unittest.mock import MagicMock, patch

from django.core.management import call_command
from django.test import SimpleTestCase

from auditlog.management.commands.prune_authentication_events import (
    retention_cutoffs,
)
from auditlog.models import AuthenticationEvent


class AuthenticationRetentionTests(SimpleTestCase):
    def test_failed_logins_retained_for_ninety_days(self):
        now = datetime(
            2026, 10, 28, 12, 0,
            tzinfo=dt_timezone.utc,
        )
        cutoffs = retention_cutoffs(now)

        self.assertEqual(
            cutoffs[AuthenticationEvent.LOGIN_FAILURE],
            now - timedelta(days=90),
        )

    def test_success_and_logout_use_twelve_calendar_months(self):
        now = datetime(
            2026, 10, 28, 12, 0,
            tzinfo=dt_timezone.utc,
        )
        cutoffs = retention_cutoffs(now)
        expected = now.replace(year=2025)

        self.assertEqual(
            cutoffs[AuthenticationEvent.LOGIN_SUCCESS],
            expected,
        )
        self.assertEqual(
            cutoffs[AuthenticationEvent.LOGOUT],
            expected,
        )

    def test_leap_day_uses_valid_calendar_date(self):
        now = datetime(
            2024, 2, 29, 12, 0,
            tzinfo=dt_timezone.utc,
        )
        cutoffs = retention_cutoffs(now)

        self.assertEqual(
            cutoffs[AuthenticationEvent.LOGIN_SUCCESS],
            datetime(
                2023, 2, 28, 12, 0,
                tzinfo=dt_timezone.utc,
            ),
        )

    def test_cutoff_preserves_strict_boundary(self):
        now = datetime(
            2026, 10, 28, 12, 0,
            tzinfo=dt_timezone.utc,
        )

        cutoffs = retention_cutoffs(now)
        cutoff = cutoffs[AuthenticationEvent.LOGIN_FAILURE]

        self.assertFalse(cutoff < cutoff)
        self.assertTrue(
            cutoff - timedelta(microseconds=1) < cutoff
        )
        self.assertFalse(
            cutoff + timedelta(microseconds=1) < cutoff
        )

    @patch(
        "auditlog.management.commands."
        "prune_authentication_events.AuthenticationEvent.objects.filter"
    )
    def test_default_is_preview_only(self, filter_mock):
        queryset = MagicMock()
        queryset.count.return_value = 4
        filter_mock.return_value = queryset

        output = StringIO()

        call_command(
            "prune_authentication_events",
            stdout=output,
        )

        self.assertEqual(filter_mock.call_count, 3)
        self.assertIn("PREVIEW ONLY", output.getvalue())
        queryset.delete.assert_not_called()

        for call in filter_mock.call_args_list:
            self.assertIn("event_type", call.kwargs)
            self.assertIn("created_at__lt", call.kwargs)

    @patch(
        "auditlog.management.commands."
        "prune_authentication_events.transaction.atomic"
    )
    @patch(
        "auditlog.management.commands."
        "prune_authentication_events.AuthenticationEvent.objects.filter"
    )
    def test_apply_deletes_only_scoped_querysets(
        self,
        filter_mock,
        atomic_mock,
    ):
        queryset = MagicMock()
        queryset.count.return_value = 2
        filter_mock.return_value = queryset
        atomic_mock.return_value = nullcontext()

        output = StringIO()

        call_command(
            "prune_authentication_events",
            "--apply",
            stdout=output,
        )

        self.assertEqual(filter_mock.call_count, 3)
        self.assertEqual(queryset.delete.call_count, 3)
        atomic_mock.assert_called_once()
        self.assertIn("APPLIED:", output.getvalue())

    def test_only_three_known_event_types_have_cutoffs(self):
        now = datetime(
            2026, 10, 28,
            tzinfo=dt_timezone.utc,
        )

        self.assertEqual(
            set(retention_cutoffs(now)),
            {
                AuthenticationEvent.LOGIN_SUCCESS,
                AuthenticationEvent.LOGIN_FAILURE,
                AuthenticationEvent.LOGOUT,
            },
        )
