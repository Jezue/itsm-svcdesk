# ai-generated: 100% - OpenAI Codex tested the published practice data and malformed SARIF boundary cases.
import copy
import json
from pathlib import Path
import unittest

from bakeoff import classes, confusion_matrix, location, tool_id


def finding(uri="set/app.py", start=7, **fields):
    return {"ruleId": "r", "properties": {"class": "injection"},
            "locations": [{"physicalLocation": {"artifactLocation": {"uri": uri},
                                                   "region": {"startLine": start}}}], **fields}


def run(results, name="Semgrep CE", **driver_fields):
    return {"tool": {"driver": {"name": name, **driver_fields}}, "results": results}


class BakeoffTests(unittest.TestCase):
    labels = {"set": "set", "defects": [
        {"id": "a", "file": "set/app.py", "class": "injection", "start_line": 7, "end_line": 8},
        {"id": "b", "file": "set/app.py", "class": "injection", "start_line": 8, "end_line": 9},
    ]}

    def matrix(self, *runs, labels=None):
        return confusion_matrix(labels or self.labels, [{"runs": list(runs)}])["tools"]

    def test_practice(self):
        practice = Path(__file__).resolve().parent.parent / "materialy-lab5/lab5-practice"
        if not practice.exists():
            self.skipTest("Course practice set is kept outside the repository")
        result = confusion_matrix(json.loads((practice / "labels.json").read_text()),
                                  [json.loads(p.read_text()) for p in sorted((practice / "sarif").glob("*.sarif"))])
        self.assertEqual(result, json.loads((practice / "expected.json").read_text()))

    def test_multiple_hits_and_false_positive_dedup_across_runs(self):
        hit = finding(start=8)
        false = finding(start=20)
        result = self.matrix(run([hit, hit, false]), run([false], name="Semgrep Pro"))["semgrep"]
        self.assertEqual((result["tp"], result["fp"], result["fn"]), (2, 1, 0))
        self.assertEqual(result["f1"], .8)

    def test_result_filters_and_first_location_only(self):
        invalid = finding(locations=[{}, finding()["locations"][0]])
        result = self.matrix(run([None, [], finding(kind="FAIL"), finding(kind="pass"),
                                 finding(suppressions=[None]), invalid]))["semgrep"]
        self.assertEqual((result["tp"], result["fp"], result["fn"]), (0, 0, 2))
        self.assertIsNone(result["precision"])
        for suppression in (None, [], {}, False, 0, ""):
            self.assertEqual(self.matrix(run([finding(suppressions=suppression)]))["semgrep"]["tp"], 1)

    def test_paths_decode_and_last_root(self):
        self.assertEqual(location(finding("FILE:///set/old/set%2Fapp.py"), "set"), ("set/app.py", 7, 7))
        self.assertIsNone(location(finding("other-set/app.py"), "set"))
        self.assertIsNone(location(finding("set\\app.py"), "set"))
        self.assertEqual(location(finding("././set/app.py"), "set"), ("set/app.py", 7, 7))

    def test_line_types(self):
        for start in (True, 7.0, "7", 0, None):
            self.assertEqual(location(finding(start=start), "set"), ("set/app.py", None, None))
        for end in (True, 7.0, "8", 0, None):
            record = finding()
            record["locations"][0]["physicalLocation"]["region"]["endLine"] = end
            self.assertEqual(location(record, "set"), ("set/app.py", 7, 7))

    def test_tool_ids_and_malformed_members(self):
        for driver in ({}, {"name": None}, {"name": 7}, {"name": "--"}):
            self.assertEqual(tool_id(driver), "unknown")
        self.assertEqual(tool_id({"name": " My AI__reviewer! "}), "my-ai-reviewer")
        result = confusion_matrix(self.labels, [{"runs": [None, [], {}, run(None),
                                                             {"tool": [], "results": {}}]}])
        self.assertEqual(set(result["tools"]), {"unknown", "semgrep"})

    def test_class_precedence_and_cwe_boundaries(self):
        rule = {"properties": {"tags": ["external/cwe/cwe-089", "CWE-0327: description", "XCWE-502", "CWE 918", None]}}
        self.assertEqual(classes({}, rule, "semgrep"), {"injection", "weak-crypto"})
        self.assertEqual(classes({"properties": {"class": "ssrf"}}, rule, "gitleaks"), {"ssrf"})
        self.assertEqual(classes({}, rule, "gitleaks"), {"secret"})
        self.assertEqual(classes({}, {"properties": {"tags": ["VULNERABILITY", "secret"]}}, "trivy"),
                         {"vulnerable-dependency", "secret"})
        self.assertEqual(classes({}, {"properties": {"tags": [" vulnerability "]}}, "trivy"), {"other"})

    def test_dependency_package_matching_without_lines(self):
        labels = {"set": "set", "defects": [{"id": "d", "file": "set/requirements.txt",
                                               "class": "vulnerable-dependency", "package": "my.pkg"}]}
        record = finding("set/requirements.txt", start=None, properties={}, message={"text": "Affected: MY_pkg."})
        self.assertEqual(self.matrix(run([record], name="grype"), labels=labels)["grype"]["tp"], 1)
        for message in ({"text": "my.pkg-extra"}, {"markdown": "my.pkg"}, None):
            record["message"] = message
            self.assertEqual(self.matrix(run([record], name="grype"), labels=labels)["grype"]["fp"], 1)

    def test_fp_rule_and_line_normalization(self):
        records = [finding(start=20, ruleId=rule) for rule in (None, "", 123)]
        duplicate = copy.deepcopy(records[0])
        duplicate["locations"][0]["physicalLocation"]["region"]["endLine"] = 20
        self.assertEqual(self.matrix(run(records + [duplicate]))["semgrep"]["fp"], 2)

    def test_first_rule_and_rule_index_ignored(self):
        record = finding(properties={}, ruleIndex=1)
        rules = [{"id": "r", "properties": {"tags": ["CWE-89"]}},
                 {"id": "r", "properties": {"tags": ["CWE-502"]}}]
        self.assertEqual(self.matrix(run([record], rules=rules))["semgrep"]["tp"], 1)

    def test_empty_defects(self):
        result = self.matrix(run([]), labels={"set": "other", "defects": []})["semgrep"]
        self.assertEqual(result, {"tp": 0, "fp": 0, "fn": 0, "precision": None, "recall": None, "f1": None})


if __name__ == "__main__":
    unittest.main()
