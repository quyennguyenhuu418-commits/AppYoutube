"""
Editorial / Composition Engine (PROMPT 10).

PUBLIC API:

This package owns the master composition timeline that places Storyboard,
Asset, Animation, Voice, and Caption subsystems onto a single deterministic
editorial timeline. It produces a `RenderPlan` that the renderer consumes.

Architectural rule (PROMPT 10 §3):
  Editorial owns placement, ordering, transitions, audio mixing,
  caption placement, and animation offsets on the master timeline.
  Editorial MUST NOT re-derive word timing, speech timing, animation
  keyframes, or caption timing. It only consumes them as references and
  applies deterministic offsets.

Modules:
  - schemas        canonical Pydantic models (C-25 EditorialProject, ...)
  - references     source-of-truth identity resolution (asset/audio/caption/animation)
  - transitions    canonical transition rules + overlap semantics
  - offsets        scene-local → master timeline transformation
  - audio          audio track + ducking computation
  - validation     editorial validation rules
  - compiler       EditorialCompiler: validate → resolve → normalize → transitions
                   → audio → captions → animations → RenderPlan
  - render_plan    RenderPlan schema (renderer-consumable, JSON-stable)

The renderer (TS) mirrors these contracts under `renderer/src/editorial/`.
"""
