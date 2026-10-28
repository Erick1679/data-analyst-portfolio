"""Record minimal authentication events without exposing credentials."""

import logging

from django.contrib.auth.signals import (
    user_logged_in,
    user_logged_out,
    user_login_failed,
)
from django.db import DatabaseError
from django.dispatch import receiver

from .models import AuthenticationEvent


logger = logging.getLogger(__name__)

# Keep this message static. Do not include exceptions,
# usernames, credentials, request headers or session IDs.
AUDIT_WRITE_FAILURE_MESSAGE = (
    "Authentication audit event could not be persisted."
)


def _record_authentication_event(event_type, user=None):
    """Isolate audit database errors from authentication signals.

    This is best-effort recording. Other programming exceptions
    deliberately propagate for investigation.
    """
    try:
        AuthenticationEvent.objects.create(
            user=user,
            event_type=event_type,
        )
    except DatabaseError:
        logger.error(AUDIT_WRITE_FAILURE_MESSAGE)
        return False

    return True


@receiver(
    user_logged_in,
    dispatch_uid="brights.auth_event.login_success.v1",
)
def record_login_success(sender, request, user, **kwargs):
    _record_authentication_event(
        AuthenticationEvent.LOGIN_SUCCESS,
        user=user,
    )


@receiver(
    user_logged_out,
    dispatch_uid="brights.auth_event.logout.v1",
)
def record_logout(sender, request, user, **kwargs):
    authenticated_user = (
        user if user is not None and user.is_authenticated else None
    )

    _record_authentication_event(
        AuthenticationEvent.LOGOUT,
        user=authenticated_user,
    )


@receiver(
    user_login_failed,
    dispatch_uid="brights.auth_event.login_failure.v1",
)
def record_login_failure(sender, credentials, request, **kwargs):
    # The credentials argument is intentionally not inspected.
    _record_authentication_event(
        AuthenticationEvent.LOGIN_FAILURE,
    )
