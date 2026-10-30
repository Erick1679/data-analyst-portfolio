"""Regression tests for conservative client-IP identification."""

from django.test import RequestFactory, SimpleTestCase

from .security_client_ip import get_network_peer_ip


class ClientIPSecurityTests(SimpleTestCase):
    """Verify network peer identification without database access."""

    def setUp(self):
        self.factory = RequestFactory()

    def test_valid_ipv4_peer(self):
        request = self.factory.get(
            "/security-check/",
            REMOTE_ADDR="192.0.2.25",
        )
        self.assertEqual(
            get_network_peer_ip(request),
            "192.0.2.25",
        )

    def test_valid_ipv6_peer(self):
        request = self.factory.get(
            "/security-check/",
            REMOTE_ADDR="2001:db8::25",
        )
        self.assertEqual(
            get_network_peer_ip(request),
            "2001:db8::25",
        )

    def test_missing_peer_address(self):
        request = self.factory.get("/security-check/")
        request.META.pop("REMOTE_ADDR", None)

        self.assertIsNone(get_network_peer_ip(request))

    def test_invalid_peer_address(self):
        request = self.factory.get(
            "/security-check/",
            REMOTE_ADDR="not-an-ip",
        )
        self.assertIsNone(get_network_peer_ip(request))

    def test_forwarded_for_cannot_spoof_peer(self):
        request = self.factory.get(
            "/security-check/",
            REMOTE_ADDR="192.0.2.25",
            HTTP_X_FORWARDED_FOR="198.51.100.99",
        )
        self.assertEqual(
            get_network_peer_ip(request),
            "192.0.2.25",
        )

    def test_other_forwarding_headers_are_ignored(self):
        request = self.factory.get(
            "/security-check/",
            REMOTE_ADDR="192.0.2.25",
            HTTP_X_REAL_IP="198.51.100.99",
            HTTP_CF_CONNECTING_IP="203.0.113.99",
        )
        self.assertEqual(
            get_network_peer_ip(request),
            "192.0.2.25",
        )

    def test_non_string_peer_address_is_rejected(self):
        request = self.factory.get("/security-check/")
        request.META["REMOTE_ADDR"] = 12345

        self.assertIsNone(get_network_peer_ip(request))

    def test_peer_with_whitespace_is_normalized(self):
        request = self.factory.get(
            "/security-check/",
            REMOTE_ADDR=" 192.0.2.25 ",
        )
        self.assertEqual(
            get_network_peer_ip(request),
            "192.0.2.25",
        )

    def test_peer_with_port_is_rejected(self):
        request = self.factory.get(
            "/security-check/",
            REMOTE_ADDR="192.0.2.25:8080",
        )
        self.assertIsNone(get_network_peer_ip(request))
