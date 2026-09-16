"""
Mock Generation Provider Adapter — deterministic, no real generation.

L-U8 — Provider Adapter Layer.

This adapter is used for testing and development. It translates canonical
semantic IR to a structured representation WITHOUT calling any real provider.

This is NOT a fake image/video generator. It is a structural translation
layer that produces a ProviderPromptRepresentation.

Architecture invariant: MockProviderAdapter does NOT produce fake media.
It ONLY translates the semantic contracts to a structured representation.
"""

from __future__ import annotations

from typing import Any, Optional

from app.providers.generation.schemas import (
    GenerationCapabilityRequirement,
    ProviderCapability,
    ProviderGenerationRequest,
    ProviderPromptAdapter,
    ProviderPromptRepresentation,
    SemanticLossField,
    SemanticLossReport,
    SemanticLossStatus,
)
from app.providers.generation.registry import get_registry


# ---- Semantic field registry for mock translation ----

# Maps canonical camera shot values to mock representation tokens
_MOCK_SHOT_MAP = {
    "extreme_wide": "extreme_wide_shot",
    "wide": "wide_shot",
    "medium_wide": "medium_wide_shot",
    "medium": "medium_shot",
    "medium_close": "medium_close_shot",
    "close": "close_up_shot",
    "extreme_close": "extreme_close_up_shot",
    "over_shoulder": "over_shoulder_shot",
    "pov": "pov_shot",
    "dutch": "dutch_angle_shot",
    "birds_eye": "birds_eye_shot",
    "worms_eye": "worms_eye_shot",
    "two_shot": "two_shot",
}

# Maps canonical camera movement values to mock representation tokens
_MOCK_MOVEMENT_MAP = {
    "hold": "hold",
    "push_in": "push_in",
    "pull_out": "pull_out",
    "pan": "pan",
    "tilt": "tilt",
    "zoom": "zoom",
    "tracking": "tracking",
    "shake": "shake",
    "orbit": "orbit",
}

# Maps canonical subject motion values to mock tokens
_MOCK_SUBJECT_MOTION_MAP = {
    "none": "none",
    "stand": "standing",
    "walk": "walking",
    "run": "running",
    "point": "pointing",
    "think": "thinking",
    "celebrate": "celebrating",
    "hide": "hiding",
    "sit": "sitting",
    "enter": "entering",
    "exit": "exiting",
    "gesture": "gesturing",
    "look": "looking",
    "turn": "turning",
    "breathing": "breathing",
    "idle": "idle",
}


