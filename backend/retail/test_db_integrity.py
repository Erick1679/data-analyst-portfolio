import uuid
from decimal import Decimal
from queue import Queue
from threading import Barrier, Event, Thread
from time import monotonic, sleep

from django.contrib.auth import get_user_model
from django.db import (
    IntegrityError,
    close_old_connections,
    connection,
    transaction,
)
from django.test import TestCase, TransactionTestCase

from organizations.models import Organization

from retail.models import (
    Branch,
    InventoryBalance,
    Product,
    Sale,
    SaleItem,
    StockMovement,
)


class RetailDatabaseIntegrityTests(TestCase):
    """Test PostgreSQL retail database integrity."""

    databases = {"default"}

    def setUp(self):
        if connection.vendor != "postgresql":
            self.skipTest("PostgreSQL-specific integrity tests.")

        User = get_user_model()

        self.user = User.objects.create_user(
            username="retail_integrity_user",
            password="local-test-password",
        )

        self.org_a = Organization.objects.create(
            name="Integrity Organization A",
            slug="integrity-organization-a",
        )

        self.org_b = Organization.objects.create(
            name="Integrity Organization B",
            slug="integrity-organization-b",
        )

        self.branch_a = Branch.objects.create(
            organization=self.org_a,
            code="MAIN",
            name="Branch A",
        )

        self.branch_b = Branch.objects.create(
            organization=self.org_b,
            code="MAIN",
            name="Branch B",
        )

        self.product_a = Product.objects.create(
            organization=self.org_a,
            sku="PRODUCT-A",
            name="Product A",
            unit_price=Decimal("100.00"),
            currency="KES",
        )

        self.product_b = Product.objects.create(
            organization=self.org_b,
            sku="PRODUCT-B",
            name="Product B",
            unit_price=Decimal("200.00"),
            currency="KES",
        )

    def create_sale(self, **kwargs):
        defaults = {
            "organization": self.org_a,
            "branch": self.branch_a,
            "reference": "SALE-001",
            "recorded_by": self.user,
            "currency": "KES",
        }
        defaults.update(kwargs)
        return Sale.objects.create(**defaults)

    def test_cross_organization_sale_insert_is_blocked(self):
        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                self.create_sale(
                    branch=self.branch_b,
                )

    def test_cross_organization_sale_update_is_blocked(self):
        sale = self.create_sale()

        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                Sale.objects.filter(pk=sale.pk).update(
                    branch=self.branch_b,
                )

        sale.refresh_from_db()
        self.assertEqual(sale.branch_id, self.branch_a.pk)


    def test_cross_organization_saleitem_insert_is_blocked(self):
        sale = self.create_sale()

        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                SaleItem.objects.create(
                    sale=sale,
                    product=self.product_b,
                    quantity=Decimal("1.000"),
                    unit_price=Decimal("200.00"),
                )

    def test_currency_mismatch_saleitem_insert_is_blocked(self):
        sale = self.create_sale()

        product_usd = Product.objects.create(
            organization=self.org_a,
            sku="PRODUCT-USD",
            name="USD Product",
            unit_price=Decimal("100.00"),
            currency="USD",
        )

        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                SaleItem.objects.create(
                    sale=sale,
                    product=product_usd,
                    quantity=Decimal("1.000"),
                    unit_price=Decimal("100.00"),
                )

    def test_cross_organization_saleitem_update_is_blocked(self):
        sale = self.create_sale()

        item = SaleItem.objects.create(
            sale=sale,
            product=self.product_a,
            quantity=Decimal("1.000"),
            unit_price=Decimal("100.00"),
        )

        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                SaleItem.objects.filter(pk=item.pk).update(
                    product=self.product_b,
                )

        item.refresh_from_db()
        self.assertEqual(item.product_id, self.product_a.pk)

    def test_cross_organization_inventory_insert_is_blocked(self):
        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                InventoryBalance.objects.create(
                    branch=self.branch_a,
                    product=self.product_b,
                    quantity_on_hand=Decimal("10.000"),
                )

    def test_cross_organization_inventory_update_is_blocked(self):
        balance = InventoryBalance.objects.create(
            branch=self.branch_a,
            product=self.product_a,
            quantity_on_hand=Decimal("10.000"),
        )

        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                InventoryBalance.objects.filter(
                    pk=balance.pk
                ).update(product=self.product_b)

        balance.refresh_from_db()
        self.assertEqual(balance.product_id, self.product_a.pk)

    def test_branch_organization_change_with_sale_is_blocked(self):
        self.create_sale()

        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                Branch.objects.filter(
                    pk=self.branch_a.pk
                ).update(organization=self.org_b)

        self.branch_a.refresh_from_db()
        self.assertEqual(
            self.branch_a.organization_id,
            self.org_a.pk,
        )

    def test_branch_organization_change_with_inventory_is_blocked(self):
        InventoryBalance.objects.create(
            branch=self.branch_a,
            product=self.product_a,
            quantity_on_hand=Decimal("10.000"),
        )

        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                Branch.objects.filter(
                    pk=self.branch_a.pk
                ).update(organization=self.org_b)

        self.branch_a.refresh_from_db()
        self.assertEqual(
            self.branch_a.organization_id,
            self.org_a.pk,
        )

    def test_product_organization_change_with_saleitem_is_blocked(self):
        sale = self.create_sale()

        SaleItem.objects.create(
            sale=sale,
            product=self.product_a,
            quantity=Decimal("1.000"),
            unit_price=Decimal("100.00"),
        )

        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                Product.objects.filter(
                    pk=self.product_a.pk
                ).update(organization=self.org_b)

        self.product_a.refresh_from_db()
        self.assertEqual(
            self.product_a.organization_id,
            self.org_a.pk,
        )

    def test_product_currency_change_with_saleitem_is_blocked(self):
        sale = self.create_sale()

        SaleItem.objects.create(
            sale=sale,
            product=self.product_a,
            quantity=Decimal("1.000"),
            unit_price=Decimal("100.00"),
        )

        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                Product.objects.filter(
                    pk=self.product_a.pk
                ).update(currency="USD")

        self.product_a.refresh_from_db()
        self.assertEqual(self.product_a.currency, "KES")

    def test_product_organization_change_with_inventory_is_blocked(self):
        InventoryBalance.objects.create(
            branch=self.branch_a,
            product=self.product_a,
            quantity_on_hand=Decimal("10.000"),
        )

        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                Product.objects.filter(
                    pk=self.product_a.pk
                ).update(organization=self.org_b)

        self.product_a.refresh_from_db()
        self.assertEqual(
            self.product_a.organization_id,
            self.org_a.pk,
        )

    def test_sale_organization_change_with_items_is_blocked(self):
        sale = self.create_sale()

        SaleItem.objects.create(
            sale=sale,
            product=self.product_a,
            quantity=Decimal("1.000"),
            unit_price=Decimal("100.00"),
        )

        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                Sale.objects.filter(pk=sale.pk).update(
                    organization=self.org_b,
                    branch=self.branch_b,
                )

        sale.refresh_from_db()
        self.assertEqual(sale.organization_id, self.org_a.pk)
        self.assertEqual(sale.branch_id, self.branch_a.pk)

    def test_sale_currency_change_with_items_is_blocked(self):
        sale = self.create_sale()

        SaleItem.objects.create(
            sale=sale,
            product=self.product_a,
            quantity=Decimal("1.000"),
            unit_price=Decimal("100.00"),
        )

        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                Sale.objects.filter(pk=sale.pk).update(
                    currency="USD",
                )

        sale.refresh_from_db()
        self.assertEqual(sale.currency, "KES")

    def test_sale_safe_organization_change_without_items_is_allowed(self):
        sale = self.create_sale()

        Sale.objects.filter(pk=sale.pk).update(
            organization=self.org_b,
            branch=self.branch_b,
        )

        sale.refresh_from_db()

        self.assertEqual(sale.organization_id, self.org_b.pk)
        self.assertEqual(sale.branch_id, self.branch_b.pk)


    def test_branch_safe_organization_change_without_dependents_is_allowed(self):
        Branch.objects.filter(
            pk=self.branch_a.pk
        ).update(
            organization=self.org_b,
            code="MAIN-A",
        )

        self.branch_a.refresh_from_db()

        self.assertEqual(
            self.branch_a.organization_id,
            self.org_b.pk,
        )
        self.assertEqual(self.branch_a.code, "MAIN-A")

    def test_product_safe_organization_and_currency_change_is_allowed(self):
        Product.objects.filter(
            pk=self.product_a.pk
        ).update(
            organization=self.org_b,
            currency="USD",
        )

        self.product_a.refresh_from_db()

        self.assertEqual(
            self.product_a.organization_id,
            self.org_b.pk,
        )
        self.assertEqual(self.product_a.currency, "USD")

    def test_inventory_branch_change_with_movements_is_blocked(self):
        balance = InventoryBalance.objects.create(
            branch=self.branch_a,
            product=self.product_a,
            quantity_on_hand=Decimal("10.000"),
        )

        StockMovement.objects.create(
            balance=balance,
            movement_type=StockMovement.MovementType.RECEIPT,
            quantity=Decimal("5.000"),
            recorded_by=self.user,
            idempotency_key=uuid.uuid4(),
        )

        alternative_branch = Branch.objects.create(
            organization=self.org_a,
            code="SECOND",
            name="Second Branch",
        )

        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                InventoryBalance.objects.filter(
                    pk=balance.pk
                ).update(branch=alternative_branch)

        balance.refresh_from_db()
        self.assertEqual(balance.branch_id, self.branch_a.pk)

    def test_inventory_product_change_with_movements_is_blocked(self):
        balance = InventoryBalance.objects.create(
            branch=self.branch_a,
            product=self.product_a,
            quantity_on_hand=Decimal("10.000"),
        )

        StockMovement.objects.create(
            balance=balance,
            movement_type=StockMovement.MovementType.RECEIPT,
            quantity=Decimal("5.000"),
            recorded_by=self.user,
            idempotency_key=uuid.uuid4(),
        )

        alternative_product = Product.objects.create(
            organization=self.org_a,
            sku="PRODUCT-SECOND",
            name="Alternative Product",
            unit_price=Decimal("150.00"),
            currency="KES",
        )

        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                InventoryBalance.objects.filter(
                    pk=balance.pk
                ).update(product=alternative_product)

        balance.refresh_from_db()
        self.assertEqual(balance.product_id, self.product_a.pk)

    def test_inventory_branch_reassignment_without_movements_is_allowed(self):
        balance = InventoryBalance.objects.create(
            branch=self.branch_a,
            product=self.product_a,
            quantity_on_hand=Decimal("10.000"),
        )

        alternative_branch = Branch.objects.create(
            organization=self.org_a,
            code="THIRD",
            name="Third Branch",
        )

        InventoryBalance.objects.filter(
            pk=balance.pk
        ).update(branch=alternative_branch)

        balance.refresh_from_db()
        self.assertEqual(balance.branch_id, alternative_branch.pk)

    def test_inventory_product_reassignment_without_movements_is_allowed(self):
        balance = InventoryBalance.objects.create(
            branch=self.branch_a,
            product=self.product_a,
            quantity_on_hand=Decimal("10.000"),
        )

        alternative_product = Product.objects.create(
            organization=self.org_a,
            sku="PRODUCT-THIRD",
            name="Third Product",
            unit_price=Decimal("150.00"),
            currency="KES",
        )

        InventoryBalance.objects.filter(
            pk=balance.pk
        ).update(product=alternative_product)

        balance.refresh_from_db()
        self.assertEqual(balance.product_id, alternative_product.pk)

    def test_stock_movement_delete_is_rejected(self):
        balance = InventoryBalance.objects.create(
            branch=self.branch_a,
            product=self.product_a,
            quantity_on_hand=Decimal("0.000"),
        )
        movement = StockMovement.objects.create(
            balance=balance,
            movement_type=StockMovement.MovementType.RECEIPT,
            quantity=Decimal("1.000"),
            recorded_by=self.user,
            idempotency_key=uuid.uuid4(),
        )

        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                StockMovement.objects.filter(pk=movement.pk).delete()

        self.assertTrue(StockMovement.objects.filter(pk=movement.pk).exists())

    def test_stock_movement_direct_sql_update_and_delete_are_rejected(self):
        balance = InventoryBalance.objects.create(
            branch=self.branch_a,
            product=self.product_a,
            quantity_on_hand=Decimal("0.000"),
        )
        movement = StockMovement.objects.create(
            balance=balance,
            movement_type=StockMovement.MovementType.RECEIPT,
            quantity=Decimal("1.000"),
            recorded_by=self.user,
            idempotency_key=uuid.uuid4(),
        )

        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                with connection.cursor() as cursor:
                    cursor.execute(
                        "UPDATE retail_stockmovement SET notes = %s WHERE id = %s",
                        ["tampered", str(movement.pk)],
                    )

        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                with connection.cursor() as cursor:
                    cursor.execute(
                        "DELETE FROM retail_stockmovement WHERE id = %s",
                        [str(movement.pk)],
                    )

        self.assertTrue(StockMovement.objects.filter(pk=movement.pk).exists())

    def test_stock_movement_insert_requires_idempotency_key(self):
        balance = InventoryBalance.objects.create(
            branch=self.branch_a,
            product=self.product_a,
            quantity_on_hand=Decimal("0.000"),
        )
        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                StockMovement.objects.create(
                    balance=balance,
                    movement_type=StockMovement.MovementType.RECEIPT,
                    quantity=Decimal("1.000"),
                    recorded_by=self.user,
                )

    def test_opening_quantity_is_immutable(self):
        balance = InventoryBalance.objects.create(
            branch=self.branch_a,
            product=self.product_a,
            quantity_on_hand=Decimal("0.000"),
            opening_quantity=Decimal("0.000"),
        )
        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                InventoryBalance.objects.filter(pk=balance.pk).update(
                    opening_quantity=Decimal("1.000")
                )

    def test_inventory_quantity_update_with_movements_is_allowed(self):
        balance = InventoryBalance.objects.create(
            branch=self.branch_a,
            product=self.product_a,
            quantity_on_hand=Decimal("10.000"),
        )

        StockMovement.objects.create(
            balance=balance,
            movement_type=StockMovement.MovementType.RECEIPT,
            quantity=Decimal("5.000"),
            recorded_by=self.user,
            idempotency_key=uuid.uuid4(),
        )

        InventoryBalance.objects.filter(
            pk=balance.pk
        ).update(quantity_on_hand=Decimal("15.000"))

        balance.refresh_from_db()
        self.assertEqual(
            balance.quantity_on_hand,
            Decimal("15.000"),
        )

