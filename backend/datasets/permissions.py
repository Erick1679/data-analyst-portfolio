"""Deny-by-default dataset authorization for The Brights Analytics."""

from organizations.models import OrganizationMembership


DATASET_PERMISSIONS = {
    "owner": {"internal", "confidential"},
    "admin": {"internal", "confidential"},
    "manager": {"internal", "confidential"},
    "editor": {"internal", "confidential"},
    "analyst": {"internal", "confidential"},
    "auditor": {"internal", "confidential"},
    "viewer": {"internal"},
}

DATASET_CREATORS = frozenset({
    "owner", "admin", "manager", "editor", "analyst",
})

RESTRICTED_CREATORS = frozenset({"owner", "admin"})


def get_active_membership(user, organization):
    """Resolve an active membership without bypassing tenant boundaries."""

    if not getattr(user, "is_authenticated", False):
        return None

    if not getattr(user, "is_active", False):
        return None

    if not organization.is_active:
        return None

    return OrganizationMembership.objects.filter(
        organization=organization,
        user=user,
        is_active=True,
    ).first()


def can_create_dataset(user, organization, classification="confidential"):
    """Check authorization to create dataset metadata."""

    membership = get_active_membership(user, organization)

    if membership is None:
        return False

    if classification not in {"internal", "confidential", "restricted"}:
        return False

    if classification == "restricted":
        return membership.role in RESTRICTED_CREATORS

    return membership.role in DATASET_CREATORS


def can_view_dataset(user, dataset):
    """Check ownership context, active membership, and classification."""

    membership = get_active_membership(
        user,
        dataset.organization,
    )

    if membership is None:
        return False

    # Restricted access requires a future explicit grant mechanism.
    # No role alone grants restricted dataset visibility.
    if dataset.classification == "restricted":
        return False

    return dataset.classification in DATASET_PERMISSIONS.get(
        membership.role,
        set(),
    )
