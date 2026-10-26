"""Corporate account URL routes."""

from django.urls import include, path

from . import views
from . import membership_views

app_name = "organizations"

urlpatterns = [
    path(
        "<uuid:organization_id>/memberships/",
        membership_views.membership_list,
        name="membership-list",
    ),
    path(
        "<uuid:organization_id>/memberships/<int:membership_id>/role/",
        membership_views.membership_role_change,
        name="membership-role-change",
    ),
    path(
        "<uuid:organization_id>/memberships/<int:membership_id>/deactivate/",
        membership_views.membership_deactivate,
        name="membership-deactivate",
    ),
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
        "<uuid:organization_id>/retail/",
        include("retail.urls"),
    ),
    path(
        "<uuid:organization_id>/audit/",
        include("auditlog.urls"),
    ),
]
