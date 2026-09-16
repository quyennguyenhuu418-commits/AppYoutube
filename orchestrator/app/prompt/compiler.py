"""
PromptCompiler — canonical prompt compilation engine.

L-U5 — Prompt Compiler V2: Knowledge + Character Aware.

Purpose
-------
The `PromptCompiler` transforms structured production intent into a canonical
`CanonicalPromptIR` (intermediate representation). It is the core engine
of the L-U5 Prompt Compilation subsystem.

Architecture
-----------
    PromptCompilationRequest
            ↓
    PromptCompiler
        ├── KnowledgePromptAdapter (L-U5 — thin)
        │       ↓
        │   KnowledgeContext + KnowledgeResolver (L-U3)
        │
        ├── CharacterReferenceSpecification (L-U4)
        │
        └── VisualGrammar (L-U1)
            ↓
    CanonicalPromptIR
            ↓
    PromptCompilationResult (with validation)

The compiler is DETERMINISTIC: same inputs → same IR.
The compiler is FROZEN: the IR is immutable after construction.
The compiler is PROVIDER-NEUTRAL: it produces structured IR, NOT provider syntax.

What this module does NOT do:
- It does NOT generate raw prompt strings
- It does NOT call image/video generation APIs
- It does NOT use LLM to write prompts
- It does NOT produce provider-specific syntax
- It does NOT access KnowledgeRegistry internals

The canonical PromptCompiler does NOT know about Google Flow, DINO AI,
Axen, or any specific provider. That knowledge lives in
ProviderPromptAdapter subclasses.
"""

from __future__ import annotations

import hashlib
from datetime import datetime
from typing import FrozenSet, Optional

from app.character.reference_schema import (
    CharacterReferenceSpecification,
    ExplicitOverride,
    IdentityBearingProperty,
    SceneVariableProperty,
)
from app.knowledge import FallbackPolicy, KnowledgeContext
from app.prompt.adapters import KnowledgePromptAdapter
from app.prompt.schemas import (
    ActionBlock,
    BackgroundBlock,
    CameraBlock,
    CanonicalPromptIR,
    EffectsBlock,
    EnvironmentBlock,
    FormatBlock,
    IdentityPreservationBlock,
    MotionBlock,
    NegativeConstraintItem,
    NegativeConstraintsBlock,
    PromptCompilationRequest,
    PromptCompilationResult,
    PromptKind,
    PromptValidationReport,
    SceneElementsBlock,
    SoundBlock,
    StyleBlock,
    SubjectBlock,
    ValidationFinding,
    ValidationSeverity,
)
from app.prompt.adapters import ResolvedPromptKnowledge
from app.prompt.validator import PromptValidator


# ============================================================================
# Compiler version — semantic version of this module
# ============================================================================

COMPILER_VERSION = "1.0.0"


# ============================================================================
# The PromptCompiler
# ============================================================================


