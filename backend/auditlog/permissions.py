"""Tenant-scoped audit log access permissions."""

from organizations.models import Organization
from datasets.permissions import get_active_membership


AUDIT_READ_ROLES = frozenset({
    "owner",
    "admin",
    "auditor",
})


def can_view_audit_events(user, organization):
    """Allow audit access only to authorized active members."""

    if not isinstance(organization, Organization):
        return False

    membership = get_active_membership(
        user,
        organization,
    )

    if membership is None:
        return False

    return membership.role in AUDIT_READ_ROLES
