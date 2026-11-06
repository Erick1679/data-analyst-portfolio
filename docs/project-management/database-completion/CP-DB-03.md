# Database Completion — Planning Checkpoint

**Checkpoint ID:** CP-DB-03  
**Date:** 2026-11-06  
**Chunk:** DB-03 — Inventory transaction services  
**Repository:** `Erick1679/data-analyst-portfolio`  
**Base commit:** `4490c129b210a52267d49dfe9eae724d4191f619`  
**Planning branch:** `feature/db-03-inventory-transaction-services`  
**Status:** IMPLEMENTATION IN PROGRESS — AUTHORIZED BY MAINTAINER ON 2026-11-06

## 1. Purpose

Plan the service layer for safe inventory receipts and adjustments using the existing retail schema and PostgreSQL integrity protections. This checkpoint records the approved detailed design and active implementation on the existing feature branch. No production migration or deployment is authorized.

## 2. Proposed scope

- Stock receipt service.
- Positive and negative stock adjustment service.
- Atomic balance creation/update and stock movement recording.
- Authorization and organization/branch tenant scoping.
- Audit-event recording in the same database transaction, subject to the existing audit architecture.
- Idempotency and duplicate-request handling.
- Historical movement protection and balance reconciliation.
- Rollback and concurrency regression tests.

Sales completion and sale-driven stock deduction remain DB-04 unless the user explicitly approves a scope change.

## 3. Repository architecture findings

The current branch was inspected at the DB-03 planning baseline. These findings describe the existing implementation; they do not authorize changes.

### Retail services and authorization
- `backend/retail/services.py` currently contains organization-scoped read services for products and branches. There are no inventory receipt or adjustment write services yet.
- Services are function-based. Existing service functions raise Django `PermissionDenied` when authorization fails.
- `backend/retail/permissions.py` defines `manage_inventory` for the owner, admin, manager, and editor roles. It delegates active-user, active-organization, and active-membership checks to `datasets.permissions.get_active_membership`.
- The existing retail HTTP views expose read-only GET endpoints. There is no inventory write endpoint. Service implementation should be separated from any API decision; a new endpoint is not automatically required by this chunk.
- The existing role matrix grants one broad `manage_inventory` permission. It does not distinguish receipt, positive adjustment, and negative adjustment permissions. Do not invent a finer role split without a product/security decision.

### Existing inventory data model
- `InventoryBalance` is unique per branch/product pair, stores `quantity_on_hand` as a three-decimal Decimal with default zero, and has a database check preventing negative balances.
- `StockMovement` stores a positive three-decimal quantity; `movement_type` expresses receipt, sale, adjustment-in, or adjustment-out direction. It also stores `recorded_by`, optional `reference`, optional `notes`, and creation time.
- The movement's balance and actor foreign keys use `PROTECT`. The optional `reference` has no uniqueness constraint and is not a safe idempotency key by itself.
- There is no existing idempotency-key field/model, no stock adjustment reason-code field, and no ledger-to-balance reconciliation constraint.

### PostgreSQL protections already present
- DB-02 enforces branch/product tenant consistency and a unique branch/product balance.
- The stock-movement insert, update, and delete triggers lock the associated inventory balance. Movement updates lock the old/new balance rows in deterministic ID order.
- These triggers provide locking; they do not make movement rows append-only. Existing SQL protections do not prohibit changing or deleting a movement, so immutable history would need an explicit service and/or database enforcement design.

### Audit-event integration
- `AuditEvent` records organization, nullable actor, action, outcome, target type, target ID, and timestamp. It intentionally does not store arbitrary payloads or quantity snapshots.
- `auditlog.services.record_audit_event` is the existing approved write path. It validates inputs and is wrapped in `transaction.atomic`; when called inside an outer inventory transaction, its nested atomic block participates in that transaction.
- The current `ALLOWED_AUDIT_ACTIONS` allowlist contains dataset and membership actions only. Inventory-specific action names must be deliberately added and tested before the inventory service can record them; otherwise the audit service rejects them.
- Existing audit tests verify rejection of unsupported actions, so adding approved retail action codes needs focused positive and negative regression coverage.

### Test conventions
- Retail has separate service, permission, API, database-integrity, and concurrency test modules.
- The DB-integrity concurrency tests use PostgreSQL `TransactionTestCase`, worker threads, separate database connections, and controlled barriers/timeouts. DB-03 should follow the established pattern for service-level races.
- The existing retail service tests use Django `TestCase` for organization-scoped service behavior.

