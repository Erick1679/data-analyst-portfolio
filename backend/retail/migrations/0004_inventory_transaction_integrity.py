"""Add durable inventory transaction metadata and PostgreSQL guards."""

from decimal import Decimal

from django.db import migrations, models
from django.db.models import Case, DecimalField, F, Sum, Value, When
from django.db.models.functions import Coalesce


def backfill_opening_quantities(apps, schema_editor):
    Balance = apps.get_model("retail", "InventoryBalance")
    Movement = apps.get_model("retail", "StockMovement")

    unclassified = list(
        Movement.objects.filter(
            movement_type__in=("adjustment_in", "adjustment_out"),
            reason_code="",
        ).values_list("pk", flat=True)[:25]
    )
    if unclassified:
        raise RuntimeError(
            "DB-03 migration blocked: legacy adjustment movements need "
            "explicit reason codes before migration. Example movement IDs: "
            + ", ".join(str(value) for value in unclassified)
        )

    for balance in Balance.objects.all().iterator():
        totals = Movement.objects.filter(balance_id=balance.pk).aggregate(
            signed=Coalesce(
                Sum(
                    Case(
                        When(
                            movement_type__in=("receipt", "adjustment_in"),
                            then=F("quantity"),
                        ),
                        When(
                            movement_type__in=("adjustment_out", "sale"),
                            then=-F("quantity"),
                        ),
                        default=Value(Decimal("0.000")),
                        output_field=DecimalField(
                            max_digits=18,
                            decimal_places=3,
                        ),
                    )
                ),
                Value(
                    Decimal("0.000"),
                    output_field=DecimalField(
                        max_digits=18,
                        decimal_places=3,
                    ),
                ),
            )
        )
        opening = balance.quantity_on_hand - totals["signed"]
        if opening < 0:
            raise RuntimeError(
                "DB-03 migration blocked: calculated opening quantity is "
                f"negative for inventory balance {balance.pk} "
                f"(stored={balance.quantity_on_hand}, signed_movements="
                f"{totals['signed']}, opening={opening}). Investigate the "
                "historical ledger before retrying."
            )
        Balance.objects.filter(pk=balance.pk).update(
            opening_quantity=opening
        )


def noop_reverse_backfill(apps, schema_editor):
    # Existing quantity_on_hand and movement rows are not rewritten.
    pass


INSTALL_SQL = """
DROP TRIGGER IF EXISTS retail_stockmovement_update_lock ON retail_stockmovement;
DROP TRIGGER IF EXISTS retail_stockmovement_delete_lock ON retail_stockmovement;

CREATE FUNCTION retail_reject_stockmovement_mutation()
RETURNS trigger
LANGUAGE plpgsql
AS $$
BEGIN
    RAISE EXCEPTION 'Stock movements are append-only; record a compensating movement'
        USING ERRCODE = '23514';
END;
$$;

CREATE TRIGGER retail_stockmovement_no_update
BEFORE UPDATE ON retail_stockmovement
FOR EACH ROW
EXECUTE FUNCTION retail_reject_stockmovement_mutation();

CREATE TRIGGER retail_stockmovement_no_delete
BEFORE DELETE ON retail_stockmovement
FOR EACH ROW
EXECUTE FUNCTION retail_reject_stockmovement_mutation();

CREATE FUNCTION retail_require_stockmovement_idempotency()
RETURNS trigger
LANGUAGE plpgsql
AS $$
BEGIN
    IF NEW.idempotency_key IS NULL THEN
        RAISE EXCEPTION 'New stock movements require an idempotency key'
            USING ERRCODE = '23514';
    END IF;
    RETURN NEW;
END;
$$;

CREATE TRIGGER retail_stockmovement_idempotency_required
BEFORE INSERT ON retail_stockmovement
FOR EACH ROW
EXECUTE FUNCTION retail_require_stockmovement_idempotency();

CREATE FUNCTION retail_apply_stockmovement_to_balance()
RETURNS trigger
LANGUAGE plpgsql
AS $$
DECLARE
    signed_quantity numeric(16, 3);
BEGIN
    IF NEW.movement_type IN ('receipt', 'adjustment_in') THEN
        signed_quantity := NEW.quantity;
    ELSE
        signed_quantity := -NEW.quantity;
    END IF;

    UPDATE retail_inventorybalance
    SET quantity_on_hand = quantity_on_hand + signed_quantity,
        updated_at = CURRENT_TIMESTAMP
    WHERE id = NEW.balance_id;

    IF NOT FOUND THEN
        RAISE EXCEPTION 'Stock movement inventory balance does not exist'
            USING ERRCODE = '23503';
    END IF;

    RETURN NEW;
END;
$$;

CREATE TRIGGER retail_stockmovement_apply_balance
AFTER INSERT ON retail_stockmovement
FOR EACH ROW
EXECUTE FUNCTION retail_apply_stockmovement_to_balance();

CREATE FUNCTION retail_protect_opening_quantity()
RETURNS trigger
LANGUAGE plpgsql
AS $$
BEGIN
    IF NEW.opening_quantity IS DISTINCT FROM OLD.opening_quantity THEN
        RAISE EXCEPTION 'Inventory opening quantity is immutable'
            USING ERRCODE = '23514';
    END IF;
    RETURN NEW;
END;
$$;

CREATE TRIGGER retail_inventory_opening_immutable
BEFORE UPDATE OF opening_quantity ON retail_inventorybalance
FOR EACH ROW
EXECUTE FUNCTION retail_protect_opening_quantity();
"""


