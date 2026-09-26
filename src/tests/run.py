# ai-generated: 95% - OpenAI Codex drafted black-box checks from the published API contract.
from __future__ import annotations

import json
import os
import time
import urllib.error
import urllib.parse
import urllib.request
from typing import Any


BASE_URL = os.getenv("SVCDESK_URL", "http://svcdesk:8080").rstrip("/")
CLOCK = "2026-10-14T10:00:00Z"
passed = 0
failed = 0


def request(method: str, path: str, body: dict[str, Any] | None = None, clock: str | None = CLOCK) -> tuple[int, Any]:
    data = json.dumps(body).encode() if body is not None else None
    headers = {"Content-Type": "application/json"}
    if clock is not None:
        headers["X-Test-Clock"] = clock
    req = urllib.request.Request(BASE_URL + path, data=data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req, timeout=5) as response:
            return response.status, json.loads(response.read())
    except urllib.error.HTTPError as exc:
        return exc.code, json.loads(exc.read())


def check(name: str, condition: bool) -> None:
    global passed, failed
    if condition:
        passed += 1
        print(f"PASS {name}")
    else:
        failed += 1
        print(f"FAIL {name}")


for _ in range(40):
    try:
        status, health = request("GET", "/health", clock=None)
        if status == 200:
            break
    except OSError:
        pass
    time.sleep(0.25)
else:
    print("service did not become healthy")
    print("ITSMLAB-TESTS: passed=0 failed=1")
    raise SystemExit(1)

check("health payload", health == {"status": "ok", "service": "svcdesk"})
status, unknown = request("GET", "/definitely-unknown", clock=None)
check("unknown path", status == 404 and isinstance(unknown, dict))

payload = {
    "title": "Own test ticket",
    "reporter": {"name": "Contract runner"},
    "impact": 1,
    "urgency": 1,
    "priority": "P4",
    "unknown": "ignored",
}
status, ticket = request("POST", "/tickets", payload)
ticket_id = ticket.get("id", "")
check("create status", status == 201 and bool(ticket_id))
check("create defaults", ticket.get("description") == "" and ticket.get("related_to") is None)
check("matrix and server ownership", ticket.get("priority") == "P1" and ticket.get("state") == "new")
check("test clock", ticket.get("created_at") == CLOCK)
check("P1 wall clock SLA", ticket.get("sla") == {
    "ack_due_at": "2026-10-14T10:15:00Z", "resolve_due_at": "2026-10-14T14:00:00Z"
})

status, fetched = request("GET", f"/tickets/{ticket_id}", clock=None)
check("get ticket", status == 200 and fetched.get("id") == ticket_id)
query = urllib.parse.urlencode({"state": "new", "priority": "P1"})
status, listed = request("GET", f"/tickets?{query}", clock=None)
check("list filters", status == 200 and any(item.get("id") == ticket_id for item in listed))

status, acknowledged = request("POST", f"/tickets/{ticket_id}/ack", clock="2026-10-14T10:05:00Z")
check("ack transition", status == 200 and acknowledged.get("state") == "acknowledged")
status, duplicate_ack = request("POST", f"/tickets/{ticket_id}/ack", clock="2026-10-14T10:06:00Z")
check("duplicate ack conflict", status == 409 and "error" in duplicate_ack)
status, started = request("POST", f"/tickets/{ticket_id}/start", clock="2026-10-14T10:10:00Z")
check("start transition", status == 200 and started.get("state") == "in_progress")
status, resolved = request("POST", f"/tickets/{ticket_id}/resolve", clock="2026-10-14T11:00:00Z")
check("resolve transition", status == 200 and resolved.get("resolved_at") == "2026-10-14T11:00:00Z")
status, reopened = request("POST", f"/tickets/{ticket_id}/reopen", clock="2026-10-20T11:00:00Z")
check("reopen within seven days", status == 200 and reopened.get("resolved_at") is None)

status, invalid = request("POST", "/tickets", {"reporter": {"name": "Runner"}, "impact": 5, "urgency": 1})
check("validation error shape", status in {400, 422} and "error" in invalid)
status, bad_clock = request("POST", "/tickets", payload, clock="yesterday")
check("malformed clock", status in {400, 422} and "error" in bad_clock)
status, missing = request("GET", "/tickets/missing-own-test", clock=None)
check("missing ticket", status == 404 and "error" in missing)

print(f"ITSMLAB-TESTS: passed={passed} failed={failed}")
raise SystemExit(0 if failed == 0 and passed >= 10 else 1)
