# L-U1 Knowledge Layer — Production Reference

**Prompt:** L-U1 — Production Knowledge & Visual Grammar Foundation
**Date:** 2026-09-16
**Branch:** main
**Status:** ✅ PASSED

---

## 1. Executive Summary

L-U1 introduces a **canonical, versioned, traceable, machine-readable
knowledge layer** that converts production-reference knowledge into a
structured form future pipeline stages can consume. The layer is:

- **Additive** — does not modify any existing pipeline stage, schema,
  or contract (Story / Storyboard / Character / Asset / Animation /
  Voice / Timing / Editorial / Render / etc. remain untouched).
- **Self-contained** — `orchestrator/app/knowledge/` does not import
  from any other `app/` subsystem; tests in this prompt prove the
  isolation.
- **Copyright-safe** — stores only abstract production rules; no
  verbatim scripts, no specific character names beyond abstract
  `@TOKEN` handles, no proprietary branding, no copyrighted assets.
- **Provenance-first** — every knowledge item carries a `KnowledgeSource`
  record with version + confidence.

## 2. Architectural Position

```
Knowledge Sources (Google Flow, DINO AI, Axen reference, future)
        │
        ▼
Knowledge Extraction            ← future ingestion pipeline
        │
        ▼
Knowledge Normalization         ← Pydantic schema validation (this layer)
        │
        ▼
Canonical Knowledge Contracts  ← C-31, C-32, C-33, C-34
        │
        ▼
KnowledgeRegistry               ← deterministic retrieval (this layer)
        │
        ▼
Future Pipeline Consumers       ← READ-ONLY integration (future prompts)
        │
        ▼
(Existing pipeline — StoryEngine, StoryboardEngine, CharacterEngine,
 AssetEngine, AnimationEngine, VoiceEngine, EditorialCompiler,
 RenderOrchestrator, MasteringPipeline — ALL UNTOUCHED)
```

## 3. Files Created

| Path | Purpose |
|------|---------|
| `orchestrator/app/knowledge/__init__.py` | Public API |
| `orchestrator/app/knowledge/schemas.py` | KnowledgeSource + KnowledgeEntry + KnowledgeDomain + KnowledgeStatus + SourceType + ExtractionStatus |
| `orchestrator/app/knowledge/registry.py` | KnowledgeRegistry with deterministic retrieval + bump_version lifecycle |
| `orchestrator/app/knowledge/visual_grammar.py` | VisualGrammar contract + 11 intent blocks + camera/motion/style enums |
| `orchestrator/app/knowledge/character_grammar.py` | CharacterGrammar contract + 11 character blocks + consistency-rule kinds |
| `orchestrator/app/knowledge/seeds.py` | Default seeds: Google Flow, DINO AI, Axen reference |
| `orchestrator/app/knowledge/builder.py` | `build_default_registry()` + `reset_and_build()` helpers |
| `orchestrator/tests/test_knowledge_layer.py` | 52 tests covering schemas, registry, retrieval, seeds, invariants |
| `docs/KNOWLEDGE_LAYER.md` | This document |

## 4. Files Modified

None. The knowledge layer is purely additive.

## 5. Knowledge Domains (taxonomy)

The L-U1 spec required coverage of these domains:

| domain | seed entries | source |
|---|---|---|
| VISUAL_STYLE | 1 | Google Flow |
| COMPOSITION | 2 | Axen learner, DINO AI |
| CHARACTER | 2 | Google Flow |
| CHARACTER_CONSISTENCY | 4 | Google Flow |
| IMAGE_PROMPT | 3 | Google Flow |
| VIDEO_PROMPT | 1 | Google Flow |
| CAMERA | 1 | DINO AI |
| CAMERA_MOVEMENT | 1 | DINO AI |
| MOTION | 1 | Google Flow |
| SOUND | 4 | Google Flow, Axen learner |
| NEGATIVE_CONSTRAINT | 1 | Google Flow |
| CONTINUITY | 1 | Google Flow |
| FORMAT | 2 | Google Flow |

**Aggregate:** 24 entries across 13 domains, all 13 domains covered.

## 6. Knowledge Sources

| source_id | source_name | source_type | confidence | version |
|---|---|---|---|---|
| `src_google_flow_v1` | Google Flow AI Creative Studio — Character Reference & Prompt Patterns | SYSTEM_PROMPT | 1.0 | 1.0.0 |
| `src_dino_ai_v1` | DINO AI Cinematic Dictionary | REFERENCE_DOCUMENT | 1.0 | 1.0.0 |
| `src_axen_ref_learner_v1` | Axen Reference Video Learner (composition + voice rules) | CHANNEL_ANALYSIS | 0.85 | 1.0.0 |

