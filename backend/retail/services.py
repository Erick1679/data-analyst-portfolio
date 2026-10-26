"""Organization-scoped services for Brights Retail Intelligence."""

from django.core.exceptions import PermissionDenied

from .models import Branch, Product
from .permissions import has_retail_permission


def get_organization_products(user, organization):
    """Return products only when retail viewing is authorized."""

    if not has_retail_permission(
        user,
        organization,
        "view_retail",
    ):
        raise PermissionDenied(
            "You do not have permission to view retail products."
        )

    return Product.objects.filter(
        organization=organization,
    ).order_by("name", "sku")


def get_organization_branches(user, organization):
    """Return branches only when retail viewing is authorized."""

    if not has_retail_permission(
        user,
        organization,
        "view_retail",
    ):
        raise PermissionDenied(
            "You do not have permission to view retail branches."
        )

    return Branch.objects.filter(
        organization=organization,
    ).order_by("name", "code")
