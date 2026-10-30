# Brights Security Shield — Adaptive Rate-Limiting Policy

## 1. Status and boundaries

Status: Design proposal; no runtime enforcement enabled.

This policy covers future API abuse detection,
adaptive throttling, and temporary restrictions.

It complements edge WAF and DDoS mitigation.
It does not replace authentication, authorization,
tenant isolation, or upstream network protection.

No production limits, scoring weights, thresholds,
ban durations, or external vendors are approved yet.

## 2. Security objectives

- Detect abnormal requests and repeated abuse.
- Protect expensive and sensitive API endpoints.
- Avoid interrupting legitimate customers.
- Recognize distributed and account-based attacks.
- Escalate responses proportionately.
- Expire temporary restrictions automatically.
- Make decisions observable and reversible.
- Support multiple application instances safely.

## 3. Request identity and trusted boundaries

Potential signals:

- Authenticated account identifier.
- Organization identifier, when verified.
- API credential identifier, when implemented.
- Validated immediate network peer IP.
- Verified client IP from trusted edge infrastructure,
  only after provider-specific trust rules are approved.
- Endpoint category and operation type.

The existing get_network_peer_ip function identifies
the immediate network peer using REMOTE_ADDR.

It does not assert original client identity behind
a reverse proxy.

Never trust arbitrary X-Forwarded-For, X-Real-IP,
CF-Connecting-IP, or other forwarding headers.

Trusted-proxy configuration requires verified topology,
network restrictions, and explicit security testing.

Do not log authentication secrets or full API keys.

## 4. Endpoint risk categories

Category A — Public low-cost read operations.

Goal:
Detect extraordinary traffic without penalizing
legitimate browsing or ordinary integrations.

Category B — Authenticated routine operations.

Goal:
Observe account- and organization-level behavior
without confusing shared corporate IPs with users.

Category C — Authentication and account recovery.

Goal:
Detect password guessing and credential stuffing.
Avoid account lockouts that enable denial of service.

Category D — Expensive analytics and data exports.

Goal:
Protect database, compute, and queue capacity.
Use workload costs in addition to request counts.

Category E — Privileged administration and grants.

Goal:
Detect repeated denied requests and unusual changes.
Never treat rate limits as a substitute for permissions.

Endpoint assignments require review against the
actual Django URL and authorization configuration.

## 5. Detection signals

Candidates include:

- Requests per time window.
- Change relative to normal traffic.
- Authentication failures.
- Permission denials and enumeration patterns.
- Distinct endpoints accessed in suspicious sequences.
- Repeated expensive analytics operations.
- Related activity across accounts or networks.
- Provider-supported bot and attack indicators.
- Backend latency, queue growth, and saturation.

A single high request rate does not prove abuse.

Behavioral signals require validation and regular review.

## 6. Proposed enforcement stages

Stage 0 — Observe only.

Record low-risk aggregate signals.
Do not interrupt requests.

Stage 1 — Enhanced observation.

Increase anomaly monitoring.
Flag suspicious patterns for review.

Stage 2 — Temporary throttling.

Apply proportionate limits to supported identities
and sensitive endpoints when sufficient evidence exists.

Return appropriate HTTP 429 responses and Retry-After
information where applicable.

Stage 3 — Temporary restriction or challenge.

Use appropriate access restrictions.
Browser challenges must not be required for
machine-to-machine API clients.

Stage 4 — Time-limited blocking.

Apply only with strongly supported abusive activity.
Require expiry, auditability, review, and rollback.

Stage 5 — Coordinated incident escalation.

Use edge-provider mitigation and incident procedures
when attacks exceed application-level control.

These stages are proposals, not active application rules.

## 7. False-positive safeguards

- Do not identify an individual solely by IP address.
- Account for NAT, VPNs, campuses, and mobile networks.
- Distinguish human users from approved integrations.
- Review limits against real endpoint processing costs.
- Observe policy outcomes before enforcement.
- Define appeal and support procedures.
- Expire restrictions and permit authorized overrides.
- Record reasons for decisions without excess personal data.
- Test against real, representative legitimate workflows.
- Avoid cascading organization-wide penalties without
  evidence that supports such broad enforcement.

## 8. Shared state and concurrency

A production implementation must use suitable shared,
atomic state across all application instances.

Local process memory is insufficient for distributed
enforcement and may produce inconsistent decisions.

The chosen backend must support:

- Atomic limit updates.
- Bounded storage and expiration.
- Defined behavior during backend failures.
- Observability of storage failures.
- Controlled retention and privacy requirements.
- Tests for concurrent and multi-instance requests.

No Redis or other shared-state provider is selected yet.

## 9. Failure behavior

Security decisions must distinguish between:

- A failed identity lookup.
- Unavailable rate-limit storage.
- Malformed request metadata.
- Backend saturation.
- Confirmed malicious activity.

Never automatically treat malformed or missing peer-IP
data as permission to bypass authentication.

Do not automatically block every request during a
shared-state outage without an approved continuity plan.

Decide failure behavior by endpoint risk, service
availability objectives, and independent edge controls.

## 10. Observability and data protection

Future security events should record only necessary:

- Time window and decision outcome.
- Endpoint risk category.
- Pseudonymous or minimally necessary identifiers.
- Evidence category or matched rule.
- Restriction expiry and reason.
- Monitoring and rollback reference.

Avoid raw passwords, tokens, request bodies,
or unnecessary sensitive personal information.

Define access control, retention, and incident use.

## 11. Integration boundaries

Edge provider:
Network and application-layer flood mitigation,
managed WAF rules, and approved edge challenges.

Django:
Authentication, authorization, tenant isolation,
endpoint-aware security signals, and appropriate
application-level throttling.

Shared state:
Atomic counters or equivalent detection data,
with expiration and failure handling.

Security operations:
Policy approval, false-positive review, alert
escalation, emergency changes, and rollback.

Do not activate middleware or security blocking
until integration tests and deployment review pass.

## 12. Required tests

- Authenticated users sharing one IP.
- Spoofed forwarding headers.
- IPv4 and IPv6 normalization.
- Invalid or missing peer IP.
- Burst traffic followed by normal activity.
- Requests across multiple application instances.
- Simultaneous requests to the same identity.
- Distributed low-rate enumeration.
- Authentication abuse versus legitimate retries.
- Expiry and rollback of temporary restrictions.
- Shared-state failure and recovery.
- Approved machine-to-machine integrations.
- Organization and tenant permission isolation.
- Appropriate 429 and Retry-After responses.

Use isolated or authorized test environments only.

## 13. Release requirements

Before any enforcement becomes active:

1. Verify deployed proxy and edge trust boundaries.
2. Review endpoint categories and expected workloads.
3. Select and validate shared-state infrastructure.
4. Approve measurable thresholds and expiry durations.
5. Implement observe-only mode with controlled logging.
6. Validate security and concurrency regression tests.
7. Test representative legitimate customers and APIs.
8. Verify monitoring, support procedures, and rollback.
9. Obtain deployment approval.
10. Record production rollout and post-release review.

## 14. Next engineering milestone

Design a pure, side-effect-free classification function
that assigns request risk categories using verified
endpoint metadata.

Do not activate rate limiting, blocking, middleware,
or external infrastructure in that milestone.
