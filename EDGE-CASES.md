---
lab2_edge_cases:
  E1: {rule: R-08, count: 3}
  E2: {rule: R-06, count: 2}
  E3: {rule: R-09, count: 4}
  E4: {rule: R-10, count: 4}
  E5: {rule: R-12, count: 1}
  E6: {rule: R-13, count: 11}
---
<!-- ai-generated: 95% - OpenAI Codex drafted the analysis from METRIC-SPEC and verified service output. -->

# Edge cases in the practice event log

## E1 - clock skew produces a negative lead time

- What the log contains: Three commit-to-deployment pairs have commit clocks later than the successful deployment that carried them.
- What a default definition would have done: A naive calculation would discard these records or expose negative durations, making the dashboard undercount delivered work or display impossible speed.
- Why the rule is defensible: R-08 keeps all three observations and clamps them to zero, preserving the delivery denominator while preventing clock skew from inventing negative elapsed time.

## E2 - a revert of a revert

- What the log contains: Two revert commits form a transitive chain back to the same original change rather than defining independent work items.
- What a default definition would have done: Counting each commit as a new change would inflate throughput and make the dashboard suggest three delivered changes where the team handled one change lineage.
- Why the rule is defensible: R-06 follows the revert relationship transitively, so operationally related commits retain one stable change identity and cannot manufacture extra delivery.

## E3 - a hotfix that never touched `main`

- What the log contains: Four distinct deployed commit SHAs use hotfix branches and nevertheless reached an in-window production deployment.
- What a default definition would have done: Filtering for `branch == main` would erase genuine production work, lowering pair counts and presenting misleading lead-time and delivery coverage.
- Why the rule is defensible: R-09 treats deployment evidence as authoritative; branch naming is workflow metadata and cannot override the fact that a commit reached production.

## E4 - a deployment with zero linked commits

- What the log contains: Four in-window production deployments have empty commit arrays, including successful and failed operational events.
- What a default definition would have done: Dropping empty deployments would make frequency, failure rate, and rework denominators inconsistent, hiding releases and failures from dashboard readers.
- Why the rule is defensible: R-10 excludes only nonexistent lead-time pairs while retaining each real deployment in every metric that is defined at deployment level.

## E5 - a deployment that failed and never recovered

- What the log contains: One failed production deployment has no covering incident with a recorded resolution and therefore remains an open failure.
- What a default definition would have done: Inventing recovery at the window boundary would report a fictional duration, while dropping the failure would improve both recovery visibility and perceived reliability.
- Why the rule is defensible: R-12 excludes the unknown duration from the median but preserves the open-failure count and includes the deployment in change fail rate.

## E6 - overlapping incidents

- What the log contains: The relevant incident intervals form eleven unordered intersecting pairs, including simultaneous recovery work around separate failed deployments.
- What a default definition would have done: Merging or summing overlapping intervals would replace per-deployment recovery with outage accounting and could double-count elapsed wall time for dashboard readers.
- Why the rule is defensible: R-13 retains independent recovery evidence for every failed deployment and reports overlap explicitly instead of silently changing the metric's unit of analysis.

## Gaming demonstration

The transformed log improves `deployment_frequency_per_day` under R-11 from 2.0 to 2.52381, a relative increase of about 26.19%. It preserves every base event and adds eleven valid, empty, successful production deployments while removing commit links only from successful base deployments, an alteration R-19 explicitly permits. As a result, the service reports zero of the 65 existing changes as delivered, so R-21 identifies clear harm even though the headline frequency improves. A target tied narrowly to deployment count could incentivise a team to issue empty releases and omit traceability; the team or manager rewarded for frequency would benefit, while customers and decision-makers would receive less delivered work and a less truthful dashboard.