def install_inventory_transaction_integrity(apps, schema_editor):
    if schema_editor.connection.vendor == "postgresql":
        schema_editor.execute(INSTALL_SQL)


def uninstall_inventory_transaction_integrity(apps, schema_editor):
    if schema_editor.connection.vendor != "postgresql":
        return

    for trigger, table in (
        ("retail_inventory_opening_immutable", "retail_inventorybalance"),
        ("retail_stockmovement_apply_balance", "retail_stockmovement"),
        ("retail_stockmovement_idempotency_required", "retail_stockmovement"),
        ("retail_stockmovement_no_delete", "retail_stockmovement"),
        ("retail_stockmovement_no_update", "retail_stockmovement"),
    ):
        schema_editor.execute(
            f"DROP TRIGGER IF EXISTS {trigger} ON {table};"
        )

    for function in (
        "retail_protect_opening_quantity",
        "retail_apply_stockmovement_to_balance",
        "retail_require_stockmovement_idempotency",
        "retail_reject_stockmovement_mutation",
    ):
        schema_editor.execute(f"DROP FUNCTION IF EXISTS {function}();")

    # Restore DB-02's movement row-lock triggers for a clean rollback.
    schema_editor.execute("""
        CREATE TRIGGER retail_stockmovement_update_lock
        BEFORE UPDATE ON retail_stockmovement
        FOR EACH ROW
        EXECUTE FUNCTION retail_lock_inventorybalance_for_movement();
    """)
    schema_editor.execute("""
        CREATE TRIGGER retail_stockmovement_delete_lock
        BEFORE DELETE ON retail_stockmovement
        FOR EACH ROW
        EXECUTE FUNCTION retail_lock_inventorybalance_for_movement();
    """)


def refuse_unsafe_reverse(apps, schema_editor):
    if schema_editor.connection.vendor != "postgresql":
        return
    with schema_editor.connection.cursor() as cursor:
        cursor.execute(
            """
            SELECT id
            FROM retail_stockmovement
            WHERE idempotency_key IS NOT NULL
               OR reason_code <> ''
            LIMIT 1
            """
        )
        row = cursor.fetchone()
    if row:
        raise RuntimeError(
            "Cannot reverse DB-03 after new inventory transaction data "
            f"has been recorded (example movement {row[0]})."
        )


class Migration(migrations.Migration):
    dependencies = [
        (
            "retail",
            "0003_postgresql_tenant_integrity",
        ),
    ]

    operations = [
        migrations.AddField(
            model_name="inventorybalance",
            name="opening_quantity",
            field=models.DecimalField(
                decimal_places=3,
                default=0,
                editable=False,
                max_digits=16,
            ),
        ),
        migrations.AddField(
            model_name="stockmovement",
            name="reason_code",
            field=models.CharField(
                blank=True,
                choices=[
                    ("", "Not specified"),
                    ("supplier_delivery", "Supplier delivery"),
                    ("customer_return", "Customer return"),
                    ("opening_stock", "Opening stock"),
                    ("stock_count", "Stock count"),
                    ("found_stock", "Found stock"),
                    ("damage", "Damage"),
                    ("expiry", "Expiry"),
                    ("loss", "Loss"),
                    ("internal_use", "Internal use"),
                    ("other", "Other"),
                ],
                default="",
                max_length=32,
            ),
        ),
        migrations.AddField(
            model_name="stockmovement",
            name="idempotency_key",
            field=models.UUIDField(
                blank=True,
                editable=False,
                null=True,
                unique=True,
            ),
        ),
        migrations.RunPython(
            backfill_opening_quantities,
            noop_reverse_backfill,
        ),
        migrations.AddConstraint(
            model_name="inventorybalance",
            constraint=models.CheckConstraint(
                condition=models.Q(("opening_quantity__gte", 0)),
                name="retail_inventory_opening_nonnegative",
            ),
        ),
        migrations.AddConstraint(
            model_name="stockmovement",
            constraint=models.CheckConstraint(
                condition=(
                    models.Q(
                        movement_type="receipt",
                        reason_code__in=[
                            "",
                            "supplier_delivery",
                            "customer_return",
                            "opening_stock",
                            "other",
                        ],
                    )
                    | models.Q(
                        movement_type="adjustment_in",
                        reason_code__in=[
                            "stock_count",
                            "found_stock",
                            "customer_return",
                            "other",
                        ],
                    )
                    | models.Q(
                        movement_type="adjustment_out",
                        reason_code__in=[
                            "stock_count",
                            "damage",
                            "expiry",
                            "loss",
                            "internal_use",
                            "other",
                        ],
                    )
                    | models.Q(movement_type="sale", reason_code="")
                ),
                name="retail_stockmovement_reason_valid",
            ),
        ),
        migrations.RunPython(
            install_inventory_transaction_integrity,
            uninstall_inventory_transaction_integrity,
        ),
        # This is deliberately last so it runs first on reverse.
        migrations.RunPython(
            migrations.RunPython.noop,
            refuse_unsafe_reverse,
        ),
    ]
