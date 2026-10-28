"""Security audit event records for The Brights Analytics."""

import uuid

from django.conf import settings
from django.db import models


class AuditEvent(models.Model):
    """Record security-relevant corporate application activity."""

    class Outcome(models.TextChoices):
        SUCCESS = "success", "Success"
        DENIED = "denied", "Denied"
        FAILURE = "failure", "Failure"

    id = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False,
    )

    organization = models.ForeignKey(
        "organizations.Organization",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="audit_events",
    )

    actor = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="security_audit_events",
    )

    action = models.CharField(
        max_length=100,
        db_index=True,
    )

    outcome = models.CharField(
        max_length=20,
        choices=Outcome.choices,
    )

    target_type = models.CharField(
        max_length=100,
        blank=True,
    )

    target_id = models.CharField(
        max_length=100,
        blank=True,
    )

    created_at = models.DateTimeField(
        auto_now_add=True,
        db_index=True,
    )

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(
                fields=["organization", "-created_at"],
                name="audit_org_created_idx",
            ),
        ]

    def __str__(self):
        return (
            f"{self.action} "
            f"({self.outcome}) "
            f"at {self.created_at}"
        )

# Authentication events are independent of organization audit records.
# Credentials, session identifiers and request metadata are not stored.
from django.conf import settings as authentication_settings


class AuthenticationEvent(models.Model):
    LOGIN_SUCCESS = "login_success"
    LOGIN_FAILURE = "login_failure"
    LOGOUT = "logout"

    EVENT_TYPES = [
        (LOGIN_SUCCESS, "Successful login"),
        (LOGIN_FAILURE, "Failed login"),
        (LOGOUT, "Logout"),
    ]

    id = models.BigAutoField(primary_key=True)

    user = models.ForeignKey(
        authentication_settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="authentication_events",
    )

    event_type = models.CharField(
        max_length=32,
        choices=EVENT_TYPES,
    )

    created_at = models.DateTimeField(
        auto_now_add=True,
        db_index=True,
    )

    class Meta:
        ordering = ("-created_at", "-id")

    def __str__(self):
        return f"Authentication event {self.pk}: {self.event_type}"
