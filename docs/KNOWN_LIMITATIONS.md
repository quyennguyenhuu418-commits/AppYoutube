# KNOWN_LIMITATIONS

Verified limitations of the current system. Each entry has been
cross-checked against the actual source code (not just documentation).

---

## L-001 — No automated TS/Python SceneDefinition contract tests

The Python `SceneDefinition` schema and the TypeScript mirror at
`renderer/src/scenes/types.ts` are maintained by hand. There is no test
that verifies the two stay in sync.

**Impact:** A future change to the Python schema can silently break the
renderer; vice versa. Mitigation: any schema change must update both
files in the same commit and pass a manual cross-check using
`docs/DATA_CONTRACTS.md` C-01.

**Workaround:** Read both files before changing either. Cross-reference
field-by-field.

---

## L-002 — HTML extraction is regex-based

`RequestsContentFetchProvider` strips script/style/nav/footer blocks and
tags with regex. JavaScript-heavy pages (React SPAs, etc.) return shell
content only.

**Impact:** Research quality degrades on modern sites.

**Workaround:** Use the mock provider for tests. For production, swap in
`newspaper3k` or `trafilatura` (planned future work).

---

## L-003 — Source lineage is not auto-detected

`SourceLineage.is_independent` is `True` by default. The engine does not
detect URL-pattern or content-overlap dependencies between sources.

**Impact:** Independence score in quality assessment may overstate
independence for syndicated or aggregator sources.

**Workaround:** Manual review via `POST /research/{id}/review/sources/{id}`
to mark dependent sources.

---

## L-004 — Contradiction detection is a stub

See `docs/TECHNICAL_DEBT.md` C-001. `ResearchPackage.contradictions` is
always empty in current output.

**Impact:** Cannot highlight conflicting claims; quality sub-score for
contradiction detection is fixed at 0.

**Workaround:** Manually review claims via the webapp (future) or
`/research/{id}/claims` + `/review/claims/{id}` API.

---

## L-005 — Geography and quantitative facts are stubs

See `docs/TECHNICAL_DEBT.md` C-002.

**Impact:** Visual opportunities and story opportunities cannot
auto-reference real locations or specific numbers.

**Workaround:** Manual addition in downstream stages if needed.

---

## L-006 — Renderer audio is not wired

See `docs/TECHNICAL_DEBT.md` C-004. `Scene.sfx[]` and `Scene.music` are
validated but never played.

**Impact:** LLM-emitted audio cues are silently dropped.

**Workaround:** Use the document-level `narration.mp3` audio track only.

---

## L-007 — Single-process synchronous pipeline

The runner is a `for stage in STAGES:` loop in one FastAPI process. Long
jobs block the event loop. There is no Celery, Redis, or background queue.

**Impact:** Cannot horizontally scale; one slow job blocks all others on
the same instance.

**Workaround:** Deploy single-instance only. `docker-compose.yml` defines
Redis/Postgres but they are unused (see `docs/TECHNICAL_DEBT.md` C-006).

---

## L-008 — File-based job store is not concurrent-safe

`orchestrator/app/db/store.py` writes JSON files without locking.

**Impact:** Do not run multiple uvicorn workers writing the same
`job.json`.

**Workaround:** Single `uvicorn` process. Use `start.bat` defaults.

---

## L-009 — No git repository

No `.git/` directory exists. There is no commit history and no diff-based
memory.

**Impact:** Cannot run `git log`, `git diff`, or `git blame`. Cannot
revert changes.

**Workaround:** None. Initialization requires user approval (see
`docs/TECHNICAL_DEBT.md` C-008).

---

## L-010 — No Python on the dev host

Python 3.11+ is not installed on the Windows dev host.

**Impact:** All Python tests are BLOCKED. Cannot run `pytest`, `ruff`,
or the orchestrator directly.

**Workaround:** Install Python 3.11+ or run tests in CI.

---

## L-011 — Stage retry is minimal

Only `s9_validate` has internal retry (re-runs `s8` once on validation
failure). All other stages fail-fast.

**Impact:** Transient LLM/network errors fail the entire job.

**Workaround:** Re-submit the job; the skip-cache will reuse successful
prior stages.

---

## L-012 — No quality gates

There is no per-stage quality threshold that aborts the pipeline.
`ResearchPackage.quality_score` emits warnings below 0.6 but does not
block downstream stages.

**Impact:** A poor research package can still drive a low-quality video.

**Workaround:** Manual inspection via `/research/{id}/quality` endpoint.

---

## L-013 — Renderer fallback scene uses hardcoded data

When `VIDEOAI_JOB_DIR` is not set and `../../workspace/demo` does not
exist, `Root.tsx` renders a hardcoded fallback scene. This is for Remotion
Studio preview only.

**Impact:** Preview without a real job will not reflect production output.

**Workaround:** Always set `VIDEOAI_JOB_DIR` for real previews.

---

## L-014 — ElevenLabs requires paid API key

If `ELEVENLABS_API_KEY` is empty, the factory falls back to gTTS, which
has weaker voice quality and uniform word alignment.

**Impact:** Free-tier deployments get noticeably worse narration.

**Workaround:** Subscribe to ElevenLabs; or accept gTTS for development.

---

## L-015 — Tests never runtime-verified

Every test suite listed in `docs/TEST_STATUS.md` is `WRITTEN, BLOCKED` or
`NOT_EXISTENT`.

**Impact:** No automated safety net. Refactor confidence is low.

**Workaround:** Manual smoke testing per stage. See
`docs/TEST_STATUS.md` for unblock instructions.

---

## L-016 — Asset System renderer wiring deferred

The Asset System emits `AssetReference.renderer_hints` for environments
and props, but the current Remotion renderer reads only `environment_id`
and `prop_id` keys in `SceneDefinition`. Rich asset metadata (palette,
lighting variant, anchor points) is serialized but not yet consumed at
render time.

**Impact:** Asset System tracks metadata correctly; visual fidelity remains
limited by current `NarrationScene` / `DiagramScene` rendering.

**Workaround:** Deferred to PROMPT 7 (Animation Engine) and PROMPT 10
(visual fidelity consolidation).

## L-017 — Embedding-based asset similarity not implemented

`AssetResolver.find_similar` uses simple word overlap on normalized
semantic tags. Truly similar assets with different wording may not be
detected as duplicates.

**Impact:** Duplicate detection may produce false negatives for assets
described with different vocabulary.

**Workaround:** Extensible design — embedding-based similarity is an
extension point. Will be added when vector infrastructure is available.

## L-018 — Cross-project asset reuse requires manual migration

Each project has its own `registry.json`. Global asset reuse across
projects requires manually copying entries.

**Impact:** Asset reuse is currently project-scoped.

**Workaround:** Deferred to roadmap (Postgres migration per ADR-006).

---

## Summary

18 verified limitations, of which:
- 3 are stub engines (L-004, L-005, L-006)
- 4 are environment / runtime (L-009, L-010, L-015, and the BLOCKED tests)
- 11 are architectural (L-001 through L-003, L-007, L-008, L-011 through L-014, L-016 through L-018)

None are CRITICAL (no data loss, no security exposure, no total system
failure). The MVP is functional but unverified.
