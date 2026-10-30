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
        "prune_authentication_events.Command._verify_target_and_lock"
    )
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
        verify_mock,
    ):
        queryset = MagicMock()
        queryset.count.return_value = 2
        queryset.delete.return_value = (
            2,
            {"auditlog.AuthenticationEvent": 2},
        )
        filter_mock.return_value = queryset
        atomic_mock.return_value = nullcontext()

        output = StringIO()

        call_command(
            "prune_authentication_events",
            "--apply",
            "--expected-database=retention_lab",
            "--expected-user=retention_lab_owner",
            stdout=output,
        )

        self.assertEqual(filter_mock.call_count, 3)
        self.assertEqual(queryset.delete.call_count, 3)
        atomic_mock.assert_called_once()
        verify_mock.assert_called_once_with(
            "retention_lab",
            "retention_lab_owner",
        )
        self.assertIn("APPLIED:", output.getvalue())
        self.assertIn("deleted_total=6", output.getvalue())
        self.assertEqual(
            output.getvalue().count("deleted=2"),
            3,
        )

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

    def test_apply_requires_database_confirmation(self):
        from django.core.management.base import CommandError

        output = StringIO()
        with self.assertRaises(CommandError):
            call_command(
                "prune_authentication_events",
                "--apply",
                stdout=output,
            )

    def test_apply_requires_both_expected_identity_fields(self):
        from django.core.management.base import CommandError

        for arguments in (
            ("--apply", "--expected-database=lab"),
            ("--apply", "--expected-user=owner"),
            (
                "--apply",
                "--expected-database= ",
                "--expected-user=owner",
            ),
        ):
            with self.subTest(arguments=arguments):
                with self.assertRaises(CommandError):
                    call_command(
                        "prune_authentication_events",
                        *arguments,
                        stdout=StringIO(),
                    )

    @patch(
        "auditlog.management.commands."
        "prune_authentication_events.connection"
    )
    def test_non_postgresql_apply_target_is_rejected(
        self, database
    ):
        from django.core.management.base import CommandError
        from auditlog.management.commands.prune_authentication_events import (
            Command,
        )

        database.vendor = "sqlite"
        command = Command()

        with self.assertRaises(CommandError):
            command._verify_target_and_lock("lab", "owner")

        database.cursor.assert_not_called()

    @patch(
        "auditlog.management.commands."
        "prune_authentication_events.connection"
    )
    def test_wrong_database_identity_is_rejected(
        self, database
    ):
        from django.core.management.base import CommandError
        from auditlog.management.commands.prune_authentication_events import (
            Command,
        )

        database.vendor = "postgresql"
        cursor = database.cursor.return_value.__enter__.return_value
        cursor.fetchone.return_value = ("wrong_db", "owner")

        with self.assertRaises(CommandError):
            Command()._verify_target_and_lock("expected_db", "owner")

        self.assertEqual(cursor.execute.call_count, 1)

    @patch(
        "auditlog.management.commands."
        "prune_authentication_events.connection"
    )
    def test_concurrent_cleanup_lock_refuses_second_run(
        self, database
    ):
        from django.core.management.base import CommandError
        from auditlog.management.commands.prune_authentication_events import (
            Command,
        )

        database.vendor = "postgresql"
        cursor = database.cursor.return_value.__enter__.return_value
        cursor.fetchone.side_effect = [
            ("lab", "owner"),
            (False,),
        ]

        with self.assertRaises(CommandError):
            Command()._verify_target_and_lock("lab", "owner")

        self.assertEqual(cursor.execute.call_count, 2)

    @patch(
        "auditlog.management.commands."
        "prune_authentication_events.connection"
    )
    def test_verified_database_acquires_advisory_lock(
        self, database
    ):
        from auditlog.management.commands.prune_authentication_events import (
            Command, LOCK_NAMESPACE, LOCK_OPERATION,
        )

        database.vendor = "postgresql"
        cursor = database.cursor.return_value.__enter__.return_value
        cursor.fetchone.side_effect = [
            ("lab", "owner"),
            (True,),
        ]

        Command()._verify_target_and_lock("lab", "owner")

        self.assertEqual(cursor.execute.call_count, 2)
        self.assertEqual(
            cursor.execute.call_args.args[1],
            [LOCK_NAMESPACE, LOCK_OPERATION],
        )

    @patch(
        "auditlog.management.commands."
        "prune_authentication_events.Command._verify_target_and_lock"
    )
    @patch(
        "auditlog.management.commands."
        "prune_authentication_events.transaction.atomic"
    )
    @patch(
        "auditlog.management.commands."
        "prune_authentication_events.AuthenticationEvent.objects.filter"
    )
    def test_actual_deletion_counts_ignore_other_models(
        self,
        filter_mock,
        atomic_mock,
        verify_mock,
    ):
        querysets = [MagicMock() for _ in range(3)]

        for queryset in querysets:
            queryset.count.return_value = 5
            queryset.delete.return_value = (
                7,
                {
                    "auditlog.AuthenticationEvent": 5,
                    "other.RelatedModel": 2,
                },
            )

        filter_mock.side_effect = querysets
        atomic_mock.return_value = nullcontext()
        output = StringIO()

        call_command(
            "prune_authentication_events",
            "--apply",
            "--expected-database=lab",
            "--expected-user=owner",
            stdout=output,
        )

        self.assertIn("deleted_total=15", output.getvalue())
        self.assertEqual(
            output.getvalue().count("deleted=5"),
            3,
        )
        verify_mock.assert_called_once_with("lab", "owner")

    @patch(
        "auditlog.management.commands."
        "prune_authentication_events.Command._verify_target_and_lock"
    )
    @patch(
        "auditlog.management.commands."
        "prune_authentication_events.transaction.atomic"
    )
    @patch(
        "auditlog.management.commands."
        "prune_authentication_events.AuthenticationEvent.objects.filter"
    )
    def test_failed_delete_never_reports_success(
        self,
        filter_mock,
        atomic_mock,
        verify_mock,
    ):
        querysets = [MagicMock() for _ in range(3)]

        for queryset in querysets:
            queryset.count.return_value = 1

        querysets[0].delete.return_value = (
            1,
            {"auditlog.AuthenticationEvent": 1},
        )
        querysets[1].delete.side_effect = RuntimeError(
            "simulated deletion failure"
        )

        filter_mock.side_effect = querysets
        atomic_mock.return_value = nullcontext()
        output = StringIO()

        with self.assertRaisesRegex(
            RuntimeError,
            "simulated deletion failure",
        ):
            call_command(
                "prune_authentication_events",
                "--apply",
                "--expected-database=lab",
                "--expected-user=owner",
                stdout=output,
            )

        self.assertNotIn("APPLIED:", output.getvalue())
        self.assertNotIn("deleted_total=", output.getvalue())
        querysets[2].delete.assert_not_called()

    @patch(
        "auditlog.management.commands."
        "prune_authentication_events.Command._verify_target_and_lock"
    )
    @patch(
        "auditlog.management.commands."
        "prune_authentication_events.transaction.atomic"
    )
    @patch(
        "auditlog.management.commands."
        "prune_authentication_events.AuthenticationEvent.objects.filter"
    )
    def test_zero_deleted_records_reported_explicitly(
        self,
        filter_mock,
        atomic_mock,
        verify_mock,
    ):
        queryset = MagicMock()
        queryset.count.return_value = 0
        queryset.delete.return_value = (0, {})
        filter_mock.return_value = queryset
        atomic_mock.return_value = nullcontext()

        output = StringIO()

        call_command(
            "prune_authentication_events",
            "--apply",
            "--expected-database=lab",
            "--expected-user=owner",
            stdout=output,
        )

        self.assertIn("deleted_total=0", output.getvalue())
        self.assertEqual(
            output.getvalue().count("deleted=0"),
            3,
        )

    @patch(
        "auditlog.management.commands."
        "prune_authentication_events.Command._handle_retention"
    )
    def test_database_error_uses_static_safe_message(self, handler):
        from django.core.management.base import CommandError
        from django.db import DatabaseError

        handler.side_effect = DatabaseError(
            "synthetic-private-value-DO-NOT-LOG"
        )

        with self.assertRaises(CommandError) as caught:
            call_command(
                "prune_authentication_events",
                stdout=StringIO(),
            )

        self.assertEqual(
            str(caught.exception),
            "Authentication retention database operation failed.",
        )
        self.assertTrue(caught.exception.__suppress_context__)

    @patch(
        "auditlog.management.commands."
        "prune_authentication_events.Command._handle_retention"
    )
    def test_operational_error_uses_static_safe_message(self, handler):
        from django.core.management.base import CommandError
        from django.db import OperationalError

        handler.side_effect = OperationalError(
            "synthetic-private-connection-detail"
        )

        with self.assertRaises(CommandError) as caught:
            call_command(
                "prune_authentication_events",
                stdout=StringIO(),
            )

        self.assertEqual(
            str(caught.exception),
            "Authentication retention database operation failed.",
        )

    @patch(
        "auditlog.management.commands."
        "prune_authentication_events.Command._handle_retention"
    )
    def test_existing_command_error_is_not_rewritten(self, handler):
        from django.core.management.base import CommandError

        handler.side_effect = CommandError(
            "Explicit cleanup authorization required."
        )

        with self.assertRaisesRegex(
            CommandError,
            "Explicit cleanup authorization required",
        ):
            call_command(
                "prune_authentication_events",
                stdout=StringIO(),
            )

    @patch(
        "auditlog.management.commands."
        "prune_authentication_events.Command._handle_retention"
    )
    def test_programming_error_still_propagates(self, handler):
        handler.side_effect = ValueError(
            "unexpected programming defect"
        )

        with self.assertRaisesRegex(
            ValueError,
            "unexpected programming defect",
        ):
            call_command(
                "prune_authentication_events",
                stdout=StringIO(),
            )
