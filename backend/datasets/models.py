"""Corporate dataset metadata for The Brights Analytics."""

import uuid

from django.conf import settings
from django.db import models


class CorporateDataset(models.Model):
    """Metadata for a dataset owned by one organization."""

    class Category(models.TextChoices):
        FINANCIAL = "financial", "Financial"
        OPERATIONAL = "operational", "Operational"
        SALES = "sales", "Sales"
        HUMAN_RESOURCES = "hr", "Human Resources"
        MARKETING = "marketing", "Marketing"
        OTHER = "other", "Other"

    class Classification(models.TextChoices):
        INTERNAL = "internal", "Internal"
        CONFIDENTIAL = "confidential", "Confidential"
        RESTRICTED = "restricted", "Restricted"

    class Status(models.TextChoices):
        DRAFT = "draft", "Draft"
        ACTIVE = "active", "Active"
        ARCHIVED = "archived", "Archived"

    id = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False,
    )

    organization = models.ForeignKey(
        "organizations.Organization",
        on_delete=models.PROTECT,
        related_name="datasets",
    )

    name = models.CharField(max_length=200)
    description = models.TextField(blank=True)

    category = models.CharField(
        max_length=20,
        choices=Category.choices,
        default=Category.OTHER,
    )

    classification = models.CharField(
        max_length=20,
        choices=Classification.choices,
        default=Classification.CONFIDENTIAL,
    )

    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.DRAFT,
    )

    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="created_corporate_datasets",
    )

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]
        constraints = [
            models.UniqueConstraint(
                fields=["organization", "name"],
                name="unique_dataset_name_per_organization",
            ),
        ]

    def __str__(self):
        return f"{self.organization.name}: {self.name}"


class DatasetAccessGrant(models.Model):
    """An explicit, revocable dataset access grant for a membership."""

    id = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False,
    )

    dataset = models.ForeignKey(
        CorporateDataset,
        on_delete=models.PROTECT,
        related_name="access_grants",
    )

    membership = models.ForeignKey(
        "organizations.OrganizationMembership",
        on_delete=models.PROTECT,
        related_name="dataset_access_grants",
    )

    granted_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="dataset_access_grants_issued",
    )

    is_active = models.BooleanField(default=True)

    granted_at = models.DateTimeField(auto_now_add=True)
    revoked_at = models.DateTimeField(
        null=True,
        blank=True,
    )

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["dataset", "membership"],
                name="unique_dataset_membership_grant",
            ),
        ]

    def clean(self):
        """Reject grants spanning different organizations."""
        from django.core.exceptions import ValidationError

        super().clean()

        if not self.dataset_id or not self.membership_id:
            return

        if (
            self.dataset.organization_id
            != self.membership.organization_id
        ):
            raise ValidationError(
                "Dataset and membership must belong "
                "to the same organization."
            )

    def __str__(self):
        return f"{self.dataset_id} -> {self.membership_id}"
