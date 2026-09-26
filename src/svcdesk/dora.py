# ai-generated: 95% - OpenAI Codex implemented the published METRIC-SPEC rules; results are fixture-verified.
from __future__ import annotations

import re
from datetime import datetime, timezone
from decimal import Decimal, ROUND_HALF_UP
from typing import Any


UTC = timezone.utc
SPEC_VERSION = "1.0.0"
RFC3339 = re.compile(
    r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d+)?(?:Z|[+-]\d{2}:\d{2})$"
)


class DoraValidationError(ValueError):
    """The request is syntactically valid JSON but violates METRIC-SPEC."""


def _reject(message: str) -> None:
    raise DoraValidationError(message)


def _instant(value: Any, field: str) -> datetime:
    if not isinstance(value, str) or not RFC3339.fullmatch(value):
        _reject(f"{field} must be an RFC 3339 instant with an offset")
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        _reject(f"{field} must be an RFC 3339 instant with an offset")
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        _reject(f"{field} must include an offset")
    return parsed.astimezone(UTC)


def _identifier(value: Any, field: str, *, max_length: int | None = None) -> str:
    if not isinstance(value, str) or not value or (max_length is not None and len(value) > max_length):
        suffix = f" of at most {max_length} characters" if max_length is not None else ""
        _reject(f"{field} must be a non-empty string{suffix}")
    return value


def _nullable_identifier(value: Any, field: str) -> str | None:
    if value is None:
        return None
    return _identifier(value, field)


def _string_list(value: Any, field: str) -> list[str]:
    if not isinstance(value, list):
        _reject(f"{field} must be an array")
    return [_identifier(item, f"{field}[{index}]") for index, item in enumerate(value)]


def _duration_seconds(later: datetime, earlier: datetime) -> Decimal:
    delta = later - earlier
    return Decimal(delta.days * 86400 + delta.seconds) + Decimal(delta.microseconds) / Decimal(1_000_000)


def _median(values: list[Decimal]) -> Decimal | None:
    if not values:
        return None
    ordered = sorted(values)
    middle = len(ordered) // 2
    if len(ordered) % 2:
        return ordered[middle]
    return (ordered[middle - 1] + ordered[middle]) / Decimal(2)


def _whole_seconds(value: Decimal | None) -> int | None:
    if value is None:
        return None
    return int(value.quantize(Decimal("1"), rounding=ROUND_HALF_UP))


def _six_places(numerator: int, denominator: Decimal | int) -> float:
    value = Decimal(numerator) / Decimal(denominator)
    return float(value.quantize(Decimal("0.000001"), rounding=ROUND_HALF_UP))


def _normalise_events(raw_events: Any) -> list[dict[str, Any]]:
    if not isinstance(raw_events, list):
        _reject("events must be an array")

    unique: list[dict[str, Any]] = []
    seen_event_ids: set[str] = set()
    for index, raw in enumerate(raw_events):
        if not isinstance(raw, dict):
            _reject(f"events[{index}] must be an object")
        event_id = _identifier(raw.get("event_id"), f"events[{index}].event_id", max_length=64)
        if event_id in seen_event_ids:
            continue
        seen_event_ids.add(event_id)

        event_type = raw.get("type")
        if event_type not in {"commit", "deployment", "incident"}:
            _reject(f"events[{index}].type is invalid")
        event = dict(raw)
        event["event_id"] = event_id
        event["type"] = event_type
        event["_at"] = _instant(raw.get("at"), f"events[{index}].at")

        if event_type == "commit":
            event["sha"] = _identifier(raw.get("sha"), f"events[{index}].sha")
            if not isinstance(raw.get("branch"), str):
                _reject(f"events[{index}].branch must be a string")
            event["branch"] = raw["branch"]
            event["change_id"] = _nullable_identifier(raw.get("change_id"), f"events[{index}].change_id")
            event["reverts"] = _nullable_identifier(raw.get("reverts"), f"events[{index}].reverts")
            if (event["reverts"] is None) != (event["change_id"] is not None):
                _reject(f"events[{index}] must carry change_id exactly when reverts is null")
        elif event_type == "deployment":
            event["deployment_id"] = _identifier(raw.get("deployment_id"), f"events[{index}].deployment_id")
            if not isinstance(raw.get("environment"), str):
                _reject(f"events[{index}].environment must be a string")
            event["environment"] = raw["environment"]
            if raw.get("outcome") not in {"success", "failure"}:
                _reject(f"events[{index}].outcome is invalid")
            event["outcome"] = raw["outcome"]
            event["commits"] = _string_list(raw.get("commits"), f"events[{index}].commits")
            if type(raw.get("unplanned")) is not bool:
                _reject(f"events[{index}].unplanned must be boolean")
            event["unplanned"] = raw["unplanned"]
            event["caused_by"] = _nullable_identifier(raw.get("caused_by"), f"events[{index}].caused_by")
        else:
            event["incident_id"] = _identifier(raw.get("incident_id"), f"events[{index}].incident_id")
            if raw.get("phase") not in {"opened", "resolved"}:
                _reject(f"events[{index}].phase is invalid")
            event["phase"] = raw["phase"]
            event["deployments"] = _string_list(raw.get("deployments"), f"events[{index}].deployments")
        unique.append(event)

    return unique


