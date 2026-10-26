# Brights Security Shield — Adaptive Abuse-Detection Design

## 1. Status and scope

Status: Proposed architecture only.

No abuse detection, request throttling, temporary
restriction, middleware, or blocking is active.

This design builds on the committed client-IP module,
endpoint risk classifier, and adaptive rate-limiting
policy.

The first engineering milestone is an isolated,
side-effect-free signal evaluation function.

Production integration requires separate approval.

## 2. Security objectives

- Identify suspicious request patterns.
- Recognize repeated authentication failures.
- Highlight unusual access-denial patterns.
- Detect excessive resource consumption.
- Distinguish sudden bursts from sustained abuse.
- Reduce false positives for legitimate users.
- Support later distributed attack correlation.
- Preserve tenant authorization boundaries.
- Produce explainable, reviewable observations.

A high request count alone does not prove abuse.

## 3. Evidence inputs

Future observations may use:

- Endpoint risk classification.
- Explicit observation-window duration.
- Request counts measured within that window.
- Authentication failure counts.
- Authorization denial counts.
- Known resource-cost indicators.
- Verified authenticated identity context.
- Trusted and validated network metadata.

All inputs must be supplied by approved collectors.

The pure evaluation function must never infer
original-client identity from arbitrary headers.

Never submit passwords, raw API keys, access tokens,
or request bodies to the evaluation function.

## 4. Identity separation

Relevant identity scopes may include:

- Individual authenticated account.
- Verified organization or tenant.
- Credential identifier, if safely supported.
- Immediate network peer.
- Original internet client only where a verified
  trusted-proxy configuration exists.

Identity scopes must remain distinguishable.

Shared IP addresses must not automatically cause
multiple unrelated accounts to be blocked.

The existing REMOTE_ADDR helper identifies the
immediate network peer only.

## 5. Endpoint sensitivity

The existing endpoint classifier returns:

- A_CANDIDATE
- B
- C
- D_CANDIDATE
- E
- UNCLASSIFIED

Candidate classifications are not approved
production policies.

Unknown routes remain UNCLASSIFIED.

An endpoint category must not override authentication,
authorization, or tenant isolation.

## 6. Initial observation levels

NORMAL:
No configured abnormality has been established.

ELEVATED:
An approved observation rule identifies activity
that warrants closer monitoring.

SUSPICIOUS:
Multiple validated signals or stronger evidence
warrant security review.

UNKNOWN:
Evidence is missing, invalid, unsupported,
or insufficient for a sound classification.

These are descriptive observation levels.

They do not authorize access or block requests.

Quantitative production thresholds are not approved.

## 7. Pure evaluation contract

The initial evaluator should accept a validated,
immutable observation structure containing:

- Endpoint category.
- Observation window duration.
- Request count.
- Authentication failure count.
- Authorization denial count.
- Optional validated workload indicator.

Output should include:

- Observation level.
- Stable evidence reason codes.
- Whether manual review is recommended.
- Whether the input is valid.

The evaluation function must:

- Be deterministic for the same inputs.
- Avoid databases and shared storage.
- Avoid network access.
- Avoid modifying incoming data.
- Avoid writing logs or audit events.
- Avoid reading environment secrets.
- Avoid middleware or request mutation.
- Avoid invoking rate-limiting enforcement.

UNKNOWN must not be interpreted as safe to
skip normal authentication or authorization.

## 8. Threshold configuration boundaries

Production thresholds must be supported by
representative traffic measurements.

Different endpoint types may require different
request-cost models.

A POST operation must not automatically receive
a high-cost classification without evidence.

Initial engineering tests may use illustrative
thresholds but must label them as test fixtures.

No illustrative threshold may become an active
production limit without separate approval.

## 9. False-positive safeguards

- Consider legitimate traffic bursts.
- Distinguish shared gateways from single accounts.
- Avoid penalizing tenant-wide activity based only
  on one account or peer IP.
- Account for scheduled integrations.
- Assess error conditions independently.
- Keep observation separate from enforcement.
- Require evidence before restrictions.
- Support review, expiry, and rollback.
- Protect availability during monitoring failures.

## 10. Distributed detection requirements

A future stateful detector must use appropriate
atomic shared storage for multiple processes
and application instances.

Local in-memory counters are insufficient for
distributed enforcement.

Storage selection must address:

- Atomicity and concurrency.
- Expiration of observation windows.
- Bounded memory usage.
- Clock and time-window behavior.
- Failure handling and recovery.
- Retention and privacy controls.
- Multi-instance consistency.
- Monitoring and incident review.

No Redis deployment or other backend is
approved by this document.

## 11. Enforcement separation

The detector provides evidence and observations.

A future policy engine may recommend actions.

A separate approved enforcement layer would
apply throttling or temporary restrictions.

No detector result may itself bypass or weaken
Django permissions.

Actual restrictions require explicit thresholds,
false-positive testing, approved storage, and
rollback procedures.

## 12. Required regression tests

- Valid low-activity observation.
- Missing or invalid observation inputs.
- Negative and non-integer counters.
- Impossible counts exceeding total requests.
- Unsupported endpoint categories.
- Deterministic outcomes.
- Distinct evidence reason codes.
- No mutation of input structures.
- No database access.
- No external service access.
- No middleware activation.
- Unknown category handling.
- Legitimate burst scenarios.
- Authentication and denial signals.
- Invalid observation-window handling.
- No automatic blocking.

Future integration tests must separately cover
concurrency, shared storage, and false positives.

## 13. Privacy and security logging

The pure evaluator performs no logging.

Future logging must use minimal necessary fields,
appropriate retention, restricted access, and
approved pseudonymous identifiers.

Do not store passwords, tokens, complete API
credentials, or unnecessary request payloads.

## 14. Implementation sequence

Phase 1:
Create an immutable observation input model
and side-effect-free evaluation function.

Phase 2:
Add isolated unit regression tests using
illustrative non-production scenarios.

Phase 3:
Validate observation results and revise rules
against representative authorized workloads.

Phase 4:
Design separate collection and shared-state
infrastructure with failure-mode tests.

Phase 5:
Run observe-only integration tests.

Phase 6:
Consider controlled enforcement only after
proxy, monitoring, rollback, and deployment
requirements have been satisfied.

## 15. Release gates

Before any live enforcement:

1. Verify complete endpoint classifications.
2. Confirm trusted-proxy boundaries.
3. Verify authentication and tenant permissions.
4. Approve signal sources and retention rules.
5. Validate representative legitimate traffic.
6. Select atomic shared-state infrastructure.
7. Approve explicit quantitative thresholds.
8. Test concurrent and distributed requests.
9. Test failures, recovery, and rollback.
10. Approve production rollout separately.

## 16. Next engineering milestone

Implement an isolated abuse-observation evaluator
and corresponding regression tests.

The implementation must not change Django
middleware, settings, database schemas, or
production traffic behavior.
