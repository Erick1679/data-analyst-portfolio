"""Isolated regression tests for the security observation pipeline.

The tests exercise trusted-looking synthetic evidence only.
They do not prove real telemetry authenticity or completeness.

No live collection, database access, network access,
production thresholds, or enforcement.
"""

from dataclasses import replace

from django.test import SimpleTestCase

from .security_request_event_aggregation import (
    SecurityRequestEvent,
    aggregate_request_events,
)
from .security_observation_conversion import (
    convert_aggregation_to_observation,
)
from .security_abuse_observation import (
    ObservationThresholds,
    evaluate_abuse_observation,
)


class SecurityObservationPipelineTests(SimpleTestCase):
    """Validate isolated aggregation, conversion and evaluation."""

    def event(self, request_id, auth=False, denial=False):
        return SecurityRequestEvent(
            request_id=request_id,
            timestamp_seconds=120,
            identity_scope_type="ACCOUNT",
            identity_scope_id="account-1",
            endpoint_category="B",
            authentication_failed=auth,
            authorization_denied=denial,
        )

    def aggregate(self, events, complete=True):
        return aggregate_request_events(
            events,
            duration_seconds=60,
            identity_scope_type="ACCOUNT",
            identity_scope_id="account-1",
            endpoint_category="B",
            window_start_seconds=120,
            complete=complete,
        )

    def thresholds(self):
        # Illustrative fixtures; never production limits.
        return ObservationThresholds(
            request_count=100,
            authentication_failures=2,
            authorization_denials=2,
        )

    def test_complete_aggregation_converts(self):
        raw = self.aggregate([
            self.event("a", auth=True),
            self.event("b", denial=True),
            self.event("c", auth=True, denial=True),
        ])

        self.assertIsNotNone(raw)
        self.assertTrue(raw.valid)
        self.assertTrue(raw.complete)

        scoped = convert_aggregation_to_observation(raw)

        self.assertIsNotNone(scoped)
        self.assertEqual(scoped.observation.request_count, 3)
        self.assertEqual(
            scoped.observation.authentication_failures, 2
        )
        self.assertEqual(
            scoped.observation.authorization_denials, 2
        )

    def test_two_signals_produce_review_recommendation(self):
        raw = self.aggregate([
            self.event("a", auth=True),
            self.event("b", denial=True),
            self.event("c", auth=True, denial=True),
        ])

        scoped = convert_aggregation_to_observation(raw)
        self.assertIsNotNone(scoped)

        result = evaluate_abuse_observation(
            scoped.observation,
            self.thresholds(),
        )

        self.assertTrue(result.valid)
        self.assertEqual(result.level, "SUSPICIOUS")
        self.assertTrue(result.review_recommended)
        self.assertEqual(
            result.reason_codes,
            (
                "AUTHENTICATION_FAILURE_THRESHOLD",
                "AUTHORIZATION_DENIAL_THRESHOLD",
            ),
        )

    def test_identity_and_window_context_preserved(self):
        raw = self.aggregate([self.event("a")])
        scoped = convert_aggregation_to_observation(raw)

        self.assertIsNotNone(scoped)
        self.assertEqual(
            scoped.identity_scope_type, "ACCOUNT"
        )
        self.assertEqual(
            scoped.identity_scope_id, "account-1"
        )
        self.assertEqual(
            scoped.window_start_seconds, 120
        )
        self.assertEqual(
            scoped.window_end_seconds, 180
        )
        self.assertEqual(
            scoped.observation.window_seconds, 60
        )

    def test_duplicates_and_overlapping_signals(self):
        raw = self.aggregate([
            self.event("a", auth=True),
            self.event("a", auth=True),
            self.event("a", denial=True),
        ])

        self.assertIsNotNone(raw)
        self.assertTrue(raw.valid)
        self.assertEqual(
            (
                raw.request_count,
                raw.authentication_failures,
                raw.authorization_denials,
            ),
            (1, 1, 1),
        )

        scoped = convert_aggregation_to_observation(raw)
        self.assertIsNotNone(scoped)
        self.assertEqual(
            scoped.observation.request_count, 1
        )

    def test_incomplete_telemetry_cannot_convert(self):
        raw = self.aggregate([], complete=False)

        self.assertIsNotNone(raw)
        self.assertFalse(raw.valid)
        self.assertFalse(raw.complete)
        self.assertIsNone(raw.request_count)

        scoped = convert_aggregation_to_observation(raw)

        self.assertIsNone(scoped)

    def test_cross_scope_evidence_rejected(self):
        event = replace(
            self.event("a"),
            identity_scope_id="another-account",
        )

        raw = self.aggregate([event])

        self.assertIsNone(raw)
        self.assertIsNone(
            convert_aggregation_to_observation(raw)
        )

    def test_forged_counter_inconsistency_rejected(self):
        raw = self.aggregate([
            self.event("a", auth=True),
            self.event("b", auth=True),
        ])

        self.assertIsNotNone(raw)

        forged = replace(
            raw,
            request_count=1,
            authentication_failures=2,
            valid=True,
            complete=True,
        )

        self.assertIsNone(
            convert_aggregation_to_observation(forged)
        )

    def test_complete_zero_event_window(self):
        raw = self.aggregate([])

        self.assertIsNotNone(raw)
        self.assertTrue(raw.valid)
        self.assertTrue(raw.complete)

        scoped = convert_aggregation_to_observation(raw)
        self.assertIsNotNone(scoped)

        self.assertEqual(
            (
                scoped.observation.request_count,
                scoped.observation.authentication_failures,
                scoped.observation.authorization_denials,
            ),
            (0, 0, 0),
        )

        result = evaluate_abuse_observation(
            scoped.observation,
            self.thresholds(),
        )

        self.assertTrue(result.valid)
        self.assertEqual(result.level, "NORMAL")
        self.assertFalse(result.review_recommended)
