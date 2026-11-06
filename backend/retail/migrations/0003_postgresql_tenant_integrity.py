
"""Enforce PostgreSQL retail tenant and currency integrity."""

from django.db import migrations



SALE_INTEGRITY_SQL = """
CREATE FUNCTION retail_check_sale_integrity()
RETURNS trigger
LANGUAGE plpgsql
AS $$
DECLARE
    branch_organization_id uuid;
BEGIN


    SELECT organization_id
    INTO branch_organization_id
    FROM retail_branch
    WHERE id = NEW.branch_id
    FOR SHARE;
    IF NOT FOUND THEN
        RAISE EXCEPTION 'Sale branch does not exist'
            USING ERRCODE = '23503';
    END IF;
    IF branch_organization_id IS DISTINCT FROM NEW.organization_id THEN
        RAISE EXCEPTION 'Sale branch organization mismatch'
            USING ERRCODE = '23514';
    END IF;

    RETURN NEW;
END;
$$;
"""


SALEITEM_INTEGRITY_SQL = """
CREATE FUNCTION retail_check_saleitem_integrity()
RETURNS trigger
LANGUAGE plpgsql
AS $$
DECLARE
    sale_organization_id uuid;
    sale_currency varchar(3);
    product_organization_id uuid;
    product_currency varchar(3);
BEGIN
    SELECT organization_id, currency
    INTO product_organization_id, product_currency
    FROM retail_product
    WHERE id = NEW.product_id
    FOR SHARE;

    IF NOT FOUND THEN
        RAISE EXCEPTION 'Sale item product does not exist'
            USING ERRCODE = '23503';
    END IF;

    SELECT organization_id, currency
    INTO sale_organization_id, sale_currency
    FROM retail_sale
    WHERE id = NEW.sale_id
    FOR SHARE;

    IF NOT FOUND THEN
        RAISE EXCEPTION 'Sale item sale does not exist'
            USING ERRCODE = '23503';
    END IF;

    IF sale_organization_id IS DISTINCT FROM product_organization_id
       OR sale_currency IS DISTINCT FROM product_currency THEN
        RAISE EXCEPTION 'Sale item organization or currency mismatch'
            USING ERRCODE = '23514';
    END IF;

    RETURN NEW;
END;
$$;
"""

INVENTORY_INTEGRITY_SQL = """
CREATE FUNCTION retail_check_inventory_integrity()
RETURNS trigger
LANGUAGE plpgsql
AS $$
DECLARE
    branch_organization_id uuid;
    product_organization_id uuid;
BEGIN
    SELECT organization_id
    INTO branch_organization_id
    FROM retail_branch
    WHERE id = NEW.branch_id
    FOR SHARE;

    IF NOT FOUND THEN
        RAISE EXCEPTION 'Inventory branch does not exist'
            USING ERRCODE = '23503';
    END IF;

    SELECT organization_id
    INTO product_organization_id
    FROM retail_product
    WHERE id = NEW.product_id
    FOR SHARE;

    IF NOT FOUND THEN
        RAISE EXCEPTION 'Inventory product does not exist'
            USING ERRCODE = '23503';
    END IF;

    IF branch_organization_id IS DISTINCT FROM product_organization_id THEN
        RAISE EXCEPTION 'Inventory branch and product organization mismatch'
            USING ERRCODE = '23514';
    END IF;

    RETURN NEW;
END;
$$;
"""

BRANCH_PROTECTION_SQL = """
CREATE FUNCTION retail_protect_branch_integrity()
RETURNS trigger
LANGUAGE plpgsql
AS $$
BEGIN
    IF NEW.organization_id IS NOT DISTINCT FROM OLD.organization_id THEN
        RETURN NEW;
    END IF;

    IF EXISTS (
        SELECT 1
        FROM retail_sale
        WHERE branch_id = NEW.id
          AND organization_id IS DISTINCT FROM NEW.organization_id
    ) OR EXISTS (
        SELECT 1
        FROM retail_inventorybalance AS balance
        JOIN retail_product AS product
          ON product.id = balance.product_id
        WHERE balance.branch_id = NEW.id
          AND product.organization_id IS DISTINCT FROM NEW.organization_id
    ) THEN
        RAISE EXCEPTION 'Branch organization change violates retail integrity'
            USING ERRCODE = '23514';
    END IF;

    RETURN NEW;
END;
$$;
"""

