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

---

## L-019 — Renderer still uses stick-figure characters (PROMPT 6.5)

| severity | mitigated |
|---|---|
| sympom | `renderer/src/components/Character.tsx` remains a hand-rolled SVG with 8 hardcoded stick-figure poses. The PROMPT 5 Character SVG generator and the renderer Character component are parallel implementations. |
| impact | Asset-2 Reference renderer-hints (palette, lighting variant, anchor points) are not consumed. Visual fidelity remains limited by the existing skeleton |
| workaround | PROMPT 7 will wire `assetAdapter.ts` + canonical SVG data into scene components |
| status | OPEN — deferred per prompt scope (no breaking rewrite) |

## L-020 — Renderer audio cues silently dropped (reminder)

See also `TECHNICAL_DEBT.md` C-004. `Scene.sfx[]` and `Scene.music` are validated by s9 but never wired to Remotion's `<Audio>` component.

## L-021 — Render smoke test exercises the simplified entry, not `Documentary.tsx`

| field | value |
|---|---|
| symptom | `scripts/render_smoke_test.py` bundles `smoke_entry.tsx` (a minimal, self-contained composition) to avoid `node:fs` webpack errors. The production `Documentary.tsx` composition is not exercised end-to-end because it depends on filesystem-loaded scenes. |
| impact | Pipeline validity is proven at the renderer boundary; full fidelity of the production composition is still UNVERIFIED. |
| possible resolution | PROMPT 7: rewrite `Documentary.tsx` to consume the `AssetAdapter` (fs-free) instead of loading scenes from disk. After that, the smoke test can bundle the real composition. |
| status | OPEN — accepted trade-off; full composition rewrite is out of scope for P6.5 |

## L-022 — Render smoke test takes ~55s (Chrome download once)

`render_smoke_test.py` typically takes ~55 seconds end-to-end because Chrome Headless Shell (~113 MB) is downloaded the first time. On subsequent runs the cache hits and the render drops to ~5–10s.
 
 - - - 
 
 
 
 # #   L - 0 1 9   ( P 7 )      S t i c k - f i g u r e   c h a r a c t e r s   ( P A R T I A L ) 
 
 
 
 R e n d e r e r   s t i l l   u s e s   s t i c k   f i g u r e s ;   P 7   a d d e d   a n i m a t e d   p o s e / s t a t e   a n d   p e r - f r a m e   i n t e r p o l a t i o n ,   b u t   v i s u a l   r i c h n e s s   ( d e t a i l e d   S V G ,   c l o t h i n g ,   e x p r e s s i o n s )   i s   s t i l l   d e f e r r e d . 
 
 
 
 # #   L - 0 2 0   ( P 7 )      A u d i o   c u e s   ( R E S O L V E D   v i a   D o c u m e n t a r y A u d i o ) 
 
 
 
 W i r e d   S c e n e . s f x [ ]   a n d   S c e n e . m u s i c   t o   R e m o t i o n   < A u d i o >   v i a   D o c u m e n t a r y A u d i o   w i t h   g a i n _ d b   �!  l i n e a r   v o l u m e   m a p p i n g . 
 
 
 
 # #   L - 0 2 1   ( P 7 )      D o c u m e n t a r y . t s x   f s - f r e e   ( R E S O L V E D ) 
 
 
 
 D o c u m e n t a r y . t s x   n o w   a c c e p t s   S c e n e D e f i n i t i o n   +   A s s e t P a c k a g e S u m m a r y   v i a   R e m o t i o n   i n p u t P r o p s ;   l o a d A s s e t A d a p t e r   i s   r e c o n s t r u c t e d   i n s i d e   t h e   b u n d l e . 
 
 
 
 # #   L - 0 2 3      A n i m a t i o n   a u d i o   l i b r a r y   n o t   y e t   w i r e d   i n   C I 
 
 
 
 A u d i o L i b r a r y   ( a u d i o L i b r a r y . t s )   i s   i m p l e m e n t e d   b u t   t h e   a n i m a t i o n   s m o k e   t e s t   d o e s   n o t   g e n e r a t e   a u d i o   f i l e s ;   D o c u m e n t a r y A u d i o   g r a c e f u l l y   s k i p s   m i s s i n g   c u e s . 
 
 
 
 # #   L - 0 2 4      W e b a p p   t e s t s   s t i l l   n o t   w r i t t e n   ( C - 0 1 0   p a r t i a l ) 
 
 
 
 P 7   c o v e r e d   r e n d e r e r   t e s t s   ( 7 1   p a s s i n g ) .   W e b a p p   t e s t s   r e m a i n   d e f e r r e d   t o   P R O M P T   1 0   o r   l a t e r . 
 
 

---

## L-025 � External TTS providers not exercised in CI (PROMPT 8)

