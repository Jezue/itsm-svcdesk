# ai-generated: 95% - OpenAI Codex drafted black-box Lab 2 checks and retained Lab 1 regression coverage.
from __future__ import annotations

import json
import os
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any

import pytest


BASE_URL = os.getenv("SVCDESK_URL", "http://svcdesk:8080").rstrip("/")
WINDOW = {"from": "2026-09-01T00:00:00Z", "to": "2026-09-22T00:00:00Z"}


def request(method: str, path: str, body: Any = None, clock: str | None = None) -> tuple[int, Any]:
    data = json.dumps(body).encode() if body is not None else None
    headers = {"Content-Type": "application/json"}
    if clock is not None:
        headers["X-Test-Clock"] = clock
    req = urllib.request.Request(BASE_URL + path, data=data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req, timeout=30) as response:
            return response.status, json.loads(response.read())
    except urllib.error.HTTPError as exc:
        return exc.code, json.loads(exc.read())


@pytest.fixture(scope="module")
def practice() -> tuple[list[dict[str, Any]], dict[str, Any]]:
    fixture_dir = Path("/app/fixtures")
    events = [json.loads(line) for line in (fixture_dir / "events-practice.jsonl").read_text().splitlines() if line]
    expected = json.loads((fixture_dir / "metrics-practice.json").read_text())
    return events, expected


def post_metrics(events: list[dict[str, Any]], window: dict[str, str] = WINDOW) -> tuple[int, Any]:
    return request("POST", "/dora/metrics", {"window": window, "events": events})


def test_health_and_lab1_identity() -> None:
    assert request("GET", "/health") == (200, {"status": "ok", "service": "svcdesk"})


def test_lab1_create_and_wallclock_sla() -> None:
    status, ticket = request("POST", "/tickets", {
        "title": "Regression ticket", "reporter": {"name": "pytest"}, "impact": 1, "urgency": 1
    }, "2026-10-16T15:00:00Z")
    assert status == 201
    assert ticket["priority"] == "P1"
    assert ticket["sla"] == {"ack_due_at": "2026-10-16T15:15:00Z", "resolve_due_at": "2026-10-16T19:00:00Z"}


def test_lab1_state_machine() -> None:
    status, ticket = request("POST", "/tickets", {
        "title": "Lifecycle", "reporter": {"name": "pytest"}, "impact": 2, "urgency": 2
    }, "2026-10-14T10:00:00Z")
    ticket_id = ticket["id"]
    assert status == 201
    assert request("POST", f"/tickets/{ticket_id}/ack", clock="2026-10-14T10:05:00Z")[1]["state"] == "acknowledged"
    assert request("POST", f"/tickets/{ticket_id}/start", clock="2026-10-14T10:06:00Z")[1]["state"] == "in_progress"
    assert request("POST", f"/tickets/{ticket_id}/resolve", clock="2026-10-14T10:20:00Z")[1]["state"] == "resolved"


def test_lab1_validation_error_shape() -> None:
    status, body = request("POST", "/tickets", {"impact": 8})
    assert status in {400, 422} and "error" in body


def test_practice_metrics_exact(practice: tuple[list[dict[str, Any]], dict[str, Any]]) -> None:
    events, expected = practice
    assert post_metrics(events) == (200, expected)


def test_metrics_are_pure(practice: tuple[list[dict[str, Any]], dict[str, Any]]) -> None:
    events, _ = practice
    assert post_metrics(events)[1] == post_metrics(events)[1]


def test_metrics_are_order_independent(practice: tuple[list[dict[str, Any]], dict[str, Any]]) -> None:
    events, expected = practice
    assert post_metrics(list(reversed(events))) == (200, expected)


def test_duplicate_event_ids_first_copy_wins(practice: tuple[list[dict[str, Any]], dict[str, Any]]) -> None:
    events, expected = practice
    assert post_metrics([event for event in events for _ in range(2)]) == (200, expected)


def test_empty_log() -> None:
    status, result = post_metrics([])
    assert status == 200
    assert result["deployment_frequency_per_day"] == 0.0
    assert result["change_lead_time_seconds_p50"] is None and result["change_fail_rate"] is None
    assert all(value == 0 for value in result["counts"].values())
    assert all(value == 0 for value in result["anomalies"].values())


def test_empty_window_rejected() -> None:
    status, result = post_metrics([], {"from": WINDOW["from"], "to": WINDOW["from"]})
    assert status in {400, 422} and "error" in result


def test_missing_events_rejected() -> None:
    status, result = request("POST", "/dora/metrics", {"window": WINDOW})
    assert status in {400, 422} and "error" in result


def test_unknown_revert_rejected() -> None:
    event = {"event_id": "bad", "type": "commit", "at": WINDOW["from"], "sha": "b", "branch": "main", "change_id": None, "reverts": "missing"}
    status, result = post_metrics([event])
    assert status in {400, 422} and "error" in result


def test_half_open_window() -> None:
    events = [
        {"event_id": "c", "type": "commit", "at": WINDOW["from"], "sha": "s", "branch": "main", "change_id": "C", "reverts": None},
        {"event_id": "d", "type": "deployment", "at": WINDOW["to"], "deployment_id": "D", "environment": "production", "outcome": "success", "commits": ["s"], "unplanned": False, "caused_by": None},
    ]
    status, result = post_metrics(events)
    assert status == 200 and result["counts"]["deployments"] == 0


def test_negative_lead_time_is_clamped_and_counted() -> None:
    events = [
        {"event_id": "c", "type": "commit", "at": "2026-09-02T00:00:01Z", "sha": "s", "branch": "hotfix", "change_id": "C", "reverts": None},
        {"event_id": "d", "type": "deployment", "at": "2026-09-02T00:00:00Z", "deployment_id": "D", "environment": "production", "outcome": "success", "commits": ["s"], "unplanned": False, "caused_by": None},
    ]
    status, result = post_metrics(events)
    assert status == 200 and result["change_lead_time_seconds_p50"] == 0
    assert result["anomalies"]["negative_lead_time_pairs"] == 1
    assert result["anomalies"]["commits_never_on_main"] == 1


def test_transitive_revert_is_one_change() -> None:
    events = [
        {"event_id": "c1", "type": "commit", "at": "2026-09-01T01:00:00Z", "sha": "s1", "branch": "main", "change_id": "C", "reverts": None},
        {"event_id": "c2", "type": "commit", "at": "2026-09-01T02:00:00Z", "sha": "s2", "branch": "main", "change_id": None, "reverts": "s1"},
        {"event_id": "c3", "type": "commit", "at": "2026-09-01T03:00:00Z", "sha": "s3", "branch": "main", "change_id": None, "reverts": "s2"},
    ]
    status, result = post_metrics(events)
    assert status == 200 and result["counts"]["changes"] == 1
    assert result["anomalies"]["revert_chains_collapsed"] == 2


def test_ticket_event_export_is_sorted_and_has_no_in_progress() -> None:
    status, stream = request("GET", "/dora/ticket-events")
    assert status == 200
    assert stream == sorted(stream, key=lambda event: (event["at"], event["ticket_id"]))
    assert all(event["phase"] != "in_progress" for event in stream)
    assert any(event["phase"] == "resolved" and event["state"] == "resolved" for event in stream)
