"""Django admin inactivity and absolute session expiration controls."""

import math
from datetime import datetime, timezone as datetime_timezone

from django.conf import settings
from django.contrib.auth import logout
from django.contrib.auth.views import redirect_to_login
from django.contrib.sessions.models import Session
from django.utils import timezone


ADMIN_LAST_ACTIVITY_KEY = "_brights_admin_last_activity"
ADMIN_ABSOLUTE_DEADLINE_KEY = "_brights_admin_absolute_deadline"


def _now():
    return timezone.now().timestamp()


def _original_deadline(request):
    """Read the existing database session expiration.

    The initial deadline comes from the actual django_session
    record, not from the current request time.

    This requires Django's configured database session backend.
    """
    if settings.SESSION_ENGINE != "django.contrib.sessions.backends.db":
        return None

    key = getattr(request.session, "session_key", None)
    if not key:
        return None

    expiry = (
        Session.objects
        .filter(session_key=key)
        .values_list("expire_date", flat=True)
        .first()
    )

    if expiry is None:
        return None

    return expiry.timestamp()


def _valid_timestamp(value):
    """Accept only finite numeric timestamps."""
    if isinstance(value, bool):
        return None

    try:
        value = float(value)
    except (TypeError, ValueError, OverflowError):
        return None

    if not math.isfinite(value):
        return None

    return value


class AdminIdleTimeoutMiddleware:
    """Enforce idle and absolute deadlines on Django admin requests.

    The existing database session expiration is captured at the
    first authenticated admin request.

    Later activity updates only the inactivity timestamp.
    The absolute expiration cannot move forward.
    """

    def __init__(self, get_response):
        self.get_response = get_response

    def _expire(self, request):
        logout(request)
        return redirect_to_login(
            request.get_full_path(),
            login_url="/admin/login/",
        )

    def __call__(self, request):
        is_admin_path = (
            request.path_info == "/admin"
            or request.path_info.startswith("/admin/")
        )

        if not (
            is_admin_path
            and request.user.is_authenticated
            and request.user.is_staff
        ):
            return self.get_response(request)

        now = _now()
        timeout = settings.ADMIN_IDLE_TIMEOUT_SECONDS

        previous_raw = request.session.get(
            ADMIN_LAST_ACTIVITY_KEY
        )

        deadline_raw = request.session.get(
            ADMIN_ABSOLUTE_DEADLINE_KEY
        )

        previous = _valid_timestamp(previous_raw)
        deadline = _valid_timestamp(deadline_raw)

        # Existing activity without a pinned absolute deadline
        # is not trustworthy enough to continue the session.
        if previous_raw is not None and deadline_raw is None:
            return self._expire(request)

        if previous_raw is not None and previous is None:
            return self._expire(request)

        if deadline_raw is not None and deadline is None:
            return self._expire(request)

        if deadline is None:
            deadline = _valid_timestamp(
                _original_deadline(request)
            )

            if deadline is None:
                return self._expire(request)

        # A session must never outlive its original deadline.
        if now >= deadline:
            return self._expire(request)

        if previous is not None:
            elapsed = now - previous

            if not (0 <= elapsed < timeout):
                return self._expire(request)

        # Persist the original absolute expiry, rather than
        # allowing Django's session save to recalculate a new
        # 12-hour expiry from the current request.
        absolute_datetime = datetime.fromtimestamp(
            deadline,
            tz=datetime_timezone.utc,
        )

        request.session.set_expiry(absolute_datetime)

        request.session[ADMIN_ABSOLUTE_DEADLINE_KEY] = deadline
        request.session[ADMIN_LAST_ACTIVITY_KEY] = now

        return self.get_response(request)
