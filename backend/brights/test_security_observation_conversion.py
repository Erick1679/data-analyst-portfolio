"""Database-free tests for secure observation conversion."""

from dataclasses import FrozenInstanceError, replace

from django.test import SimpleTestCase

from .security_abuse_observation import AbuseObservation
from .security_observation_conversion import (
    ScopedAbuseObservation,
    convert_aggregation_to_observation,
)
from .security_request_event_aggregation import (
    RequestAggregationResult,
)


class ObservationConversionTests(SimpleTestCase):

    def aggregate(self, **changes):
        base = RequestAggregationResult(
            identity_scope_type="ACCOUNT",
            identity_scope_id="account-1",
            endpoint_category="B",
            window_start_seconds=120,
            window_end_seconds=180,
            window_seconds=60,
            request_count=5,
            authentication_failures=2,
            authorization_denials=1,
            complete=True,
            valid=True,
        )
        return replace(base, **changes)

    def test_valid_aggregation_converts(self):
        result = convert_aggregation_to_observation(self.aggregate())
        self.assertIsInstance(result, ScopedAbuseObservation)
        self.assertIsInstance(result.observation, AbuseObservation)

    def test_counters_are_preserved(self):
        result = convert_aggregation_to_observation(self.aggregate())
        self.assertEqual(
            (
                result.observation.request_count,
                result.observation.authentication_failures,
                result.observation.authorization_denials,
            ),
            (5, 2, 1),
        )

    def test_identity_context_is_preserved(self):
        result = convert_aggregation_to_observation(self.aggregate())
        self.assertEqual(result.identity_scope_type, "ACCOUNT")
        self.assertEqual(result.identity_scope_id, "account-1")

    def test_utc_boundaries_are_preserved(self):
        result = convert_aggregation_to_observation(self.aggregate())
        self.assertEqual(
            (result.window_start_seconds, result.window_end_seconds),
            (120, 180),
        )

    def test_endpoint_category_is_preserved(self):
        result = convert_aggregation_to_observation(self.aggregate())
        self.assertEqual(result.observation.endpoint_category, "B")

    def test_incomplete_aggregation_is_rejected(self):
        self.assertIsNone(convert_aggregation_to_observation(
            self.aggregate(complete=False)
        ))

    def test_invalid_aggregation_is_rejected(self):
        self.assertIsNone(convert_aggregation_to_observation(
            self.aggregate(valid=False)
        ))

    def test_missing_aggregation_is_rejected(self):
        self.assertIsNone(convert_aggregation_to_observation(None))

    def test_wrong_result_type_is_rejected(self):
        self.assertIsNone(convert_aggregation_to_observation({}))

    def test_missing_counter_is_rejected(self):
        self.assertIsNone(convert_aggregation_to_observation(
            self.aggregate(request_count=None)
        ))

    def test_boolean_counter_is_rejected(self):
        self.assertIsNone(convert_aggregation_to_observation(
            self.aggregate(authentication_failures=True)
        ))

    def test_negative_counter_is_rejected(self):
        self.assertIsNone(convert_aggregation_to_observation(
            self.aggregate(authorization_denials=-1)
        ))

    def test_authentication_count_above_requests_is_rejected(self):
        self.assertIsNone(convert_aggregation_to_observation(
            self.aggregate(authentication_failures=6)
        ))

    def test_authorization_count_above_requests_is_rejected(self):
        self.assertIsNone(convert_aggregation_to_observation(
            self.aggregate(authorization_denials=6)
        ))

    def test_overlapping_failure_counts_are_valid(self):
        result = convert_aggregation_to_observation(
            self.aggregate(
                request_count=3,
                authentication_failures=3,
                authorization_denials=3,
            )
        )
        self.assertIsNotNone(result)
        self.assertEqual(result.observation.request_count, 3)

    def test_misaligned_window_is_rejected(self):
        self.assertIsNone(convert_aggregation_to_observation(
            self.aggregate(window_start_seconds=121)
        ))

    def test_incorrect_end_boundary_is_rejected(self):
        self.assertIsNone(convert_aggregation_to_observation(
            self.aggregate(window_end_seconds=181)
        ))

    def test_boolean_window_duration_is_rejected(self):
        self.assertIsNone(convert_aggregation_to_observation(
            self.aggregate(window_seconds=True)
        ))

    def test_unhashable_scope_type_is_rejected(self):
        self.assertIsNone(convert_aggregation_to_observation(
            self.aggregate(identity_scope_type=["ACCOUNT"])
        ))

    def test_unhashable_endpoint_category_is_rejected(self):
        self.assertIsNone(convert_aggregation_to_observation(
            self.aggregate(endpoint_category={"category": "B"})
        ))

    def test_empty_complete_window_can_convert(self):
        result = convert_aggregation_to_observation(
            self.aggregate(
                request_count=0,
                authentication_failures=0,
                authorization_denials=0,
            )
        )
        self.assertIsNotNone(result)
        self.assertEqual(result.observation.request_count, 0)

    def test_scoped_observation_is_immutable(self):
        result = convert_aggregation_to_observation(self.aggregate())
        with self.assertRaises(FrozenInstanceError):
            result.identity_scope_id = "different"
