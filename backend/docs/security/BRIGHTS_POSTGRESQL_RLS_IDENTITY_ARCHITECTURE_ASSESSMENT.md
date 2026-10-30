# Brights Analytics PostgreSQL RLS Identity Architecture Assessment

Status: Architecture comparison and security decision gates.
Decision: Production identity architecture not yet selected.
Implementation: Not authorized by this document.

## 1. Established baseline

Brights Analytics currently uses Django authentication and
organization-specific authorization functions.

The inspected Django models establish that:

- The Django user model is auth.User with an integer primary key.
- Organization records have UUID primary keys.
- OrganizationMembership associates users and organizations.
- Membership and user activation status are modeled explicitly.
- Product records are linked to organizations by UUID.

Step 770M-R2 demonstrated eight passing Django ORM security test
groups using two authenticated non-owner PostgreSQL runtime roles
mapped to actual Django users.

The demonstration used a disposable PostgreSQL 17 cluster and a
temporary policy on the actual migrated retail_product table.

The test did not exercise real HTTP identity routing, production
credential storage, connection pools or background workers.

## 2. Security objectives and trust boundary

The primary RLS objective is to limit access to tenant data even
when an ordinary runtime connection executes SQL that does not
include the required organization filter.

The implementation must define whether arbitrary SQL executed
using a compromised application's current database credentials
is inside the threat model.

The database must not rely solely on a custom session setting
that the same SQL principal can freely change to impersonate
another user or tenant.

Separate database users provide a possible identity boundary
only when their credentials and connection assignments are
correctly protected. They do not protect against compromise
of a schema-owner or administrator credential.

Tenant membership is not equivalent to permission to perform
every action within that tenant.

## 3. Option A: PostgreSQL login identity per Django user

Model:
- Each application user has a distinct non-owner database login.
- A protected mapping associates that login with a Django user ID.
- Database-side policies consult active users and memberships.
- Application operations use the intended user's SQL identity.

Potential advantages:
- Database-level principal separation.
- Multi-organization access within one authenticated identity.
- Individual identity revocation and restricted SQL privileges.
- Strong alignment with the successful Step 770M-R2 experiment.

Unresolved costs and risks:
- PostgreSQL role creation, rotation and deprovisioning.
- Secure database credential issuance and storage.
- Concurrent connection limits and connection-pool fragmentation.
- Reliable request-to-connection binding and cleanup.
- Authentication bootstrap before protected membership queries.
- Security of background workers and administrator operations.
- Resource usage at large user counts.

A web application retaining all users' database passwords may
still expose broad access if its credential store is compromised.

Status: Demonstrated in a disposable ORM test, not approved for
production.

## 4. Option B: PostgreSQL login identity per organization

Model:
- Runtime database logins are bound to organizations.
- Applications select the required organization connection.
- Policies restrict tenant-owned rows to the bound organization.

Potential advantages:
- Database identity count may be lower than the user count.
- Simple isolation for operations scoped to one organization.
- Straightforward tenant-specific runtime credential rotation.

Unresolved costs and risks:
- Users belonging to several organizations need safe routing.
- Shared organization credentials cannot distinguish users.
- Direct database access may bypass per-user application grants.
- Connection handling and cross-organization operations become
  more complex.
- Organization-level isolation alone does not authorize access
  to restricted datasets, audit records or administration.

Status: Not validated against actual Django request workflows.

## 5. Option C: Shared connection with verified authorization

Model:
- A shared, restricted runtime login services application work.
- Another trusted mechanism establishes user/tenant authority.
- Database policy uses authorization evidence that ordinary
  runtime SQL cannot forge or arbitrarily replace.

Potential advantages:
- Better compatibility with conventional Django deployments.
- Fewer database login roles.
- More straightforward general-purpose connection pooling.

Unresolved costs and risks:
- The identity assertion must have a demonstrable trust boundary.
- A freely assignable custom PostgreSQL setting is insufficient.
- SQL injection must not permit identity impersonation.
- Transaction-local state must not leak into another request.
- Policy validation and identity assertion mechanisms must not
  grant broad privileges to the shared runtime role.
- Revocation, replay, stale assertions and bootstrap require
  an explicit design and tests.

Status: No secure assertion architecture selected or validated.

## 6. Connection lifecycle requirements

Any option must address:

- Authenticated and unauthenticated HTTP request handling.
- Explicit transaction boundaries.
- Reused connections after request completion or errors.
- Worker concurrency and asynchronous execution.
- Database connection pooling and transaction pooling.
- Connection identity mismatch and fail-closed behavior.
- Background tasks, management commands and maintenance.
- Membership revocation during active transactions.

Prior Step 770H-R1 testing demonstrated that an established
REPEATABLE READ snapshot may retain pre-revocation visibility.

No option should promise instantaneous revocation of every
already-running transaction without additional controls.

## 7. Database privilege and schema requirements

Runtime database roles must not own protected data tables,
hold superuser privileges, or possess BYPASSRLS.

Schema ownership and maintenance identities require separate
review and tightly constrained operational access.

A SECURITY DEFINER function must receive a dedicated security
review of owner privileges, search_path, object references,
grants and callable behavior.

Coverage must extend beyond retail_product as appropriate,
including organizations, memberships, datasets, grants,
branches, audit records and indirect relationships.

The policy model must preserve row-level ownership checks and
the application's finer-grained permission requirements.

## 8. Production selection criteria

Evaluate all alternatives against the same criteria:

1. Resistance to SQL-level cross-tenant impersonation.
2. Secure correspondence with authenticated Django principals.
3. Multiple active organization memberships.
4. Membership revocation and user deactivation.
5. Credential lifecycle and recovery.
6. Database role count and scalability.
7. Connection-pool compatibility and identity cleanup.
8. Django request, service and transaction integration.
9. Dataset grants and audit access controls.
10. Background and administrative operations.
11. Testability, observability, migration and rollback.
12. Operational complexity and maintainability.

## 9. Minimum next proof of concept

Before permanent RLS migration work:

- Choose a candidate identity architecture and explicit attacker
  capabilities.
- Demonstrate request-to-database identity binding in a disposable
  Django and PostgreSQL environment.
- Test two different Django users using sequential and concurrent
  requests.
- Test failure cleanup and attempted connection identity reuse.
- Test membership revocation and user deactivation.
- Prove that runtime SQL cannot impersonate another principal.
- Test ordinary authorized and unauthorized business operations.
- Confirm no protected-main changes or permanent database effects.

## 10. Decision record

Current recommendation:
Use Option A as the security reference design because its
underlying identity mechanism passed the isolated Django ORM
experiment.

Do not adopt Option A operationally until credential provisioning,
request routing, pooling, scaling and revocation are demonstrated.

Evaluate Option C separately if a sound, database-verifiable
identity assertion and threat model can be designed.

Do not select Option B merely because it requires fewer roles:
organization identity alone cannot represent per-user authority.

Production decision: OPEN.
Permanent application changes: NOT AUTHORIZED.
Production RLS activation: NOT AUTHORIZED.
