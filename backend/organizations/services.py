"""Tenant-scoped corporate membership-management services."""

from django.contrib.auth import get_user_model
from django.core.exceptions import PermissionDenied, ValidationError
from django.db import transaction
from django.http import Http404

from auditlog.services import record_audit_event

from .models import Organization, OrganizationMembership
from .permissions import has_organization_permission


@transaction.atomic
def create_organization_membership(
    *,
    actor,
    organization,
    user,
    role="viewer",
    position="other",
    department="",
):
    """Create an authorized, audited corporate membership."""

    if not isinstance(organization, Organization):
        raise ValidationError(
            "A valid organization is required."
        )

    if not has_organization_permission(
        actor,
        organization,
        "manage_members",
    ):
        raise PermissionDenied(
            "Membership management is not permitted."
        )

    actor_membership = OrganizationMembership.objects.get(
        organization=organization,
        user=actor,
        is_active=True,
    )

    if role == "owner" and actor_membership.role != "owner":
        raise PermissionDenied(
            "Only an organization owner can appoint another owner."
        )

    if not isinstance(user, get_user_model()):
        raise ValidationError("A valid user is required.")

    if user.pk is None or not user.is_active:
        raise ValidationError(
            "The recipient must be an active saved user."
        )

    if OrganizationMembership.objects.filter(
        organization=organization,
        user=user,
    ).exists():
        raise ValidationError(
            "This user already has an organization membership."
        )

    membership = OrganizationMembership(
        organization=organization,
        user=user,
        role=role,
        position=position,
        department=department,
    )

    membership.full_clean()
    membership.save()

    record_audit_event(
        action="membership.changed",
        outcome="success",
        organization=organization,
        actor=actor,
        target_type="organization_membership",
        target_id=str(membership.pk),
    )

    return membership


@transaction.atomic
def change_organization_membership_role(
    *,
    actor,
    organization,
    membership_id,
    role,
):
    """Change a tenant membership role with owner safeguards."""

    if not isinstance(organization, Organization):
        raise ValidationError(
            "A valid organization is required."
        )

    if not has_organization_permission(
        actor,
        organization,
        "manage_members",
    ):
        raise PermissionDenied(
            "Membership management is not permitted."
        )

    # Serialize owner-role changes on databases supporting
    # SELECT FOR UPDATE, including PostgreSQL.
    organization = Organization.objects.select_for_update().get(
        pk=organization.pk,
    )

    actor_membership = OrganizationMembership.objects.get(
        organization=organization,
        user=actor,
        is_active=True,
    )

    membership = OrganizationMembership.objects.select_for_update().filter(
        id=membership_id,
        organization=organization,
    ).first()

    if membership is None:
        raise Http404("Membership not found.")

    valid_roles = {
        value
        for value, label in OrganizationMembership.AccessRole.choices
    }

    if not isinstance(role, str) or role not in valid_roles:
        raise ValidationError("Invalid membership role.")

    # Administrators may not appoint or demote owners.
    if actor_membership.role != "owner":
        if role == "owner" or membership.role == "owner":
            raise PermissionDenied(
                "Only owners may manage owner roles."
            )

    if membership.role == role:
        raise ValidationError(
            "Membership already has this role."
        )

    if membership.role == "owner" and role != "owner":
        remaining = OrganizationMembership.objects.filter(
            organization=organization,
            role="owner",
            is_active=True,
            user__is_active=True,
        ).exclude(pk=membership.pk).exists()

        if membership.is_active and membership.user.is_active:
            if not remaining:
                raise ValidationError(
                    "The last active owner cannot be demoted."
                )

    membership.role = role
    membership.full_clean()
    membership.save(update_fields=["role"])

    record_audit_event(
        action="membership.changed",
        outcome="success",
        organization=organization,
        actor=actor,
        target_type="organization_membership",
        target_id=str(membership.pk),
    )

    return membership


@transaction.atomic
def deactivate_organization_membership(
    *,
    actor,
    organization,
    membership_id,
):
    """Deactivate a tenant membership without orphaning ownership."""

    if not isinstance(organization, Organization):
        raise ValidationError(
            "A valid organization is required."
        )

    if not has_organization_permission(
        actor,
        organization,
        "manage_members",
    ):
        raise PermissionDenied(
            "Membership management is not permitted."
        )

    # Lock the organization row where supported, so ownership
    # decisions can be serialized across membership operations.
    organization = Organization.objects.select_for_update().get(
        pk=organization.pk,
    )

    actor_membership = OrganizationMembership.objects.get(
        organization=organization,
        user=actor,
        is_active=True,
    )

    membership = (
        OrganizationMembership.objects.select_for_update()
        .filter(
            pk=membership_id,
            organization=organization,
        )
        .first()
    )

    if membership is None:
        raise Http404("Membership not found.")

    if membership.role == "owner":
        if actor_membership.role != "owner":
            raise PermissionDenied(
                "Only owners may deactivate owner memberships."
            )

    if not membership.is_active:
        raise ValidationError(
            "Membership is already inactive."
        )

    if membership.role == "owner" and membership.user.is_active:
        another_owner_exists = (
            OrganizationMembership.objects.filter(
                organization=organization,
                role="owner",
                is_active=True,
                user__is_active=True,
            )
            .exclude(pk=membership.pk)
            .exists()
        )

        if not another_owner_exists:
            raise ValidationError(
                "The last active owner cannot be deactivated."
            )

    # Revoke existing restricted dataset grants before completing
    # membership deactivation. All changes share one transaction.
    from django.utils import timezone
    from datasets.models import DatasetAccessGrant

    active_grants = list(
        DatasetAccessGrant.objects.select_for_update().filter(
            membership=membership,
            dataset__organization=organization,
            is_active=True,
        )
    )

    revoked_at = timezone.now()

    for grant in active_grants:
        grant.is_active = False
        grant.revoked_at = revoked_at
        grant.full_clean()
        grant.save(update_fields=["is_active", "revoked_at"])

        record_audit_event(
            action="dataset.grant_revoked",
            outcome="success",
            organization=organization,
            actor=actor,
            target_type="dataset_access_grant",
            target_id=str(grant.pk),
        )

    membership.is_active = False
    membership.full_clean()
    membership.save(update_fields=["is_active"])

    record_audit_event(
        action="membership.changed",
        outcome="success",
        organization=organization,
        actor=actor,
        target_type="organization_membership",
        target_id=str(membership.pk),
    )

    return membership