## 4. Planning sequence

1. Inspect the existing retail app structure: services, selectors, views/API endpoints, permissions, and test conventions.
2. Inspect the audit-event model and existing audit-writing mechanism. Identify required fields and transaction behavior; do not invent a parallel audit system.
3. Define invariants for receipts and adjustments: quantity sign, movement type, precision, reason/reference requirements, actor, tenant scope, and permitted balance floor.
4. Design race-safe balance initialization and update. Address concurrent first-time creation, row locking, deterministic lock ordering for multi-balance operations, and PostgreSQL behavior.
5. Define idempotency keys or another duplicate-request strategy, including retry behavior and uniqueness enforcement if needed.
6. Define immutable-history and reconciliation rules. Prefer compensating movements over editing/deleting historical records where appropriate; verify this against existing product requirements.
7. Prepare a requirements-to-tests matrix and implementation file plan for user review.

## 5. Proposed acceptance criteria

| Area | Acceptance evidence required |
|---|---|
| Tenant isolation | Cross-organization branch/product/balance access is rejected |
| Authorization | Only permitted users can receive or adjust stock |
| Receipt | Balance and receipt movement commit together |
| Adjustment | Balance and adjustment movement commit together; reason/reference rules enforced |
| Atomicity | Any movement/audit/balance failure rolls back the whole operation |
| Balance initialization | Concurrent first receipts create one valid balance without lost updates |
| Concurrency | Concurrent operations serialize safely and preserve the ledger/balance relationship |
| Idempotency | Retried requests do not create duplicate movements or apply quantity twice |
| Nonnegative stock | Outbound adjustments cannot reduce stock below the approved floor |
| History | Historical movement tampering is rejected or handled through an approved compensating operation |
| Reconciliation | Balance can be reconciled against opening quantity plus signed movements |
| Regression | Targeted PostgreSQL tests and relevant retail/backend regressions pass |

These acceptance criteria are approved for DB-03 implementation and verification.

## 6. Approved decisions — single maintainer approval

**Decision:** APPROVED on 2026-11-06 by the project's single maintainer/reviewer. No second reviewer is required.

1. **Authorization:** Reuse the existing `manage_inventory` permission for stock receipts, positive adjustments, and negative adjustments. Do not introduce separate role permissions in DB-03.
2. **Audit actions:** Extend the existing audit allowlist with `retail.stock_received` and `retail.stock_adjusted`. Use the existing `record_audit_event` path; do not create a parallel audit system.
3. **Adjustment reasons:** Every adjustment must carry a reason code. Notes and external references remain optional. The controlled reason-code vocabulary and storage representation must be specified before coding.
4. **Movement history:** Enforce append-only stock movements at the database level by rejecting UPDATE and DELETE. Corrections must be recorded as compensating movements, not edits to historical rows.

These four decisions, together with the seven detailed defaults approved in section 10, authorize DB-03 implementation on the feature branch. They do not authorize production changes, audit-event pruning, DB-04 sales lifecycle work, or a new inventory API.

## 7. Detailed service and data design

### 7.1 Service boundary and contracts

Keep DB-03 service-only. Do not add a write API, URL, serializer, or view in this chunk. This follows the existing retail architecture: function-based services in `retail/services.py`, organization-scoped permission checks, and read-only HTTP endpoints.

Proposed service contracts:

```python
receive_stock(
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
)

adjust_stock(
    *,
    user,
    organization,
    branch_id,
    product_id,
    direction,  # adjustment_in or adjustment_out
    quantity,
    reason_code,
    idempotency_key,
    reference="",
    notes="",
)
```

Both functions return the resulting `StockMovement`. A repeated request with the same key and identical semantic payload returns the original movement and does not write another movement or audit event.

Use Django's existing exception conventions:
- `PermissionDenied` when the user lacks active `manage_inventory` permission for the supplied organization.
- `ValidationError` for invalid identifiers, inactive/mismatched branch or product, malformed quantity, unsupported reason code, or idempotency-key reuse with a different payload.
- A small `InsufficientStockError` domain exception (subclassing `ValidationError`) for an adjustment-out that would make stock negative.

The organization is an explicit service argument. Resolve branch and product with queries scoped to that organization; do not fetch globally and authorize afterward. Reject inactive branches and products. The existing membership helper continues to enforce active user, organization, and membership status.

### 7.2 Quantity and movement semantics

