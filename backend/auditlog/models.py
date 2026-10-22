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
