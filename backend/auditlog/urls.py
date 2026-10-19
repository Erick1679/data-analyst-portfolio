"""Corporate audit history routes."""

from django.urls import path

from . import views

app_name = "auditlog"

urlpatterns = [
    path(
        "",
        views.audit_history,
        name="audit-history",
    ),
]