class RetailConcurrencyTests(TransactionTestCase):
    """Test real PostgreSQL concurrency and row-level locking."""

    databases = {"default"}
    TIMEOUT = 10

    def setUp(self):
        if connection.vendor != "postgresql":
            self.skipTest("PostgreSQL-specific concurrency tests.")

        User = get_user_model()

        self.user = User.objects.create_user(
            username="retail_concurrency_user",
            password="local-test-password",
        )

        self.org = Organization.objects.create(
            name="Concurrency Organization",
            slug="concurrency-organization",
        )

        self.branch_a = Branch.objects.create(
            organization=self.org,
            code="MAIN",
            name="Main Branch",
        )

        self.alternative_branch = Branch.objects.create(
            organization=self.org,
            code="SECOND",
            name="Second Branch",
        )

        self.product = Product.objects.create(
            organization=self.org,
            sku="CONCURRENT-PRODUCT",
            name="Concurrency Product",
            unit_price=Decimal("100.00"),
            currency="KES",
        )

        self.sale = Sale.objects.create(
            organization=self.org,
            branch=self.branch_a,
            reference="CONCURRENT-SALE",
            recorded_by=self.user,
            currency="KES",
        )

    # ---------------------------------------------------------
    # Thread and transaction helpers
    # ---------------------------------------------------------

    def _start_worker(
        self,
        operation,
        started=None,
        acquired=None,
        release=None,
    ):
        pid_queue = Queue()
        result_queue = Queue()

        def worker():
            try:
                close_old_connections()

                with transaction.atomic():
                    with connection.cursor() as cursor:
                        cursor.execute(
                            "SET LOCAL lock_timeout = '8s'"
                        )
                        cursor.execute("SELECT pg_backend_pid()")
                        pid_queue.put(cursor.fetchone()[0])

                    if started is not None:
                        started.set()

                    operation()

                    if acquired is not None:
                        acquired.set()

                    if release is not None:
                        if not release.wait(self.TIMEOUT):
                            raise TimeoutError(
                                "Transaction release timed out."
                            )

                result_queue.put(None)

            except BaseException as exc:
                result_queue.put(exc)

            finally:
                close_old_connections()

        thread = Thread(target=worker, daemon=True)
        thread.start()

        return {
            "thread": thread,
            "pid": pid_queue,
            "result": result_queue,
        }

    def _wait_until_blocked(self, backend_pid):
        """Wait until PostgreSQL confirms a real lock wait."""

        deadline = monotonic() + 5

        while monotonic() < deadline:
            with connection.cursor() as cursor:
                cursor.execute(
                    """
                    SELECT wait_event_type
                    FROM pg_stat_activity
                    WHERE pid = %s
                    """,
                    [backend_pid],
                )
                row = cursor.fetchone()

            if row and row[0] == "Lock":
                return

            sleep(0.01)

        self.fail(
            f"PostgreSQL backend {backend_pid} "
            "did not enter the expected lock wait."
        )

    def _run_blocked_race(
        self,
        first_operation,
        second_operation,
        second_error=None,
    ):
        """
        Hold the first transaction's lock, start the second
        transaction, confirm PostgreSQL is blocking it, then
        release the first transaction.
        """

        first_acquired = Event()
        release_first = Event()

        first = self._start_worker(
            first_operation,
            acquired=first_acquired,
            release=release_first,
        )

        second = None

        try:
            self.assertTrue(
                first_acquired.wait(self.TIMEOUT),
                "First transaction did not acquire its lock.",
            )

            second_started = Event()

            second = self._start_worker(
                second_operation,
                started=second_started,
            )

            self.assertTrue(
                second_started.wait(self.TIMEOUT),
                "Second transaction did not start.",
            )

            second_pid = second["pid"].get(
                timeout=self.TIMEOUT
            )

            self._wait_until_blocked(second_pid)

        finally:
            # Always release the first transaction, including
            # when an assertion fails.
            release_first.set()

            first["thread"].join(self.TIMEOUT + 2)

            if second is not None:
                second["thread"].join(self.TIMEOUT + 2)

        self.assertFalse(
            first["thread"].is_alive(),
            "First transaction did not finish.",
        )

        self.assertIsNone(
            first["result"].get(timeout=1),
            "First transaction unexpectedly failed.",
        )

        if second is not None:
            self.assertFalse(
                second["thread"].is_alive(),
                "Second transaction did not finish.",
            )

            second_result = second["result"].get(timeout=1)

            if second_error is not None:
                self.assertIsInstance(
                    second_result,
                    second_error,
                )
            else:
                self.assertIsNone(
                    second_result,
                    "Second transaction unexpectedly failed.",
                )

    # ---------------------------------------------------------
    # Shared fixture helpers
    # ---------------------------------------------------------

    def _insert_sale_item(self):
        return SaleItem.objects.create(
            sale_id=self.sale.pk,
            product_id=self.product.pk,
            quantity=Decimal("1.000"),
            unit_price=Decimal("100.00"),
        )

    def _create_balance(self, branch=None):
        return InventoryBalance.objects.create(
            branch=branch or self.branch_a,
            product=self.product,
            quantity_on_hand=Decimal("10.000"),
        )

    def _insert_movement(self, balance_id):
        return StockMovement.objects.create(
            balance_id=balance_id,
            movement_type=StockMovement.MovementType.RECEIPT,
            quantity=Decimal("1.000"),
            recorded_by_id=self.user.pk,
            idempotency_key=uuid.uuid4(),
        )

    # ---------------------------------------------------------
    # Product versus SaleItem concurrency
    # ---------------------------------------------------------

    def test_product_update_wins_before_saleitem_insert(self):
        self._run_blocked_race(
            lambda: Product.objects.filter(
                pk=self.product.pk
            ).update(currency="USD"),
            self._insert_sale_item,
            second_error=IntegrityError,
        )

        self.product.refresh_from_db()

        self.assertEqual(self.product.currency, "USD")

        self.assertFalse(
            SaleItem.objects.filter(
                sale_id=self.sale.pk
            ).exists()
        )

    def test_saleitem_insert_wins_before_product_update(self):
        self._run_blocked_race(
            self._insert_sale_item,
            lambda: Product.objects.filter(
                pk=self.product.pk
            ).update(currency="USD"),
            second_error=IntegrityError,
        )

        self.product.refresh_from_db()

        self.assertEqual(self.product.currency, "KES")

        self.assertTrue(
            SaleItem.objects.filter(
                sale_id=self.sale.pk
            ).exists()
        )

    # ---------------------------------------------------------
    # Sale versus SaleItem concurrency
    # ---------------------------------------------------------

    def test_sale_update_wins_before_saleitem_insert(self):
        self._run_blocked_race(
            lambda: Sale.objects.filter(
                pk=self.sale.pk
            ).update(currency="USD"),
            self._insert_sale_item,
            second_error=IntegrityError,
        )

        self.sale.refresh_from_db()

        self.assertEqual(self.sale.currency, "USD")

        self.assertFalse(
            SaleItem.objects.filter(
                sale_id=self.sale.pk
            ).exists()
        )

    def test_saleitem_insert_wins_before_sale_update(self):
        self._run_blocked_race(
            self._insert_sale_item,
            lambda: Sale.objects.filter(
                pk=self.sale.pk
            ).update(currency="USD"),
            second_error=IntegrityError,
        )

        self.sale.refresh_from_db()

        self.assertEqual(self.sale.currency, "KES")

        self.assertTrue(
            SaleItem.objects.filter(
                sale_id=self.sale.pk
            ).exists()
        )

    # ---------------------------------------------------------
    # InventoryBalance versus StockMovement concurrency
    # ---------------------------------------------------------

    def test_balance_reassignment_wins_before_movement_insert(self):
        balance = self._create_balance()

        self._run_blocked_race(
            lambda: InventoryBalance.objects.filter(
                pk=balance.pk
            ).update(
                branch_id=self.alternative_branch.pk
            ),
            lambda: self._insert_movement(balance.pk),
        )

        balance.refresh_from_db()

        self.assertEqual(
            balance.branch_id,
            self.alternative_branch.pk,
        )

        self.assertEqual(
            StockMovement.objects.filter(
                balance_id=balance.pk
            ).count(),
            1,
        )

    def test_movement_insert_wins_before_balance_reassignment(self):
        balance = self._create_balance()

        self._run_blocked_race(
            lambda: self._insert_movement(balance.pk),
            lambda: InventoryBalance.objects.filter(
                pk=balance.pk
            ).update(
                branch_id=self.alternative_branch.pk
            ),
            second_error=IntegrityError,
        )

        balance.refresh_from_db()

        self.assertEqual(
            balance.branch_id,
            self.branch_a.pk,
        )

        self.assertEqual(
            StockMovement.objects.filter(
                balance_id=balance.pk
            ).count(),
            1,
        )

    # ---------------------------------------------------------
    # Stock movement updates must lock their inventory balance
    # ---------------------------------------------------------

    def test_stock_movement_update_is_rejected_as_append_only(self):
        balance = self._create_balance()
        movement = self._insert_movement(balance.pk)

        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                StockMovement.objects.filter(pk=movement.pk).update(
                    quantity=Decimal("2.000")
                )

        movement.refresh_from_db()
        self.assertEqual(movement.quantity, Decimal("1.000"))

    # ---------------------------------------------------------
    # Opposite-direction stock movement reassignment
    # ---------------------------------------------------------

    def test_stock_movement_balance_reassignment_is_rejected(self):
        balance_a = self._create_balance(self.branch_a)
        balance_b = self._create_balance(self.alternative_branch)
        movement = self._insert_movement(balance_a.pk)

        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                StockMovement.objects.filter(pk=movement.pk).update(
                    balance_id=balance_b.pk
                )

        movement.refresh_from_db()
        self.assertEqual(movement.balance_id, balance_a.pk)

