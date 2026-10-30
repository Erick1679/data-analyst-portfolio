"""Regression tests for the standard login session lifetime."""

from django.conf import settings
from django.test import SimpleTestCase
from django.contrib.sessions.backends.signed_cookies import (
    SessionStore,
)


class StandardSessionPolicyTests(SimpleTestCase):
    def test_session_maximum_age_is_twelve_hours(self):
        self.assertEqual(settings.SESSION_COOKIE_AGE, 43200)

    def test_session_does_not_refresh_every_request(self):
        self.assertFalse(settings.SESSION_SAVE_EVERY_REQUEST)

    def test_new_session_uses_configured_expiry(self):
        session = SessionStore()
        session["session_policy_test"] = True

        seconds = session.get_expiry_age()

        self.assertGreaterEqual(seconds, 43195)
        self.assertLessEqual(seconds, 43200)
