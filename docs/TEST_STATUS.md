# TEST_STATUS

Truthful test state. Statuses:

- `WRITTEN` — code exists
- `PASSED` — runtime evidence present in this environment
- `FAILED` — runtime evidence present, result is failure
- `BLOCKED` — cannot run because runtime dependency missing
- `UNVERIFIED` — runtime exists but no evidence gathered
- `NOT_EXISTENT` — no test file

**WRITTEN != PASSED.** Never mark a test `PASSED` without runtime
evidence from the current environment.

---

## Current state

| suite | file | tests | status | reason |
|---|---|---|---|---|
| Mock providers | `orchestrator/tests/test_mock_providers.py` | ~5 | PASSED | Runtime evidence (Prompt 3.5, 2026-09-15) |
| Scene definition | `orchestrator/tests/test_scene_definition.py` | ~6 | PASSED | Runtime evidence (Prompt 3.5, 2026-09-15) |
| Pipeline integration | `orchestrator/tests/test_pipeline_integration.py` | ~3 | PASSED | Runtime evidence (Prompt 4, 2026-09-15) |
| Research engine | `orchestrator/tests/test_research_engine.py` | 34 | PASSED | Runtime evidence (Prompt 3.5, 2026-09-15) |
| Story engine | `orchestrator/tests/test_story_engine.py` | ~50 | PASSED | Runtime evidence (Prompt 3.5, 2026-09-15) |
| Storyboard engine | `orchestrator/tests/test_storyboard_engine.py` | 62 | PASSED | Runtime evidence (Prompt 4, 2026-09-15) |
| Character System | `orchestrator/tests/test_character_system.py` | 103 | PASSED | Runtime evidence (Prompt 5, 2026-09-15) |
| **Asset System** | `orchestrator/tests/test_asset_system.py` | **105** | **PASSED** | **Runtime evidence (Prompt 6, 2026-09-15)** |
| Renderer | `renderer/**/*.test.ts*` | 0 | NOT_EXISTENT | — |
| Webapp | `webapp/**/*.test.ts*` | 0 | NOT_EXISTENT | — |
| Project audit tool | `orchestrator/app/tools/project_audit.py` | (self-test on import) | WRITTEN, BLOCKED | same |

**Aggregate:** **380 PASSED, 0 FAILED, 2 NOT_EXISTENT** (renderer/webapp).

**Latest run (Prompt 6, 2026-09-15):** `py -m pytest tests/ -q` → **380 passed, 3 warnings** (exit code 0).
Baseline before Prompt 4: 110 passed.
Prompt 4 (Storyboard): +62 → 172 passed.
Prompt 5 (Character System): +103 → 275 passed.
Prompt 6 (Asset System): +105 → 380 passed.

---

## Commands to run tests (unblock)

### 1. Install Python 3.11+

```powershell
# Option A: winget
winget install Python.Python.3.11

# Option B: from python.org installer, then verify
python --version   # must show 3.11.x or 3.12.x
```

### 2. Create virtualenv and install orchestrator deps

```powershell
cd "c:\Users\Administrator\Downloads\videoAI\orchestrator"
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

### 3. Run the test suite

```powershell
# all tests
pytest -q

# with coverage
pytest -q --cov=app --cov-report=term-missing

# one suite at a time
pytest tests/test_research_engine.py -q
pytest tests/test_scene_definition.py -q
pytest tests/test_mock_providers.py -q
pytest tests/test_pipeline_integration.py -q
```

### 4. Project audit (governance)

```powershell
# from repo root, after installing Python
python -m app.tools.project_audit
```

Expected result: `WARN` (C-001/002/003 remain; see TECHNICAL_DEBT.md).

### 5. Renderer / webapp tests (do not exist yet)

```powershell
# renderer: add Vitest
cd "c:\Users\Administrator\Downloads\videoAI\renderer"
npm install -D vitest
# then create renderer/src/**/*.test.tsx and run `npx vitest`

# webapp: add @testing-library/react
cd "c:\Users\Administrator\Downloads\videoAI\webapp"
npm install -D @testing-library/react vitest
# then create webapp/**/*.test.tsx and run `npx vitest`
```

---

## Recording results

After running tests, update this file with:

| date | command | result | exit_code | notes |
|---|---|---|---|---|
| 2026-09-15 | `py -3.11 -m pytest tests/ -q` | 110 passed, 3 warnings | 0 | Prompt 3.5 baseline fixed: +37 passing, -42 failing/erroring vs 73/24/18 baseline |
| 2026-09-15 | `py -3.11 -m pytest tests/ -q` | **172 passed**, 3 warnings | 0 | **Prompt 4: +62 Storyboard tests; Storyboard Intelligence Engine VERIFIED** |

---

## What "PASSED" requires

For each suite to be marked `PASSED`, this file must record:

1. The exact `pytest` (or `vitest`) command run.
2. The exit code (must be `0`).
3. The Python / Node version.
4. The number of tests passed.
5. Any warnings.

If even one test fails, the suite is `FAILED`, not `PARTIAL`.

---

## Common blockers and fixes

| blocker | fix |
|---|---|
| `python: command not found` | install Python 3.11+ (see step 1) |
| `ModuleNotFoundError: app` | run from `orchestrator/` directory |
| `duckduckgo_search` rate-limited | tests use `MockSearchProvider`; check `OPENAI_API_KEY=""` is set |
| `ffmpeg: command not found` | install via `winget install Gyan.FFmpeg` (only needed for s11) |
| `npx: command not found` | install Node 20+ from nodejs.org |
