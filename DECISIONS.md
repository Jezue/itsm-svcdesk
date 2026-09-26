---
svcdesk_decisions:
  C1: wallclock
  C2: immutable
  C3: matrix
---
<!-- ai-generated: 95% - OpenAI Codex drafted the rationale from the selected decisions and API contract. -->

# Decisions

## C1 - SLA clock for P1

**Decision:** P1 acknowledgement and resolution targets use uninterrupted wall-clock time, including nights and weekends.

**Rejected alternative:** We rejected pausing P1 targets outside the Monday-to-Friday business-hours window.

**Reason:** A P1 represents an organisation-wide outage, so delaying its deadline until staffed hours would hide the operational severity.

**Service owner:** The Service Desk product owner owns this choice because that role is accountable for SLA policy and escalation expectations.

**Customer outcome:** Reporters receive a continuous emergency response commitment, and operations can identify overdue critical incidents immediately.

## C2 - Closed tickets and reopening

**Decision:** Closed tickets are immutable; only resolved tickets may be reopened during the seven-day window.

**Rejected alternative:** We rejected reopening a closed ticket within seven days of its closure timestamp.

**Reason:** Closure records final confirmation of the fix, so preserving that record produces a stable audit trail and reliable reporting.

**Service owner:** The Service Desk product owner signs off because that role governs lifecycle policy, auditability, and reporting quality.

**Customer outcome:** Customers create a related follow-up ticket after closure, preserving the original history while keeping recurring work traceable.

## C3 - VIP reporters and the priority matrix

**Decision:** Priority always follows the impact-and-urgency matrix; the stored VIP flag does not alter it.

**Rejected alternative:** We rejected automatically promoting VIP tickets at P3 or P4 to priority P2.

**Reason:** Impact and urgency provide consistent operational risk signals, while reporter status alone does not describe service disruption.

**Service owner:** The Service Desk product owner owns priority policy because it controls queue ordering, SLA commitments, and staffing pressure.

**Customer outcome:** Every reporter receives prioritisation based on business impact and urgency, producing a transparent and predictable queue.
