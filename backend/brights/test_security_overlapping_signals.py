"""Contract regression tests for overlapping failure counters.

These tests intentionally specify behavior that the current
evaluator does not yet fully support.

The tests do not access databases or perform enforcement.
"""

from django.test import SimpleTestCase

from .security_abuse_observation import (
    AbuseObservation,
    ObservationThresholds,
    NORMAL,
    ELEVATED,
    SUSPICIOUS,
    UNKNOWN,
    evaluate_abuse_observation,
)


class OverlappingSignalContractTests(SimpleTestCase):
    """Verify independent, per-counter validation."""

    def setUp(self):
        # Illustrative test fixtures, not production limits.
        self.thresholds = ObservationThresholds(
            request_count=100,
            authentication_failures=3,
            authorization_denials=3,
        )

    def observe(self, requests, auth_failures, denials):
        return AbuseObservation(
            endpoint_category="B",
            window_seconds=60,
            request_count=requests,
            authentication_failures=auth_failures,
            authorization_denials=denials,
        )

    def test_overlapping_counts_can_exceed_total_when_summed(self):
        observation = self.observe(
            requests=5,
            auth_failures=4,
            denials=4,
        )
        result = evaluate_abuse_observation(
            observation, self.thresholds
        )

        self.assertTrue(result.valid)
        self.assertEqual(result.level, SUSPICIOUS)
        self.assertEqual(
            result.reason_codes,
            (
                "AUTHENTICATION_FAILURE_THRESHOLD",
                "AUTHORIZATION_DENIAL_THRESHOLD",
            ),
        )

    def test_overlap_below_threshold_remains_normal(self):
        observation = self.observe(
            requests=2,
            auth_failures=2,
            denials=2,
        )
        result = evaluate_abuse_observation(
            observation, self.thresholds
        )

        self.assertTrue(result.valid)
        self.assertEqual(result.level, NORMAL)
        self.assertFalse(result.review_recommended)

    def test_authentication_failures_exceeding_requests_are_invalid(self):
        observation = self.observe(
            requests=3,
            auth_failures=4,
            denials=0,
        )
        result = evaluate_abuse_observation(
            observation, self.thresholds
        )

        self.assertFalse(result.valid)
        self.assertEqual(result.level, UNKNOWN)

    def test_authorization_denials_exceeding_requests_are_invalid(self):
        observation = self.observe(
            requests=3,
            auth_failures=0,
            denials=4,
        )
        result = evaluate_abuse_observation(
            observation, self.thresholds
        )

        self.assertFalse(result.valid)
        self.assertEqual(result.level, UNKNOWN)

    def test_independent_signal_at_exact_request_count(self):
        observation = self.observe(
            requests=3,
            auth_failures=3,
            denials=0,
        )
        result = evaluate_abuse_observation(
            observation, self.thresholds
        )

        self.assertTrue(result.valid)
        self.assertEqual(result.level, ELEVATED)
        self.assertEqual(
            result.reason_codes,
            ("AUTHENTICATION_FAILURE_THRESHOLD",),
        )
