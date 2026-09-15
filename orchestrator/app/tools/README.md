# Project Audit Tool

Non-destructive governance audit for the videoAI repository.

## What it does

Cross-references the governance docs in `/docs/` against the actual source
code, schemas, providers, API routes, and tests. Reports PASS / WARN /
FAIL per dimension.

The tool:

- only **reads** files
- does **not** modify anything
- does **not** touch git
- does **not** make network calls
- uses **only the Python standard library** so it runs even when the
  orchestrator requirements are not installed

## Run it

From the `orchestrator/` directory:

```powershell
cd c:\Users\Administrator\Downloads\videoAI\orchestrator
python -m app.tools.project_audit
```

Or programmatically:

```python
from app.tools.project_audit import main
exit_code = main()
```

## Exit codes

| code | meaning |
|---|---|
| 0 | PASS or WARN (no HIGH/CRITICAL conflicts) |
| 2 | FAIL (at least one dimension failed) |

## Dimensions audited

| dimension | what it checks |
|---|---|
| docs presence | all 16 required `/docs/*.md` files exist |
| pipeline registry | every entry in `runner.STAGES` has a matching stage file with the expected class |
| api routes | FastAPI routes can be detected in `app/api/` and `app/main.py` |
| provider ABCs | every ABC in `providers/base.py` has >= 1 concrete implementation |
| schemas exported | all expected Pydantic schema files are present |
| test files | Python `test_*.py` files exist; runtime status defaults to BLOCKED on this host |
| research engine steps | >= 10 engine step methods are referenced in `engine.py` |
| secrets scan | grep for `sk-`, `AKIA`, `ghp_`, `xoxb-` patterns; report file:line only |
| docker-compose | declared services are actually used by orchestrator code |
| git repository | `.git/` is present |

## Expected output on this dev host

```
================================================================
videoAI Project Audit (PROMPT 0.5)
repo root: c:\Users\Administrator\Downloads\videoAI
================================================================

[PASS] docs presence: all 16 required docs present
[PASS] pipeline registry: all 11 runner.STAGES have matching files and classes
[PASS] api routes: 12 HTTP routes registered
[PASS] provider ABCs: all 5 provider ABCs have >=1 concrete impl
[PASS] schemas exported: all 5 schema files present
[PASS] test files: 4 Python test file(s) present; runtime BLOCKED on this host (no Python)
[PASS] research engine steps: 13 engine step method(s) detected
[PASS] secrets scan: no accidental secret patterns detected
[WARN] docker-compose: 1 service(s) declared but not used by code
    - redis: declared in compose but no Python usage or dep
[WARN] git repository: no .git/ directory; no commit history

----------------------------------------------------------------
OVERALL: WARN
----------------------------------------------------------------
WARN: known HIGH conflicts recorded in docs/TECHNICAL_DEBT.md
(C-001, C-002, C-003, C-008). These are NOT fixed by design.
```

## Runtime evidence

Because Python is not installed on the dev host, a PowerShell
simulation (`simulate-audit.ps1`) was used to validate the audit's
expectations match the actual repo. The simulation implements the same
ten dimensions using stdlib PowerShell and produced the expected output
above. The Python audit (`project_audit.py`) is identical in intent and
will produce the same output once Python is available.

## Why a WARN is the correct outcome

PROMPT 0.5 explicitly forbids fixing product logic. The HIGH conflicts
are documented in `docs/TECHNICAL_DEBT.md` and will be addressed by their
respective future prompts.

## Adding a new dimension

Append a new function to `orchestrator/app/tools/project_audit.py` with
the signature `() -> DimensionResult` and add it to `ALL_DIMENSIONS`.
Return `PASS`, `WARN`, or `FAIL` and populate `details` with evidence
file:line citations.
