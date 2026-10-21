"""Secure HTTP endpoints for corporate membership management."""

import json

from django.contrib.auth import get_user_model
from django.core.exceptions import PermissionDenied, ValidationError
from django.db import OperationalError, connection
from django.http import Http404, JsonResponse
from django.views.decorators.http import require_POST

from datasets.grant_views import is_sqlite_lock, sqlite_lock_response

from .models import Organization, OrganizationMembership
from .permissions import has_organization_permission
from .services import (
    create_organization_membership,
    change_organization_membership_role,
    deactivate_organization_membership,
)


def resolve_membership_context(request, organization_id):
    """Authenticate and authorize access to membership management."""

    if not request.user.is_authenticated:
        return None, JsonResponse(
            {"detail": "Authentication required."},
            status=401,
        )

    organization = Organization.objects.filter(
        pk=organization_id,
        is_active=True,
    ).first()

    if organization is None:
        raise Http404("Organization not found.")

    # Conceal organizations outside the caller's active membership.
    if not has_organization_permission(
        request.user,
        organization,
        "view_dashboard",
    ):
        raise Http404("Organization not found.")

    if not has_organization_permission(
        request.user,
        organization,
        "manage_members",
    ):
        return None, JsonResponse(
            {"detail": "Membership management is not permitted."},
            status=403,
        )

    return organization, None


def parse_membership_payload(request):
    """Validate a small JSON payload for membership creation."""

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

    if set(payload) != {"user_id", "role"}:
        return None, JsonResponse(
            {"detail": "user_id and role are required."},
            status=400,
        )

    user_id = payload["user_id"]
    role = payload["role"]

    if type(user_id) is not int or user_id <= 0:
        return None, JsonResponse(
            {"detail": "user_id must be a positive integer."},
            status=400,
        )

    if not isinstance(role, str) or not role:
        return None, JsonResponse(
            {"detail": "role must be a nonempty string."},
            status=400,
        )

    return (user_id, role), None


@require_POST
def membership_list(request, organization_id):
    """Create an audited membership within the authorized organization."""

    try:
        organization, error = resolve_membership_context(
            request,
            organization_id,
        )

        if error is not None:
            return error

        payload, error = parse_membership_payload(request)

        if error is not None:
            return error

        user_id, role = payload

        recipient = get_user_model().objects.filter(
            pk=user_id,
            is_active=True,
        ).first()

        if recipient is None:
            raise Http404("User not found.")

        membership = create_organization_membership(
            actor=request.user,
            organization=organization,
            user=recipient,
            role=role,
        )

    except OperationalError as error:
        if connection.vendor != "sqlite" or not is_sqlite_lock(error):
            raise

        return sqlite_lock_response()

    except PermissionDenied:
        return JsonResponse(
            {"detail": "Membership management is not permitted."},
            status=403,
        )

    except ValidationError as error:
        return JsonResponse(
            {"errors": error.messages},
            status=400,
        )

    return JsonResponse(
        {
            "id": membership.pk,
            "organization_id": str(organization.pk),
            "user_id": membership.user_id,
            "role": membership.role,
            "is_active": membership.is_active,
        },
        status=201,
    )


