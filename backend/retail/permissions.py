"""Organization-scoped permissions for Brights Retail Intelligence."""

from datasets.permissions import get_active_membership


RETAIL_PERMISSIONS = {
    "owner": frozenset({
        "view_retail",
        "manage_products",
        "manage_branches",
        "manage_inventory",
        "record_sales",
    }),
    "admin": frozenset({
        "view_retail",
        "manage_products",
        "manage_branches",
        "manage_inventory",
        "record_sales",
    }),
    "manager": frozenset({
        "view_retail",
        "manage_products",
        "manage_branches",
        "manage_inventory",
        "record_sales",
    }),
    "editor": frozenset({
        "view_retail",
        "manage_products",
        "manage_inventory",
        "record_sales",
    }),
    "analyst": frozenset({
        "view_retail",
    }),
    "auditor": frozenset({
        "view_retail",
    }),
    "viewer": frozenset({
        "view_retail",
    }),
}


def has_retail_permission(user, organization, permission):
    """Check an active user's retail permission within one organization."""

    membership = get_active_membership(user, organization)

    if membership is None:
        return False

    return permission in RETAIL_PERMISSIONS.get(
        membership.role,
        frozenset(),
    )


def can_access_retail_record(user, record, permission="view_retail"):
    """Authorize access through the retail record's owning organization."""

    organization = getattr(record, "organization", None)

    if organization is None:
        return False

    return has_retail_permission(user, organization, permission)