class PromptCompiler:
    """Canonical prompt compilation engine.

    Construction:
        # With Knowledge Layer (canonical L-U5 path):
        ctx = KnowledgeContext.from_registry(registry)
        compiler = PromptCompiler(knowledge_context=ctx)

        # Without Knowledge Layer (backward compatible):
        compiler = PromptCompiler()

    Usage:
        result = compiler.compile(request)
        ir = result.ir  # the compiled canonical Prompt IR
        validation = result.validation  # the validation report
    """

    def __init__(
        self,
        knowledge_context: Optional[KnowledgeContext] = None,
    ) -> None:
        self._knowledge_context = knowledge_context
        self._adapter: Optional[KnowledgePromptAdapter] = None
        if knowledge_context is not None:
            self._adapter = KnowledgePromptAdapter(context=knowledge_context)

    # ------------------------------------------------------------------
    # Introspection
    # ------------------------------------------------------------------

    @property
    def knowledge_context(self) -> Optional[KnowledgeContext]:
        return self._knowledge_context

    def is_knowledge_active(self) -> bool:
        return self._adapter is not None and self._adapter.is_active()

    # ------------------------------------------------------------------
    # Main entry point
    # ------------------------------------------------------------------

    def compile(
        self,
        request: PromptCompilationRequest,
    ) -> PromptCompilationResult:
        """Compile a PromptCompilationRequest into a PromptCompilationResult.

        Parameters:
            request: A structured prompt compilation request.

        Returns:
            A frozen PromptCompilationResult containing the canonical Prompt IR
            and a validation report.
        """
        prompt_kind = request.prompt_kind

        # 1. Resolve knowledge (if available)
        resolved_knowledge = self._resolve_knowledge(prompt_kind)

        # 2. Resolve character reference (if available)
        char_spec = self._resolve_character_spec(request)

        # 3. Build the canonical Prompt IR
        ir = self._build_ir(
            request=request,
            resolved_knowledge=resolved_knowledge,
            char_spec=char_spec,
        )

        # 4. Validate
        validator = PromptValidator()
        validation = validator.validate(ir, request)

        # 5. Build result
        return PromptCompilationResult(
            request_id=request.request_id or self._derive_request_id(request),
            prompt_kind=prompt_kind,
            ir=ir,
            validation=validation,
            compiler_version=COMPILER_VERSION,
            knowledge_version=resolved_knowledge.registry_version
            if resolved_knowledge
            else "no-knowledge",
            character_version=(
                char_spec.knowledge_version
                if char_spec and char_spec.is_knowledge_active
                else None
            ),
            fallback_policy_used=(
                self._knowledge_context.fallback_policy.value
                if self._knowledge_context
                else "engine_default"
            ),
            is_knowledge_active=resolved_knowledge.is_active
            if resolved_knowledge
            else False,
            has_conflicts=(
                len(char_spec.conflicts) > 0 if char_spec else False
            ),
            has_overrides=(
                len(char_spec.explicit_overrides) > 0 if char_spec else False
            ),
            compiled_at=datetime.utcnow(),
        )

    # ------------------------------------------------------------------
    # Internal: resolve knowledge
    # ------------------------------------------------------------------

    def _resolve_knowledge(
        self, prompt_kind: PromptKind
    ) -> ResolvedPromptKnowledge:
        """Resolve prompt-related knowledge from the Knowledge Layer."""
        if self._adapter is None:
            return ResolvedPromptKnowledge(is_active=False)
        return self._adapter.resolve_for_prompt(prompt_kind.value)

    # ------------------------------------------------------------------
    # Internal: resolve character reference spec
    # ------------------------------------------------------------------

    def _resolve_character_spec(
        self, request: PromptCompilationRequest
    ) -> Optional[CharacterReferenceSpecification]:
        """Resolve the CharacterReferenceSpecification for this request."""
        # If already provided in the request, use it directly
        if request.character_reference_spec is not None:
            return request.character_reference_spec
        # Otherwise, check if we have a reference ID and a knowledge context
        # In a real integration, we'd look up the spec from the registry
        # For L-U5, we accept it as a parameter
        return None

    # ------------------------------------------------------------------
    # Internal: build the IR
    # ------------------------------------------------------------------

    def _build_ir(
        self,
        request: PromptCompilationRequest,
        resolved_knowledge: Optional[ResolvedPromptKnowledge],
        char_spec: Optional[CharacterReferenceSpecification],
    ) -> CanonicalPromptIR:
        """Build the canonical Prompt IR from all inputs."""

        # Determine knowledge state
        is_knowledge_active = (
            resolved_knowledge is not None and resolved_knowledge.is_active
        )
        knowledge_ids = (
            resolved_knowledge.knowledge_ids
            if resolved_knowledge
            else frozenset()
        )
        knowledge_version = (
            resolved_knowledge.registry_version
            if resolved_knowledge
            else "no-knowledge"
        )

        # Build identity preservation from character spec
        identity_block = self._build_identity_block(char_spec)

        # Build scene elements from character spec
        scene_block = self._build_scene_elements_block(char_spec)

        # Build style from knowledge
        style_block = self._build_style_block(resolved_knowledge)

        # Build subject from request + char spec
        subject_block = self._build_subject_block(request, char_spec)

        # Build environment from request
        env_block = self._build_environment_block(request)

        # Build action from request
        action_block = self._build_action_block(request)

        # Build camera from request + knowledge
        camera_block = self._build_camera_block(request, resolved_knowledge)

        # Build motion from request + knowledge (VIDEO only)
        motion_block = self._build_motion_block(request, resolved_knowledge)

        # Build background from request
        bg_block = self._build_background_block(request)

        # Build effects from request
        effects_block = self._build_effects_block(request)

        # Build constraints from character spec + knowledge
        constraints_block = self._build_constraints_block(
            char_spec, resolved_knowledge
        )

        # Build sound from request
        sound_block = self._build_sound_block(request)

        # Build format from request
        format_block = self._build_format_block(request)

        return CanonicalPromptIR(
            prompt_kind=request.prompt_kind,
            compiler_version=COMPILER_VERSION,
            knowledge_ids_used=knowledge_ids,
            knowledge_version=knowledge_version,
            is_knowledge_active=is_knowledge_active,
            identity=identity_block,
            scene_elements=scene_block,
            style=style_block,
            subject=subject_block,
            environment=env_block,
            action=action_block,
            camera=camera_block,
            motion=motion_block,
            background=bg_block,
            effects=effects_block,
            constraints=constraints_block,
            sound=sound_block,
            format=format_block,
        )

    # ------------------------------------------------------------------
    # Internal: build individual IR blocks
    # ------------------------------------------------------------------

    def _build_identity_block(
        self, char_spec: Optional[CharacterReferenceSpecification]
    ) -> IdentityPreservationBlock:
        """Build identity preservation block from character spec."""
        if char_spec is None:
            return IdentityPreservationBlock()
        return IdentityPreservationBlock(
            locked_properties=char_spec.identity_properties,
            resolved_rules=[
                r.rule
                for r in char_spec.resolved_rules
                if r.is_identity_bearing
            ],
            knowledge_ids=char_spec.knowledge_ids_used,
        )

    def _build_scene_elements_block(
        self, char_spec: Optional[CharacterReferenceSpecification]
    ) -> SceneElementsBlock:
        """Build scene elements block from character spec."""
        if char_spec is None:
            return SceneElementsBlock()
        return SceneElementsBlock(
            permitted_variations=char_spec.scene_variables,
        )

    def _build_style_block(
        self, knowledge: Optional[ResolvedPromptKnowledge]
    ) -> Optional[StyleBlock]:
        """Build style block from resolved knowledge."""
        if knowledge is None or not knowledge.is_active:
            return None

        style_knowledge = knowledge.style
        if not style_knowledge.is_active:
            return None

        if style_knowledge.profile is None:
            return None

        from app.prompt.schemas import VisualStyleVocabulary

        # Map string profile to enum
        profile_map = {
            "hand_drawn_doodle": VisualStyleVocabulary.HAND_DRAWN_DOODLE,
            "semi_realistic_2d": VisualStyleVocabulary.SEMI_REALISTIC_2D,
            "flat_vector": VisualStyleVocabulary.FLAT_VECTOR,
        }

        profile = profile_map.get(style_knowledge.profile)
        if profile is None:
            return None

        return StyleBlock(
            profile=profile,
            palette_hint=style_knowledge.palette_hint,
            outline_hint=style_knowledge.outline_hint,
            line_quality=style_knowledge.line_quality,
            rendering_notes=style_knowledge.rendering_notes,
            provenance=style_knowledge.primary_provenance,
        )

    def _build_subject_block(
        self,
        request: PromptCompilationRequest,
        char_spec: Optional[CharacterReferenceSpecification],
    ) -> Optional[SubjectBlock]:
        """Build subject block from request + character spec."""
        if request.character_reference_id is None and char_spec is None:
            return None

        return SubjectBlock(
            character_id=request.character_reference_id,
            character_name=(
                char_spec.character_id if char_spec else None
            ),
            pose=request.scene_pose,
            expression=request.scene_expression,
            orientation=request.scene_orientation,
        )

    def _build_environment_block(
        self, request: PromptCompilationRequest
    ) -> Optional[EnvironmentBlock]:
        """Build environment block from request."""
        if request.scene_environment is None:
            return None
        return EnvironmentBlock(setting=request.scene_environment)

    def _build_action_block(
        self, request: PromptCompilationRequest
    ) -> Optional[ActionBlock]:
        """Build action block from request."""
        if request.scene_action is None:
            return None
        # Parse action into verbs
        action_text = request.scene_action
        verbs = [v.strip() for v in action_text.split() if len(v) > 2]
        return ActionBlock(
            description=action_text,
            verbs=verbs[:8],
        )

    def _build_camera_block(
        self,
        request: PromptCompilationRequest,
        knowledge: Optional[ResolvedPromptKnowledge],
    ) -> Optional[CameraBlock]:
        """Build camera block from request + knowledge."""
        from app.prompt.schemas import (
            CameraMovementVocabulary,
            CameraShotVocabulary,
        )

        shot_type: Optional[CameraShotVocabulary] = None
        movement: Optional[CameraMovementVocabulary] = None

        # From request
        if request.scene_camera:
            shot_type = self._parse_shot_type(request.scene_camera)
            movement = self._parse_movement(request.scene_camera)

        # From knowledge (can override if request is empty)
        if knowledge and knowledge.is_active:
            cam_knowledge = knowledge.camera
            if cam_knowledge.is_active:
                if shot_type is None and cam_knowledge.shot_type:
                    shot_type = self._parse_shot_type(cam_knowledge.shot_type)
                if movement is None and cam_knowledge.movement:
                    movement = self._parse_movement(cam_knowledge.movement)

        if shot_type is None and movement is None:
            return None

        return CameraBlock(
            shot_type=shot_type,
            movement=movement,
            provenance=(
                knowledge.camera.primary_provenance if knowledge else None
            ),
        )

    def _build_motion_block(
        self,
        request: PromptCompilationRequest,
        knowledge: Optional[ResolvedPromptKnowledge],
    ) -> Optional[MotionBlock]:
        """Build motion block (VIDEO only) from request + knowledge."""
        from app.prompt.schemas import MotionPatternVocabulary

        if request.prompt_kind != PromptKind.VIDEO:
            return None

        pattern: Optional[MotionPatternVocabulary] = None

        if knowledge and knowledge.is_active:
            mot_knowledge = knowledge.motion
            if mot_knowledge.is_active and mot_knowledge.pattern:
                pattern_map = {
                    "frame_by_frame": MotionPatternVocabulary.FRAME_BY_FRAME,
                    "loop": MotionPatternVocabulary.LOOP,
                    "rig_pose_interpolation": MotionPatternVocabulary.RIG_POSE_INTERPOLATION,
                    "kinetic_text": MotionPatternVocabulary.KINETIC_TEXT,
                    "shake_nervous": MotionPatternVocabulary.SHAKE_NERVOUS,
                }
                pattern = pattern_map.get(mot_knowledge.pattern)

        if pattern is None:
            return None

        return MotionBlock(
            pattern=pattern,
            provenance=(
                knowledge.motion.primary_provenance if knowledge else None
            ),
        )

    def _build_background_block(
        self, request: PromptCompilationRequest
    ) -> Optional[BackgroundBlock]:
        """Build background block from request."""
        # Background is optional in the request; return None if not provided
        return None

    def _build_effects_block(
        self, request: PromptCompilationRequest
    ) -> Optional[EffectsBlock]:
        """Build effects block from request."""
        return None

    def _build_constraints_block(
        self,
        char_spec: Optional[CharacterReferenceSpecification],
        knowledge: Optional[ResolvedPromptKnowledge],
    ) -> NegativeConstraintsBlock:
        """Build negative constraints block from character spec + knowledge."""
        items: list[NegativeConstraintItem] = []

        # From character spec
        if char_spec:
            for rule in char_spec.negative_constraints:
                items.append(
                    NegativeConstraintItem(
                        constraint_id=rule.forbids_property,
                        property_name=rule.forbids_property,
                        constraint_text=rule.rule,
                        is_identity_bearing=True,
                        provenance=rule.provenance,
                    )
                )

        # From knowledge
        if knowledge and knowledge.is_active:
            neg_knowledge = knowledge.negative_constraints
            if neg_knowledge.is_active:
                for constraint_dict in neg_knowledge.constraints:
                    provenance = (
                        neg_knowledge.provenance_list[0]
                        if neg_knowledge.provenance_list
                        else None
                    )
                    items.append(
                        NegativeConstraintItem(
                            constraint_id=constraint_dict.get(
                                "constraint_id", "unknown"
                            ),
                            property_name=constraint_dict.get(
                                "property_name", "general"
                            ),
                            constraint_text=constraint_dict.get(
                                "constraint_text", ""
                            ),
                            is_identity_bearing=constraint_dict.get(
                                "is_identity_bearing", False
                            ),
                            provenance=provenance,
                        )
                    )

        return NegativeConstraintsBlock(
            constraints=items,
        )

    def _build_sound_block(
        self, request: PromptCompilationRequest
    ) -> Optional[SoundBlock]:
        """Build sound block from request."""
        return None  # Sound is handled by s7 Voice/TTS, not prompts

    def _build_format_block(
        self, request: PromptCompilationRequest
    ) -> Optional[FormatBlock]:
        """Build format block from request."""
        if request.aspect_ratio is None:
            return None
        return FormatBlock(
            aspect_ratio=request.aspect_ratio,
            medium="video" if request.prompt_kind == PromptKind.VIDEO else "image",
        )

    # ------------------------------------------------------------------
    # Internal: vocabulary parsers
    # ------------------------------------------------------------------

    def _parse_shot_type(self, value: str) -> Optional[str]:
        """Parse a shot type string into a canonical vocabulary value."""
        text = value.lower().replace("_", " ").replace("-", " ")
        if "extreme wide" in text or "ews" in text:
            return "extreme_wide"
        if "wide" in text:
            return "wide"
        if "medium wide" in text:
            return "medium_wide"
        if "medium close" in text:
            return "medium_close"
        if "medium" in text:
            return "medium"
        if "close" in text and "extreme" not in text:
            return "close"
        if "extreme close" in text or "ecu" in text:
            return "extreme_close"
        if "over shoulder" in text or "ots" in text:
            return "over_shoulder"
        if "pov" in text or "point of view" in text:
            return "pov"
        if "dutch" in text or "tilt" in text:
            return "dutch"
        if "bird" in text:
            return "birds_eye"
        if "worm" in text:
            return "worms_eye"
        if "two shot" in text:
            return "two_shot"
        return None

    def _parse_movement(self, value: str) -> Optional[str]:
        """Parse a movement string into a canonical vocabulary value."""
        text = value.lower().replace("_", " ").replace("-", " ")
        if "push" in text or "dolly forward" in text:
            return "push_in"
        if "pull" in text or "dolly back" in text:
            return "pull_out"
        if "pan" in text:
            return "pan"
        if "tilt" in text:
            return "tilt"
        if "zoom" in text:
            return "zoom"
        if "tracking" in text or "follow" in text:
            return "tracking"
        if "shake" in text:
            return "shake"
        if "hold" in text or "static" in text:
            return "hold"
        return None

    # ------------------------------------------------------------------
    # Internal: deterministic request ID
    # ------------------------------------------------------------------

    def _derive_request_id(self, request: PromptCompilationRequest) -> str:
        """Derive a deterministic request ID from the request content."""
        content = f"{request.prompt_kind.value}:{request.character_reference_id or ''}:{request.aspect_ratio or ''}:{request.scene_camera or ''}:{request.scene_environment or ''}"
        return hashlib.sha256(content.encode()).hexdigest()[:16]


__all__ = [
    "PromptCompiler",
    "COMPILER_VERSION",
]
