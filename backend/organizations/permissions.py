"""Central organization-level authorization for The Brights Analytics."""

from .models import OrganizationMembership


ROLE_PERMISSIONS = {
    "owner": {
        "view_dashboard",
        "create_report",
        "manage_members",
    },
    "admin": {
        "view_dashboard",
        "create_report",
        "manage_members",
    },
    "manager": {
        "view_dashboard",
        "create_report",
    },
    "editor": {
        "view_dashboard",
        "create_report",
    },
    "analyst": {
        "view_dashboard",
        "create_report",
    },
    "auditor": {
        "view_dashboard",
    },
    "viewer": {
        "view_dashboard",
    },
}


def has_organization_permission(user, organization, permission):
    """Return True only for an authorized active membership."""

    if not getattr(user, "is_authenticated", False):
        return False

    if not getattr(user, "is_active", False):
        return False

    if not organization.is_active:
        return False

    membership = OrganizationMembership.objects.filter(
        organization=organization,
        user=user,
        is_active=True,
    ).first()

    if membership is None:
        return False

    return permission in ROLE_PERMISSIONS.get(
        membership.role, set()
    )
