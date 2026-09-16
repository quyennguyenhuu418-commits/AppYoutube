"""
Storyboard Intelligence Engine.

The StoryboardEngine transforms a StoryPackage into a StoryboardPackage:
the executable visual blueprint that the future Character, Asset, Animation,
and Remotion subsystems can execute deterministically.

Pipeline:
    StoryPackage
      ↓
    Segment Analysis
      ↓
    Visual Decomposition (segment → 1..N visual beats)
      ↓
    Visual Mode Selection (CHARACTER / ENVIRONMENT / DIAGRAM / MAP / ...)
      ↓
    Camera / Motion / Transition Planning
      ↓
    Text / Diagram / Map / Timeline / Comparison Planning
      ↓
    Asset Requirements
      ↓
    Continuity Resolution
      ↓
    Evidence Mapping (beat → claim_ids → source_ids)
      ↓
    StoryboardCompiler (StoryboardPackage → SceneDefinition candidates)
      ↓
    StoryboardQualityScore
      ↓
    StoryboardPackage

No rendering is performed. The engine is pure declarative data generation.

The engine reuses the existing LLMProvider abstraction (so the mock LLM
fixtures continue to work in tests) and the existing content-addressed
StoryboardCache for deterministic incremental runs.
"""
from __future__ import annotations

import hashlib
import re
from datetime import datetime
from typing import Any

from app.core.config import settings
from app.core.logging import get_logger
from app.providers.base import LLMMessage, LLMRequest
from app.providers.llm import get_llm_provider
from app.knowledge import KnowledgeStoryboardAdapter
from app.schemas.research_package import (
    Claim,
    ResearchPackage,
    Source,
    VisualOpportunity,
)
from app.schemas.story import (
    ScriptSegment,
    ScriptVersion,
    StoryPackage,
    StoryboardIntentItem,
    VisualMode as StoryVisualMode,
)
from app.schemas.storyboard import (
    AssetRequirement,
    AudioSyncPoint,
    CameraPlan,
    CharacterRequirement,
    Composition,
    ContinuityDependency,
    ContinuityIssue,
    ContinuityState,
    ContinuityUpdate,
    DataVisualizationSpec,
    DiagramSpec,
    EnvironmentRequirement,
    MapSpec,
    MotionItem,
    PropRequirement,
    SceneDefinitionCandidate,
    StoryboardAssetClass,
    StoryboardAssetRequirement,
    StoryboardAspectRatio,
    StoryboardCameraType,
    StoryboardContinuityFlag,
    StoryboardInformationAlignment,
    StoryboardMetadata,
    StoryboardMotionType,
    StoryboardPackage,
    StoryboardQualityScore,
    StoryboardReconstructionConfidence,
    StoryboardStatus,
    StoryboardStoryFunction,
    StoryboardTransition,
    StoryboardUncertaintyTreatment,
    StoryboardVisualMode,
    TextItem,
    TimelineSpec,
    ComparisonSpec,
    VisualBeat,
)


# ============================================================================
# ID generation
# ============================================================================

_BEAT_ID_RE = re.compile(r"^beat_\d{4}$")
_ASSET_ID_RE = re.compile(r"^asset_[a-z0-9_]+$")
_CAMERA_ID_RE = re.compile(r"^cam_[a-z0-9_]+$")


def _hash_input(*parts: Any) -> str:
    """Stable content hash for cache keys."""
    h = hashlib.sha256()
    for p in parts:
        h.update(str(p).encode("utf-8"))
        h.update(b"|")
    return h.hexdigest()[:16]


def _next_beat_id(counter: list[int]) -> str:
    counter[0] += 1
    return f"beat_{counter[0]:04d}"


def _safe_mode(raw: str | None) -> StoryboardVisualMode:
    """Coerce LLM-provided mode strings to StoryboardVisualMode enum."""
    if not raw:
        return StoryboardVisualMode.HYBRID
    try:
        return StoryboardVisualMode(str(raw).lower())
    except ValueError:
        return StoryboardVisualMode.HYBRID


def _safe_camera(raw: str | None) -> StoryboardCameraType:
    if not raw:
        return StoryboardCameraType.STATIC
    try:
        return StoryboardCameraType(str(raw).lower())
    except ValueError:
        return StoryboardCameraType.STATIC


def _safe_transition(raw: str | None) -> StoryboardTransition:
    if not raw:
        return StoryboardTransition.CUT
    try:
        return StoryboardTransition(str(raw).lower())
    except ValueError:
        return StoryboardTransition.CUT


# ============================================================================
# Engine
# ============================================================================

