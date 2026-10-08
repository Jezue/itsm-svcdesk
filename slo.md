---
lab3_slo:
  service: svcdesk
  route: /kb/search
  window: 28d
  slis:
    availability:
      objective: 0.99
      good: 'sum(rate(http_server_request_duration_seconds_count{http_route="/kb/search",http_response_status_code=~"2.."}[5m]))'
      valid: 'sum(rate(http_server_request_duration_seconds_count{http_route="/kb/search"}[5m]))'
      error_budget:
        fraction: 0.01
        minutes: 403.2
    latency:
      objective: 0.95
      threshold_seconds: 0.1849
      good: 'sum(rate(http_server_request_duration_seconds_bucket{http_route="/kb/search",le="0.1849"}[5m]))'
      valid: 'sum(rate(http_server_request_duration_seconds_count{http_route="/kb/search"}[5m]))'
      error_budget:
        fraction: 0.05
        minutes: 2016
  alerts:
    - alert: SvcdeskAvailabilityFastBurn
      sli: availability
      burn_rate: 14.4
      long_window: 1h
      short_window: 5m
    - alert: SvcdeskAvailabilitySlowBurn
      sli: availability
      burn_rate: 6
      long_window: 6h
      short_window: 30m
---
<!-- ai-generated: 95% - OpenAI Codex drafted this SLO and checked its arithmetic against the measured service. -->
# Svcdesk search SLO

The availability SLI treats a `/kb/search` request as good only when the service returns a 2xx response. Its denominator is every observed request to that route, including upstream failures. The 99% objective over 28 days leaves a 1% error budget: 403.2 minutes of equivalent complete unavailability.

The latency SLI treats a request as good when its server-side duration is at most 0.1849 seconds. That threshold is an exact histogram boundary and is just above the locally measured p99 of 0.1735 seconds. Its 95% objective leaves a 5% budget, or 2016 minutes in 28 days. Server-side latency deliberately excludes client and network time; the optional latency-gap artifact documents that distinction.

Both alert rules use a long and a short window. Requiring both windows prevents an old failure from paging after the immediate burn has stopped, while two burn rates distinguish a sharp outage from a slower but sustained budget loss. `SvcdeskAvailabilityFastBurn` is P1 because 14.4 times normal budget consumption needs rapid action. The lower 6x burn is P2 and uses a six-hour confirmation window.
