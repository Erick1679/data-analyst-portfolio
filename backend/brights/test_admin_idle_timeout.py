"""Regression tests for admin idle and absolute session expiry."""

from types import SimpleNamespace
from unittest.mock import patch

from django.conf import settings
from django.http import HttpResponse
from django.test import RequestFactory, SimpleTestCase

from brights.admin_idle_timeout import (
    ADMIN_ABSOLUTE_DEADLINE_KEY,
    ADMIN_LAST_ACTIVITY_KEY,
    AdminIdleTimeoutMiddleware,
)


class FakeSession(dict):
    """A lightweight session supporting absolute expiry assertions."""

    def __init__(self):
        super().__init__()
        self.expiry_values = []

    def set_expiry(self, value):
        self.expiry_values.append(value)


class AdminIdleTimeoutTests(SimpleTestCase):
    def setUp(self):
        self.factory = RequestFactory()
        self.middleware = AdminIdleTimeoutMiddleware(
            lambda request: HttpResponse("OK")
        )

    def request(
        self,
        path="/admin/",
        authenticated=True,
        staff=True,
    ):
        request = self.factory.get(path)
        request.session = FakeSession()
        request.user = SimpleNamespace(
            is_authenticated=authenticated,
            is_staff=staff,
        )
        return request

    def test_configured_limits(self):
        self.assertEqual(settings.ADMIN_IDLE_TIMEOUT_SECONDS, 1800)
        self.assertEqual(settings.SESSION_COOKIE_AGE, 43200)

    def test_first_request_pins_original_deadline(self):
        request = self.request()

        with patch(
            "brights.admin_idle_timeout._now",
            return_value=10000,
        ), patch(
            "brights.admin_idle_timeout._original_deadline",
            return_value=50000,
        ):
            response = self.middleware(request)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            request.session[ADMIN_LAST_ACTIVITY_KEY],
            10000,
        )
        self.assertEqual(
            request.session[ADMIN_ABSOLUTE_DEADLINE_KEY],
            50000,
        )
        self.assertEqual(
            request.session.expiry_values[-1].timestamp(),
            50000,
        )

    def test_activity_refreshes_idle_only(self):
        request = self.request()
        request.session[ADMIN_LAST_ACTIVITY_KEY] = 10000
        request.session[ADMIN_ABSOLUTE_DEADLINE_KEY] = 50000

        with patch(
            "brights.admin_idle_timeout._now",
            return_value=11799,
        ):
            response = self.middleware(request)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            request.session[ADMIN_LAST_ACTIVITY_KEY],
            11799,
        )
        self.assertEqual(
            request.session[ADMIN_ABSOLUTE_DEADLINE_KEY],
            50000,
        )
        self.assertEqual(
            request.session.expiry_values[-1].timestamp(),
            50000,
        )

    def test_repeated_activity_never_extends_deadline(self):
        request = self.request()
        request.session[ADMIN_LAST_ACTIVITY_KEY] = 49000
        request.session[ADMIN_ABSOLUTE_DEADLINE_KEY] = 50000

        for now in (49500, 49900, 49999):
            with patch(
                "brights.admin_idle_timeout._now",
                return_value=now,
            ):
                response = self.middleware(request)

            self.assertEqual(response.status_code, 200)
            self.assertEqual(
                request.session[ADMIN_ABSOLUTE_DEADLINE_KEY],
                50000,
            )
            self.assertEqual(
                request.session.expiry_values[-1].timestamp(),
                50000,
            )

    def test_exact_idle_limit_logs_out(self):
        request = self.request()
        request.session[ADMIN_LAST_ACTIVITY_KEY] = 10000
        request.session[ADMIN_ABSOLUTE_DEADLINE_KEY] = 50000

        with patch(
            "brights.admin_idle_timeout._now",
            return_value=11800,
        ), patch(
            "brights.admin_idle_timeout.logout",
        ) as logout:
            response = self.middleware(request)

        self.assertEqual(response.status_code, 302)
        logout.assert_called_once_with(request)

    def test_exact_absolute_deadline_logs_out(self):
        request = self.request()
        request.session[ADMIN_LAST_ACTIVITY_KEY] = 49999
        request.session[ADMIN_ABSOLUTE_DEADLINE_KEY] = 50000

        with patch(
            "brights.admin_idle_timeout._now",
            return_value=50000,
        ), patch(
            "brights.admin_idle_timeout.logout",
        ) as logout:
            response = self.middleware(request)

        self.assertEqual(response.status_code, 302)
        logout.assert_called_once_with(request)

    def test_invalid_idle_timestamp_fails_closed(self):
        request = self.request()
        request.session[ADMIN_LAST_ACTIVITY_KEY] = "invalid"
        request.session[ADMIN_ABSOLUTE_DEADLINE_KEY] = 50000

        with patch(
            "brights.admin_idle_timeout._now",
            return_value=10000,
        ), patch(
            "brights.admin_idle_timeout.logout",
        ) as logout:
            response = self.middleware(request)

        self.assertEqual(response.status_code, 302)
        logout.assert_called_once_with(request)

    def test_invalid_absolute_deadline_fails_closed(self):
        request = self.request()
        request.session[ADMIN_LAST_ACTIVITY_KEY] = 10000
        request.session[ADMIN_ABSOLUTE_DEADLINE_KEY] = "invalid"

        with patch(
            "brights.admin_idle_timeout._now",
            return_value=11000,
        ), patch(
            "brights.admin_idle_timeout.logout",
        ) as logout:
            response = self.middleware(request)

        self.assertEqual(response.status_code, 302)
        logout.assert_called_once_with(request)

    def test_missing_original_session_fails_closed(self):
        request = self.request()

        with patch(
            "brights.admin_idle_timeout._now",
            return_value=10000,
        ), patch(
            "brights.admin_idle_timeout._original_deadline",
            return_value=None,
        ), patch(
            "brights.admin_idle_timeout.logout",
        ) as logout:
            response = self.middleware(request)

        self.assertEqual(response.status_code, 302)
        logout.assert_called_once_with(request)

    def test_unpinned_existing_activity_fails_closed(self):
        request = self.request()
        request.session[ADMIN_LAST_ACTIVITY_KEY] = 10000

        with patch(
            "brights.admin_idle_timeout._now",
            return_value=11000,
        ), patch(
            "brights.admin_idle_timeout.logout",
        ) as logout:
            response = self.middleware(request)

        self.assertEqual(response.status_code, 302)
        logout.assert_called_once_with(request)

    def test_future_idle_timestamp_fails_closed(self):
        request = self.request()
        request.session[ADMIN_LAST_ACTIVITY_KEY] = 12000
        request.session[ADMIN_ABSOLUTE_DEADLINE_KEY] = 50000

        with patch(
            "brights.admin_idle_timeout._now",
            return_value=11000,
        ), patch(
            "brights.admin_idle_timeout.logout",
        ) as logout:
            response = self.middleware(request)

        self.assertEqual(response.status_code, 302)
        logout.assert_called_once_with(request)

    def test_anonymous_request_unchanged(self):
        request = self.request(
            authenticated=False,
            staff=False,
        )
        response = self.middleware(request)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(request.session), 0)

    def test_nonstaff_request_unchanged(self):
        request = self.request(staff=False)
        response = self.middleware(request)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(request.session), 0)

    def test_retail_request_unchanged(self):
        request = self.request(
            path="/corporate/example/retail/products/"
        )
        response = self.middleware(request)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(request.session), 0)