def _index_and_validate(events: list[dict[str, Any]]) -> tuple[
    dict[str, dict[str, Any]], dict[str, dict[str, Any]], dict[str, dict[str, Any]]
]:
    commits: dict[str, dict[str, Any]] = {}
    deployments: dict[str, dict[str, Any]] = {}
    incidents: dict[str, dict[str, Any]] = {}

    for event in events:
        if event["type"] == "commit":
            if event["sha"] in commits:
                _reject(f"duplicate commit sha: {event['sha']}")
            commits[event["sha"]] = event
        elif event["type"] == "deployment":
            if event["deployment_id"] in deployments:
                _reject(f"duplicate deployment_id: {event['deployment_id']}")
            deployments[event["deployment_id"]] = event
        else:
            incident = incidents.setdefault(
                event["incident_id"], {"incident_id": event["incident_id"], "opened": None, "resolved": None, "deployments": set()}
            )
            if incident[event["phase"]] is not None:
                _reject(f"incident {event['incident_id']} has duplicate {event['phase']} events")
            incident[event["phase"]] = event["_at"]
            incident["deployments"].update(event["deployments"])

    for commit in commits.values():
        if commit["reverts"] is not None and commit["reverts"] not in commits:
            _reject(f"reverts references unknown sha: {commit['reverts']}")
    for deployment in deployments.values():
        for sha in deployment["commits"]:
            if sha not in commits:
                _reject(f"deployment references unknown sha: {sha}")
        if deployment["caused_by"] is not None and deployment["caused_by"] not in incidents:
            _reject(f"caused_by references unknown incident: {deployment['caused_by']}")
    for incident in incidents.values():
        if incident["resolved"] is not None and incident["opened"] is None:
            _reject(f"resolved incident {incident['incident_id']} has no opened event")
        for deployment_id in incident["deployments"]:
            if deployment_id not in deployments:
                _reject(f"incident references unknown deployment: {deployment_id}")
            deployment = deployments[deployment_id]
            if deployment["environment"] != "production" or deployment["outcome"] != "failure":
                _reject(f"incident references a deployment that is not a failed production deployment: {deployment_id}")

    return commits, deployments, incidents


def _resolve_changes(commits: dict[str, dict[str, Any]]) -> tuple[dict[str, str], dict[str, datetime]]:
    resolved: dict[str, str] = {}
    visiting: set[str] = set()

    def resolve(sha: str) -> str:
        if sha in resolved:
            return resolved[sha]
        if sha in visiting:
            _reject("revert references form a cycle")
        visiting.add(sha)
        commit = commits[sha]
        change_id = commit["change_id"] if commit["reverts"] is None else resolve(commit["reverts"])
        visiting.remove(sha)
        resolved[sha] = change_id
        return change_id

    first_commit: dict[str, datetime] = {}
    for sha, commit in commits.items():
        change_id = resolve(sha)
        previous = first_commit.get(change_id)
        if previous is None or commit["_at"] < previous:
            first_commit[change_id] = commit["_at"]
    return resolved, first_commit


