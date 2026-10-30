# Brights Security Shield — Signal Collection Contract

## 1. Status and scope

Status: Proposed engineering contract.

This document is not a production configuration.

No request collector, middleware, database writer,
shared counter backend, rate limiter, or blocker is
activated by this design.

The contract is based on the Step 759 static audit
of the isolated abuse-observation evaluator.

Actual Django event producers and response paths
must be reviewed before implementation.

## 2. Observation unit

The primary observation unit is a distinct request
within an explicit identity scope and time window.

Supported future identity scopes may include:
- Authenticated account.
- Verified organization.
- Approved API credential identifier.
- Validated immediate network peer.

An identity scope must be explicitly recorded.
Counters from different scopes must not be combined
into one observation without approved correlation.

Shared network addresses do not uniquely identify users.

## 3. Request count

request_count measures distinct eligible requests
assigned to the same scope and window.

A request contributes at most once to request_count
for that scope and window.

The collection system must document which routes,
methods, and response outcomes are eligible.

Retries with distinct request identities are distinct
requests unless a reviewed deduplication policy applies.

## 4. Authentication failure counter

authentication_failures counts distinct requests
with a verified authentication-failure outcome.

Examples may include rejected credentials or denied
authentication attempts when instrumented correctly.

An HTTP status code alone does not establish
the definitive cause of the failure.

The authorized authentication event producer must
define the canonical authentication failure signal.

One request contributes at most once to this signal
within the same observation scope and window.

## 5. Authorization denial counter

authorization_denials counts distinct requests
with a verified authorization-denial outcome.

The denial must be tied to an authoritative
permission or tenant-access decision.

Do not classify all HTTP 403 responses as
authorization failures without reviewing their causes.

One request contributes at most once to this signal
within the same observation scope and window.

## 6. Overlapping request signals

The counters are not assumed mutually exclusive.

One request may contribute to both
authentication_failures and authorization_denials
if both outcomes are independently verified.

Consequently:

- authentication_failures <= request_count
- authorization_denials <= request_count

Their sum may exceed request_count.

The current evaluator has an additive validation
assumption that conflicts with this proposed contract.

That validation must be revised and retested before
the evaluator accepts overlapping collected signals.

No source-code change is authorized by this document.

## 7. Fixed observation windows

Use explicit fixed-duration UTC windows.

Represent boundaries as an inclusive start time
and exclusive end time: [start, end).

When using Unix timestamps in seconds, a window
of duration W starts at floor(timestamp / W) * W.

The end boundary equals start + W.

A request at the end boundary belongs to the
following window, not the preceding window.

The approved duration must accompany all counters.

Window duration must be positive and consistent
for all counters in an observation.

Do not compare raw counts across different window
durations as if they were equivalent request rates.

Clock synchronization and late events require
separate implementation and validation rules.

## 8. Deduplication semantics

Event collection must use a bounded, stable
request identity or another approved deduplication key.

Deduplication is per identity scope, signal type,
and observation window.

Repeated delivery of the same event must not inflate
the corresponding count.

Do not log full credentials, access tokens, or
private request bodies as deduplication keys.

Handle collisions, retries, expiration, and
multi-instance concurrency explicitly.

## 9. Missing and partial telemetry

Missing evidence is not equivalent to a zero count.

The future collector must distinguish:
- A complete window with zero matching events.
- An incomplete observation window.
- An unavailable event source.
- Invalid or inconsistent counters.
- An observation not yet finalized.

Incomplete or invalid observations must not be
silently classified NORMAL.

UNKNOWN remains the conservative evaluation result
where required evidence cannot be validated.

UNKNOWN does not bypass existing authentication,
authorization, or tenant isolation.

## 10. Concurrency and shared state

Any future production aggregation requires
an approved shared, atomic state mechanism.

Local process memory is insufficient for
consistent multi-instance collection.

Implementation must address:
- Atomic counter updates.
- Duplicate delivery.
- Expiration and retention.
- Late and out-of-order events.
- Clock boundaries.
- Multi-instance consistency.
- Partial writes and recovery.
- Monitoring failures.
- Data protection.

No particular storage product is approved here.

## 11. False-positive safeguards

Do not treat request volume alone as proof of abuse.

Review normal traffic from approved integrations,
shared gateways, scheduled jobs, and large tenants.

Distinguish account, organization, credential,
and network scopes in observation records.

Do not penalize unrelated accounts solely because
they share a network peer.

No counter result automatically authorizes
throttling, challenges, or blocking.

## 12. Evaluator compatibility requirements

The current isolated evaluator accepts:
- endpoint_category
- window_seconds
- request_count
- authentication_failures
- authorization_denials

Its threshold values are explicitly provided.
There are no approved production thresholds.

Before integrating collected events:

1. Replace the additive counter constraint with
   independent per-counter bounds.
2. Retain rejection of negative and non-integer values.
3. Retain immutable inputs and outputs.
4. Confirm matching observation-window semantics.
5. Preserve deterministic evidence reason codes.
6. Require validated telemetry completeness.
7. Extend tests for overlapping signals.
8. Preserve no-database, no-network unit tests.

Any collector implementation needs additional
integration tests before live use.

## 13. Source verification gates

Inspect the actual authentication view and helpers.

Inspect permission and membership enforcement paths.

Verify which failures produce status 401 or 403
and which conditions produce those responses.

Identify reliable request lifecycle boundaries.

Confirm if exceptions or middleware can produce
multiple independent failure events for one request.

Do not assume the static audit establishes
runtime behavior.

## 14. Privacy and security

Collect only necessary security event metadata.

Limit retention and access to collected observations.

Avoid credentials, raw authentication tokens,
unnecessary request bodies, and secrets.

Do not trust arbitrary forwarding headers.

Use the committed network-peer helper only
according to its immediate-peer semantics.

## 15. Required regression tests

- Independent upper bounds for overlapping counters.
- One request contributing to two verified signals.
- Each individual counter exceeding request_count.
- Complete zero-activity observation windows.
- Missing and incomplete telemetry.
- Fixed-window UTC boundary assignment.
- Boundary event assigned to the next window.
- Duplicate event delivery.
- Concurrent updates in future shared storage.
- Invalid and inconsistent window durations.
- No source mutation.
- No database access in pure evaluator tests.
- Preservation of existing authorization.
- No rate limiting or blocking activation.

## 16. Release and enforcement separation

The collector records validated evidence.

The evaluator describes observations.

An approved future policy may recommend responses.

A separately approved enforcement layer applies
any restrictions.

None of these phases may bypass authorization,
tenant isolation, or authenticated identity checks.

Production rollout requires infrastructure,
threshold, failure-mode, false-positive, and
rollback approvals.

## 17. Next engineering milestone

Add regression tests for overlapping counters
and fixed-window validation in isolation.

Revise evaluator validation in a separately
verified commit.

Do not connect collection to Django middleware
until event producers and storage are reviewed.