The LegacyProviderAdapter wraps existing ElevenLabs and gTTS providers so
they conform to the canonical VoiceTTSProvider interface. However, no CI
test actually calls them because:
  * ElevenLabs requires a real API key (not in CI)
  * gTTS requires network access
  * pydub is broken on Python 3.13 (audioop removed)

Only MockTTSProvider (deterministic stdlib wave) is exercised. The
adapter code is unit-tested via interface conformance tests.

**Impact:** Bugs in ElevenLabs/gTTS integration won't surface until real
credentials are added. Mitigation: integration smoke tests run manually
when credentials are available.

## L-026 � Forced alignment not implemented (PROMPT 8)

If a TTS provider does not return trustworthy word timestamps, the
SpeechTiming.timestamp_source is set to UNAVAILABLE and
SpeechTiming.words = []. No forced alignment model is run.

**Impact:** Captions (PROMPT 9) require word timestamps. Without them,
captions must fall back to sentence-level or scene-level granularity.

**Workaround:** Providers that support provider-native timestamps
(ElevenLabs) will work correctly. Mock provider generates uniform
timestamps.

## L-027 � Loudness normalization deferred (PROMPT 8)

The pipeline validates audio but does NOT apply loudness normalization
(EBU R128, LUFS) to the WAV output. Audio levels may vary across
providers and scenes.

**Impact:** Final video may have inconsistent audio levels.

**Workaround:** AudioArtifact includes an extension point
(AudioArtifactStatus.NORMALIZED) for future loudness normalization.
PROMPT 9 Captions or a future Mastering stage can apply normalization.

## L-028 � SSML translation not implemented (PROMPT 8)

PronunciationHint and EmphasisHint are canonical structures, but no
provider-specific SSML generator is included. Each provider adapter must
translate hints to its native syntax (e.g. <phoneme> for SSML, or
provider-specific request fields for ElevenLabs).

**Impact:** Pronunciation hints are accepted but only settings-based
emphasis is forwarded. Future work needed to enable SSML generation for
SSML-capable providers.

## L-029 � Webapp still has no tests (carried from PROMPT 7)

No tests in webapp/. Voice/TTS admin UI endpoints (PROMPT 8 �43) are
defined as future work but not exposed via webapp yet.

---

## L-030 — Vertical video (9:16 / Shorts) preparation only at schema level (PROMPT 9)

Caption schema supports `vertical_anchor` (TOP/CENTER/BOTTOM/LOWER_THIRD)
and `safe_area_pct` so 9:16 outputs work without contract changes. The
dedicated Shorts composition / 9:16-specific safe-area math is NOT yet
implemented.

**Impact:** 9:16 outputs render captions correctly but at the default
anchor (LOWER_THIRD). No separate Shorts compilation pipeline exists.

**Workaround:** Deferred to PROMPT 10 (Editorial / Composition Engine).

## L-031 — No real forced-alignment engine (PROMPT 9)

PROMPT 9 establishes the `AlignmentProvider` Protocol boundary +
`UniformAlignmentProvider` (deterministic fallback when
`TimestampSource.PROVIDER_NATIVE` is unavailable). No real alignment
engine (Whisper alignment, MFA, wav2vec) is wired up.

**Impact:** When provider-native timestamps are unavailable, captions
fall back to uniform pacing (`UNIFORM_ALIGNMENT`). Quality score reflects
this honestly (lower than provider-native / forced alignment).

**Workaround:** Boundary ready for future providers; `alignment_provider_id`
field on `CaptionTrack` is reserved for the future engine's identifier.

## L-032 — Remotion caption smoke render blocked by bundler cache (PROMPT 9)

The Remotion renderer for caption smoke
(`scripts/caption_smoke_test.py` → `render_caption_smoke.tsx` →
`caption_smoke_root.tsx`) is blocked by a stale `localhost:3000`
dev-server cache. The Python-side CaptionTrack compilation + JSON
validation is fully verified. The TS-side caption frame-state derivation
+ cross-runtime contract are verified by 128/128 vitest tests. The
final Remotion bundle step is the only unverified link.

**Impact:** The end-to-end MP4 render with captions is not currently
runnable in this environment. All unit-level contract tests pass.

**Workaround:** Use `remotion/cli` directly; or pre-warm the bundle
directory; or run in a fresh Node process. Targeted fix in PROMPT 10.

**Status:** RESOLVED in PROMPT 10 — the `editorial_smoke` and `final_smoke`
tests both produce a valid MP4 via the Remotion render step.

---

## L-033 — Real Voice AudioArtifact not yet E2E through Remotion (PROMPT 8 / 10)

The voice pipeline produces real WAV files via `MockTTSProvider` and
stages them into `renderer/public/voice_audio/<id>.wav`. The
`EditorialProject` schema accepts `AudioArtifactRef` objects.
However, the editorial smoke test (P10) still produces text-only
narration in the rendered MP4 — i.e. the WAV files exist on disk but
are not yet wired into `RenderPlan.audio_clips` → `RenderPlanComposition`
→ `<Audio src="..."/>`.

