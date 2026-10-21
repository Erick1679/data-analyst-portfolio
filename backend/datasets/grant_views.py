"""Secure HTTP endpoints for restricted dataset access grants."""

import json

from django.core.exceptions import PermissionDenied, ValidationError
from django.db import OperationalError, connection
from django.http import Http404, JsonResponse
from django.views.decorators.http import require_POST

from organizations.models import Organization, OrganizationMembership

from .models import CorporateDataset, DatasetAccessGrant
from .permissions import (
    can_manage_dataset_grants,
    get_active_membership,
)
from .services import (
    issue_dataset_access_grant,
    revoke_dataset_access_grant,
)



def is_sqlite_lock(error):
    """Recognize SQLite locking errors without masking other failures."""

    message = str(error).lower()

    return (
        "database is locked" in message
        or "database table is locked" in message
        or "database schema is locked" in message
    )


def sqlite_lock_response():
    """Return a sanitized, retryable database-contention response."""

    response = JsonResponse(
        {
            "detail": (
                "The operation is temporarily unavailable. "
                "Please retry shortly."
            )
        },
        status=503,
    )
    response["Retry-After"] = "1"
    return response


def resolve_context(request, organization_id, dataset_id):
    """Authenticate and resolve a tenant-scoped dataset."""

    if not request.user.is_authenticated:
        return None, JsonResponse(
            {"detail": "Authentication required."},
            status=401,
        )

    organization = Organization.objects.filter(
        id=organization_id,
        is_active=True,
    ).first()

    if organization is None:
        raise Http404("Dataset not found.")

    if get_active_membership(request.user, organization) is None:
        raise Http404("Dataset not found.")

    dataset = CorporateDataset.objects.filter(
        id=dataset_id,
        organization=organization,
    ).first()

    if dataset is None:
        raise Http404("Dataset not found.")

    if not can_manage_dataset_grants(request.user, organization):
        return None, JsonResponse(
            {"detail": "Grant management is not permitted."},
            status=403,
        )

    return (organization, dataset), None


def parse_grant_payload(request):
    """Validate a small JSON request containing a membership ID."""

    if request.content_type != "application/json":
        return None, JsonResponse(
            {"detail": "Content type must be application/json."},
            status=415,
        )

    max_body_size = 16384
    declared_length = request.META.get("CONTENT_LENGTH")

    if declared_length:
        try:
            length = int(declared_length)
        except (TypeError, ValueError):
            return None, JsonResponse(
                {"detail": "Invalid Content-Length header."},
                status=400,
            )

        if length < 0:
            return None, JsonResponse(
                {"detail": "Invalid Content-Length header."},
                status=400,
            )

        if length > max_body_size:
            return None, JsonResponse(
                {"detail": "Request body exceeds the permitted size."},
                status=413,
            )

    if len(request.body) > max_body_size:
        return None, JsonResponse(
            {"detail": "Request body exceeds the permitted size."},
            status=413,
        )

    try:
        payload = json.loads(request.body)
    except (ValueError, UnicodeDecodeError):
        return None, JsonResponse(
            {"detail": "Invalid JSON request."},
            status=400,
        )

    if not isinstance(payload, dict):
        return None, JsonResponse(
            {"detail": "JSON object required."},
            status=400,
        )

    if set(payload) != {"membership_id"}:
        return None, JsonResponse(
            {"detail": "membership_id is required."},
            status=400,
        )

    membership_id = payload["membership_id"]

    if type(membership_id) is not int or membership_id <= 0:
        return None, JsonResponse(
            {"detail": "membership_id must be a positive integer."},
            status=400,
        )

    return membership_id, None


@require_POST
def grant_list(request, organization_id, dataset_id):
    """Issue or reactivate a restricted dataset access grant."""

    context, error = resolve_context(
        request, organization_id, dataset_id
    )

    if error is not None:
        return error

    organization, dataset = context

    membership_id, error = parse_grant_payload(request)

    if error is not None:
        return error

    membership = OrganizationMembership.objects.filter(
        id=membership_id,
        organization=organization,
    ).first()

    if membership is None:
        raise Http404("Membership not found.")

    try:
        grant, action = issue_dataset_access_grant(
            user=request.user,
            organization=organization,
            dataset=dataset,
            membership=membership,
            return_action=True,
        )
    except OperationalError as error:
        if connection.vendor != "sqlite" or not is_sqlite_lock(error):
            raise

        return sqlite_lock_response()
    except PermissionDenied:
        return JsonResponse(
            {"detail": "Grant management is not permitted."},
            status=403,
        )
    except ValidationError as error:
        return JsonResponse(
            {"errors": error.messages},
            status=400,
        )

    return JsonResponse(
        {
            "id": str(grant.id),
            "dataset_id": str(dataset.id),
            "membership_id": membership.id,
            "is_active": grant.is_active,
        },
        status=201 if action == "dataset.grant_created" else 200,
    )


@require_POST
def grant_revoke(request, organization_id, dataset_id, grant_id):
    """Revoke a grant only within its matching tenant and dataset."""

    context, error = resolve_context(
        request, organization_id, dataset_id
    )

    if error is not None:
        return error

    organization, dataset = context

    if not DatasetAccessGrant.objects.filter(
        id=grant_id,
        dataset=dataset,
        membership__organization=organization,
    ).exists():
        raise Http404("Access grant not found.")

    try:
        grant = revoke_dataset_access_grant(
            user=request.user,
            organization=organization,
            grant_id=grant_id,
        )
    except OperationalError as error:
        if connection.vendor != "sqlite" or not is_sqlite_lock(error):
            raise

        return sqlite_lock_response()
    except PermissionDenied:
        return JsonResponse(
            {"detail": "Grant management is not permitted."},
            status=403,
        )
    except ValidationError as error:
        return JsonResponse(
            {"errors": error.messages},
            status=400,
        )

    return JsonResponse({
        "id": str(grant.id),
        "is_active": grant.is_active,
        "revoked_at": grant.revoked_at.isoformat(),
    })
