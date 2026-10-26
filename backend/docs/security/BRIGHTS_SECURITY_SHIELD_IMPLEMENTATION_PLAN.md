# Brights Security Shield — Infrastructure Implementation Plan

## 1. Document status

Status: Proposed implementation roadmap.
Branch: feature/brights-security-shield.

This plan translates the security architecture, threat
model, and DDoS response runbook into deliverable work.

No production WAF, DDoS service, protected origin,
or high-availability infrastructure has been verified
as deployed.

Provider selection and deployment approvals are pending.

## 2. Guiding principles

- Enforce protection at the network edge first.
- Prevent direct bypass of edge protections.
- Keep Django authentication and tenant isolation intact.
- Prefer measurable security outcomes over assumptions.
- Test false positives before enabling restrictive rules.
- Preserve rollback procedures for every deployment.
- Keep credentials out of code and documentation.
- Separate development, testing, and production changes.
- Record dependencies, costs, and operational ownership.

## 3. Phase 1 — Infrastructure discovery

Objective:
Document the actual hosting and network environment.

Required evidence:

- Public DNS records and domain ownership.
- Current website hosting and deployment configuration.
- Django deployment location and public entry points.
- Existing CDN, proxy, and load balancer arrangements.
- PostgreSQL hosting and network access configuration.
- TLS termination and certificate responsibilities.
- Existing monitoring, backups, and incident contacts.
- Secrets management and deployment permissions.

Deliverable:
Reviewed infrastructure inventory and trust-boundary map.

Acceptance:
An authorized project owner validates the documented
environment before provider-specific configuration.

Do not guess actual hosting topology.

## 4. Phase 2 — Edge protection selection

Objective:
Select appropriate CDN, WAF, and DDoS protection.

Compare candidate providers using:

- Network-level DDoS mitigation capabilities.
- Application-layer attack detection.
- Managed WAF rules and custom policy support.
- API-compatible bot mitigation and rate limiting.
- Security logs and alert integrations.
- Authenticated or restricted origin connectivity.
- DNS and TLS integration.
- Reliability, failover, and support arrangements.
- Data processing location and retention.
- Pricing and expected traffic costs.
- Configuration automation and rollback options.

Deliverable:
Provider decision record with documented tradeoffs.

Acceptance:
Capabilities and required service tiers are verified
against official provider documentation and an approved
deployment budget.

## 5. Phase 3 — Protected origin

Objective:
Ensure requests cannot bypass edge filtering.

Potential approaches, dependent on hosting capabilities:

- Private networking between edge and origin.
- Firewall allow rules restricted to trusted sources.
- Authenticated origin connections.
- Approved load balancer and proxy access controls.

Required safeguards:

- Reject direct unauthorized origin connections.
- Prevent exposure of sensitive administrative endpoints.
- Correctly validate trusted forwarding headers.
- Keep application health checks functional.
- Document recovery procedures for provider outages.

Deliverable:
Origin isolation configuration and test evidence.

Acceptance:
Approved edge traffic succeeds while unauthorized
direct-origin access fails during controlled testing.

## 6. Phase 4 — Django and proxy hardening

Objective:
Secure application behavior behind trusted proxies.

Required checks:

- HTTPS redirect behavior in the actual deployment.
- Secure cookies and session settings.
- CSRF and allowed-host configuration.
- Correct trusted proxy and client IP handling.
- Appropriate security headers.
- Authentication and authorization checks.
- Retail organization and tenant isolation.
- Safe error responses and secret redaction.
- Dependency and configuration vulnerability review.

Deliverable:
Reviewed configuration changes and automated tests.

Acceptance:
Security regression tests pass without breaking
existing application and retail functionality.

Do not change development or production settings until
the real proxy and TLS topology is confirmed.

## 7. Phase 5 — Adaptive abuse protection

Objective:
Detect and respond to suspicious request behavior.

Potential signals:

- Endpoint-specific traffic volume and change rate.
- Authentication failure patterns.
- Account or API credential abuse.
- Suspicious sequences and enumeration attempts.
- Correlated activity across multiple IP addresses.
- WAF signatures and bot indicators.
- Backend saturation and endpoint processing cost.

