"""Database-free regression tests for authentication audit signals."""

from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.contrib.auth.signals import (
    user_logged_in,
    user_logged_out,
    user_login_failed,
)
from django.test import SimpleTestCase

from auditlog.models import AuthenticationEvent


class AuthenticationSignalTests(SimpleTestCase):
    def test_model_event_type_values(self):
        self.assertEqual(
            AuthenticationEvent.LOGIN_SUCCESS,
            "login_success",
        )
        self.assertEqual(
            AuthenticationEvent.LOGIN_FAILURE,
            "login_failure",
        )
        self.assertEqual(
            AuthenticationEvent.LOGOUT,
            "logout",
        )

    @patch("auditlog.auth_signals.AuthenticationEvent.objects.create")
    def test_successful_login_records_user(self, create):
        # Django's built-in update_last_login receiver calls save().
        # Use an actual model instance and mock its save to avoid a DB.
        user = get_user_model()(username="audit_signal_lab_user")

        with patch.object(user, "save") as save:
            user_logged_in.send(
                sender=type(user),
                request=None,
                user=user,
            )

        create.assert_called_once_with(
            user=user,
            event_type=AuthenticationEvent.LOGIN_SUCCESS,
        )
        save.assert_called_once_with(
            update_fields=["last_login"],
        )

    @patch("auditlog.auth_signals.AuthenticationEvent.objects.create")
    def test_failed_login_discards_credentials(self, create):
        user_login_failed.send(
            sender=object,
            credentials={
                "username": "private-name",
                "password": "private-password",
            },
            request=None,
        )

        create.assert_called_once_with(
            user=None,
            event_type=AuthenticationEvent.LOGIN_FAILURE,
        )

    @patch("auditlog.auth_signals.AuthenticationEvent.objects.create")
    def test_logout_records_user(self, create):
        user = get_user_model()(username="audit_logout_lab_user")

        user_logged_out.send(
            sender=type(user),
            request=None,
            user=user,
        )

        create.assert_called_once_with(
            user=user,
            event_type=AuthenticationEvent.LOGOUT,
        )

    @patch("auditlog.auth_signals.AuthenticationEvent.objects.create")
    def test_anonymous_logout_has_no_user(self, create):
        user_logged_out.send(
            sender=object,
            request=None,
            user=None,
        )

        create.assert_called_once_with(
            user=None,
            event_type=AuthenticationEvent.LOGOUT,
        )

    def test_model_has_no_sensitive_columns(self):
        field_names = {
            field.name
            for field in AuthenticationEvent._meta.fields
        }

        forbidden = {
            "password",
            "username",
            "session_key",
            "cookie",
            "token",
            "ip_address",
            "user_agent",
            "credentials",
        }

        self.assertTrue(field_names.isdisjoint(forbidden))
        self.assertEqual(
            field_names,
            {"id", "user", "event_type", "created_at"},
        )

    def test_creation_timestamp_is_indexed(self):
        field = AuthenticationEvent._meta.get_field("created_at")
        self.assertTrue(field.db_index)

    @patch("auditlog.auth_signals.logger.error")
    @patch(
        "auditlog.auth_signals.AuthenticationEvent.objects.create",
        side_effect=__import__("django.db", fromlist=["DatabaseError"]).DatabaseError(
            "simulated database error with sensitive-example-value"
        ),
    )
    def test_audit_failure_does_not_interrupt_login(
        self, create, log_error
    ):
        user = get_user_model()(username="audit_failure_test")

        with patch.object(user, "save") as save:
            user_logged_in.send(
                sender=type(user),
                request=None,
                user=user,
            )

        save.assert_called_once_with(
            update_fields=["last_login"]
        )
        create.assert_called_once_with(
            user=user,
            event_type=AuthenticationEvent.LOGIN_SUCCESS,
        )
        log_error.assert_called_once_with(
            "Authentication audit event could not be persisted."
        )

    @patch("auditlog.auth_signals.logger.error")
    @patch(
        "auditlog.auth_signals.AuthenticationEvent.objects.create",
        side_effect=__import__("django.db", fromlist=["DatabaseError"]).DatabaseError(
            "simulated failed login audit storage error"
        ),
    )
    def test_audit_failure_does_not_interrupt_failed_login(
        self, create, log_error
    ):
        user_login_failed.send(
            sender=object,
            request=None,
            credentials={
                "username": "never-log-this",
                "password": "never-log-password",
            },
        )

        create.assert_called_once_with(
            user=None,
            event_type=AuthenticationEvent.LOGIN_FAILURE,
        )
        log_error.assert_called_once_with(
            "Authentication audit event could not be persisted."
        )

    @patch("auditlog.auth_signals.logger.error")
    @patch(
        "auditlog.auth_signals.AuthenticationEvent.objects.create",
        side_effect=__import__("django.db", fromlist=["DatabaseError"]).DatabaseError(
            "simulated logout audit storage error"
        ),
    )
    def test_audit_failure_does_not_interrupt_logout(
        self, create, log_error
    ):
        user = get_user_model()(username="audit_logout_failure")

        user_logged_out.send(
            sender=type(user),
            request=None,
            user=user,
        )

        create.assert_called_once_with(
            user=user,
            event_type=AuthenticationEvent.LOGOUT,
        )
        log_error.assert_called_once_with(
            "Authentication audit event could not be persisted."
        )

    @patch("auditlog.auth_signals.logger.error")
    @patch(
        "auditlog.auth_signals.AuthenticationEvent.objects.create",
        side_effect=ValueError("unexpected programming defect"),
    )
    def test_unexpected_programming_error_still_propagates(
        self, create, log_error
    ):
        with self.assertRaisesRegex(
            ValueError,
            "unexpected programming defect",
        ):
            user_login_failed.send(
                sender=object,
                request=None,
                credentials={},
            )

        log_error.assert_not_called()

    @patch("auditlog.auth_signals.logger.error")
    @patch(
        "auditlog.auth_signals.AuthenticationEvent.objects.create",
        side_effect=__import__("django.db", fromlist=["OperationalError"]).OperationalError(
            "database temporarily unavailable"
        ),
    )
    def test_operational_error_is_handled(
        self, create, log_error
    ):
        user_login_failed.send(
            sender=object,
            request=None,
            credentials={},
        )

        log_error.assert_called_once_with(
            "Authentication audit event could not be persisted."
        )

    def test_failure_message_contains_no_sensitive_information(self):
        from auditlog.auth_signals import AUDIT_WRITE_FAILURE_MESSAGE

        self.assertEqual(
            AUDIT_WRITE_FAILURE_MESSAGE,
            "Authentication audit event could not be persisted.",
        )

        self.assertNotIn(
            "username",
            AUDIT_WRITE_FAILURE_MESSAGE.lower(),
        )
        self.assertNotIn(
            "password",
            AUDIT_WRITE_FAILURE_MESSAGE.lower(),
        )
