"""Tenant-scoped dataset metadata services.

All application-facing dataset operations should use authorized
services rather than unrestricted model queries.
"""

from django.core.exceptions import PermissionDenied, ValidationError
from django.db import transaction
from django.http import Http404

from organizations.models import Organization

from .models import CorporateDataset
from .permissions import (
    DATASET_PERMISSIONS,
    can_create_dataset,
    can_view_dataset,
    get_active_membership,
)


@transaction.atomic
def create_dataset(
    *,
    user,
    organization,
    name,
    description="",
    category="other",
    classification="confidential",
):
    """Create dataset metadata after checking organization access."""

    if not isinstance(organization, Organization):
        raise ValidationError("A valid organization is required.")

    if not can_create_dataset(user, organization, classification):
        raise PermissionDenied("Dataset creation is not permitted.")

    dataset = CorporateDataset(
        organization=organization,
        created_by=user,
        name=name,
        description=description,
        category=category,
        classification=classification,
    )

    dataset.full_clean()
    dataset.save()

    return dataset


def list_accessible_datasets(*, user, organization):
    """Return only datasets visible within the specified tenant."""

    if not isinstance(organization, Organization):
        raise ValidationError("A valid organization is required.")

    membership = get_active_membership(user, organization)

    if membership is None:
        return CorporateDataset.objects.none()

    allowed = DATASET_PERMISSIONS.get(
        membership.role,
        set(),
    )

    return CorporateDataset.objects.filter(
        organization=organization,
        classification__in=allowed,
    )


def get_accessible_dataset(*, user, organization, dataset_id):
    """Resolve dataset without exposing other tenants' records."""

    dataset = CorporateDataset.objects.filter(
        organization=organization,
        id=dataset_id,
    ).first()

    if dataset is None:
        raise Http404("Dataset not found.")

    if not can_view_dataset(user, dataset):
        raise Http404("Dataset not found.")

    return dataset