PRODUCT_PROTECTION_SQL = """
CREATE FUNCTION retail_protect_product_integrity()
RETURNS trigger
LANGUAGE plpgsql
AS $$
BEGIN
    IF NEW.organization_id IS NOT DISTINCT FROM OLD.organization_id
       AND NEW.currency IS NOT DISTINCT FROM OLD.currency THEN
        RETURN NEW;
    END IF;

    IF EXISTS (
        SELECT 1
        FROM retail_saleitem AS item
        JOIN retail_sale AS sale ON sale.id = item.sale_id
        WHERE item.product_id = NEW.id
          AND (
              sale.organization_id IS DISTINCT FROM NEW.organization_id
              OR sale.currency IS DISTINCT FROM NEW.currency
          )
    ) OR EXISTS (
        SELECT 1
        FROM retail_inventorybalance AS balance
        JOIN retail_branch AS branch
          ON branch.id = balance.branch_id
        WHERE balance.product_id = NEW.id
          AND branch.organization_id IS DISTINCT FROM NEW.organization_id
    ) THEN
        RAISE EXCEPTION 'Product change violates retail integrity'
            USING ERRCODE = '23514';
    END IF;

    RETURN NEW;
END;
$$;
"""

SALE_PROTECTION_SQL = """
CREATE FUNCTION retail_protect_sale_integrity()
RETURNS trigger
LANGUAGE plpgsql
AS $$
BEGIN
    IF NEW.organization_id IS NOT DISTINCT FROM OLD.organization_id
       AND NEW.currency IS NOT DISTINCT FROM OLD.currency THEN
        RETURN NEW;
    END IF;

    IF EXISTS (
        SELECT 1
        FROM retail_saleitem AS item
        JOIN retail_product AS product
          ON product.id = item.product_id
        WHERE item.sale_id = NEW.id
          AND (
              product.organization_id IS DISTINCT FROM NEW.organization_id
              OR product.currency IS DISTINCT FROM NEW.currency
          )
    ) THEN
        RAISE EXCEPTION 'Sale change violates existing sale item integrity'
            USING ERRCODE = '23514';
    END IF;

    RETURN NEW;
END;
$$;
"""

INVENTORYBALANCE_PROTECTION_SQL = """
CREATE FUNCTION retail_protect_inventorybalance_integrity()
RETURNS trigger
LANGUAGE plpgsql
AS $$
BEGIN
    IF NEW.branch_id IS NOT DISTINCT FROM OLD.branch_id
       AND NEW.product_id IS NOT DISTINCT FROM OLD.product_id THEN
        RETURN NEW;
    END IF;

    IF EXISTS (
        SELECT 1
        FROM retail_stockmovement
        WHERE balance_id = OLD.id
    ) THEN
        RAISE EXCEPTION
            'Inventory balance cannot be reassigned after stock movements exist'
            USING ERRCODE = '23514';
    END IF;

    RETURN NEW;
END;
$$;
"""

STOCKMOVEMENT_LOCK_SQL = """
CREATE FUNCTION retail_lock_inventorybalance_for_movement()
RETURNS trigger
LANGUAGE plpgsql
AS $$
DECLARE
    locked_balance_id uuid;
BEGIN
    IF TG_OP = 'INSERT' THEN
        SELECT id
        INTO locked_balance_id
        FROM retail_inventorybalance
        WHERE id = NEW.balance_id
        FOR UPDATE;

        IF NOT FOUND THEN
            RAISE EXCEPTION 'Stock movement inventory balance does not exist'
                USING ERRCODE = '23503';
        END IF;

        RETURN NEW;

    ELSIF TG_OP = 'DELETE' THEN
        SELECT id
        INTO locked_balance_id
        FROM retail_inventorybalance
        WHERE id = OLD.balance_id
        FOR UPDATE;

        IF NOT FOUND THEN
            RAISE EXCEPTION 'Stock movement inventory balance does not exist'
                USING ERRCODE = '23503';
        END IF;

        RETURN OLD;

    ELSE
        PERFORM id
        FROM retail_inventorybalance
        WHERE id IN (OLD.balance_id, NEW.balance_id)
        ORDER BY id
        FOR UPDATE;

        RETURN NEW;
    END IF;
END;
$$;
"""

INVENTORYBALANCE_PROTECTION_TRIGGER_SQL = """
CREATE TRIGGER retail_inventorybalance_protection_trigger
BEFORE UPDATE OF branch_id, product_id
ON retail_inventorybalance
FOR EACH ROW
EXECUTE FUNCTION retail_protect_inventorybalance_integrity();
"""


STOCKMOVEMENT_INSERT_TRIGGER_SQL = """
CREATE TRIGGER retail_stockmovement_insert_lock
BEFORE INSERT
ON retail_stockmovement
FOR EACH ROW
EXECUTE FUNCTION retail_lock_inventorybalance_for_movement();
"""

STOCKMOVEMENT_UPDATE_TRIGGER_SQL = """
CREATE TRIGGER retail_stockmovement_update_lock
BEFORE UPDATE
ON retail_stockmovement
FOR EACH ROW
EXECUTE FUNCTION retail_lock_inventorybalance_for_movement();
"""

STOCKMOVEMENT_DELETE_TRIGGER_SQL = """
CREATE TRIGGER retail_stockmovement_delete_lock
BEFORE DELETE
ON retail_stockmovement
FOR EACH ROW
EXECUTE FUNCTION retail_lock_inventorybalance_for_movement();
"""

