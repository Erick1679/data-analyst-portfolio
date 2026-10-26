"""Database-free tests for pure abuse observations."""

from dataclasses import FrozenInstanceError

from django.test import SimpleTestCase

from .security_abuse_observation import (
    AbuseObservation,
    ObservationThresholds,
    ELEVATED,
    NORMAL,
    SUSPICIOUS,
    UNKNOWN,
    evaluate_abuse_observation,
)


class AbuseObservationTests(SimpleTestCase):
    """Illustrative test thresholds are not production limits."""

    def setUp(self):
        self.thresholds = ObservationThresholds(
            request_count=100,
            authentication_failures=10,
            authorization_denials=8,
        )

    def observe(
        self,
        requests=20,
        auth_failures=0,
        denials=0,
        category="B",
        window=60,
    ):
        return AbuseObservation(
            endpoint_category=category,
            window_seconds=window,
            request_count=requests,
            authentication_failures=auth_failures,
            authorization_denials=denials,
        )

    def test_normal_observation(self):
        result = evaluate_abuse_observation(
            self.observe(), self.thresholds
        )
        self.assertEqual(result.level, NORMAL)
        self.assertTrue(result.valid)
        self.assertEqual(result.reason_codes, ())
        self.assertFalse(result.review_recommended)

    def test_request_volume_signal(self):
        result = evaluate_abuse_observation(
            self.observe(requests=100), self.thresholds
        )
        self.assertEqual(result.level, ELEVATED)
        self.assertEqual(
            result.reason_codes,
            ("REQUEST_COUNT_THRESHOLD",),
        )

    def test_authentication_failure_signal(self):
        result = evaluate_abuse_observation(
            self.observe(
                requests=30, auth_failures=10
            ),
            self.thresholds,
        )
        self.assertEqual(result.level, ELEVATED)
        self.assertEqual(
            result.reason_codes,
            ("AUTHENTICATION_FAILURE_THRESHOLD",),
        )

    def test_authorization_denial_signal(self):
        result = evaluate_abuse_observation(
            self.observe(requests=20, denials=8),
            self.thresholds,
        )
        self.assertEqual(result.level, ELEVATED)

    def test_multiple_independent_signals(self):
        result = evaluate_abuse_observation(
            self.observe(
                requests=100,
                auth_failures=10,
                denials=8,
            ),
            self.thresholds,
        )
        self.assertEqual(result.level, SUSPICIOUS)
        self.assertTrue(result.review_recommended)
        self.assertEqual(len(result.reason_codes), 3)

    def test_missing_thresholds_are_unknown(self):
        result = evaluate_abuse_observation(self.observe())
        self.assertEqual(result.level, UNKNOWN)
        self.assertFalse(result.valid)

    def test_missing_observation_is_unknown(self):
        result = evaluate_abuse_observation(
            None, self.thresholds
        )
        self.assertEqual(result.level, UNKNOWN)

    def test_negative_counts_are_unknown(self):
        result = evaluate_abuse_observation(
            self.observe(requests=-1), self.thresholds
        )
        self.assertEqual(result.level, UNKNOWN)

    def test_boolean_counts_are_rejected(self):
        result = evaluate_abuse_observation(
            self.observe(requests=True), self.thresholds
        )
        self.assertEqual(result.level, UNKNOWN)

    def test_non_integer_counts_are_rejected(self):
        result = evaluate_abuse_observation(
            self.observe(requests=10.5), self.thresholds
        )
        self.assertEqual(result.level, UNKNOWN)

    def test_impossible_failure_counts_are_unknown(self):
        result = evaluate_abuse_observation(
            self.observe(
                requests=5,
                auth_failures=4,
                denials=4,
            ),
            self.thresholds,
        )
        self.assertEqual(result.level, UNKNOWN)

    def test_zero_window_is_unknown(self):
        result = evaluate_abuse_observation(
            self.observe(window=0), self.thresholds
        )
        self.assertEqual(result.level, UNKNOWN)

    def test_unknown_endpoint_category(self):
        result = evaluate_abuse_observation(
            self.observe(category="UNCLASSIFIED"),
            self.thresholds,
        )
        self.assertEqual(result.level, UNKNOWN)

    def test_invalid_threshold_is_unknown(self):
        thresholds = ObservationThresholds(
            request_count=0,
            authentication_failures=10,
            authorization_denials=8,
        )
        result = evaluate_abuse_observation(
            self.observe(), thresholds
        )
        self.assertEqual(result.level, UNKNOWN)

    def test_deterministic_results(self):
        observation = self.observe(requests=100)
        first = evaluate_abuse_observation(
            observation, self.thresholds
        )
        second = evaluate_abuse_observation(
            observation, self.thresholds
        )
        self.assertEqual(first, second)

    def test_observation_is_immutable(self):
        observation = self.observe()
        with self.assertRaises(FrozenInstanceError):
            observation.request_count = 500

    def test_result_is_immutable(self):
        result = evaluate_abuse_observation(
            self.observe(), self.thresholds
        )
        with self.assertRaises(FrozenInstanceError):
            result.level = SUSPICIOUS

    def test_unapproved_categories_are_unknown(self):
        for category in ("", "F", None, 123):
            with self.subTest(category=category):
                result = evaluate_abuse_observation(
                    self.observe(category=category),
                    self.thresholds,
                )
                self.assertEqual(result.level, UNKNOWN)

    def test_zero_requests_are_valid(self):
        result = evaluate_abuse_observation(
            self.observe(requests=0), self.thresholds
        )
        self.assertEqual(result.level, NORMAL)
        self.assertTrue(result.valid)

    def test_single_signal_never_recommends_review(self):
        result = evaluate_abuse_observation(
            self.observe(requests=150), self.thresholds
        )
        self.assertFalse(result.review_recommended)
