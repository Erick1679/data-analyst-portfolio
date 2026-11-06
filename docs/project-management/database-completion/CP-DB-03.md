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

## 3. Planning sequence

1. Inspect the existing retail app structure: services, selectors, views/API endpoints, permissions, and test conventions.
2. Inspect the audit-event model and existing audit-writing mechanism. Identify required fields and transaction behavior; do not invent a parallel audit system.
3. Define invariants for receipts and adjustments: quantity sign, movement type, precision, reason/reference requirements, actor, tenant scope, and permitted balance floor.
4. Design race-safe balance initialization and update. Address concurrent first-time creation, row locking, deterministic lock ordering for multi-balance operations, and PostgreSQL behavior.
5. Define idempotency keys or another duplicate-request strategy, including retry behavior and uniqueness enforcement if needed.
6. Define immutable-history and reconciliation rules. Prefer compensating movements over editing/deleting historical records where appropriate; verify this against existing product requirements.
7. Prepare a requirements-to-tests matrix and implementation file plan for user review.

## 4. Proposed acceptance criteria

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

## 5. Design questions to resolve before coding

- Which existing audit-event model/service must receive the inventory audit event, and which fields are mandatory?
- Which roles/permissions can receive stock, make positive adjustments, and make negative adjustments?
- Must every adjustment include a reason code, free-text note, reference, or some combination?
- What is the idempotency contract for API retries and client-generated request identifiers?
- Is a zero balance allowed? Are negative balances categorically forbidden?
- Can balances be initialized lazily on first receipt, or must they be pre-created?
- Are corrections to historical movements prohibited, with all corrections represented by compensating movements?
- Which existing API surface, if any, should expose these services? Avoid adding endpoints unless the current architecture and product need justify them.

## 6. Out of scope

- Sales draft/completion/void/refund lifecycle and sale-driven stock deduction (DB-04).
- New production database changes or deployment.
- Audit-event retention/pruning changes.
- Sustained production-like load testing unless separately planned and approved.

## 7. Files and implementation impact

No implementation files are approved or changed by this planning checkpoint. After approval, the exact service, test, and possible migration files will be determined from the repository's existing architecture and recorded before implementation.

## 8. Risks and safeguards

- A balance row may not exist when two receipts arrive concurrently; a normal `select_for_update()` alone does not lock a missing row.
- Balance, movement, and audit writes must share one atomic transaction to avoid ledger drift.
- Retry handling without a durable idempotency rule can double-apply stock.
- Authorization must be checked against the organization and branch on every operation.
- The current schema has stock movement types for receipt, sale, and adjustments, but the sign convention and audit contract must be explicitly confirmed.
- DB-02 concurrency tests are evidence for their named scenarios only and do not replace DB-03 service-level concurrency tests.

## 9. Checkpoint decision

**Decision:** AWAITING USER.

Available decisions:

- APPROVE DB-03 PLAN — authorize detailed implementation design and the approved scope above.
- REQUEST CHANGES — revise the plan before implementation.
- HOLD — pause the database completion work.

No DB-03 implementation, migration, or production action may begin until the user explicitly approves this checkpoint.
