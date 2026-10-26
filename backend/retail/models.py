import uuid

from django.core.validators import MinValueValidator, RegexValidator
from django.db import models
from django.db.models import Q


class Branch(models.Model):
    """An organization-owned retail location."""

    id = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False,
    )
    organization = models.ForeignKey(
        "organizations.Organization",
        on_delete=models.PROTECT,
        related_name="retail_branches",
    )
    code = models.CharField(max_length=30)
    name = models.CharField(max_length=200)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["name", "code"]
        constraints = [
            models.UniqueConstraint(
                fields=["organization", "code"],
                name="unique_retail_branch_code_per_org",
            ),
        ]

    def __str__(self):
        return f"{self.name} ({self.code})"


class Product(models.Model):
    """An organization-owned retail product."""

    id = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False,
    )
    organization = models.ForeignKey(
        "organizations.Organization",
        on_delete=models.PROTECT,
        related_name="retail_products",
    )
    sku = models.CharField(max_length=60)
    name = models.CharField(max_length=200)
    description = models.TextField(blank=True)
    unit_price = models.DecimalField(
        max_digits=14,
        decimal_places=2,
        validators=[MinValueValidator(0)],
    )
    currency = models.CharField(
        max_length=3,
        default="KES",
        validators=[
            RegexValidator(
                regex=r"^[A-Z]{3}$",
                message="Currency must be a three-letter uppercase code.",
            ),
        ],
    )
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["name", "sku"]
        constraints = [
            models.UniqueConstraint(
                fields=["organization", "sku"],
                name="unique_retail_product_sku_per_org",
            ),
            models.CheckConstraint(
                condition=Q(unit_price__gte=0),
                name="retail_product_nonnegative_price",
            ),
        ]

    def __str__(self):
        return f"{self.name} ({self.sku})"
