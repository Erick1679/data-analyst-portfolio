"""Read-only corporate audit history API."""

from django.core.exceptions import PermissionDenied
from django.http import Http404, JsonResponse
from django.views.decorators.http import require_GET

from organizations.models import Organization

from .services import list_organization_audit_events


@require_GET
def audit_history(request, organization_id):
    """Return tenant-scoped audit history to authorized users."""

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
        raise Http404("Audit history not found.")

    try:
        events = list_organization_audit_events(
            user=request.user,
            organization=organization,
        )
    except PermissionDenied:
        raise Http404("Audit history not found.")

    # Validate pagination before evaluating the queryset.
    page_value = request.GET.get("page", "1")

    if (
        not isinstance(page_value, str)
        or not page_value.isascii()
        or not page_value.isdecimal()
        or len(page_value) > 9
    ):
        return JsonResponse(
            {"detail": "Invalid page number."},
            status=400,
        )

    page = int(page_value)

    if page < 1:
        return JsonResponse(
            {"detail": "Page number must be positive."},
            status=400,
        )

    page_size = 50
    offset = (page - 1) * page_size

    # Fetch one extra event to determine whether another page exists.
    page_events = list(
        events[offset:offset + page_size + 1]
    )

    has_next = len(page_events) > page_size
    events = page_events[:page_size]

    results = [
        {
            "id": str(event.id),
            "action": event.action,
            "outcome": event.outcome,
            "target_type": event.target_type,
            "target_id": event.target_id,
            "created_at": event.created_at.isoformat(),
        }
        for event in events
    ]

    return JsonResponse({
        "organization_id": str(organization.id),
        "count": len(results),
        "page": page,
        "page_size": page_size,
        "has_next": has_next,
        "results": results,
    })