- Accept `Decimal` quantities only; reject binary floats and non-finite values.
- Quantity must be greater than zero and exactly representable at three decimal places. Do not silently round.
- Keep movement quantity positive. Movement type determines the signed effect:
  - `receipt`: add quantity.
  - `adjustment_in`: add quantity.
  - `adjustment_out`: subtract quantity.
  - `sale`: subtract quantity (reserved for DB-04).
- Zero stock is valid. Negative stock is never valid.
- Do not change product selling price or currency as part of inventory movement processing.

Proposed controlled reason-code vocabulary:

| Movement type | Allowed reason codes | Requirement |
|---|---|---|
| `receipt` | `supplier_delivery`, `customer_return`, `opening_stock`, `other` | Optional; use `opening_stock` for an explicit opening-stock receipt |
| `adjustment_in` | `stock_count`, `found_stock`, `customer_return`, `other` | Required |
| `adjustment_out` | `stock_count`, `damage`, `expiry`, `loss`, `internal_use`, `other` | Required |
| `sale` | blank | DB-04 owns sale-driven movements |

Notes and external references remain optional, as approved. The reference field is descriptive only and is never an idempotency key. The reason-code vocabulary was explicitly approved as a DB-03 implementation default on 2026-11-06. It remains scoped to these inventory services and is not a general-purpose enterprise reason taxonomy.

### 7.3 Durable idempotency

Use a client-supplied UUID idempotency key on every new stock movement. Add a nullable, unique `StockMovement.idempotency_key` field so historical rows can remain null while a PostgreSQL BEFORE INSERT trigger requires a key for all new rows. A global UUID uniqueness constraint avoids needing to duplicate organization data on the movement row; the service still checks the caller's organization and permission before looking up a key.

- Key lifetime is permanent because the key is stored on the immutable movement; there is no expiry or pruning job.
- The request fingerprint consists of organization, actor, branch, product, movement type, exact quantity, reason code, reference, and notes.
- Same key + same fingerprint: return the original movement (idempotent replay).
- Same key + different fingerprint: raise a generic validation conflict; do not disclose the original movement or its tenant.
- A replay creates no new movement and no new audit event.
- Do not infer idempotency from `reference`; it is optional and not unique.

Concurrency algorithm: perform the normal lookup first; if absent, execute the complete operation in one outer `transaction.atomic()`. Create/lock the balance, then insert the movement with the unique key. If two transactions race on the same key, the unique constraint chooses one winner. The losing transaction must roll back completely; after leaving the failed atomic block, fetch the winning movement and compare the full fingerprint. Return it only on an exact match; otherwise raise the conflict. Re-raise unrelated integrity errors. This covers same-key requests aimed at different balances as well as the same balance.

### 7.4 Balance creation, locking, and transaction boundary

Create missing balances lazily at zero using the existing unique constraint on (branch, product) and Django's race-safe `get_or_create()` pattern. Then acquire `select_for_update()` on the balance before checking available stock and inserting the movement. The unique constraint resolves simultaneous first creation; the row lock serializes later operations.

A single DB-03 operation changes one branch/product balance. If a future operation touches multiple balances, lock them in deterministic primary-key order. DB-04 sale completion must follow that rule.

**Use the database movement-insert trigger as the single balance mutator.** The service must not also increment `quantity_on_hand`. DB-02 already locks the balance in the BEFORE INSERT movement trigger. DB-03 adds an AFTER INSERT trigger that applies the signed movement delta to `InventoryBalance.quantity_on_hand` and updates its timestamp. The existing nonnegative check remains the final database guard. The service checks the locked balance first to raise the domain-specific insufficient-stock error; the database constraint protects against direct SQL and unexpected paths.

The following writes must commit or roll back together:
1. Any new zero-quantity balance row (if this is the first movement).
2. The stock movement row.
3. The trigger-maintained balance change.
4. The success audit event.

If movement insertion, balance update, or audit recording fails, the entire transaction rolls back. Because `record_audit_event()` is already atomic, it participates in the caller's outer transaction.

### 7.5 Audit integration

Extend `auditlog.services.ALLOWED_AUDIT_ACTIONS` with exactly:
- `retail.stock_received`
- `retail.stock_adjusted`

Use the existing `record_audit_event()` function with outcome `success`, the organization and actor, target type `retail.StockMovement`, and the movement UUID as target ID. Do not place quantity, notes, reference, or other payload data in the audit event; the existing audit model is intentionally metadata-only.

