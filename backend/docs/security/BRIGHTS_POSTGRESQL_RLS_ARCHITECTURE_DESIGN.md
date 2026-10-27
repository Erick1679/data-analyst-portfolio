# Brights Analytics PostgreSQL RLS Architecture Design

Status: Design only. No database policy, runtime integration, or production
deployment is authorized by this document.

## 1. Purpose

Design a second layer of tenant isolation for Brights Analytics using
PostgreSQL Row-Level Security (RLS). Existing Django permissions remain
necessary for operation-specific authorization, dataset classifications,
membership administration, and audit-history access.

RLS is defense in depth. Passing application permission tests does not
establish RLS, and RLS alone does not establish complete application security.

## 2. Verified Baseline

The security audit established 37 passing selected tests across SQLite
and isolated PostgreSQL. They include cross-organization access restrictions,
read/write permission checks, grant-integrity triggers, and seven PostgreSQL
concurrency tests.

A newly migrated disposable PostgreSQL 17 database contained seven inspected
application tables, zero RLS-enabled tables, zero FORCE RLS settings, and
zero public RLS policies.

These results do not establish the RLS state of any existing deployment.

## 3. Tenant-Owned Tables

Direct organization references exist in:

- organizations_organizationmembership
- datasets_corporatedataset
- auditlog_auditevent
- retail_branch
- retail_product

organizations_organization represents the organization itself.

datasets_datasetaccessgrant is indirectly tenant-scoped through its dataset
and organization membership relationships. Grant integrity triggers already
protect certain cross-organization relationships.

Policies must use actual verified model relationships and database constraints,
not guessed ownership paths.

## 4. Trust and Threat Model

Threats include cross-tenant application bugs, incorrectly scoped queries,
unguarded service calls, forged tenant identifiers, connection context leakage,
overly privileged database roles, and arbitrary SQL execution.

A custom PostgreSQL setting such as app.organization_id is not inherently
trusted. A caller with arbitrary SQL access may be able to set or replace it.

A simple SET LOCAL followed by a policy comparing organization_id to
current_setting does not independently prevent tenant impersonation by a
compromised SQL-capable runtime role.

The authorization-context trust boundary must be explicitly established and
tested before claiming defense against SQL-level context forgery.

## 5. Database Role Separation

Use distinct database roles for schema ownership/migrations and application
runtime access.

The runtime role must not own protected tables and must not have BYPASSRLS
or superuser privileges. Test role membership and inherited privileges.

FORCE ROW LEVEL SECURITY may be required for relevant ownership cases,
but it does not replace correct database-role separation.

Do not run ordinary application requests through the schema-owner role.

## 6. Authorized Organization Context

An authenticated user may have membership in more than one organization.

The application must authenticate the principal and authorize the specific
organization involved in the requested operation.

Client-provided organization IDs are lookup inputs only, not trusted proof.

The database context design must distinguish normal tenant-scoped requests,
cross-organization administrative operations, authentication bootstrap,
background tasks, and migration/maintenance operations.

## 7. Database Context Integrity

Select and document a context approach with a clear attacker model.

Potential approaches include separately controlled database identities or a
database-verifiable authorization assertion. Any signing or verification
mechanism requires secure issuance, narrow scope, expiration, rotation, and
replay analysis.

Transaction-local settings alone are insufficient against arbitrary SQL
capable of assigning another tenant identifier.

The chosen mechanism must demonstrate resistance to the threats claimed.

## 8. Transaction Boundaries

The inspected source includes transaction.atomic in organization, dataset,
and audit services, with select_for_update used on selected sensitive writes.

No ATOMIC_REQUESTS setting or existing PostgreSQL tenant-setting integration
was found in the inspected application code.

Any transaction-local authorization context must be established in the same
database transaction before protected queries and must expire at its end.

Standalone service calls and background operations need an explicit context
contract. Do not assume that all views are transaction-scoped.

## 9. Connection Reuse and Pooling

Session-level tenant context can persist across reused database connections
and accidentally affect a different request.

Avoid implicit global context, enforce predictable transaction cleanup,
and test connection reuse, exceptions, rollback, and pooled connections.

A missing, invalid, or stale authorization context must fail closed for
protected tenant operations.

## 10. Organization and Membership Bootstrap

