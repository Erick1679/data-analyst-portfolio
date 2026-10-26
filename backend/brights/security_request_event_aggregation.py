"""Pure, isolated security request-event aggregation.

This module does not collect live requests, access databases,
read clocks, create logs, or enforce security decisions.

The caller must provide independently verified evidence.
"""

from dataclasses import dataclass
from typing import Optional

from .security_observation_windows import fixed_utc_window


ALLOWED_SCOPES = frozenset({
    "ACCOUNT",
    "ORGANIZATION",
    "API_CREDENTIAL",
    "NETWORK_PEER",
})

ALLOWED_CATEGORIES = frozenset({"A", "B", "C", "D", "E"})


@dataclass(frozen=True)
class SecurityRequestEvent:
    request_id: str
    timestamp_seconds: int
    identity_scope_type: str
    identity_scope_id: str
    endpoint_category: str
    authentication_failed: bool
    authorization_denied: bool


@dataclass(frozen=True)
class RequestAggregationResult:
    identity_scope_type: str
    identity_scope_id: str
    endpoint_category: str
    window_start_seconds: int
    window_end_seconds: int
    window_seconds: int
    request_count: Optional[int]
    authentication_failures: Optional[int]
    authorization_denials: Optional[int]
    complete: bool
    valid: bool


def _identifier(value):
    """Require a bounded, nonblank identifier."""
    return (
        type(value) is str
        and 0 < len(value) <= 128
        and value == value.strip()
        and not any(character.isspace() for character in value)
    )


def aggregate_request_events(
    events,
    *,
    duration_seconds,
    identity_scope_type,
    identity_scope_id,
    endpoint_category,
    window_start_seconds,
    complete,
):
    """Aggregate one explicitly scoped, fixed UTC window.

    Return None for malformed or contradictory input.
    Incomplete telemetry returns an invalid result with
    unknown counters, never misleading zero counts.

    The complete flag is supplied by the caller.
    This function cannot independently verify completeness.
    """
    if type(complete) is not bool:
        return None

    if (
        type(identity_scope_type) is not str
        or identity_scope_type not in ALLOWED_SCOPES
    ):
        return None

    if not _identifier(identity_scope_id):
        return None

    if (
        type(endpoint_category) is not str
        or endpoint_category not in ALLOWED_CATEGORIES
    ):
        return None

    window = fixed_utc_window(
        window_start_seconds, duration_seconds
    )

    if window is None:
        return None

    if window.start_seconds != window_start_seconds:
        return None

    if type(events) not in (tuple, list):
        return None

    def result(counts, is_complete, is_valid):
        return RequestAggregationResult(
            identity_scope_type=identity_scope_type,
            identity_scope_id=identity_scope_id,
            endpoint_category=endpoint_category,
            window_start_seconds=window.start_seconds,
            window_end_seconds=window.end_seconds,
            window_seconds=window.duration_seconds,
            request_count=counts[0],
            authentication_failures=counts[1],
            authorization_denials=counts[2],
            complete=is_complete,
            valid=is_valid,
        )

    if not complete:
        return result((None, None, None), False, False)

    # This is an isolated, bounded-batch reference utility.
    # Production-scale quotas and shared state need separate review.
    if len(events) > 10000:
        return None

    requests = {}

    for event in events:
        if type(event) is not SecurityRequestEvent:
            return None

        if not _identifier(event.request_id):
            return None

        if type(event.timestamp_seconds) is not int:
            return None

        if not window.contains(event.timestamp_seconds):
            return None

        if event.identity_scope_type != identity_scope_type:
            return None

        if event.identity_scope_id != identity_scope_id:
            return None

        if event.endpoint_category != endpoint_category:
            return None

        if type(event.authentication_failed) is not bool:
            return None

        if type(event.authorization_denied) is not bool:
            return None

        previous = requests.get(event.request_id)

        if previous is None:
            requests[event.request_id] = (
                event.timestamp_seconds,
                event.authentication_failed,
                event.authorization_denied,
            )
        else:
            previous_timestamp, auth, denial = previous

            # One authoritative request must keep one timestamp.
            # Complementary verified outcome evidence may merge.
            if previous_timestamp != event.timestamp_seconds:
                return None

            requests[event.request_id] = (
                previous_timestamp,
                auth or event.authentication_failed,
                denial or event.authorization_denied,
            )

    auth_count = sum(
        int(values[1]) for values in requests.values()
    )
    denial_count = sum(
        int(values[2]) for values in requests.values()
    )

    return result(
        (len(requests), auth_count, denial_count),
        True,
        True,
    )
