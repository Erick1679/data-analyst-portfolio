"""Read-only API views for Brights Retail Intelligence."""

from functools import wraps
from django.core.exceptions import PermissionDenied
from django.http import JsonResponse
from django.shortcuts import get_object_or_404
from django.views.decorators.http import require_GET

from organizations.models import Organization

def api_login_required(view_func):
    """Return JSON 401 rather than redirecting API clients."""

    @wraps(view_func)
    def wrapped(request, *args, **kwargs):
        user = request.user

        if not (
            user.is_authenticated
            and user.is_active
        ):
            return JsonResponse(
                {"error": "Authentication required."},
                status=401,
            )

        return view_func(request, *args, **kwargs)

    return wrapped


from .services import (
    get_organization_branches,
    get_organization_products,
)


@api_login_required
@require_GET
def product_list(request, organization_id):
    """Return products for one authorized organization."""

    organization = get_object_or_404(
        Organization,
        pk=organization_id,
    )

    products = get_organization_products(
        request.user,
        organization,
    )

    results = [
        {
            "id": str(product.id),
            "sku": product.sku,
            "name": product.name,
            "unit_price": str(product.unit_price),
            "currency": product.currency,
            "is_active": product.is_active,
        }
        for product in products
    ]

    return JsonResponse({
        "organization_id": str(organization.id),
        "count": len(results),
        "results": results,
    })


@api_login_required
@require_GET
def branch_list(request, organization_id):
    """Return branches for one authorized organization."""

    organization = get_object_or_404(
        Organization,
        pk=organization_id,
    )

    branches = get_organization_branches(
        request.user,
        organization,
    )

    results = [
        {
            "id": str(branch.id),
            "code": branch.code,
            "name": branch.name,
            "is_active": branch.is_active,
        }
        for branch in branches
    ]

    return JsonResponse({
        "organization_id": str(organization.id),
        "count": len(results),
        "results": results,
    })
