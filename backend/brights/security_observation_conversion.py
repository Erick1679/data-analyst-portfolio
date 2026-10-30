"""Pure conversion of complete request aggregates to observations.

Preserves validated scope and UTC window context separately
from the existing AbuseObservation object.

No evaluation, enforcement, collection, database or network I/O.
"""

from dataclasses import dataclass

from .security_abuse_observation import AbuseObservation
from .security_observation_windows import fixed_utc_window
from .security_request_event_aggregation import (
    ALLOWED_CATEGORIES,
    ALLOWED_SCOPES,
    RequestAggregationResult,
)


@dataclass(frozen=True)
class ScopedAbuseObservation:
    """Validated observation together with its security context."""

    observation: AbuseObservation
    identity_scope_type: str
    identity_scope_id: str
    window_start_seconds: int
    window_end_seconds: int


def _identifier(value):
    """Match the aggregator's bounded identifier requirements."""
    return (
        type(value) is str
        and 0 < len(value) <= 128
        and value == value.strip()
        and not any(character.isspace() for character in value)
    )


def convert_aggregation_to_observation(aggregation):
    """Convert only independently validated, complete aggregates.

    Return None for invalid or incomplete evidence.

    This revalidates the data contract, not its provenance.
    A caller must separately establish that telemetry and
    identity information came from trusted sources.
    """
    if type(aggregation) is not RequestAggregationResult:
        return None

    if aggregation.valid is not True:
        return None

    if aggregation.complete is not True:
        return None

    if (
        type(aggregation.identity_scope_type) is not str
        or aggregation.identity_scope_type not in ALLOWED_SCOPES
    ):
        return None

    if not _identifier(aggregation.identity_scope_id):
        return None

    if (
        type(aggregation.endpoint_category) is not str
        or aggregation.endpoint_category not in ALLOWED_CATEGORIES
    ):
        return None

    window = fixed_utc_window(
        aggregation.window_start_seconds,
        aggregation.window_seconds,
    )

    if window is None:
        return None

    if (
        window.start_seconds != aggregation.window_start_seconds
        or type(aggregation.window_end_seconds) is not int
        or window.end_seconds != aggregation.window_end_seconds
    ):
        return None

    counts = (
        aggregation.request_count,
        aggregation.authentication_failures,
        aggregation.authorization_denials,
    )

    if any(type(value) is not int or value < 0 for value in counts):
        return None

    requests, authentication_failures, authorization_denials = counts

    if authentication_failures > requests:
        return None

    if authorization_denials > requests:
        return None

    observation = AbuseObservation(
        endpoint_category=aggregation.endpoint_category,
        window_seconds=window.duration_seconds,
        request_count=requests,
        authentication_failures=authentication_failures,
        authorization_denials=authorization_denials,
    )

    return ScopedAbuseObservation(
        observation=observation,
        identity_scope_type=aggregation.identity_scope_type,
        identity_scope_id=aggregation.identity_scope_id,
        window_start_seconds=window.start_seconds,
        window_end_seconds=window.end_seconds,
    )
