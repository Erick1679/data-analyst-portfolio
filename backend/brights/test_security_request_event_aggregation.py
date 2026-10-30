"""Database-free tests for isolated request aggregation."""

from dataclasses import FrozenInstanceError, replace

from django.test import SimpleTestCase

from .security_request_event_aggregation import (
    SecurityRequestEvent,
    aggregate_request_events,
)


class RequestAggregationTests(SimpleTestCase):

    def event(self, request_id="request-1", **changes):
        base = SecurityRequestEvent(
            request_id=request_id,
            timestamp_seconds=120,
            identity_scope_type="ACCOUNT",
            identity_scope_id="account-1",
            endpoint_category="B",
            authentication_failed=False,
            authorization_denied=False,
        )
        return replace(base, **changes)

    def aggregate(self, events, **changes):
        options = dict(
            duration_seconds=60,
            identity_scope_type="ACCOUNT",
            identity_scope_id="account-1",
            endpoint_category="B",
            window_start_seconds=120,
            complete=True,
        )
        options.update(changes)
        return aggregate_request_events(events, **options)

    def test_single_request(self):
        result = self.aggregate([self.event()])
        self.assertTrue(result.valid)
        self.assertEqual(result.request_count, 1)

    def test_multiple_distinct_requests(self):
        result = self.aggregate([
            self.event("a"),
            self.event("b"),
            self.event("c"),
        ])
        self.assertEqual(result.request_count, 3)

    def test_duplicate_request_is_counted_once(self):
        record = self.event()
        result = self.aggregate([record, record, record])
        self.assertEqual(result.request_count, 1)

    def test_both_failure_signals_on_one_request(self):
        record = self.event(
            authentication_failed=True,
            authorization_denied=True,
        )
        result = self.aggregate([record])
        self.assertEqual(
            (result.request_count,
             result.authentication_failures,
             result.authorization_denials),
            (1, 1, 1),
        )

    def test_complementary_duplicate_signals_merge(self):
        a = self.event(authentication_failed=True)
        b = self.event(authorization_denied=True)
        result = self.aggregate([a, b])
        self.assertEqual(
            (result.request_count,
             result.authentication_failures,
             result.authorization_denials),
            (1, 1, 1),
        )

    def test_event_order_does_not_affect_result(self):
        a = self.event("a", authentication_failed=True)
        b = self.event("b", authorization_denied=True)
        self.assertEqual(
            self.aggregate([a, b]),
            self.aggregate([b, a]),
        )

    def test_start_boundary_is_inclusive(self):
        result = self.aggregate([self.event()])
        self.assertEqual(result.window_start_seconds, 120)
        self.assertEqual(result.window_end_seconds, 180)

    def test_end_boundary_is_exclusive(self):
        record = self.event(timestamp_seconds=180)
        self.assertIsNone(self.aggregate([record]))

    def test_wrong_identity_scope_is_rejected(self):
        record = self.event(identity_scope_id="account-2")
        self.assertIsNone(self.aggregate([record]))

    def test_wrong_category_is_rejected(self):
        record = self.event(endpoint_category="C")
        self.assertIsNone(self.aggregate([record]))

    def test_conflicting_request_timestamp_is_rejected(self):
        a = self.event()
        b = self.event(timestamp_seconds=121)
        self.assertIsNone(self.aggregate([a, b]))

    def test_boolean_timestamp_is_rejected(self):
        record = self.event(timestamp_seconds=True)
        self.assertIsNone(self.aggregate([record]))

    def test_invalid_duration_is_rejected(self):
        self.assertIsNone(
            self.aggregate([], duration_seconds=0)
        )

    def test_misaligned_window_is_rejected(self):
        self.assertIsNone(
            self.aggregate([], window_start_seconds=121)
        )

    def test_invalid_security_signal_is_rejected(self):
        record = self.event(authentication_failed=1)
        self.assertIsNone(self.aggregate([record]))

    def test_incomplete_telemetry_has_unknown_counts(self):
        result = self.aggregate([], complete=False)
        self.assertFalse(result.valid)
        self.assertFalse(result.complete)
        self.assertIsNone(result.request_count)

    def test_complete_empty_window_has_zero_counts(self):
        result = self.aggregate([])
        self.assertTrue(result.valid)
        self.assertEqual(
            (result.request_count,
             result.authentication_failures,
             result.authorization_denials),
            (0, 0, 0),
        )

    def test_invalid_scope_identifier_is_rejected(self):
        self.assertIsNone(
            self.aggregate([], identity_scope_id="  ")
        )

    def test_result_is_immutable(self):
        result = self.aggregate([])
        with self.assertRaises(FrozenInstanceError):
            result.request_count = 20

    def test_request_event_is_immutable(self):
        record = self.event()
        with self.assertRaises(FrozenInstanceError):
            record.request_id = "another"

    def test_batch_limit_rejects_oversized_input(self):
        records = [self.event()] * 10001
        self.assertIsNone(self.aggregate(records))

    def test_invalid_scope_type_is_rejected(self):
        self.assertIsNone(
            self.aggregate([], identity_scope_type="UNKNOWN")
        )

    def test_list_scope_type_is_rejected_without_exception(self):
        self.assertIsNone(
            self.aggregate([], identity_scope_type=["ACCOUNT"])
        )

    def test_dictionary_scope_type_is_rejected_without_exception(self):
        self.assertIsNone(
            self.aggregate(
                [],
                identity_scope_type={"type": "ACCOUNT"},
            )
        )

    def test_list_endpoint_category_is_rejected_without_exception(self):
        self.assertIsNone(
            self.aggregate([], endpoint_category=["B"])
        )

    def test_dictionary_endpoint_category_is_rejected_without_exception(self):
        self.assertIsNone(
            self.aggregate(
                [],
                endpoint_category={"category": "B"},
            )
        )
