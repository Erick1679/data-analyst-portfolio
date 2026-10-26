"""Pure fixed-duration UTC observation-window calculations.

Uses integer Unix timestamps measured in seconds.

The returned interval includes start_seconds and excludes
end_seconds. No collection or enforcement is performed.
"""

from dataclasses import dataclass


@dataclass(frozen=True)
class ObservationWindow:
    """One aligned half-open UTC window."""

    start_seconds: int
    end_seconds: int
    duration_seconds: int

    def contains(self, timestamp_seconds):
        """Return whether an integer timestamp belongs here."""
        return (
            type(timestamp_seconds) is int
            and self.start_seconds <= timestamp_seconds
            < self.end_seconds
        )


def fixed_utc_window(timestamp_seconds, duration_seconds):
    """Return an aligned observation window, or None.

    Timestamp and duration must be integer seconds.
    Negative Unix timestamps are supported.

    Invalid values return None. No system clock is read.
    """
    if type(timestamp_seconds) is not int:
        return None

    if type(duration_seconds) is not int:
        return None

    if duration_seconds <= 0:
        return None

    start = (timestamp_seconds // duration_seconds) * duration_seconds

    return ObservationWindow(
        start_seconds=start,
        end_seconds=start + duration_seconds,
        duration_seconds=duration_seconds,
    )
