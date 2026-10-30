# Brights Analytics RLS Laboratory Findings and Identity Decisions

Status: Evidence summary and design decision record.
No permanent RLS implementation or production rollout authorized.

## 1. Verified application baseline

Thirty-seven selected security regression tests passed across SQLite
and disposable PostgreSQL environments. They covered selected
cross-organization access, permission, tenant-integrity and concurrency
scenarios. The total is not a claim of complete endpoint coverage.

The migration-built PostgreSQL baseline contained seven inspected
application tables, zero RLS-enabled tables and zero RLS policies.

## 2. Custom-setting forgery

An isolated PostgreSQL experiment demonstrated that a non-owner
runtime role could assign a different tenant identifier through a
custom session setting and obtain the corresponding records when an
RLS policy trusted that setting.

Decision: Do not use a freely assignable PostgreSQL tenant setting
as independent evidence of authorization.

## 3. Database-role-bound RLS

Disposable PostgreSQL experiments confirmed tenant-specific SELECT,
INSERT, UPDATE and DELETE restrictions for separately authenticated
non-owner roles without BYPASSRLS.

Role impersonation and wrong-password attempts were rejected in
the specific scenarios tested.

The role-bound policy was also tested on the actual migrated
retail_product schema with temporary Django-created organizations
and product records. Existing SKU uniqueness and nonnegative-price
constraints continued to operate.

These findings apply to the tested role and permission configuration.
They do not establish a complete production authorization design.

## 4. Multi-organization authorization mapping

A disposable lab used a protected membership mapping and a narrowly
scoped SECURITY DEFINER function to authorize more than one
organization for one database identity.

The tests demonstrated authorized multi-organization reads, denied
cross-organization writes, protected membership mappings, and
revocation of access for newly executed statements.

Security-definer functions require further review for ownership,
EXECUTE grants, search_path, role semantics, and unintended privilege
exposure before adoption in application migrations.

## 5. Transaction isolation and revocation

Step 770H-R1 compared two active PostgreSQL transactions.

Under READ COMMITTED, a subsequent statement no longer saw the
organization after the administrator committed revocation.

Under REPEATABLE READ, a transaction with an established older
snapshot continued to see the previously authorized organization.

A new REPEATABLE READ transaction denied access. A subsequent
revoked-organization INSERT was rejected by RLS.

Decision: Do not promise instantaneous authorization revocation for
already-running transactions. Review transaction duration,
isolation level, statement timing, and sensitive operations.

## 6. Unresolved Django-to-PostgreSQL identity boundary

Django authenticates application users independently of PostgreSQL
database logins.

If multiple Django users share one database login, PostgreSQL
session_user does not identify the individual Django user.

A role-to-organization mapping therefore cannot enforce per-user
organization membership merely because a request is authenticated.

Do not deploy this design using one shared database identity with
all tenants authorized to that identity.

## 7. Required design alternatives assessment

Evaluate explicit per-principal or per-tenant database identities,
credential issuance and rotation, connection pool behavior,
and secure database-verifiable authorization assertions.

Any proposed shared-login model must demonstrate how its
authorization evidence cannot be forged by arbitrary SQL running
under the ordinary application database role, or clearly limit
the security guarantee and threat model.

Do not assume that SET LOCAL or SET ROLE by itself establishes
trustworthy application-user identity.

## 8. Additional application requirements

Preserve existing Django role permissions, restricted dataset
classification and grant checks, membership management, and
audit-event protections.

Review independent read paths, transaction.atomic services,
background jobs, management commands, connection reuse and
authentication bootstrap before enabling policies.

Database tenant membership must not automatically authorize all
dataset, audit or administrative operations.

## 9. Required next implementation gate

Before writing permanent RLS migrations:

1. Select and review the database identity and authorization model.
2. Demonstrate how a Django principal maps securely to database access.
3. Verify revocation under relevant transaction and pool conditions.
4. Define ownership, GRANT and BYPASSRLS boundaries.
5. Enumerate policy semantics for all protected tables and operations.
6. Test allowed and denied application behavior under non-owner roles.
7. Preserve all existing tenant-integrity and concurrency protections.
8. Verify migration ordering, rollback and failure recovery.

## 10. Scope of approval

This document records completed laboratory findings only.
It authorizes no application changes, persistent database operations,
RLS rollout, remote push or infrastructure deployment.
