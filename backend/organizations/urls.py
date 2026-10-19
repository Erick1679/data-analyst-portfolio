"""Corporate account URL routes."""

from django.urls import include, path

from . import views

app_name = "organizations"

urlpatterns = [
    path(
        "<uuid:organization_id>/dashboard/",
        views.corporate_dashboard,
        name="corporate-dashboard",
    ),
    path(
        "<uuid:organization_id>/datasets/",
        include("datasets.urls"),
    ),
    path(
        "<uuid:organization_id>/audit/",
        include("auditlog.urls"),
    ),
]