Enforcement stages:

1. Observe and record.
2. Increase monitoring.
3. Apply temporary throttling.
4. Apply an appropriate challenge or restriction.
5. Temporarily block strongly supported abusive traffic.
6. Escalate coordinated incidents.

Required safeguards:

- Avoid treating IP addresses as unique users.
- Account for shared networks and legitimate integrations.
- Avoid browser-only challenges for non-browser APIs.
- Provide expiry, review, and rollback for restrictions.
- Record the reasons behind enforcement.
- Apply privacy-conscious security logging.

Deliverable:
Policy design, implementation, and regression tests.

Acceptance:
Controlled tests demonstrate mitigation while
legitimate requests continue to function.

## 8. Phase 6 — Monitoring and incident readiness

Objective:
Make security incidents detectable and manageable.

Required capabilities:

- Edge traffic and mitigation dashboards.
- Application latency and error monitoring.
- Authentication abuse and access-denial alerts.
- Database and application resource monitoring.
- Independent service health checks.
- Incident severity classification.
- Named responders and backups.
- Provider escalation contacts.
- Emergency mitigation and rollback procedures.
- Safe retention of relevant incident evidence.

Deliverable:
Operational dashboards, alerts, and assigned runbook.

Acceptance:
A tabletop exercise verifies escalation, response,
communications, rollback, and recovery.

## 9. Phase 7 — Performance and resilience validation

Objective:
Measure realistic application capacity and resilience.

Engineering target:
Evaluate sustained 10,000 requests per second under
a defined representative workload.

Required measurements:

- Requests per second and concurrency.
- Request distribution by endpoint.
- Authenticated versus unauthenticated workloads.
- Database-intensive request proportions.
- Cache hit and miss behavior.
- p95 and p99 response latency.
- Response error rates.
- Application and database utilization.
- Sustained-test duration and bursts.
- Service degradation and recovery behavior.
- Failover response where supported.

Testing restrictions:

- Use isolated or explicitly authorized environments.
- Set agreed load limits before executing tests.
- Avoid uncontrolled attack simulation.
- Establish stop conditions and monitoring.
- Record actual measurements and infrastructure costs.

Deliverable:
Capacity report with measured results and bottlenecks.

Acceptance:
The project owner reviews results against approved
service-level objectives and capacity budgets.

The 10,000 RPS figure is a target, not a guarantee.

## 10. Dependency sequence

Phase 1 must precede provider-specific design.

Phase 2 must precede production edge configuration.

Phase 3 must be completed before declaring the WAF
effective against direct origin bypass.

Phase 4 must reflect verified proxy and TLS behavior.

Phases 5 and 6 require representative traffic signals
and documented response ownership.

Phase 7 requires a defined workload, authorized test
environment, and explicit stop conditions.

## 11. Release gates

Gate A — Architecture:
Architecture, threat model, and implementation plan reviewed.

Gate B — Provider readiness:
Provider capabilities, costs, and responsibilities approved.

Gate C — Origin protection:
Direct-origin bypass tests completed successfully.

Gate D — Application security:
Configuration and authorization tests passed.

Gate E — Abuse enforcement:
Controlled abuse and false-positive tests passed.

Gate F — Incident readiness:
Monitoring, responders, and exercises verified.

Gate G — Capacity:
Performance evidence reviewed; limits documented.

Production activation requires an authorized approval
and a practical rollback plan.

## 12. Outstanding owner decisions

The project owner must confirm:

- Public domain and DNS management.
- Website hosting provider.
- Django API hosting provider.
- PostgreSQL deployment environment.
- Production and staging environments.
- Expected API traffic and usage patterns.
- Budget for edge and hosting security.
- Operational alerting and response ownership.
- Data residency and security logging requirements.
- Desired availability and recovery objectives.

Do not store credentials in this decision record.

## 13. Next engineering action

Perform a read-only inventory of existing deployment
configuration, infrastructure references, and application
security settings.

Do not deploy a WAF, modify DNS, expose local credentials,
or alter production access until that inventory is reviewed.