@require_POST
def membership_role_change(request, organization_id, membership_id):
    """Change an authorized tenant membership role and audit the result."""

    try:
        organization, error = resolve_membership_context(
            request,
            organization_id,
        )

        if error is not None:
            return error

        # Conceal memberships belonging to other organizations.
        if not OrganizationMembership.objects.filter(
            pk=membership_id,
            organization=organization,
        ).exists():
            raise Http404("Membership not found.")

        if request.content_type != "application/json":
            return JsonResponse(
                {"detail": "Content type must be application/json."},
                status=415,
            )

        max_body_size = 16384
        declared_length = request.META.get("CONTENT_LENGTH")

        if declared_length:
            try:
                length = int(declared_length)
            except (TypeError, ValueError):
                return JsonResponse(
                    {"detail": "Invalid Content-Length header."},
                    status=400,
                )

            if length < 0:
                return JsonResponse(
                    {"detail": "Invalid Content-Length header."},
                    status=400,
                )

            if length > max_body_size:
                return JsonResponse(
                    {"detail": "Request body exceeds the permitted size."},
                    status=413,
                )

        if len(request.body) > max_body_size:
            return JsonResponse(
                {"detail": "Request body exceeds the permitted size."},
                status=413,
            )

        try:
            payload = json.loads(request.body)
        except (ValueError, UnicodeDecodeError):
            return JsonResponse(
                {"detail": "Invalid JSON request."},
                status=400,
            )

        if not isinstance(payload, dict) or set(payload) != {"role"}:
            return JsonResponse(
                {"detail": "Exactly one role field is required."},
                status=400,
            )

        role = payload["role"]

        if not isinstance(role, str) or not role:
            return JsonResponse(
                {"detail": "role must be a nonempty string."},
                status=400,
            )

        membership = change_organization_membership_role(
            actor=request.user,
            organization=organization,
            membership_id=membership_id,
            role=role,
        )

    except OperationalError as error:
        if connection.vendor != "sqlite" or not is_sqlite_lock(error):
            raise

        return sqlite_lock_response()

    except PermissionDenied:
        return JsonResponse(
            {"detail": "Membership management is not permitted."},
            status=403,
        )

    except ValidationError as error:
        return JsonResponse(
            {"errors": error.messages},
            status=400,
        )

    return JsonResponse(
        {
            "id": membership.pk,
            "organization_id": str(organization.pk),
            "user_id": membership.user_id,
            "role": membership.role,
            "is_active": membership.is_active,
        },
        status=200,
    )


@require_POST
def membership_deactivate(request, organization_id, membership_id):
    """Deactivate an authorized tenant membership and audit the result."""

    try:
        organization, error = resolve_membership_context(
            request,
            organization_id,
        )

        if error is not None:
            return error

        # Prevent cross-organization membership enumeration.
        if not OrganizationMembership.objects.filter(
            pk=membership_id,
            organization=organization,
        ).exists():
            raise Http404("Membership not found.")

        if request.content_type != "application/json":
            return JsonResponse(
                {"detail": "Content type must be application/json."},
                status=415,
            )

        max_body_size = 16384
        declared_length = request.META.get("CONTENT_LENGTH")

        if declared_length:
            try:
                length = int(declared_length)
            except (TypeError, ValueError):
                return JsonResponse(
                    {"detail": "Invalid Content-Length header."},
                    status=400,
                )

            if length < 0:
                return JsonResponse(
                    {"detail": "Invalid Content-Length header."},
                    status=400,
                )

            if length > max_body_size:
                return JsonResponse(
                    {"detail": "Request body exceeds the permitted size."},
                    status=413,
                )

        if len(request.body) > max_body_size:
            return JsonResponse(
                {"detail": "Request body exceeds the permitted size."},
                status=413,
            )

        try:
            payload = json.loads(request.body)
        except (ValueError, UnicodeDecodeError):
            return JsonResponse(
                {"detail": "Invalid JSON request."},
                status=400,
            )

        if not isinstance(payload, dict) or payload:
            return JsonResponse(
                {"detail": "An empty JSON object is required."},
                status=400,
            )

        membership = deactivate_organization_membership(
            actor=request.user,
            organization=organization,
            membership_id=membership_id,
        )

    except OperationalError as error:
        if connection.vendor != "sqlite" or not is_sqlite_lock(error):
            raise

        return sqlite_lock_response()

    except PermissionDenied:
        return JsonResponse(
            {"detail": "Membership management is not permitted."},
            status=403,
        )

    except ValidationError as error:
        return JsonResponse(
            {"errors": error.messages},
            status=400,
        )

    return JsonResponse(
        {
            "id": membership.pk,
            "organization_id": str(organization.pk),
            "user_id": membership.user_id,
            "role": membership.role,
            "is_active": membership.is_active,
        },
        status=200,
    )
