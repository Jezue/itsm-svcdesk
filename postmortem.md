---
lab4_postmortem:
  ticket: "50ceffde-fa49-40b3-b4ca-957734d74bf7"
  detecting_alert: ShopCheckoutErrors
  onset: 2026-10-12T06:36:23Z
  detection: 2026-10-12T06:39:19Z
  acknowledgement: 2026-10-12T06:40:09Z
  recovery: 2026-10-12T06:44:19Z
  mttd_seconds: 176
  mtta_seconds: 50
  mttr_seconds: 476
  identified_flags: [paymentFailure, loadGeneratorFloodHomepage]
---
<!-- ai-generated: 100% - OpenAI Codex analysed the assigned recording, checked PromQL and drafted this recorded-path report. -->

# Failed checkouts during a payment fault and homepage traffic surge

## Date

The incident was recorded on 12 October 2026. This analysis was prepared on 25 October 2026 using the assigned course recording lab4-rec-4.

## Authors

Adam Gajewski, student analyst of the recorded incident. The lecturer operated the original incident; the ticket actions and timestamps below are from that recording, not actions performed during this analysis.

## Status

The detecting alert resolved in the recording. The exported ticket remains acknowledged, with no resolution timestamp. Service recovery and ticket closure are therefore separate; the follow-up action items below are proposals, not completed changes.

## Summary

Checkout requests failed while payment charge errors appeared and frontend traffic rose sharply. The recorded detecting alert was ShopCheckoutErrors. Detection took 176 seconds, acknowledgement another 50 seconds, and alert recovery was 476 seconds after onset. These are single-incident durations, despite the MTTD/MTTA/MTTR labels.

## Impact

At 06:42:00Z, checkout's five-minute server error rate was 0.03211344/s out of 0.10294678 calls/s: approximately 31.19% failed. Frontend server traffic rose from 3.80833/s on the baseline to 63.40833/s, about 16.65 times higher. These are windowed rates, not exact counts of affected customers or successful purchases.

The exact queries and responses are saved in incident/query-evidence.json: server_errors, server_calls and checkout_error_fraction. Checkout p95 at the same instant was about 47.71 milliseconds, so this recording supports an error incident rather than a two-second checkout latency incident.

## Root Causes

Two pool flags are supported by the symptoms: paymentFailure and loadGeneratorFloodHomepage. Payment SERVER and internal charge error rates changed from no baseline error series to 0.03211344/s at 06:42:00Z. Checkout's failed payment-client calls support propagation through that dependency. The frontend and frontend-proxy traffic surge, without a similar rise across all services, supports the homepage load flag.

The resource-class flag is not identified confidently. The sampled email memory and container uptime do not establish an OOM restart; recommendation memory alone is also inconclusive. It would be misleading to claim a third flag from these observations. No sealed fault was opened, and no source-code defect is proved by a failed span alone.

## Trigger

The seeded run c1daa7d0f4acf990 began its fault at 06:36:23Z, as recomputed by the official checker. The recording uses the course injector's three-class fault scenario. That onset metadata establishes the clock; it is not used in any alert or hypothesis prediction.

## Resolution

The lecturer's recorded mitigation was followed by the detecting alert resolving at 06:44:19Z. At 06:48:00Z, the payment and checkout error rates were zero and frontend traffic was back to 2.97912/s. This snapshot does not provide an operator command log, so the order and exact times of flag rollback are not asserted. I did not change the shop or edit the recorded ticket.

## Detection

ShopCheckoutErrors fired at 06:39:19Z; the recorded P1 ticket was created at 06:39:44Z and acknowledged at 06:40:09Z. The official incident command recomputed MTTD=176 s, MTTA=50 s and MTTR=476 s. The archive includes the pager and ticket-request telemetry, which the checker validates separately.

My new rules are not claimed to have detected this historic run. They cover checkout server error fraction above 5% and p95 above 2000 ms, each for one minute, plus a 2% chat warning. Only SERVER spans are paged on. P1 goes to pager, P2/P3 to chat; a same-service P1 inhibits its lower-severity warning, while the different-service test must remain active.

## Action Items

| Action Item | Type | Owner | Bug |
|---|---|---|---|
| Add a payment flag rollback step and verify checkout recovery before closing the incident | mitigate | On-call role | LAB4-01 |
| Require a staged rollout and payment-error guardrail before enabling payment fault controls outside rehearsals | prevent | Payment service owner | LAB4-02 |
| Enforce explicit incident dates in investigation prompts and reject queries outside the recorded window | process | Observability role | LAB4-03 |
| Record flag-change timestamps and ticket resolution together in future rehearsals | process | Incident commander role | LAB4-04 |

## Lessons Learned

### What went well

The preserved snapshot, P1 ticket and official clock calculation make the result reproducible. Payment and checkout failures can be checked against a quiet baseline instead of relying on the model's wording.

### What went wrong

The recorded investigator repeatedly queried 2024 instead of 2026, inferred missing checkout errors from empty results, and then repeated a payment hypothesis. It missed the large frontend traffic change and did not provide a complete three-class diagnosis.

### Where we got lucky

The course preserved the whole incident and a recovery interval. A retrospective query could therefore refute the model's empty-result inference without reproducing the fault or relying on memory.

## Timeline

| UTC | Recorded event or retrospective observation |
|---|---|
| 06:31:23 | Healthy reference instant, five minutes before onset; payment and checkout server error queries return no series |
| 06:36:23 | Fault onset, according to the official incident recomputation |
| 06:39:19 | ShopCheckoutErrors begins firing |
| 06:39:44 | The recorded P1 ticket is created |
| 06:40:09 | The recorded ticket is acknowledged |
| 06:42:00 | Retrospective evidence instant: H1 payment charge errors hold; H2's no-checkout-errors inference is refuted; H3's dependency errors hold using the real span name |
| 06:44:19 | End of the detecting alert's first firing run; the defined recovery instant |
| 06:48:00 | Recorded rates show zero payment/checkout errors and frontend traffic near baseline |

The AI ledger was evaluated after the incident. None of its claims is presented as a mitigation decision made by the recorded operator. H1-H3 carry their exact PromQL in ai-rca-eval.json.

## Supporting information

The unchanged evidence files are incident/tsdb-snapshot.tar.gz and incident/ticket.json, downloaded from lab4-rec-4 assigned to GitHub login jezue. Run ./itsmlab.sh incident 4 for the four timestamps. incident/query-evidence.py reproduces the baseline, incident and recovery comparisons against a local Prometheus serving a copy of the archive with explicit UTC query times.

The course-provided qwen3:4b-instruct transcript is retained verbatim at ai-rca/transcript.md. Its statements are scored in ai-rca-eval.json, including the false conclusion caused by a query at the wrong date. Routing and runtime inhibition are exercised by the official verify 4 checker using alertmanager/routing-tests.yml.

AI-use reflection: the supplied investigator found real payment symptoms, but lost the incident date and treated an empty response as evidence of health. Its final answer was repetitive and did not explain the traffic surge. The independent baseline comparison was more useful than the confidence of its wording. The resource-class fault remains uncertain from the evidence inspected here. Codex assisted this analysis and document drafting; it was not the recorded on-call operator.

## Problem record

- Incident record: Recorded P1 ticket 50ceffde-fa49-40b3-b4ca-957734d74bf7; alert recovery is not ticket closure.
- Root cause: Payment failure and homepage load controls are supported by the symptom changes; the third resource fault remains uncertain.
- Known error: Payment charge failures propagate to checkout, while a separate homepage flood increases frontend traffic.
- Workaround: Roll back the offending experimental controls, verify checkout error recovery and document the operator's exact change sequence.