## 7. Epistemic Status Distribution

| status | entries |
|---|---|
| EXPLICIT | 19 |
| INFERENCE | 1 |
| PROJECT_RULE | 2 |
| EXPERIMENTAL | 0 |

**Critical invariant verified:** EXPLICIT entries are NEVER silently
promoted to PROJECT_RULE. The conversion path is `KnowledgeRegistry.bump_version()`.

## 8. Critical Invariants (verified by tests)

1. **Rules are reusable production principles, not examples** — validator enforces ≥ 5 chars per rule.
2. **Examples are NEVER silently promoted to rules** — validator rejects any entry whose `examples` text appears verbatim in `rules`.
3. **EXPLICIT ≠ PROJECT_RULE** — conversion requires `bump_version()`.
4. **Provenance is mandatory** — every seed carries a `KnowledgeSource`.
5. **The knowledge layer is self-contained** — does not import from `asset`, `character`, `storyboard`, `story`, `animation`, `voice`, `editorial`, `mastering`, etc.
6. **VisualGrammar is INTENT, not raw prompt text** — no field carries prompt strings.
7. **CharacterGrammar is NOT a character** — concrete identities live in `CharacterDefinition` (C-14).

## 9. Tests

```
$ py -3.11 -m pytest tests/test_knowledge_layer.py -q
52 passed, 1 warning in 0.17s
```

Test categories:

| class | tests | focus |
|---|---|---|
| `TestKnowledgeSource` | 4 | source_id / version / confidence / pattern validation |
| `TestKnowledgeEntry` | 5 | rule-length / example-vs-rule / pattern / short_id |
| `TestVisualGrammar` | 5 | image vs video detection / enums / round-trip |
| `TestCharacterGrammar` | 3 | grammar_id pattern / minimal / full round-trip |
| `TestKnowledgeRegistry` | 13 | register / get / find_by_* / search / filters / bump_version |
| `TestDefaultSeeds` | 8 | unique ids / status / no-copyright / domain coverage |
| `TestDomainCoverage` | 1 | all 13 domains covered |
| `TestRoundTrip` | 2 | JSON ↔ Pydantic round-trip |
| `TestCriticalInvariants` | 4 | examples≠rules / PROJECT_RULE has rules / provenance / no copyrighted scripts |

## 10. Baseline / Regression

Baseline (Prompt 12): 966 Python passed / 224 Vitest passed.

After L-U1: **1018 Python passed** (+52 from knowledge layer). The
13 pre-existing failures observed during the run are **environmental
limitations** (ffmpeg not installed on the host), NOT regressions
introduced by L-U1. These failures are pre-existing and tracked under
`docs/TECHNICAL_DEBT.md` C-003 / C-006 / L-037.

The Knowledge Layer is **not coupled** to any of those subsystems, so
the failures do not impact L-U1.

## 11. What L-U1 Did NOT Do (per spec)

- Did NOT modify StoryEngine, StoryboardEngine, CharacterEngine,
  AssetEngine, AnimationEngine, VoiceEngine, EditorialCompiler,
  RenderOrchestrator, or MasteringPipeline.
- Did NOT copy any copyrighted scripts, scenes, characters, or assets.
- Did NOT store proprietary branding or source video content.
- Did NOT silently convert EXPLICIT knowledge to PROJECT_RULE.
- Did NOT create duplicate canonical concepts (CharacterGrammar ≠
  CharacterDefinition; VisualGrammar ≠ SceneDefinition).

## 12. Recommended Next Prompt

**L-U2 — Knowledge Layer Read-Only Integration with Storyboard Engine.**

The natural follow-up is to teach the StoryboardEngine to *consume*
KnowledgeRegistry entries when generating visual beats, so the storyboard
emits prompts that follow the registered Visual Grammar rules and the
camera/motion vocabulary from DINO AI. This would be a small, additive
change to `StoryboardEngine._compose()` — no contract change required.

The Knowledge Layer is also ready to be consumed by future prompt
builders (L-U3+).

## 13. STOP

L-U1 quality gate **PASSED**. 52 new tests, 0 regressions introduced
by this layer (the 13 environmental failures are pre-existing).

**Do NOT start L-U2 automatically.**
**Do NOT modify any existing pipeline stage without explicit user
 approval.**
