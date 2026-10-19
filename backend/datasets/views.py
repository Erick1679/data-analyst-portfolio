"""Protected dataset metadata API endpoints."""

import json

from django.core.exceptions import PermissionDenied, ValidationError
from django.http import Http404, JsonResponse
from django.views.decorators.http import require_GET, require_http_methods

from organizations.models import Organization

from .permissions import get_active_membership
from .services import (
    create_dataset,
    get_accessible_dataset,
    list_accessible_datasets,
)


@require_http_methods(["GET", "POST"])
def dataset_list(request, organization_id):
    """List accessible metadata or create authorized dataset metadata."""

    if not request.user.is_authenticated:
        return JsonResponse(
            {"detail": "Authentication required."},
            status=401,
        )

    organization = Organization.objects.filter(
        id=organization_id,
        is_active=True,
    ).first()

    if organization is None:
        raise Http404("Organization not found.")

    if get_active_membership(request.user, organization) is None:
        raise Http404("Organization not found.")

    if request.method == "GET":
        datasets = list_accessible_datasets(
            user=request.user,
            organization=organization,
        )

        results = [
            {
                "id": str(dataset.id),
                "name": dataset.name,
                "category": dataset.category,
                "classification": dataset.classification,
                "status": dataset.status,
            }
            for dataset in datasets
        ]

        return JsonResponse({
            "organization_id": str(organization.id),
            "count": len(results),
            "results": results,
        })

    if request.content_type != "application/json":
        return JsonResponse(
            {"detail": "Content type must be application/json."},
            status=415,
        )

    max_body_size = 16384

    # Check the declared size before reading the request body.
    declared_length = request.META.get("CONTENT_LENGTH")

    if declared_length:
        try:
            content_length = int(declared_length)
        except (TypeError, ValueError):
            return JsonResponse(
                {"detail": "Invalid Content-Length header."},
                status=400,
            )

        if content_length < 0:
            return JsonResponse(
                {"detail": "Invalid Content-Length header."},
                status=400,
            )

        if content_length > max_body_size:
            return JsonResponse(
                {"detail": "Request body exceeds the permitted size."},
                status=413,
            )

    # Retain the actual-body check as a secondary safeguard.
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

    if not isinstance(payload, dict):
        return JsonResponse(
            {"detail": "JSON object required."},
            status=400,
        )

    allowed_fields = {
        "name", "description", "category", "classification"
    }

    if set(payload) - allowed_fields:
        return JsonResponse(
            {"detail": "Unsupported fields supplied."},
            status=400,
        )

    # Reject malformed JSON types before Django model coercion.
    field_types = {
        "name": str,
        "description": str,
        "category": str,
        "classification": str,
    }

    for field, expected_type in field_types.items():
        if field in payload and not isinstance(
            payload[field], expected_type
        ):
            return JsonResponse(
                {"detail": f"{field} must be a string."},
                status=400,
            )

    name = payload.get("name", "")

    if not name.strip():
        return JsonResponse(
            {"detail": "Dataset name is required."},
            status=400,
        )

    if len(name) > 200:
        return JsonResponse(
            {"detail": "Dataset name exceeds 200 characters."},
            status=400,
        )

    try:
        dataset = create_dataset(
            user=request.user,
            organization=organization,
            name=payload.get("name", ""),
            description=payload.get("description", ""),
            category=payload.get("category", "other"),
            classification=payload.get(
                "classification", "confidential"
            ),
        )
    except PermissionDenied:
        return JsonResponse(
            {"detail": "Dataset creation is not permitted."},
            status=403,
        )
    except ValidationError as error:
        return JsonResponse(
            {"errors": error.message_dict if hasattr(
                error, "message_dict"
            ) else error.messages},
            status=400,
        )

    return JsonResponse(
        {
            "id": str(dataset.id),
            "organization_id": str(organization.id),
            "name": dataset.name,
            "classification": dataset.classification,
            "status": dataset.status,
        },
        status=201,
    )


@require_GET
def dataset_detail(request, organization_id, dataset_id):
    """Return metadata only for a dataset the user may access."""

    if not request.user.is_authenticated:
        return JsonResponse(
            {"detail": "Authentication required."},
            status=401,
        )

    organization = Organization.objects.filter(
        id=organization_id,
        is_active=True,
    ).first()

    if organization is None:
        raise Http404("Dataset not found.")

    dataset = get_accessible_dataset(
        user=request.user,
        organization=organization,
        dataset_id=dataset_id,
    )

    return JsonResponse({
        "id": str(dataset.id),
        "name": dataset.name,
        "description": dataset.description,
        "category": dataset.category,
        "classification": dataset.classification,
        "status": dataset.status,
        "organization_id": str(organization.id),
    })
