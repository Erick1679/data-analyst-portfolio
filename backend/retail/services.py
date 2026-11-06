"""Organization-scoped services for Brights Retail Intelligence."""

import uuid
from decimal import Decimal, InvalidOperation

from django.core.exceptions import PermissionDenied, ValidationError
from django.db import IntegrityError, connection, transaction
from django.db.models import F, Sum

from auditlog.services import record_audit_event

from .models import Branch, InventoryBalance, Product, StockMovement
from .permissions import has_retail_permission


def get_organization_products(user, organization):
    """Return products only when retail viewing is authorized."""

    if not has_retail_permission(
        user,
        organization,
        "view_retail",
    ):
        raise PermissionDenied(
            "You do not have permission to view retail products."
        )

    return Product.objects.filter(
        organization=organization,
    ).order_by("name", "sku")


def get_organization_branches(user, organization):
    """Return branches only when retail viewing is authorized."""

    if not has_retail_permission(
        user,
        organization,
        "view_retail",
    ):
        raise PermissionDenied(
            "You do not have permission to view retail branches."
        )

    return Branch.objects.filter(
        organization=organization,
    ).order_by("name", "code")


# ---------------------------------------------------------------------------
# Inventory transaction services
# ---------------------------------------------------------------------------



class InsufficientStockError(ValidationError):
    """Raised when an outbound movement would make stock negative."""


_REASON_CODES = {
    StockMovement.MovementType.RECEIPT: {
        "",
        StockMovement.ReasonCode.SUPPLIER_DELIVERY,
        StockMovement.ReasonCode.CUSTOMER_RETURN,
        StockMovement.ReasonCode.OPENING_STOCK,
        StockMovement.ReasonCode.OTHER,
    },
    StockMovement.MovementType.ADJUSTMENT_IN: {
        StockMovement.ReasonCode.STOCK_COUNT,
        StockMovement.ReasonCode.FOUND_STOCK,
        StockMovement.ReasonCode.CUSTOMER_RETURN,
        StockMovement.ReasonCode.OTHER,
    },
    StockMovement.MovementType.ADJUSTMENT_OUT: {
        StockMovement.ReasonCode.STOCK_COUNT,
        StockMovement.ReasonCode.DAMAGE,
        StockMovement.ReasonCode.EXPIRY,
        StockMovement.ReasonCode.LOSS,
        StockMovement.ReasonCode.INTERNAL_USE,
        StockMovement.ReasonCode.OTHER,
    },
}


def _validate_inventory_quantity(quantity):
    if not isinstance(quantity, Decimal):
        raise ValidationError("Quantity must be a Decimal value.")
    if not quantity.is_finite() or quantity <= 0:
        raise ValidationError("Quantity must be a finite value greater than zero.")
    try:
        normalized = quantity.quantize(Decimal("0.001"))
    except InvalidOperation as exc:
        raise ValidationError("Quantity must have at most three decimal places.") from exc
    if normalized != quantity:
        raise ValidationError("Quantity must have at most three decimal places.")
    if len(normalized.as_tuple().digits) > 16:
        raise ValidationError("Quantity exceeds the supported precision.")
    return normalized


def _validate_idempotency_key(key):
    if isinstance(key, uuid.UUID):
        return key
    if isinstance(key, str):
        try:
            return uuid.UUID(key)
        except (ValueError, AttributeError) as exc:
            raise ValidationError("A valid UUID idempotency key is required.") from exc
    raise ValidationError("A valid UUID idempotency key is required.")


def _movement_fingerprint(movement):
    balance = movement.balance
    return (
        balance.branch.organization_id,
        movement.recorded_by_id,
        balance.branch_id,
        balance.product_id,
        movement.movement_type,
        movement.quantity,
        movement.reason_code,
        movement.reference,
        movement.notes,
    )


def _request_fingerprint(*, organization, user, branch, product, movement_type,
                         quantity, reason_code, reference, notes):
    return (
        organization.pk,
        user.pk,
        branch.pk,
        product.pk,
        movement_type,
        quantity,
        reason_code,
        reference,
        notes,
    )


def _get_idempotent_replay(*, key, fingerprint):
    existing = (
        StockMovement.objects.select_related(
            "balance__branch",
            "balance__product",
        )
        .filter(idempotency_key=key)
        .first()
    )
    if existing is None:
        return None
    if _movement_fingerprint(existing) != fingerprint:
        raise ValidationError(
            "Idempotency key has already been used for a different request."
        )
    return existing


