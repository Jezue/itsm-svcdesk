# ai-generated: 100% - OpenAI Codex wrote behavioural tests from the supplied module's public docstrings.
from datetime import datetime, timedelta
import itertools

import pytest
import slaclock as sla


@pytest.mark.parametrize("impact,urgency", itertools.product(range(1, 4), repeat=2))
def test_priority_matrix(impact, urgency):
    expected = {(1, 1): "P1", (1, 2): "P2", (1, 3): "P3",
                (2, 1): "P2", (2, 2): "P3", (2, 3): "P4",
                (3, 1): "P3", (3, 2): "P4", (3, 3): "P4"}[impact, urgency]
    assert sla.priority_of(impact, urgency) == expected
    assert sla.priority_of(impact, urgency, True) == ("P1" if expected == "P1" else "P2")


@pytest.mark.parametrize("invalid", [-1, 0, 4, 10, 2.0, True, False, "1", None])
def test_priority_invalid(invalid):
    for args in ((invalid, 1), (1, invalid)):
        with pytest.raises(ValueError):
            sla.priority_of(*args)


@pytest.mark.parametrize("priority,expected", [("P1", (15, 240)), ("P2", (60, 480)),
                                               ("P3", (240, 1440)), ("P4", (480, 4320))])
def test_targets(priority, expected):
    assert sla.targets(priority) == expected


@pytest.mark.parametrize("priority", ["p1", " P1", "P1 ", "P0", "P5", "", "P10"])
def test_unknown_priority(priority):
    with pytest.raises(ValueError):
        sla.targets(priority)
    with pytest.raises(ValueError):
        sla.escalation_tier(priority, False, 0)


@pytest.mark.parametrize("target", [1, 4, 15, 60, 240, 480, 1440, 4320])
def test_sla_thresholds(target):
    for elapsed in {0, target // 2, max(0, (3 * target + 3) // 4 - 1),
                    (3 * target + 3) // 4, target, target + 1}:
        expected = "breached" if elapsed > target else ("warning" if 4 * elapsed >= 3 * target else "ok")
        assert sla.sla_state(elapsed, target) == expected


@pytest.mark.parametrize("elapsed,target", [(-1, 60), (0, 0), (1, -1)])
def test_invalid_sla(elapsed, target):
    with pytest.raises(ValueError):
        sla.sla_state(elapsed, target)


@pytest.mark.parametrize("weekday", range(7))
@pytest.mark.parametrize("hour,minute", [(0, 0), (7, 59), (8, 0), (8, 1), (15, 59), (16, 0), (23, 59)])
def test_business_window(weekday, hour, minute):
    moment = datetime(2026, 11, 16, hour, minute, 59, 999) + timedelta(days=weekday)
    expected = weekday < 5 and (hour, minute) >= (8, 0) and (hour, minute) < (16, 0)
    assert sla.is_business_time(moment) == expected


@pytest.mark.parametrize("start,minutes,due", [
    ("2026-11-16T08:00", 0, "2026-11-16T08:00"),
    ("2026-11-16T07:59", 0, "2026-11-16T08:00"),
    ("2026-11-16T16:00", 0, "2026-11-17T08:00"),
    ("2026-11-20T16:01", 0, "2026-11-23T08:00"),
    ("2026-11-21T10:00", 1, "2026-11-23T08:01"),
    ("2026-11-22T10:00", 480, "2026-11-23T16:00"),
    ("2026-11-16T08:00", 480, "2026-11-16T16:00"),
    ("2026-11-16T08:00", 481, "2026-11-17T08:01"),
    ("2026-11-20T15:59", 1, "2026-11-20T16:00"),
    ("2026-11-20T15:59", 2, "2026-11-23T08:01"),
    ("2026-11-16T15:30:59.123456", 30, "2026-11-16T16:00"),
    ("2026-11-16T08:00", 2400, "2026-11-20T16:00"),
    ("2026-11-16T08:00", 2401, "2026-11-23T08:01"),
])
def test_due_dates(start, minutes, due):
    begin, expected = datetime.fromisoformat(start), datetime.fromisoformat(due)
    assert sla.add_business_minutes(begin, minutes) == expected
    assert sla.business_minutes_between(begin, expected) == minutes


@pytest.mark.parametrize("start,end,expected", [
    ("2026-11-16T08:00", "2026-11-16T08:00", 0),
    ("2026-11-16T08:00:59", "2026-11-16T08:01:01", 1),
    ("2026-11-16T07:00", "2026-11-16T08:00", 0),
    ("2026-11-16T07:00", "2026-11-16T08:01", 1),
    ("2026-11-16T15:59", "2026-11-16T19:00", 1),
    ("2026-11-20T15:30", "2026-11-23T08:30", 60),
    ("2026-11-21T00:00", "2026-11-23T08:00", 0),
    ("2026-11-16T00:00", "2026-11-23T00:00", 2400),
    ("2026-11-16T17:00", "2026-11-17T07:00", 0),
])
def test_elapsed_business_minutes(start, end, expected):
    assert sla.business_minutes_between(datetime.fromisoformat(start), datetime.fromisoformat(end)) == expected


def test_calendar_limit_and_invalid_intervals():
    start = datetime(2026, 11, 16, 8)
    end = start + timedelta(days=366)
    expected = sum(480 for day in range(366) if (start + timedelta(days=day)).weekday() < 5)
    assert sla.business_minutes_between(start, end) == expected
    assert sla.add_business_minutes(start, expected + 1) == end + timedelta(minutes=1)
    with pytest.raises(ValueError):
        sla.business_minutes_between(start, end + timedelta(days=1))
    with pytest.raises(ValueError):
        sla.business_minutes_between(start, start - timedelta(minutes=1))
    with pytest.raises(ValueError):
        sla.add_business_minutes(start, -1)
    with pytest.raises(ValueError):
        sla.add_business_minutes(start, expected + 481)


@pytest.mark.parametrize("priority,breached,reopens", itertools.product(["P1", "P2", "P3", "P4"], [False, True], [0, 1, 2, 3, 100]))
def test_escalation(priority, breached, reopens):
    base = {"P1": 1, "P2": 1, "P3": 0, "P4": 0}[priority]
    extra = {"P1": 2, "P2": 1, "P3": 1, "P4": 1}[priority] if breached else 0
    assert sla.escalation_tier(priority, breached, reopens) == min(3, base + extra + int(reopens >= 2))


def test_negative_reopens():
    with pytest.raises(ValueError):
        sla.escalation_tier("P1", True, -1)


@pytest.mark.parametrize("text,expected", [("90m", 90), ("4h", 240), ("1h30m", 90), ("2d", 2880),
                                          ("1d4h", 1680), ("1d0h5m", 1445), ("1h59m", 119),
                                          ("60m", 60), ("0h60m", 60), ("0d0h90m", 90),
                                          (" 1h30m\n", 90), ("24h", 1440), ("001m", 1), ("1d0m", 1440)])
def test_durations(text, expected):
    assert sla.parse_duration(text) == expected


@pytest.mark.parametrize("text", ["", " ", "0m", "0d0h0m", "1.5h", "30m1h", "-5m", "1 h", "1H",
                                 "1h60m", "1d60m", "1m1m", "1d1d", "1", "h", "1h 1m", "1m junk"])
def test_invalid_durations(text):
    with pytest.raises(ValueError):
        sla.parse_duration(text)
