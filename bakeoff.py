# ai-generated: 100% - OpenAI Codex implemented the published CI-SPEC P-14 to P-24 matching rules and tests.
"""Read SARIF and course labels; print per-tool confusion matrices (stdlib only)."""

import argparse
import json
import re
import sys
from urllib.parse import unquote


CWE_CLASSES = {
    "secret": {259, 260, 321, 798},
    "injection": {74, 77, 78, 79, 80, 88, 89, 90, 91, 94, 95, 96, 611, 776, 917, 943, 1336},
    "deserialization": {502},
    "weak-crypto": {261, 326, 327, 328, 330, 331, 338, 759, 760, 916},
    "insecure-transport": {295, 297, 319, 322, 757},
    "path-traversal": {22, 23, 35, 36, 73},
    "ssrf": {918},
    "vulnerable-dependency": {937, 1035, 1104, 1395},
    "misconfiguration": {16, 215, 250, 489, 668, 732, 1188},
    "access-control": {284, 285, 639, 862, 863},
}


def obj(value):
    return value if isinstance(value, dict) else {}


def array(value):
    return value if isinstance(value, list) else []


def tool_id(driver):
    name = driver.get("name")
    if not isinstance(name, str):
        return "unknown"
    name = name.strip().lower()
    if name in {"semgrep", "semgrep oss", "semgrep ce", "semgrep community edition", "semgrep pro"}:
        return "semgrep"
    return re.sub(r"[^a-z0-9]+", "-", name).strip("-") or "unknown"


def tags(record):
    return [tag for tag in array(obj(record.get("properties")).get("tags")) if isinstance(tag, str)]


def classes(result, rule, tool):
    own = obj(result.get("properties")).get("class")
    if isinstance(own, str) and own in CWE_CLASSES:
        return {own}
    if tool == "gitleaks":
        return {"secret"}
    if tool in {"grype", "osv-scanner"}:
        return {"vulnerable-dependency"}
    if tool == "trivy":
        names = {"vulnerability": "vulnerable-dependency", "secret": "secret", "misconfiguration": "misconfiguration"}
        inferred = {names[tag.lower()] for tag in tags(rule) if tag.lower() in names}
        if inferred:
            return inferred
    cwes = {int(match) for tag in tags(result) + tags(rule)
            for match in re.findall(r"(?<![A-Za-z0-9])CWE-([0-9]+)", tag, re.IGNORECASE)}
    return {name for name, numbers in CWE_CLASSES.items() if numbers & cwes} or {"other"}


def location(result, root):
    locations = array(result.get("locations"))
    physical = obj(obj(locations[0]).get("physicalLocation")) if locations else {}
    uri = obj(physical.get("artifactLocation")).get("uri")
    if not isinstance(uri, str) or not uri:
        return None
    path = unquote(uri)
    if path[:7].lower() == "file://":
        path = path[7:]
    if path.startswith("./"):
        path = path[2:]
    parts = path.split("/")
    roots = [i for i, part in enumerate(parts) if part == root]
    if not roots:
        return None
    file = "/".join(parts[roots[-1]:])
    region = obj(physical.get("region"))
    start = region.get("startLine")
    if type(start) is not int or start < 1:
        return file, None, None
    end = region.get("endLine")
    if type(end) is not int or end < start:
        end = start
    return file, start, end


def package_name(name):
    return re.sub(r"[-_.]+", "-", name.lower())


def matches(defect, loc, result_classes, result):
    file, start, end = loc
    if file != defect["file"] or defect["class"] not in result_classes:
        return False
    if defect["class"] == "vulnerable-dependency":
        text = obj(result.get("message")).get("text")
        tokens = re.findall(r"[A-Za-z0-9._-]+", text) if isinstance(text, str) else []
        return any(package_name(token.strip("._-")) == package_name(defect["package"]) for token in tokens)
    return start is not None and start <= defect["end_line"] and defect["start_line"] <= end


def confusion_matrix(labels, sarif_documents):
    states = {}
    for document in sarif_documents:
        for run in array(obj(document).get("runs")):
            if not isinstance(run, dict):
                continue
            driver = obj(obj(run.get("tool")).get("driver"))
            tool = tool_id(driver)
            found, false = states.setdefault(tool, (set(), set()))
            rules = array(driver.get("rules"))
            for result in array(run.get("results")):
                if not isinstance(result, dict) or result.get("kind") not in (None, "fail") or result.get("suppressions"):
                    continue
                loc = location(result, labels["set"])
                if loc is None:
                    continue
                rid = result.get("ruleId")
                rule = next((r for r in rules if isinstance(r, dict) and rid is not None and r.get("id") == rid), {})
                result_classes = classes(result, rule, tool)
                hits = {d["id"] for d in labels["defects"] if matches(d, loc, result_classes, result)}
                if hits:
                    found.update(hits)
                else:
                    false.add((rid if isinstance(rid, str) else None, *loc))
    tools = {}
    count = len(labels["defects"])
    for tool, (found, false) in sorted(states.items()):
        tp, fp, fn = len(found), len(false), count - len(found)
        tools[tool] = {
            "tp": tp, "fp": fp, "fn": fn,
            "precision": round(tp / (tp + fp), 4) if tp + fp else None,
            "recall": round(tp / count, 4) if count else None,
            "f1": round(2 * tp / (2 * tp + fp + fn), 4) if 2 * tp + fp + fn else None,
        }
    return {"set": labels["set"], "defects": count, "tools": tools}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--labels", required=True)
    parser.add_argument("sarif", nargs="+")
    args = parser.parse_args()
    try:
        with open(args.labels, encoding="utf-8") as stream:
            labels = json.load(stream)
        documents = []
        for path in args.sarif:
            with open(path, encoding="utf-8") as stream:
                documents.append(json.load(stream))
    except (OSError, ValueError) as error:
        parser.error(str(error))
    json.dump(confusion_matrix(labels, documents), sys.stdout, indent=2)
    sys.stdout.write("\n")


if __name__ == "__main__":
    main()