@transaction.atomic
def _record_inventory_movement(
    *,
    user,
    organization,
    branch_id,
    product_id,
    quantity,
    idempotency_key,
    movement_type,
    reason_code="",
    reference="",
    notes="",
):
    if not has_retail_permission(user, organization, "manage_inventory"):
        raise PermissionDenied(
            "You do not have permission to manage inventory in this organization."
        )

    if not isinstance(reference, str) or len(reference) > 100:
        raise ValidationError("Reference must be a string of at most 100 characters.")
    if not isinstance(notes, str):
        raise ValidationError("Notes must be a string.")

    quantity = _validate_inventory_quantity(quantity)
    key = _validate_idempotency_key(idempotency_key)

    if not isinstance(movement_type, str) or movement_type not in _REASON_CODES:
        raise ValidationError("Unsupported inventory movement type.")
    if not isinstance(reason_code, str) or reason_code not in _REASON_CODES[movement_type]:
        raise ValidationError("Reason code is invalid for this movement type.")

    # Lock tenant-owned reference rows in a consistent order so a branch
    # or product cannot be deactivated/reassigned during this operation.
    branch = Branch.objects.select_for_update().filter(
        pk=branch_id,
        organization=organization,
        is_active=True,
    ).first()
    product = Product.objects.select_for_update().filter(
        pk=product_id,
        organization=organization,
        is_active=True,
    ).first()
    if branch is None or product is None:
        raise ValidationError("An active branch and product in this organization are required.")

    fingerprint = _request_fingerprint(
        organization=organization,
        user=user,
        branch=branch,
        product=product,
        movement_type=movement_type,
        quantity=quantity,
        reason_code=reason_code,
        reference=reference,
        notes=notes,
    )

    replay = _get_idempotent_replay(key=key, fingerprint=fingerprint)
    if replay is not None:
        return replay

    try:
        with transaction.atomic():
            balance, _created = InventoryBalance.objects.get_or_create(
                branch=branch,
                product=product,
                defaults={"opening_quantity": Decimal("0.000")},
            )
            balance = InventoryBalance.objects.select_for_update().get(pk=balance.pk)

            outbound = movement_type == StockMovement.MovementType.ADJUSTMENT_OUT
            if outbound and balance.quantity_on_hand < quantity:
                raise InsufficientStockError(
                    "Adjustment would reduce available stock below zero."
                )

            movement = StockMovement.objects.create(
                balance=balance,
                movement_type=movement_type,
                quantity=quantity,
                reason_code=reason_code,
                idempotency_key=key,
                recorded_by=user,
                reference=reference,
                notes=notes,
            )

            # PostgreSQL applies this delta in the AFTER INSERT trigger.
            # Keep SQLite-based unit suites useful without weakening the
            # PostgreSQL enforcement boundary.
            if connection.vendor != "postgresql":
                delta = -quantity if outbound else quantity
                InventoryBalance.objects.filter(pk=balance.pk).update(
                    quantity_on_hand=F("quantity_on_hand") + delta
                )

            action = (
                "retail.stock_received"
                if movement_type == StockMovement.MovementType.RECEIPT
                else "retail.stock_adjusted"
            )
            record_audit_event(
                action=action,
                outcome="success",
                organization=organization,
                actor=user,
                target_type="retail.StockMovement",
                target_id=str(movement.pk),
            )
            return movement

    except IntegrityError:
        # A concurrent request may have committed this same unique key.
        # The failed atomic block has rolled back before we inspect it.
        replay = _get_idempotent_replay(key=key, fingerprint=fingerprint)
        if replay is not None:
            return replay
        raise


def receive_stock(
    *,
    user,
    organization,
    branch_id,
    product_id,
    quantity,
    idempotency_key,
    reason_code="",
    reference="",
    notes="",
):
    """Record a receipt and atomically apply its stock increase."""
    return _record_inventory_movement(
        user=user,
        organization=organization,
        branch_id=branch_id,
        product_id=product_id,
        quantity=quantity,
        idempotency_key=idempotency_key,
        movement_type=StockMovement.MovementType.RECEIPT,
        reason_code=reason_code,
        reference=reference,
        notes=notes,
    )


def adjust_stock(
    *,
    user,
    organization,
    branch_id,
    product_id,
    direction,
    quantity,
    reason_code,
    idempotency_key,
    reference="",
    notes="",
):
    """Record a positive or negative stock adjustment."""
    if not isinstance(direction, str) or direction not in {
        StockMovement.MovementType.ADJUSTMENT_IN,
        StockMovement.MovementType.ADJUSTMENT_OUT,
    }:
        raise ValidationError("Direction must be adjustment_in or adjustment_out.")
    return _record_inventory_movement(
        user=user,
        organization=organization,
        branch_id=branch_id,
        product_id=product_id,
        quantity=quantity,
        idempotency_key=idempotency_key,
        movement_type=direction,
        reason_code=reason_code,
        reference=reference,
        notes=notes,
    )


def reconcile_inventory_balances(*, user, organization):
    """Return read-only expected-versus-stored inventory quantities."""
    if not has_retail_permission(user, organization, "view_retail"):
        raise PermissionDenied(
            "You do not have permission to view inventory in this organization."
        )

    balances = (
        InventoryBalance.objects.filter(
            branch__organization=organization,
            product__organization=organization,
        )
        .select_related("branch", "product")
        .order_by("pk")
    )
    results = []
    for balance in balances:
        signed_total = Decimal("0.000")
        movements = balance.movements.values("movement_type").annotate(
            total=Sum("quantity")
        )
        for row in movements:
            total = row["total"] or Decimal("0.000")
            if row["movement_type"] in {
                StockMovement.MovementType.RECEIPT,
                StockMovement.MovementType.ADJUSTMENT_IN,
            }:
                signed_total += total
            else:
                signed_total -= total
        expected = balance.opening_quantity + signed_total
        variance = balance.quantity_on_hand - expected
        results.append({
            "balance_id": balance.pk,
            "opening_quantity": balance.opening_quantity,
            "signed_movement_total": signed_total,
            "expected_quantity": expected,
            "stored_quantity": balance.quantity_on_hand,
            "variance": variance,
            "is_reconciled": variance == 0,
        })
    return results
