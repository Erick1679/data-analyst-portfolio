# Brights Security Shield — Threat Model

## 1. Document status

Status: Proposed threat-model baseline.
System: The Brights Analytics website, Django APIs,
Brights Retail Intelligence, and supporting infrastructure.

This document identifies threats and required controls.
It does not claim that the controls are deployed.

Hosting, WAF, CDN, and monitoring vendors remain undecided.

## 2. Protected assets

Critical assets include:

- Website and API availability.
- User accounts and authenticated sessions.
- Organization membership and role assignments.
- Tenant-isolated retail and analytical data.
- PostgreSQL databases and backups.
- Application secrets and API credentials.
- Security policies and WAF configuration.
- Audit logs and incident evidence.
- DNS records, TLS keys, and origin infrastructure.

## 3. Potential threat actors

Relevant actors include:

- Automated scanning bots.
- Credential-stuffing operators.
- Application-layer DDoS operators.
- Volumetric DDoS operators.
- Attackers attempting origin bypass.
- Malicious or compromised authenticated accounts.
- Attackers exploiting application vulnerabilities.
- Attackers abusing legitimate API functionality.

Insider misuse and configuration mistakes must also
be included in operational risk assessments.

## 4. Trust boundaries

Boundary A: Public internet to edge security provider.

Requests cross from untrusted networks into the
managed CDN, WAF, and DDoS mitigation infrastructure.

Boundary B: Edge security provider to protected origin.

Only authorized edge traffic should reach the origin.
Direct public access must be prevented or authenticated.

Boundary C: Load balancer to Django application.

Proxy headers must be accepted only from trusted proxies.
Original client identity must be derived securely.

Boundary D: Unauthenticated to authenticated application.

Access requires valid authentication and appropriate
session or API credential verification.

Boundary E: Authenticated user to tenant resources.

Every data operation must enforce organization membership,
permissions, and record ownership or tenant scope.

Boundary F: Application to private data services.

Database and supporting-service access must be restricted
to approved application identities and network paths.

## 5. Threat scenarios and controls

### T01 — Network-layer DDoS

Scenario:
Large volumes of network traffic attempt to exhaust
network capacity or connection-processing resources.

Potential impact:
Loss of availability and increased infrastructure costs.

Primary control:
Upstream network-level DDoS protection.

Secondary controls:
Provider escalation, redundant capacity, and failover.

Validation:
Authorized provider-supported mitigation testing
and documented response procedures.

### T02 — HTTP application-layer flooding

Scenario:
Attackers overwhelm expensive endpoints using repeated
or distributed HTTP requests.

Potential impact:
Application saturation, database overload, and downtime.

Primary control:
Edge WAF and behavioral request filtering.

Secondary controls:
Adaptive throttling, caching, scaling, and queues.

Validation:
Controlled HTTP load tests using representative
authenticated and unauthenticated request mixes.

### T03 — Distributed low-rate bot activity

Scenario:
An attacker distributes suspicious activity across
multiple IP addresses to avoid basic rate thresholds.

Potential impact:
Resource exhaustion, enumeration, and account abuse.

Primary control:
Behavioral anomaly detection using correlated signals.

Secondary controls:
Account-aware and credential-aware restrictions.

Validation:
Simulated distributed request patterns with false-positive
checks for legitimate customers.

### T04 — Origin bypass

Scenario:
Attackers discover a public origin address and connect
directly, bypassing CDN and WAF controls.

Potential impact:
Unfiltered malicious traffic reaches the application.

Primary control:
Network restrictions and authenticated origin access.

Secondary controls:
Origin-address protection and monitoring.

Validation:
Controlled tests must verify that direct origin requests
are rejected while legitimate edge traffic succeeds.

### T05 — Spoofed client IP headers

Scenario:
Attackers supply forged forwarding headers to impersonate
another client or evade adaptive restrictions.

Potential impact:
Incorrect security decisions and misleading audit logs.

Primary control:
Trusted reverse-proxy boundaries and header sanitization.

Validation:
Requests with forged forwarding metadata must not alter
the effective client identity unexpectedly.

### T06 — Credential stuffing and account abuse

Scenario:
Attackers automate login attempts or use stolen credentials.

Potential impact:
Account takeover and unauthorized information access.

Primary control:
Authentication abuse detection and secure account controls.

Secondary controls:
Adaptive enforcement and appropriate additional verification.

Validation:
Controlled login-failure and account-abuse test cases.

### T07 — Cross-tenant data access

Scenario:
A user attempts to access another organization's
products, branches, datasets, or administrative records.

Potential impact:
Confidentiality breaches and unauthorized modifications.

Primary control:
Server-side membership, permission, and tenant checks.

Secondary controls:
Database constraints, logging, and regression tests.

Validation:
Tests must cover outsiders, inactive memberships,
cross-organization access, and role changes.

### T08 — Injection and malformed requests

Scenario:
Attackers submit malicious input designed to exploit
application or database parsing and validation.

Potential impact:
Data exposure, data modification, or application compromise.

Primary control:
Parameterized database operations and input validation.

Secondary controls:
Managed WAF rules and secure dependency management.

Validation:
Security-focused tests and controlled vulnerability scans.

### T09 — Database resource exhaustion

