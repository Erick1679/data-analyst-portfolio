"""Tenant-scoped dataset metadata services.

All application-facing dataset operations should use authorized
services rather than unrestricted model queries.
"""

from django.core.exceptions import PermissionDenied, ValidationError
from django.db import transaction
from django.db.models import Q
from django.http import Http404

from organizations.models import Organization
from auditlog.services import record_audit_event

from .models import CorporateDataset, DatasetAccessGrant
from .permissions import (
    DATASET_PERMISSIONS,
    can_create_dataset,
    can_manage_dataset_grants,
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

    # Record success within the same database transaction.
    # If audit recording fails, dataset creation rolls back.
    record_audit_event(
        action="dataset.created",
        outcome="success",
        organization=organization,
        actor=user,
        target_type="dataset",
        target_id=str(dataset.id),
    )

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

    # Include restricted datasets only with an explicit active grant.
    # Keep the queryset tenant-scoped and avoid duplicate results.
    restricted_ids = DatasetAccessGrant.objects.filter(
        membership=membership,
        dataset__organization=organization,
        dataset__classification="restricted",
        is_active=True,
        revoked_at__isnull=True,
    ).values("dataset_id")

    return CorporateDataset.objects.filter(
        Q(
            organization=organization,
            classification__in=allowed,
        )
        | Q(
            organization=organization,
            classification="restricted",
            id__in=restricted_ids,
        )
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


@transaction.atomic
def issue_dataset_access_grant(
    *,
    user,
    organization,
    dataset,
    membership,
    return_action=False,
):
    """Issue or reactivate a tenant-scoped restricted dataset grant."""

    if not isinstance(organization, Organization):
        raise ValidationError("A valid organization is required.")

    if not can_manage_dataset_grants(user, organization):
        raise PermissionDenied(
            "Dataset grant management is not permitted."
        )

    if not isinstance(dataset, CorporateDataset):
        raise ValidationError("A valid dataset is required.")

    if dataset.organization_id != organization.pk:
        raise PermissionDenied(
            "Dataset grant management is not permitted."
        )

    from organizations.models import OrganizationMembership

    if not isinstance(membership, OrganizationMembership):
        raise ValidationError("A valid membership is required.")

    if membership.organization_id != organization.pk:
        raise PermissionDenied(
            "Dataset grant management is not permitted."
        )

    if not membership.is_active or not membership.user.is_active:
        raise PermissionDenied(
            "Cannot grant access to an inactive member."
        )

    if dataset.classification != "restricted":
        raise ValidationError(
            "Explicit grants currently require restricted datasets."
        )

    grant = DatasetAccessGrant.objects.select_for_update().filter(
        dataset=dataset,
        membership=membership,
    ).first()

    if grant is not None and grant.is_active:
        raise ValidationError(
            "An active access grant already exists."
        )

    if grant is None:
        grant = DatasetAccessGrant(
            dataset=dataset,
            membership=membership,
            granted_by=user,
        )
        action = "dataset.grant_created"
    else:
        grant.is_active = True
        grant.revoked_at = None
        grant.granted_by = user
        action = "dataset.grant_reactivated"

    grant.full_clean()
    grant.save()

    record_audit_event(
        action=action,
        outcome="success",
        organization=organization,
        actor=user,
        target_type="dataset_access_grant",
        target_id=str(grant.id),
    )

    if return_action:
        return grant, action

    return grant


@transaction.atomic
def revoke_dataset_access_grant(
    *,
    user,
    organization,
    grant_id,
):
    """Revoke an existing tenant-scoped dataset access grant."""

    from django.utils import timezone

    if not isinstance(organization, Organization):
        raise ValidationError("A valid organization is required.")

    if not can_manage_dataset_grants(user, organization):
        raise PermissionDenied(
            "Dataset grant management is not permitted."
        )

    grant = DatasetAccessGrant.objects.select_for_update().filter(
        id=grant_id,
        dataset__organization=organization,
        membership__organization=organization,
    ).first()

    if grant is None:
        raise Http404("Access grant not found.")

    if not grant.is_active:
        raise ValidationError(
            "This access grant is already revoked."
        )

    grant.is_active = False
    grant.revoked_at = timezone.now()

    grant.full_clean()
    grant.save(update_fields=["is_active", "revoked_at"])

    record_audit_event(
        action="dataset.grant_revoked",
        outcome="success",
        organization=organization,
        actor=user,
        target_type="dataset_access_grant",
        target_id=str(grant.id),
    )

    return grant
