"""Corporate dataset URL routes."""

from django.urls import path

from . import views, grant_views

app_name = "datasets"

urlpatterns = [
    path(
        "<uuid:dataset_id>/grants/",
        grant_views.grant_list,
        name="grant-list",
    ),
    path(
        "<uuid:dataset_id>/grants/<uuid:grant_id>/revoke/",
        grant_views.grant_revoke,
        name="grant-revoke",
    ),
    path(
        "",
        views.dataset_list,
        name="dataset-list",
    ),
    path(
        "<uuid:dataset_id>/",
        views.dataset_detail,
        name="dataset-detail",
    ),
]
