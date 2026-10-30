# Brights Security Shield — Endpoint Risk Classification

## 1. Status

Status: Proposed security design only.

No rate limiting, scoring, enforcement, middleware,
blocking, or production routing changes are activated.

This design uses the static Django route and view
inspection completed in development Steps 747 and 748.

The identified methods are based on view decorators
and source references, not live HTTP verification.

Included URL prefixes, authorization helpers,
resource costs, and runtime access controls require
additional validation before enforcement.

## 2. Classification categories

A — Public read candidate

Read-oriented operations that may be public.
Low execution cost and anonymous access are not
yet established by the static inspection.

B — Authenticated or tenant-sensitive read

Operations associated with organization, datasets,
retail resources, or other tenant-sensitive data.

C — Authentication-sensitive

Login, credential recovery, and authentication
operations. No dedicated application endpoint was
verified for this category during Steps 747–748.

D — Potentially expensive or resource-changing

Operations whose resource cost or request effects
require workload-specific review. A POST method
alone does not prove high computation cost.

E — Privileged or security-sensitive

Membership changes, access-grant modifications,
and sensitive security or audit operations.

UNCLASSIFIED — Review required

Unknown handlers, unsupported methods, unresolved
URL patterns, or endpoints without sufficient evidence.

UNCLASSIFIED is not a permission decision.
It never grants access or bypasses authorization.

## 3. Observed handler and method inventory

The following are proposed design classifications,
not verified production enforcement assignments.

| Application | Handler | Method | Proposed category | Evidence or remaining review |
|---|---|---|---|---|
| analytics | dashboard | GET | A candidate | require_GET; public access and cost unverified |
| analytics | indicator_api | GET | A candidate | require_GET; cost and access unverified |
| analytics | places_api | GET | A candidate | require_GET; cost and access unverified |
| organizations | corporate_dashboard | GET | B | require_GET; organization permission reference |
| retail | product_list | GET | B | require_GET; api_login_required decorator |
| retail | branch_list | GET | B | require_GET; api_login_required decorator |
| datasets | dataset_list | GET | B | GET/POST decorator; membership reference |
| datasets | dataset_list | POST | D candidate | GET/POST decorator; operation and cost review needed |
| datasets | dataset_detail | GET | B | require_GET; membership reference |
| datasets | grant_list | POST | E | require_POST; grant and membership references |
| datasets | grant_revoke | POST | E | require_POST; permission and context references |
| organizations | membership_list | POST | E | require_POST; membership creation references |
| organizations | membership_role_change | POST | E | require_POST; role modification references |
| organizations | membership_deactivate | POST | E | require_POST; deactivation references |
| auditlog | audit_history | GET | E | require_GET; PermissionDenied reference |

These are 15 observed handler-method combinations.

Administrative URLs are present under admin/.
The administrator endpoint tree and HTTP methods
were not inventoried here and remain unclassified.

## 4. Route resolution requirements

Do not guess final public URL paths from handlers.

The root Django URL configuration includes
nested organization, dataset, retail, and audit URLs.

Resolve the complete URL hierarchy and named
route identifiers before runtime integration.

The initial classifier should accept explicitly
verified identifiers rather than substring matches
against arbitrary request paths.

Unknown or unmatched identifiers must return
UNCLASSIFIED.

## 5. HTTP method requirements

HTTP methods must be normalized consistently.

Do not automatically classify all methods for
a handler as equivalent.

GET and POST may have different resource costs
and security implications.

HEAD and OPTIONS behavior must be reviewed
separately where framework handling differs.

Unsupported methods must not silently receive
a lower-risk category.

## 6. Authentication and authorization boundaries

Classification is not authentication.

Classification is not authorization.

The existing permission and tenant isolation
mechanisms remain authoritative.

No classification can authorize a request that
Django would otherwise deny.

Authentication and authorization within helper
functions must be verified separately.

## 7. Identity and proxy safeguards

Do not classify trustworthiness from arbitrary
X-Forwarded-For or similar request headers.

The existing get_network_peer_ip function
identifies only the immediate network peer.

Original-client identity behind trusted proxies
remains unresolved until deployment validation.

Rate limiting by network peer alone risks
false positives for shared corporate networks.

## 8. Planned pure classification component

Create a side-effect-free Python classifier.

Inputs:
- Explicitly verified handler or route identifier.
- Normalized HTTP method.

Output:
- Proposed category or UNCLASSIFIED.

The classifier must not:
- Read or write databases.
- Access Redis or external services.
- Inspect secrets.
- Read authentication tokens.
- Mutate requests.
- Write security audit events.
- Enforce throttling or blocking.
- Override tenant permissions.

Risk classification must remain separate from
rate-limit configuration and enforcement decisions.

## 9. Required regression tests

- Every explicitly approved handler-method mapping.
- Unknown handler returns UNCLASSIFIED.
- Unknown HTTP method returns UNCLASSIFIED.
- Case normalization is deterministic.
- Unsupported handler-method pairs remain unclassified.
- Privileged POST routes never downgrade to public read.
- Dataset GET and POST remain distinct.
- No database access occurs.
- No middleware or settings changes are required.
- Existing client-IP tests remain passing.

## 10. Review gates before enforcement

1. Resolve full Django URL prefixes and namespaces.
2. Confirm framework-resolved route identifiers.
3. Inspect authorization helper behavior.
4. Review the actual dataset POST operation.
5. Confirm anonymous access to public candidates.
6. Measure expensive endpoint workloads.
7. Identify authentication and recovery routes.
8. Review administrator and third-party routes.
9. Establish trusted proxy boundaries.
10. Select atomic shared-state infrastructure.
11. Define and test quantitative limits.
12. Perform observe-only validation.
13. Approve rollback and deployment procedures.

## 11. Next milestone

Implement the isolated, side-effect-free classification
component with explicit mappings and regression tests.

Leave A and D candidates reviewable rather than
treating them as production-approved thresholds.

Do not activate enforcement or middleware.
