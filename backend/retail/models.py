import uuid

from django.conf import settings
from django.core.exceptions import ValidationError
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


class Sale(models.Model):
    """A retail sale belonging to one organization and branch."""

    class Status(models.TextChoices):
        DRAFT = "draft", "Draft"
        COMPLETED = "completed", "Completed"
        VOIDED = "voided", "Voided"

    id = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False,
    )

    organization = models.ForeignKey(
        "organizations.Organization",
        on_delete=models.PROTECT,
        related_name="retail_sales",
    )

    branch = models.ForeignKey(
        Branch,
        on_delete=models.PROTECT,
        related_name="sales",
    )

    reference = models.CharField(max_length=60)

    recorded_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="recorded_retail_sales",
    )

    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.DRAFT,
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

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]

        constraints = [
            models.UniqueConstraint(
                fields=["organization", "reference"],
                name="unique_retail_sale_reference_per_org",
            ),
        ]

    def clean(self):
        super().clean()

        if self.branch_id and self.organization_id:
            if self.branch.organization_id != self.organization_id:
                raise ValidationError({
                    "branch": (
                        "Sale branch must belong "
                        "to the same organization."
                    )
                })

    def __str__(self):
        return f"{self.reference} ({self.status})"


class SaleItem(models.Model):
    """A product line with its recorded selling price."""

    id = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False,
    )

    sale = models.ForeignKey(
        Sale,
        on_delete=models.PROTECT,
        related_name="items",
    )

    product = models.ForeignKey(
        Product,
        on_delete=models.PROTECT,
        related_name="sale_items",
    )

    quantity = models.DecimalField(
        max_digits=14,
        decimal_places=3,
        validators=[MinValueValidator(0.001)],
    )

    unit_price = models.DecimalField(
        max_digits=14,
        decimal_places=2,
        validators=[MinValueValidator(0)],
    )

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["created_at", "id"]
        constraints = [
            models.CheckConstraint(
                condition=Q(quantity__gt=0),
                name="retail_saleitem_positive_quantity",
            ),
            models.CheckConstraint(
                condition=Q(unit_price__gte=0),
                name="retail_saleitem_nonnegative_price",
            ),
        ]

    def clean(self):
        super().clean()

        if not self.sale_id or not self.product_id:
            return

        product_errors = []

        if self.product.organization_id != self.sale.organization_id:
            product_errors.append(
                "Sale item product must belong "
                "to the sale organization."
            )

        if self.product.currency != self.sale.currency:
            product_errors.append(
                "Product currency must match sale currency."
            )

        if product_errors:
            raise ValidationError({
                "product": product_errors,
            })

    @property
    def line_total(self):
        return self.quantity * self.unit_price

    def __str__(self):
        return f"{self.product.sku} x {self.quantity}"


class InventoryBalance(models.Model):
    """Current stock quantity for a product at one branch."""

    id = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False,
    )

    branch = models.ForeignKey(
        Branch,
        on_delete=models.PROTECT,
        related_name="inventory_balances",
    )

    product = models.ForeignKey(
        Product,
        on_delete=models.PROTECT,
        related_name="inventory_balances",
    )

    quantity_on_hand = models.DecimalField(
        max_digits=16,
        decimal_places=3,
        default=0,
    )

    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["branch", "product"],
                name="unique_retail_branch_product_balance",
            ),
            models.CheckConstraint(
                condition=Q(quantity_on_hand__gte=0),
                name="retail_inventory_nonnegative_balance",
            ),
        ]

    def clean(self):
        super().clean()

        if not self.branch_id or not self.product_id:
            return

        if self.branch.organization_id != self.product.organization_id:
            raise ValidationError({
                "product": (
                    "Inventory product and branch must "
                    "belong to the same organization."
                )
            })

    def __str__(self):
        return f"{self.branch.code}: {self.product.sku}"


class StockMovement(models.Model):
    """An inventory movement recorded against a branch-product balance."""

    class MovementType(models.TextChoices):
        RECEIPT = "receipt", "Stock Receipt"
        SALE = "sale", "Sale"
        ADJUSTMENT_IN = "adjustment_in", "Positive Adjustment"
        ADJUSTMENT_OUT = "adjustment_out", "Negative Adjustment"

    id = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False,
    )

    balance = models.ForeignKey(
        InventoryBalance,
        on_delete=models.PROTECT,
        related_name="movements",
    )

    movement_type = models.CharField(
        max_length=20,
        choices=MovementType.choices,
    )

    quantity = models.DecimalField(
        max_digits=16,
        decimal_places=3,
        validators=[MinValueValidator(0.001)],
    )

    recorded_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="retail_stock_movements",
    )

    reference = models.CharField(
        max_length=100,
        blank=True,
    )

    notes = models.TextField(blank=True)

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at", "-id"]
        constraints = [
            models.CheckConstraint(
                condition=Q(quantity__gt=0),
                name="retail_stockmovement_positive_qty",
            ),
        ]

    def __str__(self):
        return (
            f"{self.movement_type}: "
            f"{self.balance_id} ({self.quantity})"
        )