Scenario:
Expensive queries or excessive concurrent requests
overload PostgreSQL.

Potential impact:
Elevated latency, rejected requests, or service disruption.

Primary control:
Efficient queries, connection management, and workload limits.

Secondary controls:
Caching, asynchronous processing, and observability.

Validation:
Representative workload, connection, and saturation tests.

### T10 — False-positive WAF or ban enforcement

Scenario:
Security rules block legitimate customers or integrations.

Potential impact:
Customer disruption and business revenue loss.

Primary control:
Observe-before-enforce rollout and conservative escalation.

Secondary controls:
Rule review, allow exceptions, automatic expiry, and rollback.

Validation:
Legitimate-user test traffic must remain functional.

### T11 — Monitoring or response failure

Scenario:
An attack is not detected or responders cannot
execute containment procedures.

Potential impact:
Extended outages and delayed recovery.

Primary control:
Independent health monitoring and actionable alerts.

Secondary controls:
Documented on-call ownership and incident exercises.

Validation:
Alert-delivery tests and incident-response simulations.

### T12 — Compromised infrastructure credentials

Scenario:
Secrets or deployment credentials are disclosed or abused.

Potential impact:
Infrastructure takeover or sensitive data exposure.

Primary control:
Least-privilege identities and managed secret storage.

Secondary controls:
Credential rotation, audit trails, and incident procedures.

Validation:
Secret scanning and access-control review.

## 6. Adaptive anomaly-detection design

Candidate detection dimensions include:

- Client IP and network reputation.
- Account and organization activity.
- API credential or session identity.
- Rate changes relative to historical baselines.
- Repeated authentication and authorization failures.
- Suspicious request sequences.
- Repeated resource enumeration.
- Endpoint cost and observed backend saturation.
- Known attack signatures and automated bot signals.

Detection must consider distributed activity across IPs.

An IP address must not be treated as a unique person.
Shared networks and legitimate integrations require
false-positive safeguards.

Risk thresholds and scoring weights remain undecided.

## 7. Progressive enforcement requirements

Proposed sequence:

1. Observe and log relevant behavior.
2. Increase monitoring for suspicious patterns.
3. Apply proportionate temporary throttling.
4. Challenge or restrict access where appropriate.
5. Temporarily block strongly supported abusive sources.
6. Escalate coordinated attacks to incident responders.

API clients must not depend on browser-only challenges.

Restrictions must have defined expiry, review, and rollback.

Permanent bans must not be automatic based solely on volume.

## 8. Availability and performance risks

Target:
Evaluate sustained 10,000 requests per second for a
defined representative workload.

This is not a demonstrated current capability.

Testing must assess:

- Static and cached response handling.
- Authenticated Django API requests.
- Database-intensive retail requests.
- Request concurrency and queueing.
- p95 and p99 response latency.
- Error rates under sustained load.
- Cache failure and backend saturation.
- Load-balancer and instance failover.
- Recovery after overload or mitigation.

Capacity depends on selected infrastructure, request
complexity, and operational configuration.

No system should be described as incapable of downtime.

## 9. Detection and monitoring

Required observations include:

- Edge request and mitigation events.
- WAF rule matches and actions.
- Authentication and authorization anomalies.
- HTTP error rates and response latency.
- Load-balancer and application health.
- PostgreSQL saturation indicators.
- Infrastructure resource utilization.
- Origin-bypass attempts.

Security logs should avoid exposing passwords, secrets,
full authentication tokens, or unnecessary personal data.

Logging access and retention require explicit policies.

## 10. Control ownership

Edge security provider:
Network-level DDoS mitigation and edge WAF enforcement.

Cloud hosting provider:
Network isolation, load balancing, instance availability,
and platform-level protections.

Brights application:
Authentication, authorization, tenant isolation,
input validation, and security event generation.

Brights security operations:
Detection policy, escalation decisions, incident handling,
false-positive review, and recovery exercises.

Specific vendors, personnel, and service agreements
must be selected before production deployment.

## 11. Incident-response prerequisites

Before launch, establish:

- A documented DDoS response runbook.
- Named incident owner and backup.
- Severity classification.
- Provider escalation contacts.
- Emergency WAF policy and rollback process.
- Customer-status communications.
- Recovery objectives.
- Evidence retention and review procedures.
- Periodic incident-response exercises.

## 12. Validation and acceptance criteria

The threat model is addressed only when:

1. Controls have assigned owners.
2. Required edge filtering is deployed and tested.
3. Direct origin bypass is demonstrably prevented.
4. Client-IP handling resists spoofed forwarding headers.
5. Cross-tenant permission tests pass.
6. Adaptive restrictions are tested against false positives.
7. DDoS response procedures have been exercised.
8. Monitoring and alert delivery are verified.
9. Workload tests measure performance and recovery.
10. Security changes have documented rollback procedures.

## 13. Open decisions

- WAF and CDN provider.
- Cloud hosting and network topology.
- Origin isolation mechanism.
- Adaptive scoring architecture.
- Storage and retention for security events.
- Alerting and incident-management tooling.
- Security ownership and escalation contacts.
- Acceptable availability and recovery targets.
- Production traffic and capacity budgets.
- Legal and privacy requirements for IP telemetry.

All open decisions must be resolved or risk-accepted
before the relevant controls are declared production-ready.
