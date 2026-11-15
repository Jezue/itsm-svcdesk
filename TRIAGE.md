---
lab5_triage:
  image: ghcr.io/jezue/itsm-svcdesk@sha256:1f60349724cbf3aa7f69c4641509fbf8289f488722ae9b33da263a034d563f75
  sarif_receipt: 434
---
<!-- ai-generated: 100% - OpenAI Codex analysed actual CI scanner output and drafted the decisions and measured comparison. -->
# Triage

The first run, 43743534538, passed the service tests but failed the image gate. I updated the base image,
applied the available Debian upgrade, upgraded FastAPI and pytest, and removed pip after installation.
Run 43744168999 on main commit 6b8c085 passed all seven jobs. Its image digest is above; provenance and SPDX
attestations were checked with both course-prescribed `gh attestation verify` commands.

These decisions cover the service, not the deliberately defective canary. No CVE or secret was allow-listed:
both ignore files contain comments only. The canary stays on its separate branch and is never merged or run.

| Tool | Rule | Decision | Reason |
|---|---|---|---|
| trivy | CVE-2026-76844 | fix | The initial image scanner reported zlib1g. Dockerfile now applies Debian updates; zlib1g upgrades to 1:1.3.dfsg+really1.3.1-1+deb13u1 and the image gate passes. |
| trivy | CVE-2026-85091 | fix | The same zlib1g upgrade removes the second HIGH finding reported by the image gate; no ignore was used. |
| trivy | CVE-2025-62727 | fix | FastAPI 0.116.1 constrained Starlette to vulnerable 0.47.3. requirements.txt now selects FastAPI 0.163.1; the successful build installed Starlette 1.10.0 and retained passing API tests. |
| trivy | CVE-2026-48818 | fix | The initial image reported this Starlette advisory. Upgrading the compatible FastAPI/Starlette combination removes that old dependency rather than suppressing the alert. |
| trivy | CVE-2026-54283 | fix | Starlette 1.10.0 is beyond the 1.3.1 fix named by the initial scan. The final image gate confirms no remaining fixable HIGH/CRITICAL finding. |
| trivy | CVE-2026-114613 | fix | The flagged msgpack copy was inside pip's vendored packages, not a service import. Dockerfile removes pip after dependencies are installed; the service does not invoke pip at runtime. |
| trivy | GHSA-6v7p-g79w-8964 | fix | Removing the unused runtime installer also removes its vendored msgpack copy responsible for this second finding. No package advisory was ignored. |
| trivy | CVE-2025-47273 | fix | The scanner found pip's vendored setuptools metadata. Removing pip after installation removes that unused attack surface while preserving the installed application packages. |
| trivy | CVE-2026-97687 | fix | The affected urllib3 copy was bundled with pip. pip is removed from the final runtime image; installed service dependencies and tests still work. |
| trivy | CVE-2026-97689 | fix | The second vendored urllib3 finding is handled by the same runtime-pip removal, with a successful image rescan rather than an ignore. |
| trivy | CVE-2025-71176 | fix | The reporting scan found pytest 8.4.2 in requirements.txt. It is now pinned to 9.1.1, beyond the reported 9.0.3 fix; service tests remain green. |
| grype | GHSA-6w46-j5rx-g56g-pytest | fix | Grype independently reported the old pytest dependency. The explicit requirements.txt upgrade to 9.1.1 addresses the same finding without changing the canary pins. |
| osv-scanner | CVE-2025-71176 | fix | OSV-Scanner also reported pytest 8.4.2. Upgrading the service pin to 9.1.1 addresses the advisory; the intentionally vulnerable canary requirements are untouched. |
| semgrep | dockerfile.security.missing-user.missing-user | accept | Dockerfile still runs this local teaching service as root. I retain the existing named-volume ownership contract for this lab; review a non-root user and data migration by 28 November 2026, before production deployment. |
| semgrep | python.lang.security.audit.dynamic-urllib-use-detected.dynamic-urllib-use-detected | false-positive | incident/query-evidence.py builds a URL from a fixed localhost Prometheus endpoint and static query/time constants. It does not accept a client-controlled host, scheme or path. |
| semgrep | python.sqlalchemy.security.sqlalchemy-execute-raw-query.sqlalchemy-execute-raw-query | false-positive | src/svcdesk/main.py list_tickets concatenates fixed SQL clause strings only; state and priority values are passed separately as SQLite bound parameters. It does not interpolate those values into SQL. |
| semgrep | svcdesk-test-clock-switch | accept | This custom review guard deliberately records the SVCDESK_TEST_CLOCK configuration point in main.py. The test clock is required for course fixtures; it must remain disabled for production. It is not a claim of a generic security defect. |
| semgrep | svcdesk-sqlite-connection | accept | This custom guard records the two SQLite connection sites in schema initialisation and the database context manager. Both own and close their connections; new sites require the same ownership review. |

## Bake-off

The pipeline passed on main M (6b8c085, run 43744168999). The checker then added the unchanged canary
as C (112173a, run 43744378399): deps and secrets failed, while build-test, image, code, ignore-policy and
capture passed. I downloaded its five SARIF files unchanged, committed them at abca5d1, and obtained
[SARIF receipt #434](https://github.com/swasik/itsm-2026-submissions/issues/434). The course revealed the labels
after that receipt. Their 11 defects, rather than scanner result counts, are the denominator for recall.

`bakeoff.json` contains these results, calculated by `bakeoff.py` under the course matching rules:

| Tool | TP | FP | FN | Precision | Recall | F1 |
|---|---|---|---|---|---|---|
| gitleaks | 3 | 0 | 8 | 1.0000 | 0.2727 | 0.4286 |
| grype | 2 | 0 | 9 | 1.0000 | 0.1818 | 0.3077 |
| osv-scanner | 2 | 0 | 9 | 1.0000 | 0.1818 | 0.3077 |
| semgrep | 6 | 0 | 5 | 1.0000 | 0.5455 | 0.7059 |
| trivy | 4 | 0 | 7 | 1.0000 | 0.3636 | 0.5333 |

I would keep gitleaks and Trivy in the gates. Gitleaks found all three planted credentials without an FP;
Trivy caught both vulnerable pins and two credentials. Grype and OSV-Scanner each found the same two dependency
defects: their 0.1818 overall recall does not make them bad dependency scanners, because the denominator also
contains nine defects outside that specialism. In this small set they added no unique detection to Trivy.

Semgrep found three application defects and all three credentials. Its 0.5455 recall was the best of these
five tools, but it still missed five defects. I would keep the broad registry rules as review findings rather
than treating one clean scan as permission to deploy. Zero FPs here does not establish a general false-positive
rate: this login's six application modules were all labelled defective, and the sample is only 11 defects.
The three findings on our own code are triaged separately above; they are outside the measured set.

The union of all five tools found 8/11 defects. None matched A03 (path traversal in attachment_read.py),
A08 (random.choice for password-reset tokens), or A16 (a customer-supplied destination passed to requests.post).
These require checking how filenames, random values and outbound destinations are used, not just counting
package CVEs or recognising credential strings. I inspected them only after the label reveal and did not
run the canary code. A timeout on the webhook does not make its destination safe.

These are measurements on planted, synthetic defects, which tend to flatter detectors. Their recall is an
upper bound for this exercise, not evidence that the same percentage of real production bugs will be found.
I would combine the two gates with tests and review of data flows. The mutation suite and our two local
Semgrep review guards add separate evidence; their results are not silently counted as sixth-detector SARIF.
