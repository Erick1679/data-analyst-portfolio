"""Corporate dataset URL routes."""

from django.urls import path

from . import views

app_name = "datasets"

urlpatterns = [
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