Record the audit event after movement creation but before the outer transaction commits. A rejected/failed operation must not leave a success audit event. DB-03 does not create a parallel audit mechanism or alter authentication-event retention.

### 7.6 Append-only movement history

Add PostgreSQL BEFORE UPDATE and BEFORE DELETE triggers on `retail_stockmovement` that always raise an integrity exception. Corrections are new compensating movements with a new idempotency key and the appropriate adjustment direction/reason code.

The existing DB-02 movement UPDATE/DELETE lock triggers become unnecessary once writes are prohibited. The DB-03 migration should replace those two triggers with the append-only guards while retaining the existing INSERT balance-lock trigger. The trigger must reject no-op updates too; no field, including actor, quantity, balance, reference, notes, reason code, or idempotency key, is mutable after insertion.

Application-level model methods are not a sufficient protection because queryset updates and direct SQL bypass them. PostgreSQL is the enforcement boundary. Tests must exercise ORM `update()`, ORM `delete()`, and direct SQL.

### 7.7 Opening stock and reconciliation

Add an immutable `InventoryBalance.opening_quantity` Decimal field. During migration, set it to:

`current quantity_on_hand - signed sum of all existing stock movements for that balance`

If the result is negative, stop the migration and require manual investigation; do not silently rewrite historical movements or invent an actor. Add a PostgreSQL trigger preventing later changes to `opening_quantity`.

For new balances, `opening_quantity` defaults to zero. A new initial stock intake is represented by a normal receipt movement with reason code `opening_stock`; it is not written directly into the balance.

The reconciliation equation is:

`quantity_on_hand = opening_quantity + receipts + adjustments_in - adjustments_out - sales`

Build a read-only reconciliation query/helper that reports balance ID, opening quantity, signed movement total, expected quantity, stored quantity, and variance. It must not repair records automatically. A nonzero variance is a blocker for sign-off and requires investigation and a separately authorized compensating operation.

### 7.8 Migration and rollback design

Create one additive migration, proposed name `retail.0004_inventory_transaction_integrity`, after `0003_postgresql_tenant_integrity`.

Planned operations:
1. Add `reason_code`, nullable unique `idempotency_key`, and `opening_quantity`.
2. Backfill `opening_quantity` using the reconciliation formula above.
3. Fail with actionable IDs if any pre-existing adjustment movement lacks a reason code; classify those records explicitly before retrying the migration.
4. Add check constraints for valid movement types, reason-code/movement-type combinations, and nonnegative opening quantity.
5. Replace the DB-02 movement UPDATE/DELETE lock triggers with append-only guards; retain INSERT locking.
6. Install the idempotency/reason-code INSERT guard, the AFTER INSERT balance-application trigger, and the opening-quantity immutability trigger.
7. Add a reverse guard as the final migration operation so it executes first during rollback. If any post-migration movement has an idempotency key or new reason-code data, refuse reversal rather than silently discarding operational history. A clean, unused migration can be reversed and reapplied in the disposable migration-test database.

The migration is PostgreSQL-specific, additive, and safely reversible only before DB-03 movement data is written. No production migration is authorized by this design.

## 8. Implementation file plan

Implementation is authorized. The following files are being updated on the existing feature branch:

| File | Planned change |
|---|---|
| `backend/retail/models.py` | Add reason-code choices, idempotency key, and immutable opening quantity metadata/constraints |
| `backend/retail/services.py` | Add receipt/adjustment services and read-only reconciliation helper, following existing function-based conventions |
| `backend/auditlog/services.py` | Add the two approved retail audit action names |
| `backend/retail/migrations/0004_inventory_transaction_integrity.py` | Add fields, safe baseline backfill, constraints, and PostgreSQL triggers |
| `backend/retail/test_services.py` or a focused `test_inventory_services.py` | Test service contracts, authorization, validation, atomicity, audit, idempotency, and reconciliation |
| `backend/retail/test_db_integrity.py` | Test append-only, reason/idempotency guards, trigger-maintained balances, and opening-quantity immutability; replace DB-02 tests that expected movement updates to succeed |
| `backend/auditlog/test_services.py` | Test acceptance of the two retail actions and continued rejection of unsupported actions |
| Focused PostgreSQL concurrency test module | Test simultaneous first receipt, concurrent receipts/adjustments, duplicate idempotency keys, and lock behavior |

No API/view/URL files are planned for DB-03. No DB-04 sales lifecycle implementation is included.

## 9. Requirements-to-test matrix

