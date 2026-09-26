# ai-generated: 95% - OpenAI Codex drafted the service; behavior was verified against the published contract.
from __future__ import annotations

import os
import sqlite3
import uuid
from contextlib import contextmanager
from datetime import datetime, time, timedelta, timezone
from pathlib import Path
from typing import Any, Iterator
from zoneinfo import ZoneInfo

from fastapi import Depends, FastAPI, Header, HTTPException, Query
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from pydantic import BaseModel, ConfigDict, Field, StrictBool, StrictInt, StrictStr
from starlette.exceptions import HTTPException as StarletteHTTPException


UTC = timezone.utc
WARSAW = ZoneInfo("Europe/Warsaw")
DB_PATH = os.getenv("SVCDESK_DB", "/data/svcdesk.db")
TEST_CLOCK_ENABLED = os.getenv("SVCDESK_TEST_CLOCK", "").lower() in {"1", "true"}

PRIORITY_MATRIX = {
    (1, 1): "P1", (1, 2): "P2", (1, 3): "P3",
    (2, 1): "P2", (2, 2): "P3", (2, 3): "P4",
    (3, 1): "P3", (3, 2): "P4", (3, 3): "P4",
}
SLA_TARGETS = {
    "P1": (timedelta(minutes=15), timedelta(hours=4)),
    "P2": (timedelta(hours=1), timedelta(hours=8)),
    "P3": (timedelta(hours=4), timedelta(hours=24)),
    "P4": (timedelta(hours=8), timedelta(hours=72)),
}


class ReporterInput(BaseModel):
    model_config = ConfigDict(extra="ignore")
    name: StrictStr = Field(min_length=1, max_length=100)
    email: StrictStr | None = None
    vip: StrictBool = False


class TicketInput(BaseModel):
    model_config = ConfigDict(extra="ignore")
    title: StrictStr = Field(min_length=1, max_length=200)
    description: StrictStr = Field(default="", max_length=4000)
    reporter: ReporterInput
    impact: StrictInt = Field(ge=1, le=3)
    urgency: StrictInt = Field(ge=1, le=3)
    related_to: StrictStr | None = None


app = FastAPI(title="svcdesk", docs_url=None, redoc_url=None, openapi_url=None)


def error(status: int, code: str, message: str) -> HTTPException:
    return HTTPException(status_code=status, detail={"code": code, "message": message})


@app.exception_handler(RequestValidationError)
async def validation_error_handler(_request: Any, exc: RequestValidationError) -> JSONResponse:
    first = exc.errors()[0] if exc.errors() else {}
    location = ".".join(str(part) for part in first.get("loc", []) if part != "body")
    message = first.get("msg", "invalid request")
    if location:
        message = f"{location}: {message}"
    return JSONResponse(status_code=422, content={"error": {"code": "validation", "message": message}})


@app.exception_handler(StarletteHTTPException)
async def http_error_handler(_request: Any, exc: StarletteHTTPException) -> JSONResponse:
    detail = exc.detail
    payload = detail if isinstance(detail, dict) and "code" in detail else {
        "code": "http_error", "message": str(detail)
    }
    return JSONResponse(status_code=exc.status_code, content={"error": payload})


