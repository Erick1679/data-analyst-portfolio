"""Side-effect-free endpoint risk classification.

This module describes proposed endpoint sensitivity.
It does not authorize requests, enforce limits,
access databases, or inspect request headers.

A_CANDIDATE and D_CANDIDATE require further review
before they are approved for runtime enforcement.

Inputs use explicit application and handler identifiers,
not substring matches against arbitrary URL paths.
"""

from types import MappingProxyType


UNCLASSIFIED = "UNCLASSIFIED"

A_CANDIDATE = "A_CANDIDATE"
B = "B"
C = "C"
D_CANDIDATE = "D_CANDIDATE"
E = "E"


# Mappings based on the committed endpoint design.
# Categories are proposed, not production-approved rules.
_ENDPOINT_RISKS = MappingProxyType({
    ("analytics", "dashboard", "GET"): A_CANDIDATE,
    ("analytics", "indicator_api", "GET"): A_CANDIDATE,
    ("analytics", "places_api", "GET"): A_CANDIDATE,

    ("organizations", "corporate_dashboard", "GET"): B,

    ("retail", "product_list", "GET"): B,
    ("retail", "branch_list", "GET"): B,

    ("datasets", "dataset_list", "GET"): B,
    ("datasets", "dataset_list", "POST"): D_CANDIDATE,
    ("datasets", "dataset_detail", "GET"): B,

    ("datasets", "grant_list", "POST"): E,
    ("datasets", "grant_revoke", "POST"): E,

    ("organizations", "membership_list", "POST"): E,
    ("organizations", "membership_role_change", "POST"): E,
    ("organizations", "membership_deactivate", "POST"): E,

    ("auditlog", "audit_history", "GET"): E,
})


def classify_endpoint_risk(app_label, handler_name, http_method):
    """Return the proposed risk category or UNCLASSIFIED.

    The application and handler identifiers must match an
    explicitly reviewed mapping.

    HTTP method matching is case-insensitive and accepts
    surrounding whitespace.

    Invalid, unknown, or unsupported inputs are unclassified.

    Classification must never be used as an authorization
    decision or as a production blocking rule.
    """
    if not all(
        isinstance(value, str)
        for value in (app_label, handler_name, http_method)
    ):
        return UNCLASSIFIED

    method = http_method.strip().upper()

    if not method:
        return UNCLASSIFIED

    return _ENDPOINT_RISKS.get(
        (app_label, handler_name, method),
        UNCLASSIFIED,
    )