def compute_metrics(payload: Any) -> dict[str, Any]:
    if not isinstance(payload, dict):
        _reject("request body must be an object")
    window = payload.get("window")
    if not isinstance(window, dict):
        _reject("window must be an object")
    if "from" not in window or "to" not in window:
        _reject("window.from and window.to are required")
    window_from = _instant(window["from"], "window.from")
    window_to = _instant(window["to"], "window.to")
    if window_to <= window_from:
        _reject("window.to must be after window.from")
    if "events" not in payload:
        _reject("events is required")

    events = _normalise_events(payload["events"])
    commits, deployments, incidents = _index_and_validate(events)
    change_for_sha, first_commit_for_change = _resolve_changes(commits)

    scoped = [
        deployment for deployment in deployments.values()
        if deployment["environment"] == "production" and window_from <= deployment["_at"] < window_to
    ]
    scoped.sort(key=lambda item: (item["_at"], item["deployment_id"]))
    scoped_ids = {deployment["deployment_id"] for deployment in scoped}

    successful = [deployment for deployment in scoped if deployment["outcome"] == "success"]
    failed = [deployment for deployment in scoped if deployment["outcome"] == "failure"]
    rework = [deployment for deployment in scoped if deployment["unplanned"] and deployment["caused_by"] is not None]

    first_success_for_sha: dict[str, datetime] = {}
    for deployment in successful:
        for sha in set(deployment["commits"]):
            if sha not in first_success_for_sha:
                first_success_for_sha[sha] = deployment["_at"]
    lead_times: list[Decimal] = []
    negative_lead_times = 0
    for sha, deployed_at in first_success_for_sha.items():
        lead_time = _duration_seconds(deployed_at, commits[sha]["_at"])
        if lead_time < 0:
            negative_lead_times += 1
            lead_time = Decimal(0)
        lead_times.append(lead_time)

    off_main = {
        sha for deployment in scoped for sha in set(deployment["commits"])
        if commits[sha]["branch"] != "main"
    }
    empty_deployments = sum(not deployment["commits"] for deployment in scoped)

    recovery_times: list[Decimal] = []
    open_failures = 0
    for deployment in failed:
        covering = [incident for incident in incidents.values() if deployment["deployment_id"] in incident["deployments"]]
        covering.sort(key=lambda incident: (incident["opened"], incident["incident_id"]))
        incident = covering[0] if covering else None
        if incident is None or incident["resolved"] is None:
            open_failures += 1
            continue
        recovery = _duration_seconds(incident["resolved"], deployment["_at"])
        recovery_times.append(max(Decimal(0), recovery))

    caused_by_ids = {deployment["caused_by"] for deployment in scoped if deployment["caused_by"] is not None}
    relevant_incidents = [
        incident for incident in incidents.values()
        if incident["incident_id"] in caused_by_ids or bool(incident["deployments"] & scoped_ids)
    ]
    overlapping_pairs = 0
    for index, left in enumerate(relevant_incidents):
        left_end = left["resolved"] if left["resolved"] is not None else window_to
        for right in relevant_incidents[index + 1:]:
            right_end = right["resolved"] if right["resolved"] is not None else window_to
            if left["opened"] < right_end and right["opened"] < left_end:
                overlapping_pairs += 1

    first_success_for_change: dict[str, datetime] = {}
    for deployment in successful:
        for sha in set(deployment["commits"]):
            change_id = change_for_sha[sha]
            if change_id not in first_success_for_change:
                first_success_for_change[change_id] = deployment["_at"]
    true_lead_times = [
        max(Decimal(0), _duration_seconds(deployed_at, first_commit_for_change[change_id]))
        for change_id, deployed_at in first_success_for_change.items()
    ]

    deployment_count = len(scoped)
    window_days = _duration_seconds(window_to, window_from) / Decimal(86400)
    return {
        "spec_version": SPEC_VERSION,
        "window": {"from": window["from"], "to": window["to"]},
        "deployment_frequency_per_day": _six_places(deployment_count, window_days),
        "change_lead_time_seconds_p50": _whole_seconds(_median(lead_times)),
        "failed_deployment_recovery_time_seconds_p50": _whole_seconds(_median(recovery_times)),
        "change_fail_rate": _six_places(len(failed), deployment_count) if deployment_count else None,
        "deployment_rework_rate": _six_places(len(rework), deployment_count) if deployment_count else None,
        "counts": {
            "deployments": deployment_count,
            "successful_deployments": len(successful),
            "failed_deployments": len(failed),
            "recovered_failures": len(recovery_times),
            "open_failures": open_failures,
            "rework_deployments": len(rework),
            "lead_time_pairs": len(lead_times),
            "changes": len(first_commit_for_change),
        },
        "anomalies": {
            "negative_lead_time_pairs": negative_lead_times,
            "deployments_without_commits": empty_deployments,
            "commits_never_on_main": len(off_main),
            "revert_chains_collapsed": sum(commit["reverts"] is not None for commit in commits.values()),
            "overlapping_incident_pairs": overlapping_pairs,
        },
        "ground_truth": {
            "changes_delivered": len(first_success_for_change),
            "true_change_lead_time_seconds_p50": _whole_seconds(_median(true_lead_times)),
        },
    }
