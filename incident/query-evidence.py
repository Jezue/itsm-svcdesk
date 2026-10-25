# ai-generated: 100% - OpenAI Codex collected reproducible read-only queries against the course recording.
import json
import urllib.parse
import urllib.request
from pathlib import Path

QUERIES = {
    "server_errors": 'sum by(service_name)(rate(traces_span_metrics_calls_total{span_kind="SPAN_KIND_SERVER",status_code="STATUS_CODE_ERROR"}[5m]))',
    "server_calls": 'sum by(service_name)(rate(traces_span_metrics_calls_total{span_kind="SPAN_KIND_SERVER"}[5m]))',
    "p95_ms": 'histogram_quantile(0.95, sum by(service_name,le)(rate(traces_span_metrics_duration_milliseconds_bucket{span_kind="SPAN_KIND_SERVER"}[5m])))',
    "container_memory": 'container_memory_usage_total_bytes',
    "container_uptime": 'container_uptime_seconds',
    "charge_errors": 'sum(rate(traces_span_metrics_calls_total{service_name="payment",span_name="charge",status_code="STATUS_CODE_ERROR"}[5m]))',
    "checkout_error_fraction": 'sum(rate(traces_span_metrics_calls_total{service_name="checkout",span_kind="SPAN_KIND_SERVER",status_code="STATUS_CODE_ERROR"}[5m])) / sum(rate(traces_span_metrics_calls_total{service_name="checkout",span_kind="SPAN_KIND_SERVER"}[5m]))',
}
TIMES = ["2026-10-12T06:31:23Z", "2026-10-12T06:40:00Z", "2026-10-12T06:42:00Z", "2026-10-12T06:48:00Z"]

def query(expr, time):
    url = "http://127.0.0.1:19090/api/v1/query?" + urllib.parse.urlencode({"query": expr, "time": time})
    with urllib.request.urlopen(url, timeout=30) as response:
        body = json.load(response)
    assert body["status"] == "success", body
    return body["data"]["result"]

if __name__ == "__main__":
    evidence = {name: {"query": expr, "results": {time: query(expr, time) for time in TIMES}} for name, expr in QUERIES.items()}
    Path(__file__).with_name("query-evidence.json").write_text(json.dumps(evidence, indent=2) + "\n")
    for name, record in evidence.items():
        print(name)
        for time, result in record["results"].items():
            print(time, [(r["metric"].get("service_name") or r["metric"].get("container_name") or r["metric"], r["value"][1]) for r in result])