class MockGenerationProviderAdapter(ProviderPromptAdapter):
    """Deterministic mock adapter that translates canonical IR to structured representation.

    This adapter does NOT generate media. It ONLY translates the canonical
    semantic contracts into a ProviderPromptRepresentation.

    The semantic_loss report documents every field's translation status.
    """

    ADAPTER_VERSION = "1.0.0"

    def __init__(self, provider_id: str = "mock_gen") -> None:
        self._provider_id = provider_id
        self._registry = get_registry()

    @property
    def provider_id(self) -> str:
        return self._provider_id

    def get_capability(self) -> ProviderCapability:
        caps = self._registry.list_capabilities_for_provider(self._provider_id)
        if caps:
            return caps[0]
        raise ValueError(f"No capability found for provider '{self._provider_id}'")

    def translate(
        self,
        canonical_ir: Any,
        cms_result: Any,
        quality_result: Any,
        character_spec: Any,
        provider_generation_params: Optional[Any] = None,
    ) -> ProviderPromptRepresentation:
        """Translate canonical semantic IR to mock structured representation.

        This is a deterministic, pure function. It does NOT call any real provider.
        """
        fields: list[SemanticLossField] = []

        # ---- Determine prompt kind ----
        prompt_kind = self._get_field(canonical_ir, "prompt_kind") or "unknown"
        if hasattr(prompt_kind, "value"):
            prompt_kind = prompt_kind.value

        # ---- Camera shot ----
        camera_shot = self._get_cms_field(cms_result, "camera.shot_type")
        shot_status, shot_value = self._translate_shot(camera_shot)
        fields.append(SemanticLossField(
            field_path="camera.shot_type",
            status=shot_status,
            description=self._status_desc(shot_status, "camera shot"),
            provider_value=shot_value,
        ))

        # ---- Camera movement ----
        camera_movement = self._get_cms_field(cms_result, "camera.movement")
        movement_status, movement_value = self._translate_movement(camera_movement)
        fields.append(SemanticLossField(
            field_path="camera.movement",
            status=movement_status,
            description=self._status_desc(movement_status, "camera movement"),
            provider_value=movement_value,
        ))

        # ---- Subject motion ----
        subject_action = self._get_cms_field(cms_result, "subject_motion.action")
        motion_status, motion_value = self._translate_subject_motion(subject_action)
        fields.append(SemanticLossField(
            field_path="subject_motion.action",
            status=motion_status,
            description=self._status_desc(motion_status, "subject motion"),
            provider_value=motion_value,
        ))

        # ---- Style ----
        style_block = self._get_ir_field(canonical_ir, "style")
        style_profile = self._get_ir_field(style_block, "profile") if style_block else None
        style_status, style_value = self._translate_style(style_profile)
        fields.append(SemanticLossField(
            field_path="style.profile",
            status=style_status,
            description=self._status_desc(style_status, "style"),
            provider_value=style_value,
        ))

        # ---- Character reference ----
        if character_spec is not None:
            char_id = getattr(character_spec, "character_id", None)
            char_status = (
                SemanticLossStatus.SUPPORTED
                if char_id
                else SemanticLossStatus.OMITTED_WITH_REASON
            )
            fields.append(SemanticLossField(
                field_path="character_reference.character_id",
                status=char_status,
                description=(
                    "character reference supported" if char_id
                    else "no character reference provided"
                ),
                provider_value=str(char_id) if char_id else None,
                reason="no character" if not char_id else None,
            ))
        else:
            fields.append(SemanticLossField(
                field_path="character_reference.character_id",
                status=SemanticLossStatus.OMITTED_WITH_REASON,
                description="no character reference provided",
                reason="character_spec=None",
            ))

        # ---- Sound layers ----
        sound_layers = self._get_cms_field(cms_result, "sound.layers")
        sound_status, sound_value = self._translate_sound_layers(sound_layers)
        fields.append(SemanticLossField(
            field_path="sound.layers",
            status=sound_status,
            description=self._status_desc(sound_status, "sound layers"),
            provider_value=sound_value,
        ))

        # ---- Compute semantic loss counts ----
        supported = sum(
            1 for f in fields if f.status == SemanticLossStatus.SUPPORTED
        )
        transformed = sum(
            1 for f in fields if f.status == SemanticLossStatus.TRANSFORMED
        )
        approximated = sum(
            1 for f in fields if f.status == SemanticLossStatus.APPROXIMATED
        )
        omitted = sum(
            1 for f in fields if f.status == SemanticLossStatus.OMITTED_WITH_REASON
        )
        unsupported = sum(
            1 for f in fields if f.status == SemanticLossStatus.UNSUPPORTED
        )

        # ---- Build representation ----
        representation = {
            "mock_generation": True,
            "semantic_prompt": self._build_semantic_prompt(
                canonical_ir, cms_result, character_spec,
                shot_value, movement_value, motion_value, style_value,
            ),
            "prompt_kind": prompt_kind,
            "camera_shot": shot_value,
            "camera_movement": movement_value,
            "subject_motion": motion_value,
            "style": style_value,
        }

        semantic_loss = SemanticLossReport(
            total_fields=len(fields),
            supported_fields=supported,
            transformed_fields=transformed,
            approximated_fields=approximated,
            omitted_fields=omitted,
            unsupported_fields=unsupported,
            fields=tuple(fields),
        )

        return ProviderPromptRepresentation(
            provider_id=self._provider_id,
            capability_id=self.get_capability().capability_id,
            prompt_kind=prompt_kind,
            representation=representation,
            semantic_loss=semantic_loss,
            adapter_version=self.ADAPTER_VERSION,
            provider_version="1.0.0",
        )

    # ---- Translation helpers ----

    def _translate_shot(self, shot) -> tuple[SemanticLossStatus, Optional[str]]:
        shot_value = getattr(shot, "value", None)
        if shot_value is None:
            return SemanticLossStatus.OMITTED_WITH_REASON, None
        mock_value = _MOCK_SHOT_MAP.get(shot_value)
        if mock_value:
            return SemanticLossStatus.SUPPORTED, mock_value
        # Unknown shot — transformed
        return SemanticLossStatus.TRANSFORMED, str(shot_value)

    def _translate_movement(self, movement) -> tuple[SemanticLossStatus, Optional[str]]:
        mv_value = getattr(movement, "value", None)
        if mv_value is None:
            return SemanticLossStatus.OMITTED_WITH_REASON, None
        mock_value = _MOCK_MOVEMENT_MAP.get(mv_value)
        if mock_value:
            return SemanticLossStatus.SUPPORTED, mock_value
        return SemanticLossStatus.TRANSFORMED, str(mv_value)

    def _translate_subject_motion(self, action) -> tuple[SemanticLossStatus, Optional[str]]:
        action_value = getattr(action, "value", None)
        if action_value is None:
            return SemanticLossStatus.OMITTED_WITH_REASON, None
        mock_value = _MOCK_SUBJECT_MOTION_MAP.get(action_value)
        if mock_value:
            return SemanticLossStatus.SUPPORTED, mock_value
        return SemanticLossStatus.APPROXIMATED, str(action_value)

    def _translate_style(self, style) -> tuple[SemanticLossStatus, Optional[str]]:
        style_value = getattr(style, "value", None)
        if style_value is None:
            return SemanticLossStatus.OMITTED_WITH_REASON, None
        return SemanticLossStatus.SUPPORTED, str(style_value)

    def _translate_sound_layers(self, layers) -> tuple[SemanticLossStatus, Optional[str]]:
        if layers is None:
            return SemanticLossStatus.OMITTED_WITH_REASON, None
        return SemanticLossStatus.SUPPORTED, f"mock_sound_layers"

    def _build_semantic_prompt(
        self,
        canonical_ir: Any,
        cms_result: Any,
        character_spec: Any,
        shot: Optional[str],
        movement: Optional[str],
        subject_motion: Optional[str],
        style: Optional[str],
    ) -> str:
        """Build a human-readable semantic prompt description."""
        parts = []
        if style:
            parts.append(f"style: {style}")
        if shot:
            parts.append(f"shot: {shot}")
        if movement:
            parts.append(f"movement: {movement}")
        if subject_motion and subject_motion != "none":
            parts.append(f"action: {subject_motion}")
        char_id = getattr(character_spec, "character_id", None) if character_spec else None
        if char_id:
            parts.append(f"character: {char_id}")
        return "; ".join(parts) if parts else "generic scene"

    @staticmethod
    def _get_field(obj: Any, name: str) -> Any:
        if obj is None:
            return None
        return getattr(obj, name, None)

    @staticmethod
    def _get_ir_field(obj: Any, dot_path: str) -> Any:
        """Get a nested field from an object by dot-path."""
        if obj is None:
            return None
        parts = dot_path.split(".")
        current = obj
        for part in parts:
            if current is None:
                return None
            current = getattr(current, part, None)
        return current

    @staticmethod
    def _get_cms_field(obj: Any, dot_path: str) -> Any:
        """Get a nested field from CMS result by dot-path."""
        return MockGenerationProviderAdapter._get_ir_field(obj, dot_path)

    @staticmethod
    def _status_desc(status: SemanticLossStatus, field_name: str) -> str:
        desc = {
            SemanticLossStatus.SUPPORTED: f"{field_name} supported",
            SemanticLossStatus.TRANSFORMED: f"{field_name} transformed to provider syntax",
            SemanticLossStatus.APPROXIMATED: f"{field_name} approximated",
            SemanticLossStatus.OMITTED_WITH_REASON: f"{field_name} omitted",
            SemanticLossStatus.UNSUPPORTED: f"{field_name} unsupported",
        }
        return desc.get(status, field_name)


__all__ = ["MockGenerationProviderAdapter"]
