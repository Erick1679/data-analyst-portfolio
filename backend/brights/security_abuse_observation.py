"""Pure, non-enforcing security observation evaluation.

This module is an isolated development component.

Thresholds must be supplied explicitly by the caller.
No production thresholds are defined or approved here.

No database, network, caching, logging, or request access.
No throttling, authorization, or blocking decisions.
"""

from dataclasses import dataclass

from .security_endpoint_risk import (
    A_CANDIDATE,
    B,
    C,
    D_CANDIDATE,
    E,
    UNCLASSIFIED,
)


NORMAL = "NORMAL"
ELEVATED = "ELEVATED"
SUSPICIOUS = "SUSPICIOUS"
UNKNOWN = "UNKNOWN"

SUPPORTED_CATEGORIES = frozenset({
    A_CANDIDATE, B, C, D_CANDIDATE, E,
})


@dataclass(frozen=True)
class AbuseObservation:
    """Counters collected in one externally defined window."""

    endpoint_category: str
    window_seconds: int
    request_count: int
    authentication_failures: int
    authorization_denials: int


@dataclass(frozen=True)
class ObservationThresholds:
    """Illustrative test thresholds; not production approval."""

    request_count: int
    authentication_failures: int
    authorization_denials: int


@dataclass(frozen=True)
class ObservationResult:
    """Explanation only; never an enforcement instruction."""

    level: str
    reason_codes: tuple[str, ...]
    review_recommended: bool
    valid: bool


def _positive_integer(value):
    return type(value) is int and value > 0


def _nonnegative_integer(value):
    return type(value) is int and value >= 0


def evaluate_abuse_observation(observation, thresholds=None):
    """Evaluate pre-collected evidence without side effects.

    Returns UNKNOWN on invalid evidence or missing thresholds.

    One met signal produces ELEVATED; two or more independent
    met signals produce SUSPICIOUS.

    Thresholds describe illustrative window-count comparisons,
    not production-safe rates or approved enforcement limits.
    """
    unknown = ObservationResult(
        level=UNKNOWN,
        reason_codes=("INVALID_OR_UNAPPROVED_INPUT",),
        review_recommended=False,
        valid=False,
    )

    if not isinstance(observation, AbuseObservation):
        return unknown

    if not isinstance(thresholds, ObservationThresholds):
        return unknown

    if observation.endpoint_category not in SUPPORTED_CATEGORIES:
        return unknown

    if not _positive_integer(observation.window_seconds):
        return unknown

    if not all((
        _nonnegative_integer(observation.request_count),
        _nonnegative_integer(observation.authentication_failures),
        _nonnegative_integer(observation.authorization_denials),
    )):
        return unknown

    if (
        observation.authentication_failures
        > observation.request_count
        or observation.authorization_denials
        > observation.request_count
    ):
        return unknown

    if not all((
        _positive_integer(thresholds.request_count),
        _positive_integer(thresholds.authentication_failures),
        _positive_integer(thresholds.authorization_denials),
    )):
        return unknown

    reasons = []

    if observation.request_count >= thresholds.request_count:
        reasons.append("REQUEST_COUNT_THRESHOLD")

    if (
        observation.authentication_failures
        >= thresholds.authentication_failures
    ):
        reasons.append("AUTHENTICATION_FAILURE_THRESHOLD")

    if (
        observation.authorization_denials
        >= thresholds.authorization_denials
    ):
        reasons.append("AUTHORIZATION_DENIAL_THRESHOLD")

    if len(reasons) >= 2:
        level = SUSPICIOUS
    elif reasons:
        level = ELEVATED
    else:
        level = NORMAL

    return ObservationResult(
        level=level,
        reason_codes=tuple(reasons),
        review_recommended=(level == SUSPICIOUS),
        valid=True,
    )
