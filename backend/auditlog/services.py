"""Controlled security audit event recording services."""

from django.contrib.auth import get_user_model
from django.core.exceptions import PermissionDenied, ValidationError
from django.db import transaction

from organizations.models import Organization

from .models import AuditEvent
from .permissions import can_view_audit_events


ALLOWED_AUDIT_ACTIONS = frozenset({
    "dataset.created",
    "dataset.creation_denied",
    "dataset.viewed",
    "dataset.access_denied",
    "membership.changed",
})

ALLOWED_OUTCOMES = frozenset({
    "success",
    "denied",
    "failure",
})


@transaction.atomic
def record_audit_event(
    *,
    action,
    outcome,
    organization=None,
    actor=None,
    target_type="",
    target_id="",
):
    """Create validated audit metadata without recording payloads."""

    if not isinstance(action, str):
        raise ValidationError("Audit action must be a string.")

    if action not in ALLOWED_AUDIT_ACTIONS:
        raise ValidationError("Unsupported audit action.")

    if not isinstance(outcome, str):
        raise ValidationError("Audit outcome must be a string.")

    if outcome not in ALLOWED_OUTCOMES:
        raise ValidationError("Unsupported audit outcome.")

    if organization is not None:
        if not isinstance(organization, Organization):
            raise ValidationError(
                "A valid organization instance is required."
            )

        if organization.pk is None:
            raise ValidationError(
                "Organization must already be saved."
            )

    if actor is not None:
        if not isinstance(actor, get_user_model()):
            raise ValidationError(
                "A valid user instance is required."
            )

        if actor.pk is None:
            raise ValidationError(
                "Actor must already be saved."
            )

    for field_name, value in {
        "target_type": target_type,
        "target_id": target_id,
    }.items():
        if not isinstance(value, str):
            raise ValidationError(
                f"{field_name} must be a string."
            )

        if len(value) > 100:
            raise ValidationError(
                f"{field_name} exceeds 100 characters."
            )

    event = AuditEvent(
        action=action,
        outcome=outcome,
        organization=organization,
        actor=actor,
        target_type=target_type,
        target_id=target_id,
    )

    event.full_clean()
    event.save()

    return event



def list_organization_audit_events(*, user, organization):
    """Return audit history only for an authorized organization member.

    This service returns a lazy queryset. Database-level tenant
    filtering ensures that events from other organizations are
    excluded from the result.
    """

    if not isinstance(organization, Organization):
        raise PermissionDenied(
            "Audit history access is not permitted."
        )

    if not can_view_audit_events(user, organization):
        raise PermissionDenied(
            "Audit history access is not permitted."
        )

    return AuditEvent.objects.filter(
        organization=organization,
    ).order_by("-created_at", "-id")
