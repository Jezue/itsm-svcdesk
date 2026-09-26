---
actual_minutes: 12
ratio: 0.13
---
<!-- ai-generated: 90% - OpenAI Codex recorded the measured run and drafted the retrospective from observed work. -->

# METR n=1 result

The prediction estimated 90 minutes for the complete DORA computation module in `src/svcdesk/dora.py`. The first correct practice-fixture comparison and successful pytest run occurred at 2026-09-26T10:41:16Z, 11.78 minutes after the receipted prediction time of 2026-09-26T10:29:30Z. I record `actual_minutes` as 12, rounded to the nearest whole minute. The required ratio is therefore **actual/predicted = 0.13** to two decimal places.

The work was substantially faster than predicted because the published metric specification removed ambiguity: each edge case had an explicit unit of analysis, reference rule, and expected practice value. The implementation could be checked immediately against the full fixture rather than debugged through partial dashboard output. Validation and transitive revert resolution took less time than expected, and the existing FastAPI error handler made endpoint integration small. Docker dependency installation and the combined Lab 1/Lab 2 pytest pass were also straightforward. The original estimate had reserved considerably more time for interpreting recovery overlap, rounding behaviour, and hidden-fixture-safe validation than the actual implementation required.
