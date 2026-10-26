# Brights Security Shield

## 1. Status and scope

Status: Proposed architecture baseline; not deployed.
Project: The Brights Analytics.
Branch: feature/brights-security-shield.

This document defines security and availability requirements
for the website, Django API, and supporting infrastructure.

The eventual hosting, CDN, WAF, and monitoring providers
have not yet been selected or verified.

No traffic capacity or DDoS-resilience guarantee is implied
by this document.

## 2. Security objectives

1. Inspect and mitigate suspicious traffic at the edge.
2. Prevent direct bypass of edge protection.
3. Preserve authentication, authorization, and tenant isolation.
4. Detect abusive behavior across multiple dimensions.
5. Escalate enforcement without unnecessary customer blocking.
6. Preserve availability during attacks and traffic spikes.
7. Detect incidents quickly and recover predictably.
8. Keep security configuration reviewable and testable.

## 3. Proposed network trust boundaries

Internet clients
    |
    v
Edge CDN / DDoS protection / Web Application Firewall
    |
    v
Protected origin and load balancer
    |
    v
Django application instances
    |
    v
Private PostgreSQL and supporting services

Boundary A: Internet to edge.

The edge must provide TLS termination or equivalent
encrypted transport, managed attack rules, reputation
signals, and volumetric mitigation.

Boundary B: Edge to origin.

Origin access must be restricted to approved edge paths
or authenticated connections, with authenticated origin
pulls or equivalent controls where supported.

The application origin must not remain openly reachable
through an unprotected public address.

Boundary C: Load balancer to Django.

Only trusted reverse proxies may supply client-IP
forwarding metadata. Forged forwarding headers must
not permit IP spoofing or bypass security decisions.

Boundary D: Django to data stores.

Database connectivity must remain private and protected
by least-privilege accounts, network restrictions, and
appropriate encryption.

## 4. Web Application Firewall requirements

The WAF must sit in front of the public website and API.

Required capabilities include:

- Managed rules for common web attacks.
- Protection against abusive automated traffic.
- Global and path-aware filtering.
- Rules for suspicious request patterns.
- Challenges or blocks where appropriate.
- Audit logs and rule-level monitoring.
- Emergency controls with safe rollback.
- Allow rules for validated legitimate integrations.

WAF rules must initially run in observation or an
equivalent safe testing mode where supported.

False positives must be evaluated before enforcement.

## 5. Adaptive anomaly detection

Detection must not rely on requests per second alone.

Candidate signals include:

- Request rate relative to historical behavior.
- Authentication failures and repeated denials.
- Enumeration and systematic resource scanning.
- Endpoint traversal and unusual request sequences.
- Known attack signatures and bot indicators.
- Traffic across related IPs, accounts, and tenants.
- Connection patterns and application error spikes.

IP reputation is one input, not the sole identity signal.

Shared IP addresses, mobile networks, corporate proxies,
and legitimate API clients must be accounted for.

Enforcement decisions require defined thresholds,
evidence retention, expiry, and a review mechanism.

## 6. Progressive enforcement

Proposed response levels:

Level 0: Normal monitoring.
Level 1: Enhanced logging and anomaly analysis.
Level 2: Temporary throttling of suspicious activity.
Level 3: Appropriate challenge or restricted access.
Level 4: Short-lived block for strongly supported abuse.
Level 5: Escalation for recurring coordinated attacks.

Durations and thresholds remain undecided until
traffic baselines and controlled tests are available.

For machine-to-machine APIs, challenges must not assume
that clients can solve browser-based verification.

Blocks must expire automatically unless explicitly
reviewed and renewed.

## 7. DDoS resilience and availability

The design must consider both:

- Network-layer and volumetric attacks.
- HTTP/application-layer resource exhaustion.

The engineering performance objective is to evaluate
sustained 10,000 requests per second under a defined,
representative workload.

This is a test target, not a current capability
or an availability guarantee.

Performance validation must specify:

- API request mix and response payload sizes.
- Authentication and database query complexity.
- Cache hit ratios.
- Concurrency and connection limits.
- p95 and p99 response latency.
- Error rate and saturation thresholds.
- Sustained-load duration.
- Burst and attack-simulation conditions.
- Failover and recovery behavior.

Potential infrastructure controls include a CDN,
load balancer, horizontal scaling, caching, database
connection pooling, and asynchronous job processing.

Infrastructure capacity and costs must be validated
before any production commitment.

## 8. DDoS incident response requirements

A version-controlled DDoS response runbook must exist
before public production launch.

It must define:

Preparation:
- Incident owner and backup.
- Hosting and security-provider escalation contacts.
- Dashboard and alert access.
- Baseline traffic and normal service indicators.
- Customer communications and status channels.

Detection:
- Traffic anomalies and attack alerts.
- Elevated error rates and response latency.
- Backend, load balancer, and database saturation.

Triage:
- Differentiate legitimate spikes from malicious traffic.
- Record affected applications, tenants, and regions.
- Assess customer impact and severity.

Containment:
- Apply reviewed edge mitigations.
- Protect critical application paths.
- Avoid broad IP blocks without supporting evidence.
- Document emergency configuration changes.

Recovery:
- Verify application and database health.
- Restore normal policies incrementally.
- Confirm legitimate clients can reconnect.
- Monitor for attack recurrence.

Post-incident:
- Preserve appropriate evidence.
- Record incident timeline and decisions.
- Identify false positives and service impacts.
- Update controls, tests, and response procedures.

Incident contact details, recovery objectives,
severity thresholds, and exact escalation triggers
remain to be established.

## 9. Application security boundaries

The WAF must complement, not replace:

- Django authentication.
- Organization-scoped authorization.
- Least privilege and tenant isolation.
- Input validation.
- CSRF protection where applicable.
- Secure cookies, TLS, and security headers.
- Database constraints and audit logging.

Public errors and logs must not expose secrets.

## 10. CI and controlled testing

Proposed future CI enhancements:

- Python dependency vulnerability checks.
- Static analysis and secret scanning.
- Security regression tests.
- Configuration validation for WAF policies.
- Controlled load and resilience testing.

Attack simulation must use owned or explicitly
authorized infrastructure and agreed test limits.

Never run load or attack simulations against public
production infrastructure without authorization.

## 11. Acceptance criteria

Before declaring Brights Security Shield production-ready:

1. Edge protection is configured and tested.
2. The origin is demonstrably protected against bypass.
3. WAF rules and false-positive handling are documented.
4. Adaptive enforcement is tested with legitimate users.
5. Temporary bans expire and support review/rollback.
6. Security logging and incident alerts are operational.
7. A DDoS response runbook has assigned owners.
8. Recovery procedures are exercised.
9. API workload tests report measured capacity.
10. Deployment and rollback procedures are documented.

## 12. Decisions still required

- Cloud hosting and network topology.
- Edge WAF/CDN provider and service tier.
- DNS and TLS management.
- Origin isolation technique.
- Monitoring and incident notification providers.
- Cache and background-job design.
- Performance budget and recovery objectives.
- Data retention and regulatory constraints.
- Service-level objectives and acceptable risk.

All vendor-specific controls require verification
against the selected deployment environment.

## 13. Change-control rules

All implementation changes must:

- Remain on the dedicated security feature branch.
- Preserve the existing retail application and tests.
- Avoid applying migrations to persistent databases.
- Avoid exposing local secrets or credentials.
- Receive review and automated checks before merging.
- Remain disabled in production until validated.