def initialise_database() -> None:
    Path(DB_PATH).parent.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(DB_PATH)
    try:
        connection.execute("PRAGMA journal_mode=WAL")
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS tickets (
                id TEXT PRIMARY KEY, title TEXT NOT NULL, description TEXT NOT NULL,
                reporter_name TEXT NOT NULL, reporter_email TEXT, reporter_vip INTEGER NOT NULL,
                impact INTEGER NOT NULL, urgency INTEGER NOT NULL, priority TEXT NOT NULL,
                state TEXT NOT NULL, created_at TEXT NOT NULL, acknowledged_at TEXT,
                resolved_at TEXT, closed_at TEXT, related_to TEXT,
                ack_due_at TEXT NOT NULL, resolve_due_at TEXT NOT NULL
            )
            """
        )
        connection.commit()
    finally:
        connection.close()


@contextmanager
def database(write: bool = False) -> Iterator[sqlite3.Connection]:
    connection = sqlite3.connect(DB_PATH, timeout=30)
    connection.row_factory = sqlite3.Row
    try:
        if write:
            connection.execute("BEGIN IMMEDIATE")
        yield connection
        if write:
            connection.commit()
    except Exception:
        if write:
            connection.rollback()
        raise
    finally:
        connection.close()


def parse_instant(raw: str) -> datetime:
    try:
        parsed = datetime.fromisoformat(raw.replace("Z", "+00:00"))
    except (TypeError, ValueError) as exc:
        raise error(422, "invalid_clock", "X-Test-Clock must be an RFC 3339 instant with an offset") from exc
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise error(422, "invalid_clock", "X-Test-Clock must include a timezone offset")
    return parsed.astimezone(UTC)


def request_now(x_test_clock: str | None = Header(default=None, alias="X-Test-Clock")) -> datetime:
    if TEST_CLOCK_ENABLED and x_test_clock is not None:
        return parse_instant(x_test_clock)
    return datetime.now(UTC)


def format_instant(value: datetime) -> str:
    return value.astimezone(UTC).isoformat().replace("+00:00", "Z")


def next_business_open(value: datetime) -> datetime:
    current = value
    if current.weekday() < 5 and current.time() < time(8):
        return current.replace(hour=8, minute=0, second=0, microsecond=0)
    current += timedelta(days=1)
    while current.weekday() >= 5:
        current += timedelta(days=1)
    return current.replace(hour=8, minute=0, second=0, microsecond=0)


def add_business_time(start: datetime, duration: timedelta) -> datetime:
    current = start.astimezone(WARSAW)
    if current.weekday() >= 5 or current.time() >= time(16):
        current = next_business_open(current)
    elif current.time() < time(8):
        current = current.replace(hour=8, minute=0, second=0, microsecond=0)
    remaining = duration
    while True:
        close = current.replace(hour=16, minute=0, second=0, microsecond=0)
        available = close - current
        if remaining <= available:
            return (current + remaining).astimezone(UTC)
        remaining -= available
        current = next_business_open(current)


def is_business_time(value: datetime) -> bool:
    local = value.astimezone(WARSAW)
    return local.weekday() < 5 and time(8) <= local.time() < time(16)


def due_instants(created_at: datetime, priority: str) -> tuple[datetime, datetime]:
    ack_target, resolve_target = SLA_TARGETS[priority]
    if priority == "P1":
        return created_at + ack_target, created_at + resolve_target
    return add_business_time(created_at, ack_target), add_business_time(created_at, resolve_target)


def row_to_ticket(row: sqlite3.Row) -> dict[str, Any]:
    return {
        "id": row["id"], "title": row["title"], "description": row["description"],
        "reporter": {"name": row["reporter_name"], "email": row["reporter_email"], "vip": bool(row["reporter_vip"])},
        "impact": row["impact"], "urgency": row["urgency"], "priority": row["priority"],
        "state": row["state"], "created_at": row["created_at"],
        "acknowledged_at": row["acknowledged_at"], "resolved_at": row["resolved_at"],
        "closed_at": row["closed_at"], "related_to": row["related_to"],
        "sla": {"ack_due_at": row["ack_due_at"], "resolve_due_at": row["resolve_due_at"]},
    }


def fetch_ticket(connection: sqlite3.Connection, ticket_id: str) -> sqlite3.Row:
    row = connection.execute("SELECT * FROM tickets WHERE id = ?", (ticket_id,)).fetchone()
    if row is None:
        raise error(404, "not_found", "ticket was not found")
    return row


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok", "service": "svcdesk"}


@app.post("/tickets", status_code=201)
def create_ticket(payload: TicketInput, now: datetime = Depends(request_now)) -> dict[str, Any]:
    ticket_id = str(uuid.uuid4())
    priority = PRIORITY_MATRIX[(payload.impact, payload.urgency)]
    ack_due, resolve_due = due_instants(now, priority)
    values = (
        ticket_id, payload.title, payload.description, payload.reporter.name, payload.reporter.email,
        int(payload.reporter.vip), payload.impact, payload.urgency, priority, "new", format_instant(now),
        payload.related_to, format_instant(ack_due), format_instant(resolve_due),
    )
    with database(write=True) as connection:
        connection.execute(
            """
            INSERT INTO tickets (
                id, title, description, reporter_name, reporter_email, reporter_vip,
                impact, urgency, priority, state, created_at, related_to, ack_due_at, resolve_due_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, values,
        )
        row = fetch_ticket(connection, ticket_id)
    return row_to_ticket(row)