**Impact:** The "final" MP4 from P10 is silent. L-033 stays open until
a final MP4 contains a real audio stream measured by `ffprobe`.

**Workaround:** Deferred to PROMPT 11.

**Status:** **RESOLVED in PROMPT 11.** `RenderPlanComposition` accepts
`audioArtifactSummaries` via inputProps; the renderer CLI stages the
WAVs into the Remotion bundle directory; the final smoke test produces
an MP4 with 1 audio stream (`aac 48 kHz / 2ch`) verified by `ffprobe`.
See `plans/prompt_11_FINAL_REPORT.md` §3.

---

## L-034 — Mastering / loudness / final audio QA not implemented (PROMPT 11)

No LUFS measurement, no `loudnorm` normalization, no true-peak detection,
no audio clipping protection, no per-check QA engine.

**Impact:** Even if a final MP4 contained real audio, no measurement
could tell whether it was broadcast-safe (loudness, peak, clipping).

**Workaround:** Deferred to PROMPT 11.

**Status:** **RESOLVED in PROMPT 11.** The `mastering` package now ships:

- `RenderProfile` (C-27) — versioned render settings.
- `MasteringProfile` (C-28) — configurable LUFS, true-peak, fades,
  silence policy.
- `FinalVideoArtifact` (C-28) — canonical artifact with checksum +
  lifecycle status.
- `MediaQAReport` (C-29) — 11-check QA engine with PASS/WARN/FAIL/
  UNAVAILABLE semantics.
- `MediaProcessor` — safe FFmpeg wrapper using argument arrays
  (no shell injection).
- Two-pass loudness normalization (`ebur128` measure → `loudnorm`
  apply) with `LRA` clamping.
- Ducking via `NarrationTimeline` (deterministic).
- Atomic finalization (temp → validate → rename).
- 86 mastering unit tests + 13 Vitest + the full E2E
  `final_smoke_test.py` PASS.

See `plans/prompt_11_FINAL_REPORT.md` §4.

---

## L-035 — Title card / overlay system remains minimal (PROMPT 11)

`RenderPlan.title_cards` is part of the contract but the visual
implementation is intentionally a stub (plain text box). No animated
title-card composition is wired up.

**Impact:** Documentary videos look barebones until L-035 is addressed.
Not on the PROMPT 11 critical path (L-033 and L-034 take priority).

**Workaround:** Use a placeholder text overlay; defer to a future
prompt.

---

## L-036 — Single-instance file-based job persistence (PROMPT 12)

The render job store is file-based JSON
(`workspace/{job_id}/render_job.json`). The RenderOrchestrator reads
and writes this file at every state transition. There is no database,
no locking, and no replication.

**Impact:** Multi-worker uvicorn deployments can corrupt the job
state if two workers write the same job concurrently. Process restart
preserves state (file is durable) but is not crash-safe in the strict
sense — a write that fails partway leaves a partial JSON file.

**Workaround:** Single uvicorn worker. The job API is idempotent
(`load_job()` returns the existing state). Document this explicitly as
KNOWN_LIMITATION, not PRODUCTION_READY for distributed/cloud deployment.

---

## L-037 — Synthetic silence MP4 fails QA loudness checks (PROMPT 12)

The orchestrator's E2E smoke path generates silence when no audio
clips are present in the render plan (because `MediaProcessor` does
not have a `silence_wav` helper). EBU R128 loudness measurement
correctly identifies silence as failing the LUFS target, and the
QA gate correctly marks the artifact as `qa_fail` → `rejected`.

This is **correct behavior** — it proves the §34 strict model
(`RENDERING SUCCESS != FINAL SUCCESS`) works. But it means that the
test fixture does not produce an APPROVED MP4 unless a real audio
file is staged.

**Impact:** E2E tests using synthetic silence verify the rejection
path (status = failed, video endpoint = 403). To produce an APPROVED
artifact, a real audio WAV must be staged at `mixed.wav` before
running the orchestrator.

**Workaround:** Future prompts may add an explicit "synthetic QA
fixture" that satisfies loudness checks (e.g. a pre-mastered WAV
matching the target LUFS). For now, the production path uses real
narration audio.

---

## L-038 — Frontend render inspector uses 2s polling, not SSE (PROMPT 12)

The Final Render Inspector polls `/render/{job_id}/status` every
2 seconds. P12 §16 mandates reusing existing progress mechanisms;
the existing webapp uses polling, so P12 follows suit.

**Impact:** Up to 2s of perceived latency for stage transitions. For
a production render that takes minutes, this is negligible. For an
SSE-required deployment, an upgrade is needed.

**Workaround:** Future prompts can add Server-Sent Events on top of
the same status endpoint.

