"""Isolated URL configuration for retail HTTP security tests.

Not included in the production URL configuration.
"""

from django.urls import path

from retail.views import branch_list, product_list

urlpatterns = [
    path(
        "test-retail/<uuid:organization_id>/products/",
        product_list,
        name="test-retail-products",
    ),
    path(
        "test-retail/<uuid:organization_id>/branches/",
        branch_list,
        name="test-retail-branches",
    ),
]
