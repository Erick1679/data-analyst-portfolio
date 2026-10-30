"""Regression tests for production startup requirements.

All settings evaluations occur in isolated subprocesses.
No persistent database access is required.
"""

import os
import secrets
import subprocess
import sys

from django.test import SimpleTestCase


class ProductionConfigurationTests(SimpleTestCase):
    """Verify fail-closed production configuration behavior."""

    SETTINGS_PROBE = """
import sys

try:
    from django.conf import settings

    if settings.DEBUG is not False:
        sys.exit(3)

    if not settings.SECRET_KEY:
        sys.exit(4)

    if not settings.ALLOWED_HOSTS:
        sys.exit(5)

except Exception as exc:
    if type(exc).__name__ == "ImproperlyConfigured":
        sys.exit(20)
    sys.exit(21)

sys.exit(0)
"""

    def probe(self, *, secret, allowed_hosts):
        env = os.environ.copy()
        env["DJANGO_SETTINGS_MODULE"] = "brights.settings"
        env["DJANGO_DEBUG"] = "0"
        env["BRIGHTS_DATABASE_ENGINE"] = "sqlite"
        env["PYTHONDONTWRITEBYTECODE"] = "1"

        # Explicitly remove inherited production values.
        # Only this subprocess receives the test settings.
        env.pop("DJANGO_SECRET_KEY", None)
        env.pop("DJANGO_ALLOWED_HOSTS", None)

        if secret:
            env["DJANGO_SECRET_KEY"] = secrets.token_urlsafe(64)

        if allowed_hosts:
            env["DJANGO_ALLOWED_HOSTS"] = (
                "security-audit.invalid"
            )

        result = subprocess.run(
            [sys.executable, "-c", self.SETTINGS_PROBE],
            env=env,
            capture_output=True,
            text=True,
            timeout=15,
        )

        # Return only the exit status. Never expose raw
        # exception text or environment-variable contents.
        return result.returncode

    def test_production_loads_with_both_requirements(self):
        self.assertEqual(
            self.probe(secret=True, allowed_hosts=True),
            0,
        )

    def test_production_rejects_missing_secret_key(self):
        self.assertEqual(
            self.probe(secret=False, allowed_hosts=True),
            20,
        )

    def test_production_rejects_missing_allowed_hosts(self):
        self.assertEqual(
            self.probe(secret=True, allowed_hosts=False),
            20,
        )

    def test_production_rejects_both_missing_requirements(self):
        self.assertEqual(
            self.probe(secret=False, allowed_hosts=False),
            20,
        )
