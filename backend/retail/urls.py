"""URL definitions for Brights Retail Intelligence."""

from django.urls import path

from .views import branch_list, product_list

app_name = "retail"

urlpatterns = [
    path(
        "products/",
        product_list,
        name="product-list",
    ),
    path(
        "branches/",
        branch_list,
        name="branch-list",
    ),
]
