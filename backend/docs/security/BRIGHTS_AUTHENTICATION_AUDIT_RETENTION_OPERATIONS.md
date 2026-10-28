# Brights Analytics Authentication Audit Retention Operations

## 1. Deployment status

Status: DESIGN AND TESTING ONLY.

The authentication event retention command is implemented and has
passed isolated PostgreSQL integration testing. It has not been
scheduled, deployed, or executed against an existing application
database as part of this work.

Production activation is prohibited until the approval gates in
Section 7 are satisfied.

## 2. Current retention proposal

| Event | Proposed retention |
| --- | --- |
| Successful login | 12 calendar months |
| Failed login | 90 elapsed days |
| Logout | 12 calendar months |

Records whose creation timestamp equals the cutoff are retained.
Only records strictly older than their cutoff qualify for deletion.

These durations require applicable legal, contractual, and privacy
review before production activation.

## 3. Existing command safety controls

Django command:

`prune_authentication_events`

Preview is the default behavior. A preview reports matching
authentication event counts and does not delete records.

Deletion requires all three arguments:

- `--apply`
- `--expected-database`
- `--expected-user`

Before deletion, the command verifies the live PostgreSQL database
name and current database user against the supplied expectations.

The command obtains a transaction-scoped PostgreSQL advisory lock.
A concurrent cleanup against the same database using the same
lock identifiers is rejected.

All eligible deletion groups execute inside one database transaction.
An unsuccessful transaction rolls back database deletions.

These controls reduce accidental execution and overlapping runs.
Database name and user verification alone do not prove the hosting
environment or cluster identity.

## 4. Execution architecture

Preferred design: one daily scheduled job using the hosting
platform's native scheduler.

Proposed operational time: 02:00 Africa/Nairobi.

Actual execution time, scheduler type, and environment are not yet
approved or configured.

Do not introduce Celery, Redis, or an additional scheduling service
solely for this command without a demonstrated need.

Do not configure a GitHub Actions schedule that connects to a
production database without a separate security and deployment
review.

Run only one authorized cleanup instance per database. The
advisory lock provides additional concurrent-run protection.

## 5. Database and credential requirements

Before deployment:

1. Identify the hosting platform and intended PostgreSQL cluster.
2. Confirm the actual database name, user, host, and environment
   using a secure deployment process.
3. Verify the cluster identity separately from database name and user.
4. Use a purpose-specific least-privilege database account where
   technically feasible.
5. Permit only the tables and operations actually required.
6. Obtain credentials from the deployment secret manager.
7. Do not store passwords, connection URLs, or tokens in this file.
8. Never test destructive commands against production merely to
   establish that they work.

The database role must have the permissions necessary for the
retention command and no unnecessary broader privileges.

## 6. Monitoring and failure handling

The scheduled runner must report:

- job start and finish time
- job outcome: success or failure
- job duration
- counts of eligible and deleted authentication events
- whether database identity verification succeeded
- whether execution was refused because another cleanup held the lock

Use privacy-safe operational metadata only. Never include
passwords, session identifiers, raw login credentials, full
connection strings, or request payloads.

The currently implemented command reports eligible counts and an
apply confirmation. Detailed actual deletion counts, structured
metrics, and centralized alert delivery are not yet implemented.

The scheduling platform should treat a nonzero process exit code as
a failed execution and alert the responsible operator.

A rejected advisory lock must not be interpreted as a successful
cleanup. Avoid overlapping automatic retries.

If a job fails, investigate the reason before retrying. Verify that
the intended database and environment are still correct.

## 7. Mandatory production activation gates

All gates must be independently reviewed:

- Retention periods approved by the responsible data owner.
- Privacy, legal, and contractual requirements reviewed.
- Deployment platform identified and approved.
- Production database and cluster identity independently verified.
- Database account privileges reviewed.
- Production configuration and secret management approved.
- Job output and monitoring requirements implemented.
- Failure notification route tested.
- Nonproduction scheduled-run test completed.
- Recovery and database backup procedures reviewed.
- Named operational owner assigned.
- Final deployment change approved.

Until all gates pass, scheduled deletion must remain disabled.

## 8. Rollback and recovery

If a production run behaves unexpectedly:

1. Disable the scheduler to prevent further runs.
2. Preserve the operational logs without exposing credentials.
3. Confirm which database and role were used.
4. Determine the actual affected records and time range.
5. Escalate according to the incident response procedure.
6. Recover deleted records only through an approved backup or
   recovery process where supported.

A committed deletion transaction cannot be reversed simply by
stopping the scheduler. Database recovery depends on available
backups and operational procedures.

## 9. Existing test evidence

The implementation has passed:

- database-free regression tests
- disposable PostgreSQL 17 integration tests
- strict retention boundary checks
- preview and explicit deletion tests
- incorrect database identity rejection tests
- overlapping advisory lock tests
- full transaction rollback tests
- unrelated Django session and organizational audit preservation tests

These tests do not constitute production deployment approval.

## 10. Outstanding operational decisions

- Select and verify hosting infrastructure.
- Approve retention periods.
- Establish dedicated execution credentials.
- Implement reliable actual-deletion metrics.
- Define monitoring and alert destinations.
- Complete a nonproduction scheduled execution.
- Approve and activate the daily schedule.

No automatic retention cleanup is enabled by this document.
