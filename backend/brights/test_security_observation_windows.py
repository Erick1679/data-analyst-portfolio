"""Database-free tests for fixed UTC observation windows."""

from dataclasses import FrozenInstanceError

from django.test import SimpleTestCase

from .security_observation_windows import fixed_utc_window


class ObservationWindowTests(SimpleTestCase):
    """Check deterministic UTC boundary calculations."""

    def test_timestamp_inside_first_window(self):
        window = fixed_utc_window(59, 60)
        self.assertEqual((window.start_seconds, window.end_seconds), (0, 60))

    def test_timestamp_at_boundary_starts_next_window(self):
        window = fixed_utc_window(60, 60)
        self.assertEqual((window.start_seconds, window.end_seconds), (60, 120))

    def test_timestamp_before_boundary_remains_previous_window(self):
        window = fixed_utc_window(119, 60)
        self.assertEqual((window.start_seconds, window.end_seconds), (60, 120))

    def test_timestamp_at_second_boundary(self):
        window = fixed_utc_window(120, 60)
        self.assertEqual((window.start_seconds, window.end_seconds), (120, 180))

    def test_end_boundary_is_exclusive(self):
        window = fixed_utc_window(119, 60)
        self.assertTrue(window.contains(119))
        self.assertFalse(window.contains(120))

    def test_start_boundary_is_inclusive(self):
        window = fixed_utc_window(120, 60)
        self.assertTrue(window.contains(120))

    def test_zero_duration_rejected(self):
        self.assertIsNone(fixed_utc_window(100, 0))

    def test_negative_duration_rejected(self):
        self.assertIsNone(fixed_utc_window(100, -60))

    def test_boolean_duration_rejected(self):
        self.assertIsNone(fixed_utc_window(100, True))

    def test_fractional_duration_rejected(self):
        self.assertIsNone(fixed_utc_window(100, 60.5))

    def test_boolean_timestamp_rejected(self):
        self.assertIsNone(fixed_utc_window(True, 60))

    def test_fractional_timestamp_rejected(self):
        self.assertIsNone(fixed_utc_window(100.5, 60))

    def test_negative_timestamp_alignment(self):
        window = fixed_utc_window(-1, 60)
        self.assertEqual((window.start_seconds, window.end_seconds), (-60, 0))

    def test_epoch_timestamp_alignment(self):
        window = fixed_utc_window(0, 60)
        self.assertEqual((window.start_seconds, window.end_seconds), (0, 60))

    def test_nonstandard_window_duration(self):
        window = fixed_utc_window(301, 300)
        self.assertEqual((window.start_seconds, window.end_seconds), (300, 600))

    def test_duration_is_recorded(self):
        window = fixed_utc_window(301, 300)
        self.assertEqual(window.duration_seconds, 300)

    def test_window_is_immutable(self):
        window = fixed_utc_window(301, 300)
        with self.assertRaises(FrozenInstanceError):
            window.start_seconds = 0

    def test_deterministic_window_calculation(self):
        self.assertEqual(
            fixed_utc_window(123456789, 60),
            fixed_utc_window(123456789, 60),
        )

    def test_contains_rejects_non_integer_timestamp(self):
        window = fixed_utc_window(120, 60)
        self.assertFalse(window.contains("120"))
        self.assertFalse(window.contains(True))

    def test_invalid_timestamp_returns_none(self):
        self.assertIsNone(fixed_utc_window(None, 60))