SALE_TRIGGER_SQL = """
CREATE TRIGGER retail_sale_integrity_trigger
BEFORE INSERT OR UPDATE OF branch_id, organization_id
ON retail_sale
FOR EACH ROW
EXECUTE FUNCTION retail_check_sale_integrity();
"""
SALEITEM_TRIGGER_SQL = """
CREATE TRIGGER retail_saleitem_integrity_trigger
BEFORE INSERT OR UPDATE OF sale_id, product_id
ON retail_saleitem
FOR EACH ROW
EXECUTE FUNCTION retail_check_saleitem_integrity();
"""
INVENTORY_TRIGGER_SQL = """
CREATE TRIGGER retail_inventory_integrity_trigger
BEFORE INSERT OR UPDATE OF branch_id, product_id
ON retail_inventorybalance
FOR EACH ROW
EXECUTE FUNCTION retail_check_inventory_integrity();
"""
BRANCH_TRIGGER_SQL = """
CREATE TRIGGER retail_branch_protection_trigger
BEFORE UPDATE OF organization_id
ON retail_branch
FOR EACH ROW
EXECUTE FUNCTION retail_protect_branch_integrity();
"""
PRODUCT_TRIGGER_SQL = """
CREATE TRIGGER retail_product_protection_trigger
BEFORE UPDATE OF organization_id, currency
ON retail_product
FOR EACH ROW
EXECUTE FUNCTION retail_protect_product_integrity();
"""
SALE_PROTECTION_TRIGGER_SQL = """
CREATE TRIGGER retail_sale_protection_trigger
BEFORE UPDATE OF organization_id, currency
ON retail_sale
FOR EACH ROW
EXECUTE FUNCTION retail_protect_sale_integrity();
"""

def install_retail_integrity(apps, schema_editor):
    if schema_editor.connection.vendor != "postgresql":
        return

    statements = (
        SALE_INTEGRITY_SQL,
        SALEITEM_INTEGRITY_SQL,
        INVENTORY_INTEGRITY_SQL,
        BRANCH_PROTECTION_SQL,
        PRODUCT_PROTECTION_SQL,
        SALE_PROTECTION_SQL,
        INVENTORYBALANCE_PROTECTION_SQL,
        STOCKMOVEMENT_LOCK_SQL,
        SALE_TRIGGER_SQL,
        SALEITEM_TRIGGER_SQL,
        INVENTORY_TRIGGER_SQL,
        BRANCH_TRIGGER_SQL,
        PRODUCT_TRIGGER_SQL,
        SALE_PROTECTION_TRIGGER_SQL,
        INVENTORYBALANCE_PROTECTION_TRIGGER_SQL,
        STOCKMOVEMENT_INSERT_TRIGGER_SQL,
        STOCKMOVEMENT_UPDATE_TRIGGER_SQL,
        STOCKMOVEMENT_DELETE_TRIGGER_SQL,
    )

    for statement in statements:
        schema_editor.execute(statement)


def uninstall_retail_integrity(apps, schema_editor):
    if schema_editor.connection.vendor != "postgresql":
        return

    triggers = (
        ("retail_stockmovement_delete_lock", "retail_stockmovement"),
        ("retail_stockmovement_update_lock", "retail_stockmovement"),
        ("retail_stockmovement_insert_lock", "retail_stockmovement"),
        ("retail_inventorybalance_protection_trigger", "retail_inventorybalance"),
        ("retail_sale_protection_trigger", "retail_sale"),
        ("retail_product_protection_trigger", "retail_product"),
        ("retail_branch_protection_trigger", "retail_branch"),
        ("retail_inventory_integrity_trigger", "retail_inventorybalance"),
        ("retail_saleitem_integrity_trigger", "retail_saleitem"),
        ("retail_sale_integrity_trigger", "retail_sale"),
    )

    for trigger_name, table_name in triggers:
        schema_editor.execute(
            f"DROP TRIGGER IF EXISTS {trigger_name} ON {table_name};"
        )

    functions = (
        "retail_lock_inventorybalance_for_movement",
        "retail_protect_inventorybalance_integrity",
        "retail_protect_sale_integrity",
        "retail_protect_product_integrity",
        "retail_protect_branch_integrity",
        "retail_check_inventory_integrity",
        "retail_check_saleitem_integrity",
        "retail_check_sale_integrity",
    )

    for function_name in functions:
        schema_editor.execute(
            f"DROP FUNCTION IF EXISTS {function_name}();"
        )

class Migration(migrations.Migration):
    dependencies = [
        (
            "retail",
            "0002_inventorybalance_sale_saleitem_stockmovement_and_more",
        ),
    ]

    operations = [
        migrations.RunPython(
            install_retail_integrity,
            uninstall_retail_integrity,
        ),
    ]
