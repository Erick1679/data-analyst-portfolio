# Database Completion — Planning Checkpoint

**Checkpoint ID:** CP-DB-03  
**Date:** 2026-11-06  
**Chunk:** DB-03 — Inventory transaction services  
**Repository:** `Erick1679/data-analyst-portfolio`  
**Base commit:** `4490c129b210a52267d49dfe9eae724d4191f619`  
**Planning branch:** `feature/db-03-inventory-transaction-services`  
**Status:** DRAFT — AWAITING USER REVIEW AND EXPLICIT APPROVAL

## 1. Purpose

Plan the service layer for safe inventory receipts and adjustments using the existing retail schema and PostgreSQL integrity protections. This checkpoint is a planning artifact only; no DB-03 service implementation or migration has started.

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

These are proposed criteria; exact business rules must be confirmed before implementation.

## 6. Design questions to resolve before coding

- Approve the inventory audit action names (for example, `retail.stock_received` and `retail.stock_adjusted`) to add to the existing audit allowlist?
- Is the existing `manage_inventory` permission sufficient for receipts and both adjustment directions, or should the role matrix distinguish these operations?
- Must every adjustment include a controlled reason code, free-text note, external reference, or a combination? The current model has notes/reference but no reason-code field.
- What durable idempotency contract is required? The current optional `StockMovement.reference` is not unique and must not be treated as an idempotency key without an explicit rule and constraint.
- Confirm zero is allowed and negative balances are forbidden for all operations; the existing balance check already rejects negative stored balances.
- Can balances be initialized lazily on first receipt, or must they be pre-created?
- Should stock movements be append-only at the database level (reject UPDATE/DELETE) with corrections represented only by compensating movements? DB-02 currently locks movement updates/deletes but does not prohibit them.
- Which existing API surface, if any, should expose these services? Avoid adding endpoints unless the current architecture and product need justify them.

## 7. Out of scope

- Sales draft/completion/void/refund lifecycle and sale-driven stock deduction (DB-04).
- New production database changes or deployment.
- Audit-event retention/pruning changes.
- Sustained production-like load testing unless separately planned and approved.

## 8. Files and implementation impact

No implementation files are approved or changed by this planning checkpoint. After approval, the exact service, test, and possible migration files will be determined from the repository's existing architecture and recorded before implementation.

## 9. Risks and safeguards

- A balance row may not exist when two receipts arrive concurrently; a normal `select_for_update()` alone does not lock a missing row.
- Balance, movement, and audit writes must share one atomic transaction to avoid ledger drift.
- Retry handling without a durable idempotency rule can double-apply stock.
- Authorization must be checked against the organization and branch on every operation.
- Movement quantities are positive and movement type carries direction; service arithmetic must consistently add receipt/adjustment-in and subtract adjustment-out. The audit allowlist needs approved retail action codes.
- DB-02 concurrency tests are evidence for their named scenarios only and do not replace DB-03 service-level concurrency tests.

## 10. Checkpoint decision

**Decision:** AWAITING USER.

Available decisions:

- APPROVE DB-03 PLAN — authorize detailed implementation design and the approved scope above.
- REQUEST CHANGES — revise the plan before implementation.
- HOLD — pause the database completion work.

No DB-03 implementation, migration, or production action may begin until the user explicitly approves this checkpoint.
