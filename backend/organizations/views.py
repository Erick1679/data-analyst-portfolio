"""Protected corporate dashboard endpoints."""

from django.http import Http404, JsonResponse
from django.views.decorators.http import require_GET

from .models import Organization
from .permissions import has_organization_permission


@require_GET
def corporate_dashboard(request, organization_id):
    """Return a minimal dashboard only to authorized members."""

    if not request.user.is_authenticated:
        return JsonResponse(
            {"detail": "Authentication required."},
            status=401,
        )

    try:
        organization = Organization.objects.get(
            id=organization_id,
            is_active=True,
        )
    except Organization.DoesNotExist:
        raise Http404

    if not has_organization_permission(
        request.user,
        organization,
        "view_dashboard",
    ):
        raise Http404

    return JsonResponse({
        "organization_id": str(organization.id),
        "organization_name": organization.name,
        "dashboard": "Corporate dashboard access granted",
    })