@app.get("/tickets")
def list_tickets(state: str | None = Query(default=None), priority: str | None = Query(default=None)) -> list[dict[str, Any]]:
    clauses: list[str] = []
    parameters: list[str] = []
    if state is not None:
        clauses.append("state = ?")
        parameters.append(state)
    if priority is not None:
        clauses.append("priority = ?")
        parameters.append(priority)
    query = "SELECT * FROM tickets" + ((" WHERE " + " AND ".join(clauses)) if clauses else "")
    with database() as connection:
        rows = connection.execute(query, parameters).fetchall()
    return [row_to_ticket(row) for row in rows]


@app.get("/tickets/{ticket_id}")
def get_ticket(ticket_id: str) -> dict[str, Any]:
    with database() as connection:
        row = fetch_ticket(connection, ticket_id)
    return row_to_ticket(row)


def perform_transition(ticket_id: str, action: str, now: datetime) -> dict[str, Any]:
    expected_states = {"ack": "new", "start": "acknowledged", "resolve": "in_progress", "close": "resolved"}
    destination_states = {"ack": "acknowledged", "start": "in_progress", "resolve": "resolved", "close": "closed"}
    with database(write=True) as connection:
        row = fetch_ticket(connection, ticket_id)
        if action == "reopen":
            if row["state"] == "closed":
                raise error(409, "ticket_closed", "closed tickets are immutable")
            if row["state"] != "resolved":
                raise error(409, "invalid_transition", "only a resolved ticket can be reopened")
            resolved_at = parse_instant(row["resolved_at"])
            if now > resolved_at + timedelta(days=7):
                raise error(409, "reopen_window_expired", "the seven-day reopen window has expired")
            connection.execute("UPDATE tickets SET state = 'in_progress', resolved_at = NULL, closed_at = NULL WHERE id = ?", (ticket_id,))
        else:
            if row["state"] != expected_states[action]:
                raise error(409, "invalid_transition", f"cannot {action} a ticket in state {row['state']}")
            updates = ["state = ?"]
            parameters: list[Any] = [destination_states[action]]
            timestamp_column = {"ack": "acknowledged_at", "resolve": "resolved_at", "close": "closed_at"}.get(action)
            if timestamp_column is not None:
                updates.append(f"{timestamp_column} = ?")
                parameters.append(format_instant(now))
            parameters.append(ticket_id)
            connection.execute(f"UPDATE tickets SET {', '.join(updates)} WHERE id = ?", parameters)
        updated = fetch_ticket(connection, ticket_id)
    return row_to_ticket(updated)


@app.post("/tickets/{ticket_id}/ack")
def acknowledge_ticket(ticket_id: str, now: datetime = Depends(request_now)) -> dict[str, Any]:
    return perform_transition(ticket_id, "ack", now)


@app.post("/tickets/{ticket_id}/start")
def start_ticket(ticket_id: str, now: datetime = Depends(request_now)) -> dict[str, Any]:
    return perform_transition(ticket_id, "start", now)


@app.post("/tickets/{ticket_id}/resolve")
def resolve_ticket(ticket_id: str, now: datetime = Depends(request_now)) -> dict[str, Any]:
    return perform_transition(ticket_id, "resolve", now)


@app.post("/tickets/{ticket_id}/close")
def close_ticket(ticket_id: str, now: datetime = Depends(request_now)) -> dict[str, Any]:
    return perform_transition(ticket_id, "close", now)


@app.post("/tickets/{ticket_id}/reopen")
def reopen_ticket(ticket_id: str, now: datetime = Depends(request_now)) -> dict[str, Any]:
    return perform_transition(ticket_id, "reopen", now)


@app.get("/tickets/{ticket_id}/sla")
def get_sla(ticket_id: str, now: datetime = Depends(request_now)) -> dict[str, Any]:
    with database() as connection:
        row = fetch_ticket(connection, ticket_id)
    ack_due, resolve_due = parse_instant(row["ack_due_at"]), parse_instant(row["resolve_due_at"])
    acknowledged_at = parse_instant(row["acknowledged_at"]) if row["acknowledged_at"] else None
    resolved_at = parse_instant(row["resolved_at"]) if row["resolved_at"] else None
    return {
        "priority": row["priority"], "ack_due_at": row["ack_due_at"], "resolve_due_at": row["resolve_due_at"],
        "ack_breached": acknowledged_at > ack_due if acknowledged_at is not None else now > ack_due,
        "resolve_breached": resolved_at > resolve_due if resolved_at is not None else now > resolve_due,
        "paused": row["priority"] != "P1" and row["state"] not in {"resolved", "closed"} and not is_business_time(now),
    }


initialise_database()
