"""PostgreSQL-backed concurrency tests for inventory transactions."""

import uuid
from decimal import Decimal
from queue import Queue
from threading import Barrier, Thread

from django.contrib.auth import get_user_model
from django.db import close_old_connections, connection
from django.test import TransactionTestCase

from auditlog.models import AuditEvent
from organizations.models import Organization, OrganizationMembership
from retail.models import Branch, InventoryBalance, Product, StockMovement
from retail.services import receive_stock


class InventoryIdempotencyConcurrencyTests(TransactionTestCase):
    reset_sequences = True
    databases = {"default"}
    TIMEOUT = 12

    def setUp(self):
        if connection.vendor != "postgresql":
            self.skipTest("PostgreSQL-specific inventory concurrency tests.")

        User = get_user_model()
        self.user = User.objects.create_user(username="inventory_race_owner")
        self.organization = Organization.objects.create(
            name="Inventory Race Organization",
            slug="inventory-race-organization",
        )
        OrganizationMembership.objects.create(
            organization=self.organization,
            user=self.user,
            role="owner",
        )
        self.branch = Branch.objects.create(
            organization=self.organization,
            code="MAIN",
            name="Main Branch",
        )
        self.product = Product.objects.create(
            organization=self.organization,
            sku="RACE-001",
            name="Race Product",
            unit_price=Decimal("10.00"),
        )

    def test_same_key_concurrent_first_receipts_apply_once(self):
        key = uuid.uuid4()
        barrier = Barrier(2)
        results = Queue()

        def worker():
            try:
                close_old_connections()
                user = get_user_model().objects.get(pk=self.user.pk)
                organization = Organization.objects.get(pk=self.organization.pk)
                barrier.wait(timeout=self.TIMEOUT)
                movement = receive_stock(
                    user=user,
                    organization=organization,
                    branch_id=self.branch.pk,
                    product_id=self.product.pk,
                    quantity=Decimal("4.000"),
                    idempotency_key=key,
                    reason_code="supplier_delivery",
                )
                results.put(("ok", movement.pk))
            except BaseException as exc:
                results.put(("error", exc))
            finally:
                close_old_connections()

        workers = [Thread(target=worker, daemon=True) for _ in range(2)]
        for thread in workers:
            thread.start()
        for thread in workers:
            thread.join(self.TIMEOUT + 2)

        for thread in workers:
            self.assertFalse(thread.is_alive(), "Inventory worker did not finish.")

        outcomes = [results.get(timeout=1) for _ in workers]
        self.assertTrue(
            all(outcome[0] == "ok" for outcome in outcomes),
            repr(outcomes),
        )
        self.assertEqual(outcomes[0][1], outcomes[1][1])
        self.assertEqual(StockMovement.objects.count(), 1)
        self.assertEqual(AuditEvent.objects.filter(
            action="retail.stock_received"
        ).count(), 1)
        balance = InventoryBalance.objects.get(
            branch=self.branch,
            product=self.product,
        )
        self.assertEqual(balance.quantity_on_hand, Decimal("4.000"))