Membership lookup is necessary to establish authorized organization context,
yet membership tables are themselves candidates for RLS.

A circular dependency must not be solved by unrestricted public membership
access.

Design a narrow, independently authorized bootstrap mechanism and test
its privilege boundaries before enforcing membership-table RLS.

Organization discovery must not expose unrelated organizations or private
membership data.

## 11. Direct Tenant Table Policies

For each directly tenant-scoped table, define and independently test:

- SELECT USING: visibility of existing rows.
- INSERT WITH CHECK: permission to create rows for the target organization.
- UPDATE USING: which existing rows may be modified.
- UPDATE WITH CHECK: which new row state may be written.
- DELETE USING: which existing rows may be deleted.

Do not infer authorization for mutation from visibility alone.

Where deletion or direct mutation is prohibited by product rules, explicitly
deny it rather than supplying a broad tenant-wide policy.

## 12. Dataset and Grant Semantics

Dataset classification remains subject to existing Django authorization
rules, including restricted dataset grants.

Tenant membership must not automatically reveal restricted datasets.

Dataset grant policies must validate both the dataset organization and the
membership organization, with applicable issuance/revocation permissions.

Preserve existing integrity constraints and locking protections.

## 13. Audit Log Requirements

Audit records require organization isolation, but audit recording must remain
available for legitimate permitted and denied operations.

Audit viewing roles differ from ordinary tenant membership.

Define narrow append, retrieval, and privileged maintenance paths. Prevent
ordinary users from modifying or deleting evidence if the application policy
requires append-only audit history.

Avoid recording secrets or excessive personal information in RLS diagnostics.

## 14. Read and Write Compatibility

Review every ORM and raw-SQL pathway that accesses protected tables.

Test permitted requests as well as denied requests. Legitimate organization
membership changes, dataset creation, grant revocation, retail listings,
and audit-event recording must remain functional.

Include anonymous requests, inactive users, inactive organizations,
revoked memberships, and stale authorization contexts.

## 15. Non-Owner Enforcement Tests

Use a fresh isolated PostgreSQL cluster and apply migrations there first.

Create non-owner, non-BYPASSRLS runtime credentials.

Verify SELECT, INSERT, UPDATE, and DELETE behavior separately with
multiple organizations and principals.

Test missing context, incorrect organization, cross-tenant identifiers,
reused connections, rollback, and privilege escalation attempts.

Do not count owner-role or superuser queries as proof of RLS enforcement.

## 16. SQL Context Forgery Tests

If the design uses custom PostgreSQL settings, test attempts to replace
or spoof organization context through the ordinary runtime SQL role.

An implementation that can impersonate another tenant through
SET or set_config must not be described as SQL-forgery-resistant RLS.

Define which security guarantees remain even if the runtime role is
compromised or an application SQL injection is discovered.

## 17. Migrations and Deployment

Policy creation, database-role configuration, Django integration, and
runtime cutover require a coordinated plan.

Test dependencies and migration ordering against a disposable PostgreSQL
cluster. Introduce policies only after legitimate request paths and
bootstrap operations are supported.

Do not apply RLS to existing application databases during design review.

## 18. Rollback and Recovery

Create a reviewed rollback plan for policies, grants, and runtime integration.

Avoid uncontrolled disabling of RLS as an incident response.

Record the conditions, authorized owners, and tests required to reverse
a rollout while protecting existing data and audit evidence.

## 19. Acceptance Gates

Before production consideration, require:

1. Reviewed ownership, role, and threat model.
2. Reviewed authorization-context issuer and forgery resistance.
3. Verified transaction and connection-lifecycle integration.
4. Complete policy mapping for every affected table and operation.
5. Passing cross-user HTTP, service, and raw-SQL tests.
6. Passing positive-access and denial tests under non-owner roles.
7. Passing existing SQLite and PostgreSQL regressions.
8. Verified migration, rollback, and recovery procedures.
9. Explicit approval for any rollout or enforcement activation.

## 20. Current Authorization Boundary

This document authorizes documentation and further isolated experiments only.

It does not authorize modifying production or persistent databases,
activating RLS, installing middleware, changing database credentials,
deploying infrastructure, or pushing changes to GitHub.

The next engineering activity is to review this design against actual
application call paths and then build a narrowly scoped disposable
PostgreSQL proof of concept.
