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

    # Return only the 50 most recent audit events.
    events = events[:50]

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
        "results": results,
    })
