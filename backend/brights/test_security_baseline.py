"""Security behavior regression tests for Brights Analytics.

These tests use isolated Django settings overrides and do not
alter persistent databases or production security configuration.
"""

from django.conf import settings
from django.http import HttpResponse
from django.test import RequestFactory, SimpleTestCase, override_settings
from django.middleware.security import SecurityMiddleware
from django.middleware.clickjacking import XFrameOptionsMiddleware


class SecurityBaselineTests(SimpleTestCase):
    """Exercise security middleware independently of database state."""

    def setUp(self):
        self.factory = RequestFactory()
        self.response = lambda request: HttpResponse("OK")

    def test_security_middleware_precedes_session_and_auth(self):
        middleware = list(settings.MIDDLEWARE)

        security = middleware.index(
            "django.middleware.security.SecurityMiddleware"
        )
        session = middleware.index(
            "django.contrib.sessions.middleware.SessionMiddleware"
        )
        csrf = middleware.index(
            "django.middleware.csrf.CsrfViewMiddleware"
        )
        auth = middleware.index(
            "django.contrib.auth.middleware.AuthenticationMiddleware"
        )

        self.assertLess(security, session)
        self.assertLess(session, csrf)
        self.assertLess(csrf, auth)

    @override_settings(
        SECURE_SSL_REDIRECT=True,
        SECURE_PROXY_SSL_HEADER=None,
        SECURE_HSTS_SECONDS=0,
    )
    def test_http_redirects_to_https_when_enabled(self):
        request = self.factory.get(
            "/security-check/?source=test",
            secure=False,
        )
        middleware = SecurityMiddleware(self.response)
        response = middleware(request)

        self.assertEqual(response.status_code, 301)
        self.assertEqual(
            response["Location"],
            "https://testserver/security-check/?source=test",
        )

    @override_settings(
        SECURE_SSL_REDIRECT=True,
        SECURE_PROXY_SSL_HEADER=None,
    )
    def test_https_request_is_not_redirected(self):
        request = self.factory.get(
            "/security-check/",
            secure=True,
        )
        middleware = SecurityMiddleware(self.response)
        response = middleware(request)

        self.assertEqual(response.status_code, 200)

    @override_settings(
        SECURE_SSL_REDIRECT=True,
        SECURE_PROXY_SSL_HEADER=None,
    )
    def test_untrusted_forwarded_proto_does_not_bypass_redirect(self):
        request = self.factory.get(
            "/security-check/",
            secure=False,
            HTTP_X_FORWARDED_PROTO="https",
        )
        middleware = SecurityMiddleware(self.response)
        response = middleware(request)

        self.assertFalse(request.is_secure())
        self.assertEqual(response.status_code, 301)

    @override_settings(
        SECURE_SSL_REDIRECT=False,
        SECURE_HSTS_SECONDS=3600,
        SECURE_HSTS_INCLUDE_SUBDOMAINS=False,
        SECURE_HSTS_PRELOAD=False,
    )
    def test_hsts_is_emitted_for_https_only(self):
        middleware = SecurityMiddleware(self.response)

        secure_response = middleware(
            self.factory.get("/security-check/", secure=True)
        )
        insecure_response = middleware(
            self.factory.get("/security-check/", secure=False)
        )

        self.assertEqual(
            secure_response["Strict-Transport-Security"],
            "max-age=3600",
        )
        self.assertNotIn(
            "Strict-Transport-Security",
            insecure_response,
        )

    @override_settings(
        SECURE_SSL_REDIRECT=False,
        SECURE_CONTENT_TYPE_NOSNIFF=True,
    )
    def test_nosniff_header_is_emitted(self):
        middleware = SecurityMiddleware(self.response)
        response = middleware(
            self.factory.get("/security-check/", secure=True)
        )

        self.assertEqual(
            response["X-Content-Type-Options"],
            "nosniff",
        )

    @override_settings(X_FRAME_OPTIONS="DENY")
    def test_clickjacking_protection_header(self):
        middleware = XFrameOptionsMiddleware(self.response)
        response = middleware(
            self.factory.get("/security-check/", secure=True)
        )

        self.assertEqual(
            response["X-Frame-Options"],
            "DENY",
        )