| Requirement | Required regression evidence |
|---|---|
| Tenant scope | Own-organization branch/product succeeds; cross-organization and inactive records rejected |
| Authorization | Owner/admin/manager/editor can manage; analyst/auditor/viewer, outsider, inactive user, inactive membership, and inactive organization are denied |
| Quantity | Zero, negative, float, NaN/infinity, and more than three decimal places rejected; valid three-decimal values accepted |
| Receipt | Receipt movement and trigger-maintained balance increase commit together |
| Adjustments | Both directions require a valid direction-specific reason code; in adds and out subtracts |
| Stock floor | Adjustment-out above available quantity raises the domain error and leaves balance/movement/audit unchanged |
| Atomicity | Forced movement, trigger, or audit failure rolls back the complete operation |
| Lazy creation | Concurrent first receipts create exactly one balance and preserve the total quantity |
| Existing balance concurrency | Concurrent operations serialize and final balance equals opening quantity plus signed movements |
| Idempotency replay | Same key and same payload returns one movement, one balance effect, and one audit event |
| Idempotency conflict | Same key with different actor, tenant, product, quantity, reason, or other payload is rejected with no second effect |
| Append-only | ORM and direct SQL UPDATE/DELETE fail; compensating INSERT succeeds |
| Opening baseline | Migration backfill produces a nonnegative baseline; negative baseline or unclassified legacy adjustment aborts safely |
| Reconciliation | Exact expected/stored match passes; deliberate variance is reported without automatic repair |
| Audit | Only approved action names are accepted; audit and inventory changes share one transaction |
| Migration | Clean forward, reverse-before-use, reapply, trigger catalog, and migration consistency checks pass |
| Regression | Focused PostgreSQL tests, retail suite, then full backend suite pass |

Concurrency tests must use PostgreSQL `TransactionTestCase`, separate worker connections, barriers/timeouts, and database-observed lock behavior, consistent with DB-02. They demonstrate the named scenarios only; they are not a substitute for sustained load testing.

## 10. Approved detailed implementation defaults

The maintainer explicitly approved all seven defaults on 2026-11-06. These are implementation requirements:

1. Adopt the reason-code vocabulary in section 7.2, including the direction-specific allowed values.
2. Lazily create a missing branch/product balance at zero on the first receipt or adjustment-in. The first operation still requires a positive movement; no opening quantity is silently seeded.
3. Use a globally unique UUID idempotency key with permanent retention and exact-payload replay semantics.
4. Use `opening_quantity` as the immutable cutover baseline and fail migration if it would be negative or if legacy adjustment rows are unclassified.
5. Apply movement deltas in a PostgreSQL AFTER INSERT trigger so the database is the single balance mutator; services must never update the balance separately.
6. Reject inactive branches and products for new movements.
7. Keep DB-03 service-only; do not add a write API.

## 11. Risks and safeguards

- The migration may be blocked by existing unclassified adjustment movements or inconsistent historical balance data. Inspect and report those records before retrying; do not silently invent reasons or actors.
- The append-only rule intentionally changes DB-02 behavior: tests that previously demonstrated successful movement UPDATE/reassignment must be replaced with rejection tests. The balance itself remains the mutable current-state projection.
- Direct manual edits to `quantity_on_hand` can create a reconciliation variance; restrict operational writes to the approved service/database path and run the read-only reconciliation check.
- Unique idempotency keys are permanent. Clients must generate a fresh UUID for a genuinely new operation and reuse the same key only for retries of the same request.
- The movement-insert trigger applies `sale` deltas too; DB-04 must use the same service/database contract and deterministic multi-balance lock ordering.
- No sustained stress test, production deployment, backup/restore exercise, or production database inspection is included.

## 12. Out of scope

- Sales draft/completion/void/refund lifecycle and sale-driven stock deduction service/API (DB-04).
- Production database changes or deployment.
- Audit-event retention/pruning changes.
- New inventory write endpoints.
- Automatic reconciliation repairs.
- Sustained production-like load testing unless separately planned and approved.

## 13. Implementation checkpoint

**Decision:** IMPLEMENTATION AUTHORIZED — WORK IN PROGRESS ON THE EXISTING FEATURE BRANCH.

The maintainer approved all seven detailed defaults and explicitly authorized implementation on `feature/db-03-inventory-transaction-services`. Initial implementation commits now cover model metadata, receipt/adjustment services, audit actions, migration triggers, and regression tests. Automated test execution, migration validation, and final diff review remain outstanding. Production migration and deployment remain out of scope and are not authorized.
