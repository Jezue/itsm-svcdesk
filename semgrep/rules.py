# ai-generated: 100% - OpenAI Codex added positive and negative fixtures for the two service review guards.
import os
import sqlite3


def test_switches():
    # ruleid: svcdesk-test-clock-switch
    enabled = os.getenv("SVCDESK_TEST_CLOCK", "").lower() == "true"
    # ok: svcdesk-test-clock-switch
    path = os.getenv("SVCDESK_DB", "/data/svcdesk.db")
    return enabled, path


def connect_database(path):
    # ruleid: svcdesk-sqlite-connection
    connection = sqlite3.connect(path, timeout=30)
    # ok: svcdesk-sqlite-connection
    row = connection.execute("SELECT 1").fetchone()
    return row
