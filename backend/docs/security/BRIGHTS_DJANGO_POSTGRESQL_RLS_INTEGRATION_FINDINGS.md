# Brights Analytics Django and PostgreSQL RLS Integration Findings

Status: Verified disposable-laboratory proof of concept.
No permanent application integration or production rollout authorized.

## 1. Test environment

Step 770M-R2 completed successfully in a fresh PostgreSQL 17
cluster using SCRAM-SHA-256 authentication and a private Unix
socket with TCP listening disabled.

The actual Django migrations were applied only to the disposable
cluster. No pre-existing application database was accessed.

The experiment created two auth.User records, three Organization
records, three OrganizationMembership records, and three Product
records using the actual Django models.

## 2. Identity model

The Django user primary key is an integer AutoField.
The organization primary key is a UUID.

Two independently authenticated PostgreSQL roles were mapped to
the actual Django user IDs through a protected private table.

Both database runtime roles lacked superuser and BYPASSRLS
privileges and were separate from the schema-owner identity.

A SECURITY DEFINER function checked the authenticated database
role, mapped Django user, active user status, active organization
membership, and active organization status.

The function and role mappings existed only in the laboratory.

## 3. Tested PostgreSQL enforcement

A temporary RLS policy was enabled on the actual retail_product
table in the disposable migrated database.

All eight Step 770M-R2 test groups passed:

1. One Django principal accessed two authorized organizations,
   while another principal accessed only a third organization.
2. Forging a custom tenant setting did not expand access.
3. An authorized Django ORM product INSERT succeeded.
4. An unauthorized ORM INSERT was rejected by PostgreSQL RLS
   with SQLSTATE 42501 and did not persist.
5. Cross-tenant ORM UPDATE and DELETE affected zero rows.
6. Revoking a Django organization membership removed access
   on subsequent queries while retaining other authorized access.
7. Deactivating the mapped Django user removed protected product
   visibility without removing an unrelated active user's access.
8. The ordinary runtime database role was denied direct access
   to the private principal mapping table.

The experiment finished with a zero process exit code.

## 4. Transaction and revocation limitations

Previous Step 770H-R1 tests established that a new statement
under READ COMMITTED recognized committed membership revocation.

A transaction operating under REPEATABLE READ could continue
using an earlier membership snapshot.

The integration experiment does not establish instantaneous
revocation in long-running or already-established transactions.

## 5. Unresolved production architecture

The laboratory created database identities manually and
configured separate Django database aliases inside the test.

It did not implement or validate:

- Automated PostgreSQL principal provisioning and deprovisioning.
- Credential issuance, rotation, storage, and recovery.
- Mapping authenticated HTTP requests to database connections.
- Isolation when connection pools or workers reuse connections.
- Authentication bootstrap, including unauthenticated requests.
- User removal, password changes, and emergency lockout.
- Background jobs, scheduled tasks, or management commands.
- Database permissions for all application models.
- Restricted dataset grants and classifications at the RLS layer.
- Migration ownership, policy installation, and safe rollback.
- Resource scaling for large numbers of Django user principals.

## 6. Critical trust boundary

An authenticated PostgreSQL role identifies a database principal.
It does not automatically identify the current Django HTTP user.

Do not share database credentials across unrelated Django users
and assume that the private mapping still provides per-user
database isolation.

Do not replace database-authenticated identity with a freely
assignable session variable without an independently validated
trust mechanism.

## 7. Recommended next work

Compare realistic production identity approaches against these
requirements:

1. Database-enforced protection against arbitrary SQL executed
   with an ordinary runtime role.
2. Trustworthy binding between Django principal and SQL access.
3. Efficient support for multi-organization membership.
4. Safe use of pooled and reused database connections.
5. Practical credential lifecycle and database role scale.
6. Secure bootstrap and background-job authorization.
7. Preservation of fine-grained Django permission checks.
8. Clear revocation guarantees and transaction handling.

Select an architecture only after evaluating the tradeoffs.

Then implement a limited, reversible security-branch prototype,
test it in isolated PostgreSQL, and review its threat model before
considering permanent application migrations.

## 8. Project preservation

Step 770M-R2 stopped and removed its disposable database cluster.
The security worktree remained clean and the protected main
branch retained all 26 untracked website assets.

No source change, Git commit, push, infrastructure deployment,
or permanent PostgreSQL RLS activation occurred during the test.
