# Brights Security Shield
# DDoS Incident Response Runbook

## 1. Document control

Status: Draft for operational implementation.
System: The Brights Analytics.
Applies to: Public website, Django APIs and infrastructure.

This runbook must be operationalized and exercised before
public production launch.

The security providers, hosting arrangements and named
incident responders have not yet been selected.

No active WAF, DDoS mitigation service or guaranteed
10,000 RPS capacity is implied by this document.

## 2. Objectives

1. Detect attacks and service degradation quickly.
2. Protect legitimate website and API customers.
3. Contain malicious traffic at the network edge.
4. Preserve authentication and tenant isolation.
5. Maintain critical functionality where feasible.
6. Restore normal service safely.
7. Preserve relevant incident evidence.
8. Improve controls after each incident.

## 3. Incident roles

Incident Commander:
Owner: TO BE ASSIGNED
Backup: TO BE ASSIGNED

Security Operations Lead:
Owner: TO BE ASSIGNED

Infrastructure Lead:
Owner: TO BE ASSIGNED

Application and Database Lead:
Owner: TO BE ASSIGNED

Customer Communications Lead:
Owner: TO BE ASSIGNED

External contacts:
WAF/DDoS provider: TO BE SELECTED
Hosting provider: TO BE SELECTED
DNS provider: TO BE SELECTED
Emergency escalation channel: TO BE ESTABLISHED

All contacts, access permissions and backup personnel
must be verified before production launch.

## 4. Incident severity

SEV-1 — Critical

Examples:
- Public website or essential APIs unavailable.
- Broad legitimate-user disruption.
- Severe infrastructure exhaustion.
- Attack-related outage requiring emergency coordination.

Response:
Activate the highest incident escalation level.
Coordinate with hosting and DDoS mitigation providers.
Prioritize safe restoration of essential services.

SEV-2 — High

Examples:
- Significant degradation or elevated API errors.
- Sustained malicious traffic with partial customer impact.
- Backend saturation approaching service failure.

Response:
Begin coordinated mitigation and customer-impact review.

SEV-3 — Moderate

Examples:
- Suspicious patterns without material service disruption.
- Localized abusive automation or repeated scanning.
- Increased mitigation events requiring investigation.

Response:
Investigate and apply proportionate controls if justified.

SEV-4 — Informational

Examples:
- Isolated suspicious activity.
- Low-risk anomaly without confirmed service impact.

Response:
Record, monitor and review.

Specific response times and severity thresholds must be
defined from business requirements and service baselines.

## 5. Detection indicators

Monitor where supported:

- Edge request volume and geographic distribution.
- DDoS and WAF detection events.
- Request patterns and attack signatures.
- Authentication and authorization failures.
- HTTP 429, 500, 502, 503 and 504 responses.
- p95 and p99 application latency.
- CPU, memory and network saturation.
- Connection pool and PostgreSQL utilization.
- Load balancer health and application instance failures.
- Cache efficiency and background queue growth.

No single metric establishes malicious intent.

Correlate multiple signals before broad enforcement.

## 6. Initial incident checklist

When an alert or outage is reported:

1. Record incident start time and detection source.
2. Confirm whether the website or APIs are affected.
3. Check monitoring availability and data reliability.
4. Compare current traffic with known normal patterns.
5. Determine whether an infrastructure failure,
   software regression or DDoS attack is suspected.
6. Identify affected routes, regions and tenants.
7. Assign an Incident Commander.
8. Establish an incident record and communications channel.
9. Select the initial severity.
10. Begin mitigation only through authorized controls.

Do not assume that all traffic spikes are attacks.

## 7. Traffic triage

Identify whether the event appears to involve:

- Network-layer volumetric flooding.
- HTTP application-layer flooding.
- Distributed low-rate bots.
- Credential stuffing or authentication abuse.
- Origin bypass.
- Expensive endpoint or database-query exhaustion.
- Legitimate customer traffic growth.
- Infrastructure or deployment failure.

Preserve relevant request identifiers, timestamps,
provider alerts and system-health evidence.

Avoid collecting unnecessary personal information
or exposing authentication tokens in incident records.

## 8. Edge containment

Authorized responders may use available controls to:

1. Activate provider-supported DDoS mitigation.
2. Enable appropriate managed WAF protections.
3. Apply targeted behavioral rate limiting.
4. Restrict strongly supported abusive sources.
5. Challenge suspicious browser traffic where appropriate.
6. Escalate coordinated attacks to the edge provider.
7. Review effects on legitimate customer traffic.