class StoryboardEngine:
    """Produces a StoryboardPackage from a StoryPackage."""

    # Hardcoded character id used by the existing renderer / placeholders.
    NARRATOR_ID = "narrator"
    NARRATOR_NAME = "Narrator"

    # Renderer-supported environment ids (from s6_assets._ENV_HINTS).
    _RENDERER_ENVIRONMENTS = {
        "ice_age_plains",
        "cave_interior",
        "diagram_white",
        "mammoth_camp",
        "title_card",
    }

    # Renderer-supported prop kinds.
    _RENDERER_PROP_KINDS = {
        "human_silhouette",
        "cave",
        "fire",
        "tree_pine",
        "snowflake",
        "arrow",
        "timeline",
        "chart_axes",
        "animal_mammoth",
        "sun",
        "mountain",
        "question_mark",
    }

    # Maps a storyboard env hint to a renderer env id.
    _ENV_HINT_TO_ID = {
        "plains": "ice_age_plains",
        "tundra": "ice_age_plains",
        "snow": "ice_age_plains",
        "cave": "cave_interior",
        "diagram": "diagram_white",
        "camp": "mammoth_camp",
        "title": "title_card",
        "default": "diagram_white",
    }

    # Maps StoryboardVisualMode → renderer env id (when no specific env hint).
    _MODE_TO_ENV = {
        StoryboardVisualMode.CHARACTER: "diagram_white",
        StoryboardVisualMode.ENVIRONMENT: "ice_age_plains",
        StoryboardVisualMode.DIAGRAM: "diagram_white",
        StoryboardVisualMode.MAP: "diagram_white",
        StoryboardVisualMode.TIMELINE: "diagram_white",
        StoryboardVisualMode.COMPARISON: "diagram_white",
        StoryboardVisualMode.ARTIFACT: "cave_interior",
        StoryboardVisualMode.TEXT_GRAPHIC: "diagram_white",
        StoryboardVisualMode.DATA_VISUALIZATION: "diagram_white",
        StoryboardVisualMode.ARCHIVAL: "cave_interior",
        StoryboardVisualMode.HYBRID: "diagram_white",
    }

    # Visual mode → default character posture / motion / camera defaults.
    _MODE_DEFAULTS = {
        StoryboardVisualMode.CHARACTER: {
            "camera": StoryboardCameraType.STATIC,
            "motion": StoryboardMotionType.CHARACTER_ACTION,
            "function": StoryboardStoryFunction.SHOW,
            "needs_characters": True,
        },
        StoryboardVisualMode.ENVIRONMENT: {
            "camera": StoryboardCameraType.PUSH_IN,
            "motion": StoryboardMotionType.PARALLAX_DRIFT,
            "function": StoryboardStoryFunction.SHOW,
            "needs_characters": False,
        },
        StoryboardVisualMode.DIAGRAM: {
            "camera": StoryboardCameraType.STATIC,
            "motion": StoryboardMotionType.OVERLAY_APPEAR,
            "function": StoryboardStoryFunction.EXPLAIN,
            "needs_characters": False,
        },
        StoryboardVisualMode.MAP: {
            "camera": StoryboardCameraType.STATIC,
            "motion": StoryboardMotionType.OVERLAY_APPEAR,
            "function": StoryboardStoryFunction.SHOW,
            "needs_characters": False,
        },
        StoryboardVisualMode.TIMELINE: {
            "camera": StoryboardCameraType.PAN,
            "motion": StoryboardMotionType.OVERLAY_APPEAR,
            "function": StoryboardStoryFunction.EXPLAIN,
            "needs_characters": False,
        },
        StoryboardVisualMode.COMPARISON: {
            "camera": StoryboardCameraType.STATIC,
            "motion": StoryboardMotionType.OVERLAY_APPEAR,
            "function": StoryboardStoryFunction.CONTRAST,
            "needs_characters": False,
        },
        StoryboardVisualMode.ARTIFACT: {
            "camera": StoryboardCameraType.PUSH_IN,
            "motion": StoryboardMotionType.PROP_ROTATE,
            "function": StoryboardStoryFunction.REVEAL,
            "needs_characters": False,
        },
        StoryboardVisualMode.TEXT_GRAPHIC: {
            "camera": StoryboardCameraType.STATIC,
            "motion": StoryboardMotionType.OVERLAY_APPEAR,
            "function": StoryboardStoryFunction.EMPHASIZE,
            "needs_characters": False,
        },
        StoryboardVisualMode.DATA_VISUALIZATION: {
            "camera": StoryboardCameraType.STATIC,
            "motion": StoryboardMotionType.OVERLAY_APPEAR,
            "function": StoryboardStoryFunction.EXPLAIN,
            "needs_characters": False,
        },
        StoryboardVisualMode.ARCHIVAL: {
            "camera": StoryboardCameraType.STATIC,
            "motion": StoryboardMotionType.NONE,
            "function": StoryboardStoryFunction.SHOW,
            "needs_characters": False,
        },
        StoryboardVisualMode.HYBRID: {
            "camera": StoryboardCameraType.STATIC,
            "motion": StoryboardMotionType.CHARACTER_ACTION,
            "function": StoryboardStoryFunction.SHOW,
            "needs_characters": True,
        },
    }

    # Words that strongly suggest a particular visual mode.
    _DIAGRAM_KEYWORDS = (
        "diagram", "flow", "process", "sequence", "step", "stages",
        "cycle", "system", "pipeline", "mechanism", "chain",
        "how it works", "how does", "why", "because",
    )
    _MAP_KEYWORDS = (
        "map", "geography", "region", "continent", "ocean", "mountain",
        "valley", "river", "where", "located", "migration",
    )
    _TIMELINE_KEYWORDS = (
        "years ago", "century", "millennia", "thousand years",
        "before", "after", "earlier", "later", "timeline",
        "history", "historically", "evolved", "evolution",
    )
    _COMPARISON_KEYWORDS = (
        "compared", "comparison", "versus", "vs", "rather than",
        "instead of", "difference", "contrast", "twice as", "half",
        "ten times", "hundred times",
    )
    _ARTIFACT_KEYWORDS = (
        "tool", "artifact", "stone", "spear", "bone", "remains",
        "fossil", "skeleton", "weapons", "objects",
    )
    _DATA_KEYWORDS = (
        "percent", "%", "temperature", "degrees", "celsius", "fahrenheit",
        "meters", "kilometers", "feet", "miles", "tons", "kilograms",
        "population", "people", "estimated", "average", "data",
    )
    _TEXT_KEYWORDS = (
        "definition", "term", "name", "called", "known as", "label",
        "title", "concept",
    )
    _ENVIRONMENT_KEYWORDS = (
        "landscape", "climate", "weather", "season", "sky", "forest",
        "tundra", "ice", "snow", "cave", "wilderness", "habitat",
    )
    _CHARACTER_KEYWORDS = (
        "hunter", "gatherer", "ancient human", "ancestor", "person",
        "people", "child", "woman", "man", "tribe", "family",
        "behavior", "action", "movement", "they", "their",
    )
    _ARCHIVAL_KEYWORDS = (
        "documented", "photograph", "record", "archive",
    )

    def __init__(
        self,
        job_id: str,
        use_mock: bool = False,
        use_cache: bool = False,
        knowledge_adapter: KnowledgeStoryboardAdapter | None = None,
    ) -> None:
        self.job_id = job_id
        self.use_mock = use_mock
        self.use_cache = use_cache
        self._llm = get_llm_provider()
        self._logger = get_logger(f"storyboard.{job_id}")
        # L-U2: optional Knowledge Layer adapter. When None, the engine
        # behaves exactly as before (backward compatible). When provided,
        # the adapter is consulted for camera/motion/style hints.
        self._knowledge_adapter = knowledge_adapter

    # ------------------------------------------------------------------
    # Public entrypoint
    # ------------------------------------------------------------------

    def run(
        self,
        story_package: StoryPackage,
        research_package: ResearchPackage | None = None,
    ) -> StoryboardPackage:
        """Build a StoryboardPackage from a StoryPackage.

        Steps (in order):
          1. Pre-flight (story_package has a FINAL script?)
          2. Resolve ScriptSegment list
          3. Decompose segments into VisualBeats
          4. Resolve continuity, asset requirements, camera, motion, transitions
          5. Compile SceneDefinition candidates
          6. Score quality
          7. Final validation
        """
        self._logger.info(
            f"Storyboard engine starting for story={story_package.metadata.story_package_id}"
        )

        segments = self._resolve_segments(story_package)
        if not segments:
            self._logger.error("Storyboard: no script segments to plan")
            return self._empty_package(story_package)

        intent_items = self._resolve_intent_items(story_package)
        intent_by_segment = self._index_intent(intent_items)

        # 1. Decompose each segment into 1..N visual beats
        beats = self._decompose_segments(segments, intent_by_segment)

        # 2. Camera / motion / transition plans
        beats = self._apply_camera_motion(beats)

        # 3. Text / diagram / map / timeline / comparison specs
        beats, diagram_specs, map_specs, timeline_specs, comparison_specs = (
            self._apply_specialised_specs(beats, segments, story_package)
        )

        # 4. Asset requirements
        asset_reqs = self._build_asset_requirements(beats, segments)

        # 5. Continuity state and issues
        continuity_state = ContinuityState()
        updates: list[ContinuityUpdate] = []
        dependencies: list[ContinuityDependency] = []
        issues: list[ContinuityIssue] = []
        self._resolve_continuity(
            beats, continuity_state, updates, dependencies, issues
        )

        # 6. Evidence linking
        self._link_evidence(beats, story_package, research_package)

        # 7. Reconstruction safety
        self._apply_reconstruction_safety(beats, research_package)

        # 8. Compile SceneDefinition candidates
        scene_candidates = self._compile_scene_candidates(beats)

        # 9. Quality score
        quality = self._compute_quality(
            beats, scene_candidates, issues, asset_reqs, story_package
        )

        # 10. Build StoryboardMetadata
        metadata = StoryboardMetadata(
            storyboard_package_id=f"SB-{story_package.metadata.story_package_id}",
            story_package_id=story_package.metadata.story_package_id,
            story_version=story_package.metadata.version,
            job_id=story_package.metadata.job_id or self.job_id,
            topic=story_package.metadata.topic,
            input_hash=_hash_input(
                story_package.metadata.research_package_hash,
                story_package.metadata.story_package_id,
                story_package.metadata.updated_at.isoformat()
                if story_package.metadata.updated_at
                else "",
            ),
            provider=settings.story_llm_model.split(":")[0]
            if ":" in settings.story_llm_model
            else "openai",
            model=settings.story_llm_model,
            status=StoryboardStatus.DRAFT,
        )

        warnings = [i.detail for i in issues if i.severity == "warning"]
        failures = [i.detail for i in issues if i.severity == "failure"]
        warnings.extend(quality.warnings)
        failures.extend(quality.failures)

        pkg = StoryboardPackage(
            metadata=metadata,
            story_package_id=story_package.metadata.story_package_id,
            story_version=story_package.metadata.version,
            segments=[s.segment_id for s in segments],
            visual_beats=beats,
            continuity_state=continuity_state,
            continuity_updates=updates,
            continuity_dependencies=dependencies,
            continuity_issues=issues,
            asset_requirements=asset_reqs,
            camera_plan=[b.camera for b in beats if b.camera is not None],
            transition_plan=[
                {
                    "beat_id": b.beat_id,
                    "transition": b.transition.value,
                    "reason": b.transition_reason,
                }
                for b in beats
            ],
            text_plan=[t for b in beats for t in b.text],
            audio_sync_points=self._build_audio_sync_points(beats),
            diagram_specs=diagram_specs,
            map_specs=map_specs,
            timeline_specs=timeline_specs,
            comparison_specs=comparison_specs,
            data_visualization_specs=self._build_data_specs(beats, research_package),
            scene_definition_candidates=scene_candidates,
            storyboard_quality_score=quality,
            warnings=list(dict.fromkeys(warnings)),
            failures=list(dict.fromkeys(failures)),
            status=StoryboardStatus.BLOCKED if failures else StoryboardStatus.DRAFT,
        )

        self._logger.info(
            f"Storyboard built: {len(beats)} beats, "
            f"{len(asset_reqs)} asset requirements, "
            f"quality={quality.overall_score:.2f}, "
            f"warnings={len(warnings)}, failures={len(failures)}"
        )
        return pkg

    # ------------------------------------------------------------------
    # Helpers — segment resolution
    # ------------------------------------------------------------------

    def _empty_package(self, story_package: StoryPackage) -> StoryboardPackage:
        """Return an empty (but valid) StoryboardPackage when no segments exist."""
        metadata = StoryboardMetadata(
            storyboard_package_id=f"SB-{story_package.metadata.story_package_id}",
            story_package_id=story_package.metadata.story_package_id,
            story_version=story_package.metadata.version,
            job_id=story_package.metadata.job_id or self.job_id,
            topic=story_package.metadata.topic,
            status=StoryboardStatus.BLOCKED,
        )
        return StoryboardPackage(
            metadata=metadata,
            story_package_id=story_package.metadata.story_package_id,
            story_version=story_package.metadata.version,
            status=StoryboardStatus.BLOCKED,
            failures=["No script segments available to plan storyboard"],
        )

    def _resolve_segments(self, story_package: StoryPackage) -> list[ScriptSegment]:
        """Pick the FINAL version if present; else REVISION; else DRAFT."""
        for version_type in (
            ScriptVersion.FINAL,
            ScriptVersion.REVISION,
            ScriptVersion.DRAFT,
        ):
            v = story_package.script.get_version(version_type)
            if v and v.segments:
                return sorted(v.segments, key=lambda s: s.order)
        return []

    def _resolve_intent_items(
        self, story_package: StoryPackage
    ) -> list[StoryboardIntentItem]:
        intent = story_package.storyboard_intent
        if not intent:
            return []
        return list(intent.items)

    def _index_intent(
        self, items: list[StoryboardIntentItem]
    ) -> dict[str, StoryboardIntentItem]:
        return {i.segment_id: i for i in items if i.segment_id}

    # ------------------------------------------------------------------
    # Step 1 — Visual decomposition
    # ------------------------------------------------------------------

    def _decompose_segments(
        self,
        segments: list[ScriptSegment],
        intent_by_segment: dict[str, StoryboardIntentItem],
    ) -> list[VisualBeat]:
        """Decompose each script segment into one or more VisualBeats.

        Most segments produce 1 beat. Long segments with multiple distinct
        information goals can produce 2+ beats.
        """
        beats: list[VisualBeat] = []
        counter = [0]
        running_time = 0.0

        for seg in segments:
            intent = intent_by_segment.get(seg.segment_id)
            seg_beats = self._decompose_single_segment(seg, intent, running_time, counter)
            beats.extend(seg_beats)
            if seg_beats:
                running_time = seg_beats[-1].end_time
            else:
                running_time += seg.estimated_duration_sec

        # Re-assign order values.
        for i, beat in enumerate(beats):
            beat.order = i
        return beats

    def _decompose_single_segment(
        self,
        seg: ScriptSegment,
        intent: StoryboardIntentItem | None,
        start_time: float,
        counter: list[int],
    ) -> list[VisualBeat]:
        """Build VisualBeat(s) for one script segment."""
        # Decide how many beats the segment needs.
        n_beats = self._estimate_beat_count(seg, intent)

        seg_duration = max(seg.estimated_duration_sec, 2.0)
        per_beat = seg_duration / n_beats

        # Pre-compute visual mode + rationale (once per segment, applied to all its beats).
        mode, rationale = self._select_visual_mode(seg, intent)

        # Optional: ask LLM for refined per-beat sub-mode (capped to 1 call/segment).
        sub_modes = self._maybe_ask_sub_modes(seg, intent, n_beats, mode)

        beats: list[VisualBeat] = []
        for k in range(n_beats):
            b_start = start_time + k * per_beat
            b_end = b_start + per_beat
            beat_id = _next_beat_id(counter)
            sub_mode = sub_modes[k] if sub_modes else mode

            beat = VisualBeat(
                beat_id=beat_id,
                segment_id=seg.segment_id,
                order=0,  # re-assigned later
                start_time=round(b_start, 2),
                end_time=round(b_end, 2),
                duration=round(per_beat, 2),
                purpose=intent.purpose if intent and intent.purpose else seg.purpose.value,
                visual_function=self._select_function(sub_mode, seg),
                visual_mode=sub_mode,
                visual_rationale=rationale,
                composition=self._compose(sub_mode, seg),
                characters=self._character_requirements(seg, sub_mode, intent),
                environment=self._environment_requirement(sub_mode, intent),
                props=self._prop_requirements(seg, intent, sub_mode),
                action=intent.visual_goal if intent else seg.visual_intent,
                camera=None,  # filled in by _apply_camera_motion
                motion=[],
                text=[],
                transition=StoryboardTransition.CUT,
                source_ids=list(seg.source_ids),
                claim_ids=list(seg.claim_ids),
                evidence_trace=[],
                continuity_requirements=[],
                asset_requirements=[],
                information_alignment=self._information_alignment(sub_mode, seg),
                reconstruction_confidence=StoryboardReconstructionConfidence.ILLUSTRATIVE,
            )
            beats.append(beat)

        return beats

    def _estimate_beat_count(
        self, seg: ScriptSegment, intent: StoryboardIntentItem | None
    ) -> int:
        """Heuristic: 1 beat for short segments, 2 for medium, 3 for long.
        Cap at 3 — quality > volume."""
        dur = seg.estimated_duration_sec
        if dur <= 8.0:
            return 1
        if dur <= 16.0:
            return 2
        return 3

    # ------------------------------------------------------------------
    # Step 2 — Visual mode selection (heuristic + optional LLM)
    # ------------------------------------------------------------------

    def _select_visual_mode(
        self, seg: ScriptSegment, intent: StoryboardIntentItem | None
    ) -> tuple[StoryboardVisualMode, str]:
        """Pick the best visual mode for the segment and explain why."""
        text = " ".join(
            [
                seg.narration or "",
                seg.visual_intent or "",
                (intent.visual_goal if intent else ""),
            ]
        ).lower()

        scores: dict[StoryboardVisualMode, int] = {}
        for kw in self._DIAGRAM_KEYWORDS:
            if kw in text:
                scores[StoryboardVisualMode.DIAGRAM] = scores.get(StoryboardVisualMode.DIAGRAM, 0) + 1
        for kw in self._MAP_KEYWORDS:
            if kw in text:
                scores[StoryboardVisualMode.MAP] = scores.get(StoryboardVisualMode.MAP, 0) + 1
        for kw in self._TIMELINE_KEYWORDS:
            if kw in text:
                scores[StoryboardVisualMode.TIMELINE] = scores.get(StoryboardVisualMode.TIMELINE, 0) + 1
        for kw in self._COMPARISON_KEYWORDS:
            if kw in text:
                scores[StoryboardVisualMode.COMPARISON] = scores.get(StoryboardVisualMode.COMPARISON, 0) + 1
        for kw in self._ARTIFACT_KEYWORDS:
            if kw in text:
                scores[StoryboardVisualMode.ARTIFACT] = scores.get(StoryboardVisualMode.ARTIFACT, 0) + 1
        for kw in self._DATA_KEYWORDS:
            if kw in text:
                scores[StoryboardVisualMode.DATA_VISUALIZATION] = scores.get(StoryboardVisualMode.DATA_VISUALIZATION, 0) + 1
        for kw in self._TEXT_KEYWORDS:
            if kw in text:
                scores[StoryboardVisualMode.TEXT_GRAPHIC] = scores.get(StoryboardVisualMode.TEXT_GRAPHIC, 0) + 1
        for kw in self._ENVIRONMENT_KEYWORDS:
            if kw in text:
                scores[StoryboardVisualMode.ENVIRONMENT] = scores.get(StoryboardVisualMode.ENVIRONMENT, 0) + 1
        for kw in self._CHARACTER_KEYWORDS:
            if kw in text:
                scores[StoryboardVisualMode.CHARACTER] = scores.get(StoryboardVisualMode.CHARACTER, 0) + 1
        for kw in self._ARCHIVAL_KEYWORDS:
            if kw in text:
                scores[StoryboardVisualMode.ARCHIVAL] = scores.get(StoryboardVisualMode.ARCHIVAL, 0) + 1

        # Honour the intent if the LLM Story Engine picked something specific.
        if intent and intent.visual_mode:
            try:
                story_mode = StoryVisualMode(intent.visual_mode)
            except ValueError:
                story_mode = None
            mapped = self._map_story_mode(story_mode) if story_mode else None
            if mapped:
                scores[mapped] = scores.get(mapped, 0) + 3

        if not scores:
            mode = StoryboardVisualMode.CHARACTER
            rationale = (
                "Default CHARACTER mode chosen because no specialised visual "
                "indicator was found in narration."
            )
        else:
            # Pick the highest score; ties broken by enumeration order (favouring CHARACTER).
            mode = max(
                scores.items(),
                key=lambda kv: (kv[1], -list(StoryboardVisualMode).index(kv[0])),
            )[0]
            rationale = (
                f"{mode.value} mode chosen: keyword score={scores[mode]} "
                f"(strongest match in narration)."
            )
        return mode, rationale

    def _map_story_mode(
        self, mode: StoryVisualMode | None
    ) -> StoryboardVisualMode | None:
        if mode is None:
            return None
        mapping = {
            StoryVisualMode.CHARACTER: StoryboardVisualMode.CHARACTER,
            StoryVisualMode.ENVIRONMENT: StoryboardVisualMode.ENVIRONMENT,
            StoryVisualMode.DIAGRAM: StoryboardVisualMode.DIAGRAM,
            StoryVisualMode.MAP: StoryboardVisualMode.MAP,
            StoryVisualMode.TIMELINE: StoryboardVisualMode.TIMELINE,
            StoryVisualMode.COMPARISON: StoryboardVisualMode.COMPARISON,
            StoryVisualMode.ARTIFACT: StoryboardVisualMode.ARTIFACT,
            StoryVisualMode.TEXT: StoryboardVisualMode.TEXT_GRAPHIC,
            StoryVisualMode.HYBRID: StoryboardVisualMode.HYBRID,
        }
        return mapping.get(mode)

    def _maybe_ask_sub_modes(
        self,
        seg: ScriptSegment,
        intent: StoryboardIntentItem | None,
        n_beats: int,
        default_mode: StoryboardVisualMode,
    ) -> list[StoryboardVisualMode] | None:
        """Optional refinement: ask the LLM for per-beat sub-modes.

        Returns None on any failure — fall back to default_mode for every beat.
        Never raises — quality > speed.
        """
        if n_beats <= 1:
            return None  # single beat, no sub-decomposition needed
        if not self._llm:
            return None

        prompt = (
            "You are a storyboard visual planner.\n"
            "Decompose the following narration segment into {n} visual beats.\n"
            "Each beat should have a visual_mode from:\n"
            "character, environment, diagram, map, timeline, comparison,\n"
            "artifact, text_graphic, data_visualization, archival, hybrid.\n\n"
            "Return JSON: {{\"sub_modes\": [\"...\", \"...\", \"...\"]}}\n\n"
            "Segment purpose: {purpose}\n"
            "Narration: {narration}\n"
            "Default visual mode: {default}\n"
        ).format(
            n=n_beats,
            purpose=seg.purpose.value,
            narration=seg.narration,
            default=default_mode.value,
        )

        try:
            messages = [
                LLMMessage(role="system", content="Return JSON only."),
                LLMMessage(role="user", content=prompt),
            ]
            data = self._llm_complete(messages, task="storyboard_sub_mode")
            if not data or "sub_modes" not in data:
                return None
            modes = [_safe_mode(m) for m in data["sub_modes"][:n_beats]]
            while len(modes) < n_beats:
                modes.append(default_mode)
            return modes
        except Exception as exc:  # noqa: BLE001
            self._logger.warning(f"Sub-mode refinement failed: {exc}")
            return None

    # ------------------------------------------------------------------
    # Step 3 — Camera / motion / transition planning
    # ------------------------------------------------------------------

    def _apply_camera_motion(self, beats: list[VisualBeat]) -> list[VisualBeat]:
        """Apply mode-based defaults; add editorial intent.

        L-U2: when ``self._knowledge_adapter`` is set, consult it for
        camera + motion hints derived from the Knowledge Layer. When
        not set, behavior is identical to pre-L-U2.
        """
        for beat in beats:
            defaults = self._MODE_DEFAULTS.get(beat.visual_mode, {})

            # Camera: prefer knowledge-derived choice if adapter present
            if self._knowledge_adapter is not None and self._knowledge_adapter.is_active():
                cam_type = self._knowledge_adapter.get_camera_for_mode(beat.visual_mode)
                cam_reason = self._knowledge_adapter.get_camera_reason(beat.visual_mode)
                if cam_reason is not None:
                    cam_reason_text = cam_reason
                else:
                    cam_reason_text = self._camera_reason(beat, cam_type)
            else:
                cam_type = defaults.get("camera", StoryboardCameraType.STATIC)
                cam_reason_text = self._camera_reason(beat, cam_type)
            camera = CameraPlan(
                camera_id=f"cam_{beat.beat_id}",
                type=cam_type,
                duration_sec=beat.duration,
                focus="center",
                easing="ease_in_out",
                reason=cam_reason_text,
                start_zoom=1.0,
                end_zoom=self._zoom_for_type(cam_type),
            )
            beat.camera = camera

            # Motion: prefer knowledge-derived choice if adapter present
            if self._knowledge_adapter is not None and self._knowledge_adapter.is_active():
                motion_type = self._knowledge_adapter.get_motion_for_mode(beat.visual_mode)
                motion_intensity = self._knowledge_adapter.get_motion_intensity(beat.visual_mode)
            else:
                motion_type = defaults.get("motion", StoryboardMotionType.NONE)
                motion_intensity = 0.5
            if motion_type != StoryboardMotionType.NONE:
                beat.motion = [
                    MotionItem(
                        motion_type=motion_type,
                        target="subject",
                        duration_sec=beat.duration,
                        intensity=motion_intensity,
                        purpose=self._motion_purpose(motion_type),
                    )
                ]

            # Transition (between beats)
            beat.transition = self._select_transition(beat)
            beat.transition_reason = self._transition_reason(beat.transition, beat)
        return beats

    def _camera_reason(self, beat: VisualBeat, cam_type: StoryboardCameraType) -> str:
        if cam_type == StoryboardCameraType.PUSH_IN:
            return f"Push-in emphasises the {beat.visual_mode.value} subject"
        if cam_type == StoryboardCameraType.PULL_OUT:
            return "Pull-out reveals context around the subject"
        if cam_type == StoryboardCameraType.PAN:
            return "Pan follows action across the frame"
        if cam_type == StoryboardCameraType.PARALLAX:
            return "Parallax communicates depth"
        if cam_type == StoryboardCameraType.ORBIT:
            return "Orbit reveals 3D form"
        return "Static camera holds focus on the subject"

    def _zoom_for_type(self, cam_type: StoryboardCameraType) -> float:
        if cam_type == StoryboardCameraType.PUSH_IN:
            return 1.3
        if cam_type == StoryboardCameraType.PULL_OUT:
            return 0.85
        return 1.0

    def _motion_purpose(self, motion_type: StoryboardMotionType) -> str:
        mapping = {
            StoryboardMotionType.CHARACTER_ACTION: "Drives the story forward through action",
            StoryboardMotionType.CHARACTER_WALK: "Communicates travel",
            StoryboardMotionType.CHARACTER_GESTURE: "Adds human expressiveness",
            StoryboardMotionType.CAMERA_PUSH: "Emphasises discovery",
            StoryboardMotionType.CAMERA_PULL: "Reveals context",
            StoryboardMotionType.PARALLAX_DRIFT: "Communicates depth",
            StoryboardMotionType.PROP_FALL: "Communicates failure / danger",
            StoryboardMotionType.PROP_RISE: "Communicates success / ascension",
            StoryboardMotionType.PROP_ROTATE: "Reveals 3D form",
            StoryboardMotionType.OVERLAY_APPEAR: "Draws attention to overlay",
            StoryboardMotionType.OVERLAY_DISAPPEAR: "Clears overlay for next beat",
            StoryboardMotionType.ZOOM_FOCUS: "Focuses attention",
            StoryboardMotionType.SHAKE_INTENSITY: "Communicates danger / impact",
        }
        return mapping.get(motion_type, "")

    def _select_transition(self, beat: VisualBeat) -> StoryboardTransition:
        """Default to CUT. Use CROSSFADE only at emotional pivots."""
        text = beat.purpose.lower()
        if "reveal" in text or "revelation" in text:
            return StoryboardTransition.MATCH_CUT
        if "reflection" in text or "ending" in text:
            return StoryboardTransition.CROSSFADE
        if beat.visual_mode == StoryboardVisualMode.MAP:
            return StoryboardTransition.WIPE
        return StoryboardTransition.CUT

    def _transition_reason(
        self, transition: StoryboardTransition, beat: VisualBeat
    ) -> str:
        if transition == StoryboardTransition.CUT:
            return "Default CUT — clean transition between beats"
        if transition == StoryboardTransition.MATCH_CUT:
            return "MATCH_CUT for revelation beats — visual continuity"
        if transition == StoryboardTransition.CROSSFADE:
            return "CROSSFADE for reflective or emotional beat"
        if transition == StoryboardTransition.WIPE:
            return "WIPE for spatial transition (e.g. between map regions)"
        return ""

    # ------------------------------------------------------------------
    # Step 4 — Specialised specs (diagram / map / timeline / comparison / data)
    # ------------------------------------------------------------------

    def _apply_specialised_specs(
        self,
        beats: list[VisualBeat],
        segments: list[ScriptSegment],
        story_package: StoryPackage,
    ) -> tuple[
        list[VisualBeat],
        list[DiagramSpec],
        list[MapSpec],
        list[TimelineSpec],
        list[ComparisonSpec],
    ]:
        diagram_specs: list[DiagramSpec] = []
        map_specs: list[MapSpec] = []
        timeline_specs: list[TimelineSpec] = []
        comparison_specs: list[ComparisonSpec] = []

        for beat in beats:
            seg = next((s for s in segments if s.segment_id == beat.segment_id), None)
            if not seg:
                continue
            if beat.visual_mode == StoryboardVisualMode.DIAGRAM:
                spec = self._build_diagram_spec(beat, seg)
                diagram_specs.append(spec)
            elif beat.visual_mode == StoryboardVisualMode.MAP:
                spec = self._build_map_spec(beat, seg)
                map_specs.append(spec)
            elif beat.visual_mode == StoryboardVisualMode.TIMELINE:
                spec = self._build_timeline_spec(beat, seg)
                timeline_specs.append(spec)
            elif beat.visual_mode == StoryboardVisualMode.COMPARISON:
                spec = self._build_comparison_spec(beat, seg)
                comparison_specs.append(spec)
        return beats, diagram_specs, map_specs, timeline_specs, comparison_specs

    def _build_diagram_spec(
        self, beat: VisualBeat, seg: ScriptSegment
    ) -> DiagramSpec:
        """Extract a simple flow from narration."""
        # Naive: split narration into "stages" by sentence.
        sentences = [s.strip() for s in re.split(r"[.!?]", seg.narration) if s.strip()]
        nodes = [f"step_{i + 1}" for i in range(len(sentences))]
        labels = sentences[:5]
        arrows = []
        for i in range(len(sentences) - 1):
            arrows.append({"from": f"step_{i + 1}", "to": f"step_{i + 2}"})
        return DiagramSpec(
            nodes=nodes,
            relationships=[f"{a['from']} -> {a['to']}" for a in arrows],
            labels=labels,
            arrows=arrows,
            sequence=labels,
            emphasis=[],
            animation_order=nodes,
        )

    def _build_map_spec(self, beat: VisualBeat, seg: ScriptSegment) -> MapSpec:
        return MapSpec(
            region="unspecified",
            locations=[],
            routes=[],
            relative_positions=[],
            labels=[],
            highlight_areas=[],
            coordinates_are_real=False,
        )

    def _build_timeline_spec(
        self, beat: VisualBeat, seg: ScriptSegment
    ) -> TimelineSpec:
        return TimelineSpec(
            events=[],
            ordering=[],
            approximate_dates=[],
            labels=[],
            highlighted_period="",
        )

    def _build_comparison_spec(
        self, beat: VisualBeat, seg: ScriptSegment
    ) -> ComparisonSpec:
        return ComparisonSpec(
            axis="size",
            items=[],
            values=[],
            units=[],
            source_ids=list(seg.source_ids),
        )

    def _build_data_specs(
        self,
        beats: list[VisualBeat],
        research_package: ResearchPackage | None,
    ) -> list[DataVisualizationSpec]:
        if not research_package:
            return []
        specs: list[DataVisualizationSpec] = []
        for q in research_package.quantitative_facts or []:
            specs.append(
                DataVisualizationSpec(
                    metric=q.metric,
                    unit=q.unit,
                    value=q.value,
                    range=q.range,
                    uncertainty=q.uncertainty,
                    source_ids=list(q.source_ids),
                    visual_type="bar",
                    annotation=q.context,
                )
            )
        return specs

    # ------------------------------------------------------------------
    # Step 5 — Asset / character / environment / prop requirements
    # ------------------------------------------------------------------

    def _character_requirements(
        self,
        seg: ScriptSegment,
        mode: StoryboardVisualMode,
        intent: StoryboardIntentItem | None,
    ) -> list[CharacterRequirement]:
        """Decide which characters appear in this beat."""
        defaults = self._MODE_DEFAULTS.get(mode, {})
        if not defaults.get("needs_characters"):
            return []

        characters: list[CharacterRequirement] = [
            CharacterRequirement(
                character_id=self.NARRATOR_ID,
                required_pose="stand",
                required_expression="neutral",
                required_clothing="default",
                required_action="narrating",
                required_scale=1.0,
                screen_position="center",
                orientation="3/4_left",
                continuity_constraints=["default_narrator_look"],
            )
        ]
        if intent and intent.characters:
            for cid in intent.characters:
                if cid == self.NARRATOR_ID:
                    continue
                characters.append(
                    CharacterRequirement(
                        character_id=cid,
                        required_pose="stand",
                        required_expression="neutral",
                        required_clothing="default",
                        required_action="present",
                        required_scale=1.0,
                        screen_position="right",
                        orientation="3/4_right",
                        continuity_constraints=[],
                    )
                )
        return characters

    def _environment_requirement(
        self, mode: StoryboardVisualMode, intent: StoryboardIntentItem | None
    ) -> EnvironmentRequirement:
        """Decide which environment this beat uses."""
        env_id = self._resolve_environment_id(mode, intent)
        env_key = env_id  # renderer-readable id

        return EnvironmentRequirement(
            environment_id=env_key,
            location=intent.environment if intent else "",
            time_of_day="day",
            season="",
            weather="clear",
            lighting="natural",
            foreground_requirements=[],
            background_requirements=[],
            atmosphere="neutral",
            required_props=[],
            continuity_constraints=[],
            mood="calm",
        )

    def _prop_requirements(
        self,
        seg: ScriptSegment,
        intent: StoryboardIntentItem | None,
        mode: StoryboardVisualMode,
    ) -> list[PropRequirement]:
        """Identify props needed for this beat."""
        props: list[PropRequirement] = []
        if mode == StoryboardVisualMode.ARTIFACT:
            props.append(
                PropRequirement(
                    prop_id=f"prop_{seg.segment_id}_artifact",
                    type="artifact",
                    size="medium",
                    position="center",
                    orientation="3/4_left",
                    interaction="static",
                    continuity="new",
                )
            )
        if mode == StoryboardVisualMode.ENVIRONMENT and "fire" in seg.narration.lower():
            props.append(
                PropRequirement(
                    prop_id=f"prop_{seg.segment_id}_fire",
                    type="fire",
                    size="small",
                    position="bottom_center",
                    orientation="3/4_left",
                    interaction="burning",
                    continuity="new",
                )
            )
        if intent and intent.props:
            for p in intent.props:
                props.append(
                    PropRequirement(
                        prop_id=p,
                        type="generic",
                        size="medium",
                        position="center",
                        orientation="3/4_left",
                        interaction="static",
                        continuity="new",
                    )
                )
        return props

    def _resolve_environment_id(
        self, mode: StoryboardVisualMode, intent: StoryboardIntentItem | None
    ) -> str:
        """Pick a renderer-readable environment_id."""
        # Honour intent if provided.
        if intent and intent.environment:
            env_lower = intent.environment.lower()
            for kw, eid in self._ENV_HINT_TO_ID.items():
                if kw in env_lower:
                    return eid
        # Default per mode.
        return self._MODE_TO_ENV.get(mode, "diagram_white")

    def _build_asset_requirements(
        self,
        beats: list[VisualBeat],
        segments: list[ScriptSegment],
    ) -> list[AssetRequirement]:
        """Aggregate all character / environment / prop needs into AssetRequirement list."""
        assets: dict[str, AssetRequirement] = {}

        # 1. Always include the narrator.
        assets[self.NARRATOR_ID] = AssetRequirement(
            asset_id=self.NARRATOR_ID,
            asset_class=StoryboardAssetClass.CHARACTER,
            type="narrator",
            purpose="voice-over presenter",
            source="reuse_existing",
            requirement=StoryboardAssetRequirement.REUSE_EXISTING,
            asset_reuse_key="narrator",
            continuity_priority=1.0,
            reuse_priority=1.0,
            description="Reusable narrator character",
        )

        for beat in beats:
            for char in beat.characters:
                if char.character_id not in assets:
                    assets[char.character_id] = AssetRequirement(
                        asset_id=char.character_id,
                        asset_class=StoryboardAssetClass.CHARACTER,
                        type="character",
                        purpose=char.required_action or "present",
                        source="create_new",
                        requirement=StoryboardAssetRequirement.CREATE_NEW,
                        asset_reuse_key=char.character_id,
                        continuity_priority=0.7,
                        reuse_priority=0.8,
                        description=f"Character from {beat.segment_id}",
                    )
            if beat.environment and beat.environment.environment_id:
                eid = beat.environment.environment_id
                if eid not in assets:
                    assets[eid] = AssetRequirement(
                        asset_id=eid,
                        asset_class=StoryboardAssetClass.ENVIRONMENT,
                        type="background",
                        purpose=beat.environment.location or "scene background",
                        source="create_new",
                        requirement=StoryboardAssetRequirement.CREATE_NEW,
                        asset_reuse_key=eid,
                        continuity_priority=0.6,
                        reuse_priority=0.7,
                        description=f"Environment for {beat.visual_mode.value} beats",
                    )
            for prop in beat.props:
                if prop.prop_id not in assets:
                    assets[prop.prop_id] = AssetRequirement(
                        asset_id=prop.prop_id,
                        asset_class=StoryboardAssetClass.PROP,
                        type=prop.type,
                        purpose=prop.interaction,
                        source="create_new",
                        requirement=StoryboardAssetRequirement.CREATE_NEW,
                        asset_reuse_key=prop.prop_id,
                        continuity_priority=0.5,
                        reuse_priority=0.6,
                        description=f"Prop for {beat.beat_id}",
                    )

        # Link assets back to beats.
        for beat in beats:
            asset_ids: list[str] = []
            for c in beat.characters:
                asset_ids.append(c.character_id)
            if beat.environment:
                asset_ids.append(beat.environment.environment_id)
            for p in beat.props:
                asset_ids.append(p.prop_id)
            beat.asset_requirements = asset_ids

        return list(assets.values())

    # ------------------------------------------------------------------
    # Step 6 — Continuity resolution & validation
    # ------------------------------------------------------------------

    def _resolve_continuity(
        self,
        beats: list[VisualBeat],
        state: ContinuityState,
        updates: list[ContinuityUpdate],
        dependencies: list[ContinuityDependency],
        issues: list[ContinuityIssue],
    ) -> None:
        """Track state across beats and flag discontinuities."""
        prev_beat: VisualBeat | None = None
        prev_char_ids: set[str] = set()
        prev_env_id: str | None = None
        prev_weather: str | None = None
        prev_time: str | None = None
        prev_scale: float = 1.0
        prev_props: set[str] = set()

        for beat in beats:
            char_ids = {c.character_id for c in beat.characters}
            env_id = beat.environment.environment_id if beat.environment else None
            scale = 1.0  # we don't model per-character scale changes
            weather = beat.environment.weather if beat.environment else None
            time_of_day = beat.environment.time_of_day if beat.environment else None
            prop_ids = {p.prop_id for p in beat.props}

            if prev_beat is not None:
                # Disappearing character?
                disappeared = prev_char_ids - char_ids - {self.NARRATOR_ID}
                for cid in disappeared:
                    issues.append(
                        ContinuityIssue(
                            flag=StoryboardContinuityFlag.CHARACTER_DISAPPEARED,
                            severity="warning",
                            beat_id=beat.beat_id,
                            detail=f"Character '{cid}' disappeared in beat {beat.beat_id}",
                            suggestion="Add an introduction/exit beat or keep the character",
                        )
                    )
                # New character introduced without scene transition?
                introduced = char_ids - prev_char_ids - {self.NARRATOR_ID}
                for cid in introduced:
                    pass  # introduction is fine
                # Environment change?
                if env_id != prev_env_id and prev_env_id is not None:
                    issues.append(
                        ContinuityIssue(
                            flag=StoryboardContinuityFlag.ENVIRONMENT_CHANGED,
                            severity="warning",
                            beat_id=beat.beat_id,
                            detail=(
                                f"Environment changed from '{prev_env_id}' to "
                                f"'{env_id}' in beat {beat.beat_id}"
                            ),
                            suggestion="Add a transition beat if the change is not intentional",
                        )
                    )
                # Weather change?
                if weather != prev_weather and prev_weather is not None:
                    issues.append(
                        ContinuityIssue(
                            flag=StoryboardContinuityFlag.WEATHER_CHANGED,
                            severity="warning",
                            beat_id=beat.beat_id,
                            detail=(
                                f"Weather changed from '{prev_weather}' to "
                                f"'{weather}' in beat {beat.beat_id}"
                            ),
                            suggestion="Use CONTINUITY_CUT transition or explain the change",
                        )
                    )
                # Time-of-day change?
                if time_of_day != prev_time and prev_time is not None:
                    issues.append(
                        ContinuityIssue(
                            flag=StoryboardContinuityFlag.TIME_OF_DAY_CHANGED,
                            severity="warning",
                            beat_id=beat.beat_id,
                            detail=(
                                f"Time of day changed from '{prev_time}' to "
                                f"'{time_of_day}' in beat {beat.beat_id}"
                            ),
                            suggestion="Add a transition beat for time skip",
                        )
                    )

            updates.append(
                ContinuityUpdate(
                    beat_id=beat.beat_id,
                    updated_fields=[],
                    detail=f"Beat {beat.beat_id}: {len(char_ids)} chars, env={env_id}, {len(prop_ids)} props",
                )
            )
            dependencies.append(
                ContinuityDependency(
                    beat_id=beat.beat_id,
                    depends_on=[prev_beat.beat_id] if prev_beat else [],
                    detail=f"Depends on previous beat's state" if prev_beat else "Initial beat — no dependencies",
                )
            )

            # Track state.
            for c in beat.characters:
                state.characters[c.character_id] = c
            for p in beat.props:
                state.props[p.prop_id] = p
            if beat.environment:
                state.environment = beat.environment
                state.time_of_day = beat.environment.time_of_day
                state.weather = beat.environment.weather
                state.lighting = beat.environment.lighting

            prev_beat = beat
            prev_char_ids = char_ids
            prev_env_id = env_id
            prev_weather = weather
            prev_time = time_of_day
            prev_scale = scale
            prev_props = prop_ids

    # ------------------------------------------------------------------
    # Step 7 — Evidence linking
    # ------------------------------------------------------------------

    def _link_evidence(
        self,
        beats: list[VisualBeat],
        story_package: StoryPackage,
        research_package: ResearchPackage | None,
    ) -> None:
        """Link beats to claim_ids and source_ids.

        For each beat, inherit claim_ids from its source ScriptSegment,
        then resolve source_ids via the research_package's claim_source_links.
        """
        if not research_package:
            return

        # Index: claim_id -> set(source_id)
        claim_sources: dict[str, set[str]] = {}
        for link in research_package.claim_source_links or []:
            claim_sources.setdefault(link.claim_id, set()).add(link.source_id)

        for beat in beats:
            evidence: list[str] = []
            for cid in beat.claim_ids:
                sources = claim_sources.get(cid, set())
                for sid in sources:
                    if sid not in beat.source_ids:
                        beat.source_ids.append(sid)
                    evidence.append(f"{cid}->{sid}")
            beat.evidence_trace = evidence

    # ------------------------------------------------------------------
    # Step 8 — Reconstruction safety
    # ------------------------------------------------------------------

    def _apply_reconstruction_safety(
        self,
        beats: list[VisualBeat],
        research_package: ResearchPackage | None,
    ) -> None:
        """Mark beats that show prehistoric/historical scenes as ILLUSTRATIVE
        unless research explicitly supports a DOCUMENTED reconstruction."""
        if not research_package:
            for beat in beats:
                beat.reconstruction_confidence = (
                    StoryboardReconstructionConfidence.ILLUSTRATIVE
                )
                if beat.visual_mode in {
                    StoryboardVisualMode.CHARACTER,
                    StoryboardVisualMode.ENVIRONMENT,
                    StoryboardVisualMode.ARTIFACT,
                }:
                    beat.uncertainty_treatment = (
                        StoryboardUncertaintyTreatment.ILLUSTRATIVE_RECONSTRUCTION
                    )
            return

        # If research has documented sources, mark CHARACTER/ENVIRONMENT/ARTIFACT
        # beats with confidence based on average source tier.
        tier_score = self._avg_source_tier_score(research_package)
        confidence = (
            StoryboardReconstructionConfidence.DOCUMENTED
            if tier_score >= 0.8
            else StoryboardReconstructionConfidence.INFERRED
            if tier_score >= 0.5
            else StoryboardReconstructionConfidence.ILLUSTRATIVE
        )

        for beat in beats:
            if beat.visual_mode in {
                StoryboardVisualMode.CHARACTER,
                StoryboardVisualMode.ENVIRONMENT,
                StoryboardVisualMode.ARTIFACT,
            }:
                beat.reconstruction_confidence = confidence
                if confidence == StoryboardReconstructionConfidence.ILLUSTRATIVE:
                    beat.uncertainty_treatment = (
                        StoryboardUncertaintyTreatment.ILLUSTRATIVE_RECONSTRUCTION
                    )
                elif confidence == StoryboardReconstructionConfidence.INFERRED:
                    beat.uncertainty_treatment = (
                        StoryboardUncertaintyTreatment.APPROXIMATION
                    )
                else:
                    beat.uncertainty_treatment = None
            else:
                beat.reconstruction_confidence = confidence

    def _avg_source_tier_score(self, research_package: ResearchPackage) -> float:
        if not research_package.sources:
            return 0.5
        tier_scores = {"tier1": 1.0, "tier2": 0.75, "tier3": 0.5, "tier4": 0.25}
        scores = [
            tier_scores.get(s.tier.value, 0.5) for s in research_package.sources
        ]
        return sum(scores) / max(len(scores), 1)

    # ------------------------------------------------------------------
    # Step 9 — Compile SceneDefinition candidates
    # ------------------------------------------------------------------

    def _compile_scene_candidates(
        self, beats: list[VisualBeat]
    ) -> list[SceneDefinitionCandidate]:
        """Convert each beat into a SceneDefinition candidate that the existing
        SceneDefinition schema accepts."""
        candidates: list[SceneDefinitionCandidate] = []
        for i, beat in enumerate(beats):
            scene_id = f"scene_{i + 1:03d}"
            candidate = SceneDefinitionCandidate(
                scene_id=scene_id,
                beat_id=beat.beat_id,
                segment_id=beat.segment_id,
                start_sec=round(beat.start_time, 2),
                end_sec=round(beat.end_time, 2),
                environment_id=self._resolve_environment_id_for_compile(beat),
                kind=self._resolve_scene_kind(beat),
                narration_text="",  # filled by s7_narration later
                narration_word_count=0,
                actor_ids=[c.character_id for c in beat.characters],
                prop_kinds=[p.type for p in beat.props],
                camera_pan_xy=(0.5, 0.5) if beat.camera else None,
                camera_zoom=beat.camera.end_zoom if beat.camera else 1.0,
                overlay_text_ids=[t.text for t in beat.text],
                notes=beat.visual_rationale,
            )
            beat.scene_definition_candidate = candidate
            candidates.append(candidate)
        return candidates

    def _resolve_environment_id_for_compile(self, beat: VisualBeat) -> str:
        """Render-ready env id from beat.environment."""
        if beat.environment and beat.environment.environment_id:
            return beat.environment.environment_id
        return self._MODE_TO_ENV.get(beat.visual_mode, "diagram_white")

    def _resolve_scene_kind(self, beat: VisualBeat) -> str:
        """Map StoryboardVisualMode to SceneKind."""
        mapping = {
            StoryboardVisualMode.CHARACTER: "narration",
            StoryboardVisualMode.ENVIRONMENT: "narration",
            StoryboardVisualMode.DIAGRAM: "diagram",
            StoryboardVisualMode.MAP: "diagram",
            StoryboardVisualMode.TIMELINE: "diagram",
            StoryboardVisualMode.COMPARISON: "diagram",
            StoryboardVisualMode.ARTIFACT: "narration",
            StoryboardVisualMode.TEXT_GRAPHIC: "title",
            StoryboardVisualMode.DATA_VISUALIZATION: "diagram",
            StoryboardVisualMode.ARCHIVAL: "narration",
            StoryboardVisualMode.HYBRID: "narration",
        }
        return mapping.get(beat.visual_mode, "narration")

    # ------------------------------------------------------------------
    # Step 10 — Audio sync points
    # ------------------------------------------------------------------

    def _build_audio_sync_points(self, beats: list[VisualBeat]) -> list[AudioSyncPoint]:
        """Build minimal audio-sync alignment points at beat boundaries."""
        points: list[AudioSyncPoint] = []
        for beat in beats:
            points.append(
                AudioSyncPoint(
                    at_sec=round(beat.start_time, 2),
                    kind="beat_start",
                    word="",
                    visual_change=f"new visual for {beat.visual_mode.value}",
                    narration_excerpt="",
                )
            )
        return points

    # ------------------------------------------------------------------
    # Step 11 — Quality score
    # ------------------------------------------------------------------

    def _compute_quality(
        self,
        beats: list[VisualBeat],
        scene_candidates: list[SceneDefinitionCandidate],
        issues: list[ContinuityIssue],
        asset_reqs: list[AssetRequirement],
        story_package: StoryPackage,
    ) -> StoryboardQualityScore:
        """14-axis quality score + overall."""
        if not beats:
            return StoryboardQualityScore(
                overall_score=0.0,
                warnings=["No beats generated"],
                failures=["Storyboard is empty"],
            )

        # 1. narration_visual_alignment
        nva = sum(
            1.0 if b.information_alignment in (
                StoryboardInformationAlignment.EXPLAINS,
                StoryboardInformationAlignment.COMPLEMENTS,
            ) else 0.5
            for b in beats
        ) / max(len(beats), 1)

        # 2. visual_variety
        modes = {b.visual_mode for b in beats}
        visual_variety = min(1.0, len(modes) / 5.0)

        # 3. visual_clarity
        visual_clarity = sum(
            1.0 if b.camera else 0.0 for b in beats
        ) / max(len(beats), 1)

        # 4. information_communication
        text_density = sum(len(b.text) for b in beats) / max(len(beats), 1)
        info_comm = min(1.0, 0.5 + text_density * 0.1)

        # 5. character_continuity
        char_continuity = 1.0 - sum(
            1 for i in issues if i.flag == StoryboardContinuityFlag.CHARACTER_DISAPPEARED
        ) / max(len(beats), 1) * 0.5
        char_continuity = max(0.0, char_continuity)

        # 6. environment_continuity
        env_continuity = 1.0 - sum(
            1 for i in issues if i.flag == StoryboardContinuityFlag.ENVIRONMENT_CHANGED
        ) / max(len(beats), 1) * 0.5
        env_continuity = max(0.0, env_continuity)

        # 7. camera_quality
        camera_quality = visual_clarity

        # 8. motion_quality
        motion_quality = sum(
            1.0 if b.motion else 0.5 for b in beats
        ) / max(len(beats), 1)

        # 9. composition (heuristic — every beat has a Composition by default)
        composition = 1.0

        # 10. asset_reuse
        reuse_count = sum(
            1 for a in asset_reqs if a.requirement == StoryboardAssetRequirement.REUSE_EXISTING
        )
        asset_reuse = reuse_count / max(len(asset_reqs), 1)

        # 11. evidence_traceability
        evidence_count = sum(1 for b in beats if b.evidence_trace)
        evidence_trace = evidence_count / max(len(beats), 1)

        # 12. uncertainty_integrity
        uncert = sum(
            1.0 if b.uncertainty_treatment or b.reconstruction_confidence
            in {
                StoryboardReconstructionConfidence.DOCUMENTED,
                StoryboardReconstructionConfidence.INFERRED,
            }
            else 0.0
            for b in beats
        ) / max(len(beats), 1)

        # 13. vertical_reframe_readiness
        vrr = sum(
            1.0 if not b.composition.vertical_reframe_required else 0.5
            for b in beats
        ) / max(len(beats), 1)

        # 14. editorial_progression
        functions = {b.visual_function for b in beats}
        editorial_progression = min(1.0, len(functions) / 4.0)

        dimension_scores = {
            "narration_visual_alignment": round(nva, 3),
            "visual_variety": round(visual_variety, 3),
            "visual_clarity": round(visual_clarity, 3),
            "information_communication": round(info_comm, 3),
            "character_continuity": round(char_continuity, 3),
            "environment_continuity": round(env_continuity, 3),
            "camera_quality": round(camera_quality, 3),
            "motion_quality": round(motion_quality, 3),
            "composition": round(composition, 3),
            "asset_reuse": round(asset_reuse, 3),
            "evidence_traceability": round(evidence_trace, 3),
            "uncertainty_integrity": round(uncert, 3),
            "vertical_reframe_readiness": round(vrr, 3),
            "editorial_progression": round(editorial_progression, 3),
        }

        overall = sum(dimension_scores.values()) / max(len(dimension_scores), 1)

        warnings: list[str] = []
        failures: list[str] = []
        recommendations: list[str] = []

        for issue in issues:
            if issue.severity == "failure":
                failures.append(issue.detail)
            else:
                warnings.append(issue.detail)

        if not scene_candidates:
            failures.append("SceneDefinition compilation produced no candidates")
        if visual_variety < 0.3:
            warnings.append("Low visual variety — most beats share the same mode")
            recommendations.append("Diversify visual modes across beats")
        if evidence_trace < 0.5:
            warnings.append("Low evidence traceability — many beats lack claim/source mapping")
            recommendations.append("Link more beats to research claim_ids")

        return StoryboardQualityScore(
            overall_score=round(overall, 3),
            dimension_scores=dimension_scores,
            warnings=warnings,
            failures=failures,
            recommendations=recommendations,
        )

    # ------------------------------------------------------------------
    # Step 12 — Helpers used by composition / function / alignment
    # ------------------------------------------------------------------

    def _compose(self, mode: StoryboardVisualMode, seg: ScriptSegment) -> Composition:
        """Default composition for the mode."""
        canvas = StoryboardAspectRatio.LANDSCAPE_16_9
        focus = "center"
        text_area = "bottom_center"
        needs_vertical_reframe = False

        if mode == StoryboardVisualMode.CHARACTER:
            focus = "center"
            text_area = "bottom_center"
        elif mode == StoryboardVisualMode.ENVIRONMENT:
            focus = "center"
            text_area = "top_left"
        elif mode == StoryboardVisualMode.DIAGRAM:
            focus = "center"
            text_area = "bottom_center"
        elif mode == StoryboardVisualMode.MAP:
            focus = "center"
            text_area = "top_left"
        elif mode == StoryboardVisualMode.COMPARISON:
            focus = "split_horizontal"
            text_area = "bottom_center"
            needs_vertical_reframe = True  # splits don't survive 9:16
        elif mode == StoryboardVisualMode.ARTIFACT:
            focus = "center"
            text_area = "bottom_center"

        return Composition(
            canvas=canvas,
            safe_area={"top": 0.1, "bottom": 0.1, "left": 0.1, "right": 0.1},
            subject_positions=[focus],
            foreground=[],
            midground=[],
            background=[],
            visual_focus=focus,
            negative_space="balanced",
            text_area=text_area,
            vertical_reframe_required=needs_vertical_reframe,
        )

    def _select_function(
        self, mode: StoryboardVisualMode, seg: ScriptSegment
    ) -> StoryboardStoryFunction:
        purpose = seg.purpose.value.lower()
        if "reveal" in purpose or "revelation" in purpose:
            return StoryboardStoryFunction.REVEAL
        if "payoff" in purpose or "ending" in purpose:
            return StoryboardStoryFunction.RESOLVE
        if "hook" in purpose:
            return StoryboardStoryFunction.EMPHASIZE
        if "escalat" in purpose or "complication" in purpose:
            return StoryboardStoryFunction.ESCALATE
        if "evidence" in purpose:
            return StoryboardStoryFunction.EXPLAIN
        if "counterpoint" in purpose:
            return StoryboardStoryFunction.CONTRAST
        if "modern_reflection" in purpose:
            return StoryboardStoryFunction.REFLECT
        return self._MODE_DEFAULTS.get(mode, {}).get(
            "function", StoryboardStoryFunction.SHOW
        )

    def _information_alignment(
        self, mode: StoryboardVisualMode, seg: ScriptSegment
    ) -> StoryboardInformationAlignment:
        text = (seg.narration or "").lower()
        if mode == StoryboardVisualMode.CHARACTER and any(
            kw in text for kw in self._DIAGRAM_KEYWORDS + self._MAP_KEYWORDS
        ):
            return StoryboardInformationAlignment.DECORATES
        if mode in {
            StoryboardVisualMode.DIAGRAM,
            StoryboardVisualMode.MAP,
            StoryboardVisualMode.TIMELINE,
            StoryboardVisualMode.COMPARISON,
            StoryboardVisualMode.DATA_VISUALIZATION,
        }:
            return StoryboardInformationAlignment.EXPLAINS
        return StoryboardInformationAlignment.COMPLEMENTS

    # ------------------------------------------------------------------
    # LLM helper
    # ------------------------------------------------------------------

    def _llm_complete(
        self, messages: list[LLMMessage], task: str
    ) -> dict | None:
        """Call the LLM and return parsed JSON, or None on any failure."""
        req = LLMRequest(
            messages=messages,
            json_mode=True,
            model_hint="large",
            temperature=settings.story_temperature,
            max_tokens=2048,
        )
        try:
            resp = self._llm.complete(req)
            return resp.parsed_json if resp else None
        except Exception as exc:  # noqa: BLE001
            self._logger.warning(f"LLM call failed ({task}): {exc}")
            return None
