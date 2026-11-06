"""Service-level tests for atomic inventory transactions."""

import uuid
from decimal import Decimal
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.core.exceptions import PermissionDenied, ValidationError
from django.test import TestCase

from auditlog.models import AuditEvent
from organizations.models import Organization, OrganizationMembership
from retail.models import Branch, InventoryBalance, Product, StockMovement
from retail.services import (
    InsufficientStockError,
    adjust_stock,
    receive_stock,
    reconcile_inventory_balances,
)


class InventoryTransactionServiceTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        User = get_user_model()
        cls.owner = User.objects.create_user(username="inventory_tx_owner")
        cls.viewer = User.objects.create_user(username="inventory_tx_viewer")
        cls.organization = Organization.objects.create(
            name="Inventory Transaction Organization",
            slug="inventory-transaction-organization",
        )
        OrganizationMembership.objects.create(
            organization=cls.organization,
            user=cls.owner,
            role="owner",
        )
        OrganizationMembership.objects.create(
            organization=cls.organization,
            user=cls.viewer,
            role="viewer",
        )
        cls.branch = Branch.objects.create(
            organization=cls.organization,
            code="MAIN",
            name="Main Branch",
        )
        cls.product = Product.objects.create(
            organization=cls.organization,
            sku="INV-001",
            name="Inventory Product",
            unit_price=Decimal("25.00"),
        )

    def request(self, **overrides):
        values = {
            "user": self.owner,
            "organization": self.organization,
            "branch_id": self.branch.pk,
            "product_id": self.product.pk,
            "quantity": Decimal("5.000"),
            "idempotency_key": uuid.uuid4(),
        }
        values.update(overrides)
        return values

    def test_receipt_creates_movement_balance_and_audit(self):
        movement = receive_stock(**self.request())

        balance = InventoryBalance.objects.get(
            branch=self.branch,
            product=self.product,
        )
        self.assertEqual(balance.quantity_on_hand, Decimal("5.000"))
        self.assertEqual(movement.movement_type, StockMovement.MovementType.RECEIPT)
        self.assertEqual(AuditEvent.objects.filter(
            action="retail.stock_received",
            target_id=str(movement.pk),
        ).count(), 1)

    def test_receipt_idempotent_replay_returns_original(self):
        request = self.request()
        first = receive_stock(**request)
        second = receive_stock(**request)

        self.assertEqual(first.pk, second.pk)
        self.assertEqual(StockMovement.objects.count(), 1)
        self.assertEqual(AuditEvent.objects.count(), 1)
        balance = InventoryBalance.objects.get(
            branch=self.branch,
            product=self.product,
        )
        self.assertEqual(balance.quantity_on_hand, Decimal("5.000"))

    def test_idempotency_key_payload_mismatch_rejected(self):
        request = self.request()
        receive_stock(**request)
        request["quantity"] = Decimal("6.000")

        with self.assertRaises(ValidationError):
            receive_stock(**request)

        self.assertEqual(StockMovement.objects.count(), 1)
        self.assertEqual(AuditEvent.objects.count(), 1)

    def test_adjustment_in_requires_reason_and_increases_balance(self):
        movement = adjust_stock(
            **self.request(),
            direction=StockMovement.MovementType.ADJUSTMENT_IN,
            reason_code=StockMovement.ReasonCode.FOUND_STOCK,
        )
        self.assertEqual(movement.reason_code, "found_stock")
        self.assertEqual(
            InventoryBalance.objects.get(
                branch=self.branch,
                product=self.product,
            ).quantity_on_hand,
            Decimal("5.000"),
        )

    def test_adjustment_out_reduces_balance(self):
        receive_stock(**self.request(quantity=Decimal("8.000")))
        movement = adjust_stock(
            **self.request(quantity=Decimal("3.000")),
            direction=StockMovement.MovementType.ADJUSTMENT_OUT,
            reason_code=StockMovement.ReasonCode.DAMAGE,
        )
        self.assertEqual(movement.movement_type, "adjustment_out")
        self.assertEqual(
            InventoryBalance.objects.get(
                branch=self.branch,
                product=self.product,
            ).quantity_on_hand,
            Decimal("5.000"),
        )

    def test_adjustment_out_cannot_make_stock_negative(self):
        with self.assertRaises(InsufficientStockError):
            adjust_stock(
                **self.request(),
                direction=StockMovement.MovementType.ADJUSTMENT_OUT,
                reason_code=StockMovement.ReasonCode.LOSS,
            )
        self.assertEqual(StockMovement.objects.count(), 0)
        self.assertEqual(AuditEvent.objects.count(), 0)
        self.assertFalse(InventoryBalance.objects.exists())

    def test_inventory_management_role_matrix(self):
        User = get_user_model()
        allowed_roles = {"admin", "manager", "editor"}
        denied_roles = {"analyst", "auditor"}

        for role in allowed_roles | denied_roles:
            user = User.objects.create_user(username=f"inventory_role_{role}")
            OrganizationMembership.objects.create(
                organization=self.organization,
                user=user,
                role=role,
            )
            request = self.request(user=user)
            if role in allowed_roles:
                movement = receive_stock(**request)
                self.assertIsNotNone(movement.pk)
            else:
                with self.assertRaises(PermissionDenied):
                    receive_stock(**request)

    def test_viewer_cannot_manage_inventory(self):
        with self.assertRaises(PermissionDenied):
            receive_stock(**self.request(user=self.viewer))
        self.assertEqual(StockMovement.objects.count(), 0)

    def test_inactive_branch_is_rejected(self):
        self.branch.is_active = False
        self.branch.save(update_fields=["is_active"])
        with self.assertRaises(ValidationError):
            receive_stock(**self.request())
        self.assertEqual(StockMovement.objects.count(), 0)

    def test_non_decimal_and_overprecision_quantities_are_rejected(self):
        for quantity in (1.0, Decimal("1.0001"), Decimal("NaN"), Decimal("Infinity")):
            with self.subTest(quantity=quantity):
                with self.assertRaises(ValidationError):
                    receive_stock(**self.request(quantity=quantity))
        self.assertEqual(StockMovement.objects.count(), 0)

    def test_audit_failure_rolls_back_movement_and_balance(self):
        with patch(
            "retail.services.record_audit_event",
            side_effect=ValidationError("audit unavailable"),
        ):
            with self.assertRaises(ValidationError):
                receive_stock(**self.request())

        self.assertEqual(StockMovement.objects.count(), 0)
        self.assertEqual(InventoryBalance.objects.count(), 0)

    def test_reconciliation_reports_exact_balance(self):
        receive_stock(**self.request())
        result = reconcile_inventory_balances(
            user=self.owner,
            organization=self.organization
        )
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]["variance"], Decimal("0.000"))
        self.assertTrue(result[0]["is_reconciled"])

    def test_reconciliation_reports_manual_variance_without_repair(self):
        receive_stock(**self.request())
        balance = InventoryBalance.objects.get(
            branch=self.branch,
            product=self.product,
        )
        InventoryBalance.objects.filter(pk=balance.pk).update(
            quantity_on_hand=Decimal("7.000")
        )
        result = reconcile_inventory_balances(
            user=self.owner,
            organization=self.organization
        )
        self.assertEqual(result[0]["variance"], Decimal("2.000"))
        self.assertFalse(result[0]["is_reconciled"])
        balance.refresh_from_db()
        self.assertEqual(balance.quantity_on_hand, Decimal("7.000"))
