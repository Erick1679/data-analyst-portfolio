# The Brights Analytics — Chunked Database Completion Plan

Protocol: One chunk per session. Each chunk has 5–7 discrete steps, followed by evidence-based validation and a pause for user review and explicit approval.

## DB-01 — Retail schema baseline (6 steps)
1. Confirm feature branch and initial baseline — implementation reported complete; final Git status/commit evidence is not recorded in the current checkpoint.
2. Review `Branch`, `Product`, and retail permission/service conventions — completed.
3. Implement `Sale` and `SaleItem` and run Django checks — completed.
4. Implement `InventoryBalance` and `StockMovement`; generate and inspect `retail.0002` — completed.
5. Install handoff documents and run baseline checks — performed; exact Git diff and push status remain unverified.
6. Record remaining integrity gaps and migration design — superseded by DB-02 work and evidence below.

Checkpoint CP-DB-01: Historical checkpoint record available. The record documents PASS and user approval dated 2026-11-01. A Git commit reference is not recorded in the current evidence set.

## DB-02 — PostgreSQL tenant integrity (6 steps)
1. Reconfirm schema and isolated PostgreSQL environment — **completed**. PostgreSQL 16.15 at `127.0.0.1:55433`; database `brights_analytics_dev_db`.
2. Specify cross-organization and currency invariants — **completed**.
3. Design update/reassignment protections and concurrency lock ordering — **completed for the tested scenarios**.
4. Implement additive reversible PostgreSQL integrity migration — **completed**. `retail.0003_postgresql_tenant_integrity`.
5. Add direct database-integrity and concurrency regression tests — **completed**. 22 integrity tests and 7 controlled concurrency tests passed.
6. Run forward/reverse migration checks and regression tests on PostgreSQL — **completed**.

Evidence:
- 22 database-integrity tests passed.
- 7 retail concurrency tests passed.
- 82 retail tests passed.
- 628 full backend tests run: 623 passed, 5 skipped, 0 failures.
- Forward migration installed 10 triggers and 8 functions.
- Reverse migration removed all 10 triggers and 8 functions.
- Reapplication restored 10 triggers and 8 functions.
- Development database has all retail migrations applied, all 10 triggers enabled, and no pending migrations.

**Merge record:** PR #8 was squash-merged into `main` on 2026-11-06. The verified merge commit is `4490c129b210a52267d49dfe9eae724d4191f619`. The user verified local `main` and `origin/main` both point to this SHA and the working tree is clean.

Checkpoint CP-DB-02: **CLOSED — MERGED TO MAIN.** See `CP-DB-02.md`.



## DB-03 — Inventory transaction services (6 implementation steps)

1. Inspect existing retail service, permission, audit-event, API, and test conventions; record the existing interfaces — **completed**.
2. Approve the inventory authorization, audit actions, mandatory adjustment reasons, append-only history, and seven detailed defaults — **approved 2026-11-06**.
3. Implement model metadata, reason-code constraints, idempotency key storage, and immutable opening-quantity baseline — **committed to feature branch**.
4. Implement atomic receipt/adjustment services, balance locking, idempotent replay, audit integration, and read-only reconciliation — **committed to feature branch**.
5. Implement PostgreSQL migration/backfill/triggers and service, audit, database-integrity, and concurrency regression tests — **committed to feature branch; validation pending**.
6. Run Django checks, migration forward/reverse/reapply checks, focused PostgreSQL tests, full backend tests, and final branch diff review — **pending**.

Implementation is explicitly authorized on `feature/db-03-inventory-transaction-services`. No production migration/deployment, new inventory write API, or DB-04 sales lifecycle work is authorized by this chunk.

Checkpoint CP-DB-03: **IMPLEMENTATION IN PROGRESS — CODE AND TESTS COMMITTED; AUTOMATED VALIDATION NOT YET RUN.** See `CP-DB-03.md`.

## DB-04 — Sales lifecycle (7 steps)
1. Agree draft/completed/voided/refund/currency rules.
2. Implement draft sale and item validation.
3. Atomically complete sales and deduct stock.
4. Prevent duplicate completion and ensure rollback.
5. Protect completed sale/item history.
6. Add APIs only where justified by the existing architecture.
7. Test end-to-end tenant isolation, parallel completion, and reconciliation.

Checkpoint CP-DB-04: Sales and inventory behavior verified and user-approved.

## DB-05 — Other database applications (6 steps)
1. Audit analytics, organizations, datasets, and auditlog against agreed requirements.
2. Review migrations, indexes, and tenant isolation.
3. Review permissions, provenance, audit, and deletion rules.
4. Implement approved missing constraints/entities.
5. Add regression tests.
6. Record a requirements-to-evidence matrix.

Checkpoint CP-DB-05: Verified completeness and explicit deferrals.

## DB-06 — Database readiness (7 steps)
1. Validate the migration chain from a clean database.
2. Run the full backend suite on disposable PostgreSQL.
3. Run direct-SQL isolation and concurrency tests.
4. Review safe migration reversibility.
5. Document backup/recovery, credentials, and retention gates.
6. Review the diff, pull request, and CI without deployment.
7. Produce a readiness report and request approval.

Checkpoint CP-DB-06: Evidence-backed sign-off; deployment remains separately authorized.

## Handoff format
For each checkpoint record: chunk, branch/commit, environment, step evidence, files changed, test results, decisions, blockers, checkpoint status, reviewer approval, and next action.

Do not advance to the next chunk without a recorded passing checkpoint and explicit user approval.
