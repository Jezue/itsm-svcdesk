# ai-generated: 95% - OpenAI Codex created a pytest launcher with the required ITSMLAB summary protocol.
from __future__ import annotations

import pytest


class ResultCounter:
    def __init__(self) -> None:
        self.passed = 0

    def pytest_runtest_logreport(self, report: pytest.TestReport) -> None:
        if report.when == "call" and report.passed:
            self.passed += 1


counter = ResultCounter()
exit_code = pytest.main(["-q", "/app/src/tests/test_api.py"], plugins=[counter])
failed = 0 if exit_code == pytest.ExitCode.OK else 1
print(f"ITSMLAB-TESTS: passed={counter.passed} failed={failed}")
raise SystemExit(int(exit_code))