For machine-to-machine APIs, browser challenges may
break legitimate integrations. Prefer API-compatible
mitigations where appropriate.

Every emergency rule must record:

- Incident reference.
- Authorizing responder.
- Reason for enforcement.
- Scope and affected traffic.
- Time enabled.
- Expiry or review time.
- Rollback instructions.

Do not issue indefinite IP bans solely because
a request-rate threshold was exceeded.

## 9. Origin and infrastructure protection

Verify that:

- Direct public access to the origin is restricted.
- Edge-to-origin connections are authenticated
  or restricted through approved network controls.
- Client IP forwarding headers are trusted only
  from approved reverse proxies.
- Load balancer health checks remain operational.
- Application instances have safe connection limits.
- PostgreSQL is not publicly exposed.
- Administrative interfaces remain protected.

Origin protection must be independently tested before
the system is considered production-ready.

## 10. Service continuity

During an attack:

- Prioritize authentication and critical API operations.
- Preserve organization and tenant authorization checks.
- Use validated cache rules where appropriate.
- Defer nonessential background processing if safe.
- Scale healthy application capacity where available.
- Monitor database and connection pool saturation.
- Preserve a controlled rollback path.

Never disable tenant isolation, audit protections or
authentication merely to restore throughput.

Changes to caching must not expose private tenant data.

## 11. Customer communications

Customer updates should explain:

- Whether service is degraded or unavailable.
- Which general services are affected.
- Whether mitigations are underway.
- Where future status updates will appear.
- When the next communication is expected,
  if a cadence has been agreed.

Do not disclose sensitive mitigation rules,
infrastructure secrets or unverified attack attribution.

Assign a communications owner and approved status
channel before production launch.

## 12. Recovery checklist

Before declaring recovery:

1. Verify website and API health.
2. Confirm critical authenticated requests work.
3. Check organization-level data isolation.
4. Verify PostgreSQL and supporting services are healthy.
5. Check latency and error rates against baselines.
6. Review ongoing edge mitigation events.
7. Gradually relax emergency rules where safe.
8. Confirm legitimate customers are not blocked.
9. Monitor for renewed malicious activity.
10. Obtain Incident Commander approval to close.

Recovery objectives must be approved before launch.

## 13. Evidence and incident record

Maintain an incident record containing:

- Incident ID and severity.
- Detection and response timeline.
- Affected services and customer impact.
- Relevant monitoring metrics.
- Security rules activated or modified.
- Authorized operational decisions.
- Escalations and provider interactions.
- Recovery validation and incident closure.
- Follow-up actions and accountable owners.

Restrict evidence access and establish lawful retention.

## 14. Post-incident review

Conduct a documented review covering:

- Root cause and attack characteristics.
- Detection effectiveness.
- Time to respond and recover.
- Service availability and customer impact.
- False-positive WAF or ban decisions.
- Infrastructure bottlenecks.
- Communication effectiveness.
- Necessary rule, configuration and process changes.
- Retesting and follow-up owners.

Update the threat model when new attack paths emerge.

## 15. Testing and exercises

Before production launch:

1. Verify monitoring and alert delivery.
2. Test emergency contact and escalation channels.
3. Practice WAF rule activation and rollback.
4. Confirm origin-bypass protection.
5. Validate legitimate API integration behavior.
6. Exercise a tabletop DDoS incident.
7. Test application recovery and failover.
8. Confirm that evidence can be collected safely.
9. Document the exercise and corrective actions.

Load or attack simulations must be authorized and
restricted to approved environments.

The 10,000 requests-per-second objective requires
separate representative workload testing.

It is not an incident-response guarantee.

## 16. Launch readiness requirements

The runbook is not operationally ready until:

- Responders and backups are assigned.
- Provider contacts are verified.
- Monitoring and alerts are configured.
- WAF and DDoS controls are deployed and tested.
- Origin access is restricted.
- Incident escalation paths are available.
- Customer communications are prepared.
- Recovery objectives are approved.
- A tabletop exercise has been completed.
- Remediation actions are tracked.

## 17. Change control

All changes must be:

- Reviewed on the security development branch.
- Tested before production activation.
- Documented with rollback instructions.
- Compatible with existing retail permissions.
- Free of embedded private credentials.
- Recorded in the incident history when used urgently.

This draft does not authorize production changes.
