"""Voice / TTS / Audio canonical schemas (C-17).

PROMPT 8 §6–§26. Every cross-system data contract for voice, narration,
synthesized audio, and speech timing. These objects are designed to be
serialized to JSON and round-tripped through the renderer.

Design rules
------------
1. No provider-specific fields in canonical models. Provider logic lives
   in `provider_base.py` and `mock_tts.py`.
2. No secrets. API keys, auth headers, and provider credentials live only
   in environment / configuration.
3. Identity is content-based, not filename-based.
   `VoiceDefinition.voice_id`, `AudioArtifact.artifact_id`, etc. are
   derived from a SHA-256 fingerprint of canonical inputs.
4. Every model validates with Pydantic v2. Cross-field invariants live
   in `@model_validator(mode="after")`.
5. Enums are stable strings. Renderer mirrors them in TypeScript.
"""
from __future__ import annotations

import hashlib
import json
import re
from datetime import datetime
from enum import Enum
from typing import Any

from pydantic import BaseModel, Field, model_validator


# ============================================================================
# Enums
# ============================================================================

class VoiceLifecycleStatus(str, Enum):
    """Voice lifecycle states (PROMPT 8 §9)."""
    DRAFT = "draft"
    VALIDATED = "validated"
    APPROVED = "approved"
    ACTIVE = "active"
    DEPRECATED = "deprecated"
    ARCHIVED = "archived"


class VoiceGender(str, Enum):
    """Gender/presentation where provider supports it.

    We deliberately do NOT infer biological gender from arbitrary text —
    gender is set explicitly by the project owner or speaker role.
    """
    FEMALE = "female"
    MALE = "male"
    NEUTRAL = "neutral"
    UNSPECIFIED = "unspecified"


class VoiceStyle(str, Enum):
    """Style preset (where supported by provider)."""
    NARRATOR = "narrator"
    DOCUMENTARY = "documentary"
    CONVERSATIONAL = "conversational"
    ENERGETIC = "energetic"
    CALM = "calm"
    DRAMATIC = "dramatic"
    NEWS = "news"
    UNSPECIFIED = "unspecified"


class TtsProviderName(str, Enum):
    """Canonical provider names (PROMPT 8 §13).

    New providers (CosyVoice, F5-TTS, Vi-F5-TTS, local GPU, …) are added
    here and implemented as siblings of `mock_tts.py`.
    """
    MOCK = "mock"               # deterministic mock; tests + smoke
    GTTS = "gtts"               # gTTS (no word timestamps)
    ELEVENLABS = "elevenlabs"   # ElevenLabs cloud (timestamps on pro tier)
    COSYVOICE = "cosyvoice"     # future
    F5_TTS = "f5_tts"           # future
    VI_F5_TTS = "vi_f5_tts"     # future
    LOCAL_GPU = "local_gpu"     # future


class TtsEnvironment(str, Enum):
    """Runtime environment for TTS provider selection (PROMPT 8 §21)."""
    MOCK = "mock"               # force mock provider (tests, offline)
    DEVELOPMENT = "development" # allow free / fallback providers
    PRODUCTION = "production"   # strict: only configured provider, no silent fallback


class AudioArtifactStatus(str, Enum):
    """Lifecycle of a synthesized AudioArtifact."""
    PENDING = "pending"          # generation in progress
    GENERATED = "generated"      # provider output captured
    VALIDATED = "validated"      # passed validation
    NORMALIZED = "normalized"    # post-normalization (loudness / format)
    REJECTED = "rejected"        # failed validation
    SUPERSEDED = "superseded"    # replaced by a newer artifact


class TimestampSource(str, Enum):
    """How the word-level timestamps were obtained (PROMPT 8 §25).

    `UNAVAILABLE` is honest: never fabricate fake timestamps.
    """
    PROVIDER_NATIVE = "provider_native"
    FORCED_ALIGNMENT = "forced_alignment"
    UNIFORM_ALIGNMENT = "uniform_alignment"   # computed by gTTS fallback
    UNAVAILABLE = "unavailable"


class DurationReconciliationStrategy(str, Enum):
    """What to do when audio duration differs from scene/animation duration
    (PROMPT 8 §28)."""
    FOLLOW_AUDIO = "follow_audio"     # scene duration = audio duration + padding
    FOLLOW_SCENE = "follow_scene"     # audio is trimmed to scene duration (warning)
    PAD_TO_SCENE = "pad_to_scene"     # scene waits for audio + silence tail
    FAIL = "fail"                     # reject (debug mode)
    AUTO = "auto"                     # default: follow_audio with explicit padding


# ============================================================================
# VoiceDefinition / VoiceInstance / VoiceRegistryEntry
# ============================================================================

# Voice ID canonical form: lowercase snake_case, 1..64 chars.
_VOICE_ID_RX = re.compile(r"^[a-z0-9_]+$")


class PronunciationHint(BaseModel):
    """Structured pronunciation hint (PROMPT 8 §30).

    Provider adapters translate this to provider-specific syntax (SSML,
    IPA, custom phoneme fields, etc.). The canonical form is always
    provider-neutral.
    """
    hint_id: str = Field(min_length=1, max_length=64)
    word: str = Field(min_length=1, max_length=64,
                      description="The text in the narration that this hint applies to.")
    replacement: str | None = Field(default=None, max_length=128,
                                     description="Text replacement (alias).")
    phonetic: str | None = Field(default=None, max_length=128,
                                   description="IPA / phonetic spelling.")
    alias: str | None = Field(default=None, max_length=128,
                               description="Alternative alias the TTS should read.")
    emphasis_intensity: float = Field(default=0.0, ge=0.0, le=1.0)
    break_ms: int | None = Field(default=None, ge=0, le=2000,
                                  description="Insert a pause after the word (ms).")


class EmphasisHint(BaseModel):
    """Emphasis hint on a word/phrase (PROMPT 8 §31)."""
    hint_id: str = Field(min_length=1, max_length=64)
    text: str = Field(min_length=1, max_length=200)
    intensity: float = Field(default=0.5, ge=0.0, le=1.0)
    pacing_change: float = Field(default=0.0, ge=-0.5, le=0.5,
                                  description="Relative pacing delta (negative = slower).")


class VoiceSettings(BaseModel):
    """Provider-neutral voice settings (PROMPT 8 §6).

    Provider adapters may map `stability` / `similarity` / `pitch` to
    provider-specific knobs, but the canonical values are bounded.
    """
    speaking_rate: float = Field(default=1.0, ge=0.5, le=2.0)
    pitch: float = Field(default=1.0, ge=0.5, le=2.0)
    stability: float = Field(default=0.5, ge=0.0, le=1.0)
    similarity: float = Field(default=0.5, ge=0.0, le=1.0)
    style_exaggeration: float = Field(default=0.0, ge=0.0, le=1.0)
    default_volume_db: float = Field(default=0.0, ge=-60.0, le=12.0)
    pronunciation_profile: str = Field(default="", max_length=64,
                                         description="Named pronunciation profile (e.g. 'vi_vn_default').")


class VoiceDefinition(BaseModel):
    """Canonical voice definition (C-17 / PROMPT 8 §6).

    Voice identity is stable. Changing text or synthesis parameters does
    NOT create a new voice — it produces a new AudioArtifact.
    """
    version: str = Field(default="1.0.0")
    voice_id: str = Field(min_length=1, max_length=64)
    name: str = Field(min_length=1, max_length=128)
    language: str = Field(min_length=2, max_length=8,
                           description="BCP-47 language code, e.g. 'vi', 'en', 'ko'.")
    locale: str = Field(default="", max_length=16,
                         description="BCP-47 locale, e.g. 'vi-VN', 'en-US', 'ko-KR'.")
    gender: VoiceGender = VoiceGender.UNSPECIFIED
    provider: TtsProviderName = TtsProviderName.MOCK
    provider_voice_id: str = Field(default="", max_length=128,
                                     description="Provider-specific voice ID (e.g. ElevenLabs voice UUID).")
    style: VoiceStyle = VoiceStyle.UNSPECIFIED
    settings: VoiceSettings = Field(default_factory=VoiceSettings)
    supported_languages: list[str] = Field(default_factory=list, max_length=32)
    pronunciation_hints: list[PronunciationHint] = Field(default_factory=list, max_length=200)
    status: VoiceLifecycleStatus = VoiceLifecycleStatus.DRAFT
    version_label: str = Field(default="v1", max_length=32)
    metadata: dict[str, Any] = Field(default_factory=dict)
    created_at: datetime = Field(default_factory=datetime.utcnow)

    @model_validator(mode="after")
    def _validate_voice_id(self) -> "VoiceDefinition":
        if not _VOICE_ID_RX.match(self.voice_id):
            raise ValueError(
                f"voice_id must match {_VOICE_ID_RX.pattern}; got {self.voice_id!r}"
            )
        if not self.locale:
            self.locale = f"{self.language}-XX"
        if not self.supported_languages:
            self.supported_languages = [self.language]
        return self

    def to_dict(self) -> dict[str, Any]:
        return self.model_dump(mode="json")


class VoiceInstance(BaseModel):
    """Scene/project-level voice instance (PROMPT 8 §7).

    References a canonical `voice_id` and may override settings per scene
    or per project. Voice identity remains canonical; only settings may
    differ.
    """
    instance_id: str = Field(min_length=1, max_length=64)
    voice_id: str = Field(min_length=1, max_length=64)
    speaker_role: str = Field(default="narrator", max_length=32,
                               description="e.g. 'narrator', 'historian', 'character_a'.")
    speaker_id: str = Field(default="", max_length=64,
                             description="NarrationUnit.speaker_id this instance matches.")
    project_id: str = Field(default="", max_length=64)
    scene_id: str = Field(default="", max_length=64,
                           description="Empty = project-wide instance.")
    settings_override: VoiceSettings | None = None
    volume_override_db: float | None = Field(default=None, ge=-60.0, le=12.0)
    pronunciation_hints_override: list[PronunciationHint] = Field(default_factory=list, max_length=200)
    metadata: dict[str, Any] = Field(default_factory=dict)

    @model_validator(mode="after")
    def _validate_id(self) -> "VoiceInstance":
        if not _VOICE_ID_RX.match(self.instance_id):
            raise ValueError(
                f"instance_id must match {_VOICE_ID_RX.pattern}; got {self.instance_id!r}"
            )
        if not _VOICE_ID_RX.match(self.voice_id):
            raise ValueError(
                f"voice_id must match {_VOICE_ID_RX.pattern}; got {self.voice_id!r}"
            )
        return self

    def speaker_id_compatible(self, unit_speaker_id: str) -> bool:
        """True if this instance matches the unit's speaker_id."""
        if not self.speaker_id:
            # No speaker_id means "project-wide default for speaker_role".
            return True
        return self.speaker_id == unit_speaker_id


class VoiceRegistryEntry(BaseModel):
    """Registry bookkeeping for a voice (PROMPT 8 §8)."""
    voice_id: str
    version_label: str = "v1"
    status: VoiceLifecycleStatus = VoiceLifecycleStatus.DRAFT
    usage_count: int = Field(default=0, ge=0)
    last_used_at: datetime | None = None
    approved_by: str = Field(default="", max_length=64)
    approved_at: datetime | None = None
    deprecated_reason: str = Field(default="", max_length=300)


class VoiceRegistry(BaseModel):
    """Canonical voice registry state (PROMPT 8 §8).

    Mirrors the `AssetRegistry` / `CharacterRegistry` pattern: holds the
    canonical list of voices and their lifecycle state.
    """
    project_id: str = Field(default="", max_length=64)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
    voices: list[VoiceRegistryEntry] = Field(default_factory=list, max_length=512)
    warnings: list[str] = Field(default_factory=list, max_length=256)
    failures: list[str] = Field(default_factory=list, max_length=256)

    def to_dict(self) -> dict[str, Any]:
        return self.model_dump(mode="json")


# ============================================================================
# NarrationScript
# ============================================================================

class SpeakerRole(str, Enum):
    """Default speaker roles. Project may extend with custom roles."""
    NARRATOR = "narrator"
    HISTORIAN = "historian"
    CHARACTER_A = "character_a"
    CHARACTER_B = "character_b"
    UNSPECIFIED = "unspecified"


class NarrationUnit(BaseModel):
    """A single narration unit (PROMPT 8 §10).

    One `NarrationUnit` typically maps to one visual beat / scene
    narration block. Multi-speaker projects have multiple units per scene
    (one per speaker).
    """
    narration_id: str = Field(min_length=1, max_length=64)
    scene_id: str = Field(default="", max_length=64)
    beat_id: str = Field(default="", max_length=64)
    speaker_id: str = Field(default="narrator", max_length=64)
    speaker_role: SpeakerRole = SpeakerRole.NARRATOR
    voice_id: str | None = Field(default=None, max_length=64,
                                  description="Explicit voice override; None = resolve from speaker_id.")
    text: str = Field(min_length=1, max_length=4000)
    language: str = Field(default="en", min_length=2, max_length=8)
    locale: str = Field(default="", max_length=16)
    pronunciation_hints: list[PronunciationHint] = Field(default_factory=list, max_length=64)
    emphasis_hints: list[EmphasisHint] = Field(default_factory=list, max_length=64)
    pacing_intent: float = Field(default=1.0, ge=0.5, le=2.0,
                                  description="Relative pacing multiplier (1.0 = default).")
    expected_duration_sec: float | None = Field(default=None, ge=0.0, le=600.0,
                                                  description="Hint from Story; audio is authoritative.")
    version: str = Field(default="v1", max_length=32)
    source_lineage: dict[str, Any] = Field(default_factory=dict,
                                            description="Provenance: beat_id, claim_ids, source_ids.")

    @model_validator(mode="after")
    def _validate_ids(self) -> "NarrationUnit":
        if not _VOICE_ID_RX.match(self.narration_id):
            raise ValueError(
                f"narration_id must match {_VOICE_ID_RX.pattern}; got {self.narration_id!r}"
            )
        if self.voice_id is not None and not _VOICE_ID_RX.match(self.voice_id):
            raise ValueError(
                f"voice_id must match {_VOICE_ID_RX.pattern}; got {self.voice_id!r}"
            )
        if not self.locale:
            self.locale = f"{self.language}-XX"
        return self


class NarrationScript(BaseModel):
    """Canonical narration script (C-17 / PROMPT 8 §10).

    Holds the canonical ordered list of narration units for a project.
    Order is the canonical narrative order (matches scene order).
    """
    version: str = Field(default="1.0.0")
    script_id: str = Field(min_length=1, max_length=64)
    project_id: str = Field(default="", max_length=64)
    job_id: str = Field(default="", max_length=64)
    language: str = Field(default="en", min_length=2, max_length=8)
    locale: str = Field(default="en-US", max_length=16)
    units: list[NarrationUnit] = Field(default_factory=list, max_length=1024)
    default_voice_id: str | None = Field(default=None, max_length=64,
                                          description="Voice used when a unit has no explicit voice_id.")
    version_label: str = Field(default="v1", max_length=32)
    source_lineage: dict[str, Any] = Field(default_factory=dict)
    warnings: list[str] = Field(default_factory=list, max_length=256)
    failures: list[str] = Field(default_factory=list, max_length=256)
    created_at: datetime = Field(default_factory=datetime.utcnow)

    @model_validator(mode="after")
    def _validate_ids(self) -> "NarrationScript":
        if not _VOICE_ID_RX.match(self.script_id):
            raise ValueError(
                f"script_id must match {_VOICE_ID_RX.pattern}; got {self.script_id!r}"
            )
        if self.default_voice_id is not None and not _VOICE_ID_RX.match(self.default_voice_id):
            raise ValueError(
                f"default_voice_id must match {_VOICE_ID_RX.pattern}; "
                f"got {self.default_voice_id!r}"
            )
        # Ensure narration_ids are unique.
        seen: set[str] = set()
        for u in self.units:
            if u.narration_id in seen:
                raise ValueError(f"Duplicate narration_id: {u.narration_id!r}")
            seen.add(u.narration_id)
        return self

    def to_dict(self) -> dict[str, Any]:
        return self.model_dump(mode="json")


# ============================================================================
# Provider Capability Matrix (PROMPT 8 §14)
# ============================================================================

class ProviderCapability(BaseModel):
    """Capability declaration for a TTS provider (PROMPT 8 §14)."""
    provider: TtsProviderName
    supported_languages: list[str] = Field(default_factory=list)
    supports_word_timestamps: bool = False
    supports_pronunciation_hints: bool = False
    supports_emphasis_hints: bool = False
    supports_ssml: bool = False
    supports_voice_cloning: bool = False
    supports_streaming: bool = False
    output_formats: list[str] = Field(default_factory=lambda: ["wav"])
    max_text_length: int = Field(default=5000, ge=1)
    requires_api_key: bool = False
    deterministic: bool = False


# ============================================================================
# AudioArtifact
# ============================================================================

_AUDIO_ID_RX = re.compile(r"^[a-z0-9_]+$")


def _canonical_text(text: str) -> str:
    """Normalize narration text for fingerprinting (PROMPT 8 §18).

    Whitespace collapse + lowercase. Provider-specific normalization
    happens inside the provider adapter.
    """
    return " ".join(text.split())


def compute_text_hash(text: str) -> str:
    """SHA-256 hex of canonicalized text (first 16 chars)."""
    canonical = _canonical_text(text)
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()[:16]


def compute_voice_config_hash(
    voice: VoiceDefinition,
    settings_override: VoiceSettings | None = None,
) -> str:
    """SHA-256 hex of canonical voice configuration.

    Includes voice_id, version_label, provider, provider_voice_id,
    language, locale, settings (or override), pronunciation profile.
    """
    payload: dict[str, Any] = {
        "voice_id": voice.voice_id,
        "version_label": voice.version_label,
        "provider": voice.provider.value,
        "provider_voice_id": voice.provider_voice_id,
        "language": voice.language,
        "locale": voice.locale,
    }
    settings = settings_override if settings_override is not None else voice.settings
    payload["settings"] = settings.model_dump(mode="json")
    payload["pronunciation_profile"] = settings.pronunciation_profile
    raw = json.dumps(payload, sort_keys=True, ensure_ascii=False)
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:16]


def compute_audio_fingerprint(
    text: str,
    voice: VoiceDefinition,
    settings_override: VoiceSettings | None = None,
) -> str:
    """Content-addressed fingerprint of (text + voice config) (PROMPT 8 §18).

    Used as the basis for both the audio artifact_id and the TTS cache
    key. Deterministic.
    """
    return compute_text_hash(text) + "_" + compute_voice_config_hash(
        voice, settings_override
    )


class AudioArtifact(BaseModel):
    """Canonical synthesized audio artifact (C-17 / PROMPT 8 §17).

    `artifact_id` is content-derived (not filename-derived).
    """
    version: str = Field(default="1.0.0")
    artifact_id: str = Field(min_length=1, max_length=64)
    narration_id: str = Field(min_length=1, max_length=64)
    voice_id: str = Field(min_length=1, max_length=64)
    provider: TtsProviderName
    provider_version: str = Field(default="", max_length=64)
    source_text_hash: str = Field(min_length=16, max_length=16)
    voice_config_hash: str = Field(min_length=16, max_length=16)
    format: str = Field(default="wav", min_length=2, max_length=8)
    sample_rate: int = Field(default=22050, ge=8000, le=48000)
    channels: int = Field(default=1, ge=1, le=2)
    bits_per_sample: int = Field(default=16, ge=8, le=32)
    duration_sec: float = Field(ge=0.0, le=600.0)
    uri: str = Field(min_length=1, max_length=512,
                      description="Relative path within the project workspace.")
    absolute_path: str = Field(default="", max_length=512)
    checksum_sha256: str = Field(default="", max_length=64)
    byte_size: int = Field(default=0, ge=0)
    created_at: datetime = Field(default_factory=datetime.utcnow)
    status: AudioArtifactStatus = AudioArtifactStatus.GENERATED
    fingerprint: str = Field(min_length=1, max_length=64)
    metadata: dict[str, Any] = Field(default_factory=dict)

    @model_validator(mode="after")
    def _validate_id_format(self) -> "AudioArtifact":
        # artifact_id is content-derived: "{text_hash}_{voice_config_hash}".
        if "_" not in self.artifact_id:
            raise ValueError(
                f"artifact_id must contain '_' (got {self.artifact_id!r})"
            )
        parts = self.artifact_id.split("_")
        if len(parts) != 2 or not all(len(p) == 16 for p in parts):
            raise ValueError(
                f"artifact_id must be 'texthash_voiceconfighash' (both 16 hex chars); "
                f"got {self.artifact_id!r}"
            )
        if not _AUDIO_ID_RX.match(self.fingerprint):
            raise ValueError(
                f"fingerprint must match {_AUDIO_ID_RX.pattern}; got {self.fingerprint!r}"
            )
        return self

    def to_dict(self) -> dict[str, Any]:
        return self.model_dump(mode="json")


# ============================================================================
# SpeechTiming
# ============================================================================

class WordTiming(BaseModel):
    """Word-level timestamp (PROMPT 8 §24)."""
    word: str = Field(min_length=1, max_length=64)
    start_sec: float = Field(ge=0.0)
    end_sec: float = Field(ge=0.0)
    confidence: float | None = Field(default=None, ge=0.0, le=1.0)

    @model_validator(mode="after")
    def _validate_order(self) -> "WordTiming":
        if self.end_sec < self.start_sec - 1e-6:
            raise ValueError(
                f"WordTiming end_sec ({self.end_sec}) < start_sec ({self.start_sec})"
            )
        return self


class SegmentTiming(BaseModel):
    """Phrase/segment timing (PROMPT 8 §24)."""
    text: str = Field(min_length=1, max_length=400)
    start_sec: float = Field(ge=0.0)
    end_sec: float = Field(ge=0.0)

    @model_validator(mode="after")
    def _validate_order(self) -> "SegmentTiming":
        if self.end_sec < self.start_sec - 1e-6:
            raise ValueError(
                f"SegmentTiming end_sec ({self.end_sec}) < start_sec ({self.start_sec})"
            )
        return self


class SpeechTiming(BaseModel):
    """Canonical speech timing metadata (C-17 / PROMPT 8 §24).

    `timestamp_source` is honest: if the provider did not return usable
    timestamps, this is `UNAVAILABLE` and `words` / `segments` are
    empty. We never fabricate timestamps.
    """
    version: str = Field(default="1.0.0")
    timing_id: str = Field(min_length=1, max_length=64)
    artifact_id: str = Field(min_length=1, max_length=64)
    narration_id: str = Field(min_length=1, max_length=64)
    language: str = Field(default="en", min_length=2, max_length=8)
    timestamp_source: TimestampSource = TimestampSource.UNAVAILABLE
    words: list[WordTiming] = Field(default_factory=list, max_length=8192)
    segments: list[SegmentTiming] = Field(default_factory=list, max_length=1024)
    duration_sec: float = Field(ge=0.0, le=600.0)
    provider: TtsProviderName = TtsProviderName.MOCK
    metadata: dict[str, Any] = Field(default_factory=dict)

    @model_validator(mode="after")
    def _validate_word_ordering(self) -> "SpeechTiming":
        last_end = 0.0
        for i, w in enumerate(self.words):
            if w.start_sec < last_end - 1e-6:
                # Words may overlap slightly (coarticulation); flag if too far.
                if w.start_sec < last_end - 0.5:
                    raise ValueError(
                        f"Word {i} start_sec ({w.start_sec}) is far before "
                        f"previous word end_sec ({last_end:.3f})"
                    )
            if w.end_sec > self.duration_sec + 0.5:
                raise ValueError(
                    f"Word {i} end_sec ({w.end_sec}) exceeds timing duration "
                    f"({self.duration_sec}) by > 0.5s"
                )
            last_end = max(last_end, w.end_sec)
        for i, s in enumerate(self.segments):
            if s.end_sec > self.duration_sec + 0.5:
                raise ValueError(
                    f"Segment {i} end_sec ({s.end_sec}) exceeds timing duration "
                    f"({self.duration_sec}) by > 0.5s"
                )
        return self

    def to_dict(self) -> dict[str, Any]:
        return self.model_dump(mode="json")


# ============================================================================
# NarrationTimeline (PROMPT 8 §26)
# ============================================================================

class NarrationTimelineEntry(BaseModel):
    """Per-narration-unit entry in the NarrationTimeline."""
    narration_id: str = Field(min_length=1, max_length=64)
    scene_id: str = Field(default="", max_length=64)
    artifact_id: str = Field(min_length=1, max_length=64)
    timing_id: str = Field(min_length=1, max_length=64)
    voice_id: str = Field(min_length=1, max_length=64)
    speaker_id: str = Field(default="narrator", max_length=64)
    audio_start_sec: float = Field(ge=0.0)
    audio_end_sec: float = Field(ge=0.0)
    scene_start_sec: float = Field(ge=0.0)
    scene_end_sec: float = Field(ge=0.0)
    pre_roll_sec: float = Field(default=0.0, ge=0.0, le=2.0)
    post_roll_sec: float = Field(default=0.0, ge=0.0, le=2.0)
    padding_sec: float = Field(default=0.0, ge=0.0, le=2.0)
    resolution_strategy: DurationReconciliationStrategy = DurationReconciliationStrategy.FOLLOW_AUDIO
    metadata: dict[str, Any] = Field(default_factory=dict)

    @model_validator(mode="after")
    def _validate_order(self) -> "NarrationTimelineEntry":
        if self.audio_end_sec < self.audio_start_sec - 1e-6:
            raise ValueError(
                f"audio_end_sec ({self.audio_end_sec}) < audio_start_sec ({self.audio_start_sec})"
            )
        if self.scene_end_sec < self.scene_start_sec - 1e-6:
            raise ValueError(
                f"scene_end_sec ({self.scene_end_sec}) < scene_start_sec ({self.scene_start_sec})"
            )
        return self


class NarrationTimeline(BaseModel):
    """Canonical NarrationTimeline (C-17 / PROMPT 8 §26).

    Maps NarrationScript + AudioArtifact + SpeechTiming to canonical
    scene timing. Consumed by PROMPT 9 (Captions/Timing) and the
    renderer (for scene duration enforcement).
    """
    version: str = Field(default="1.0.0")
    timeline_id: str = Field(min_length=1, max_length=64)
    script_id: str = Field(min_length=1, max_length=64)
    project_id: str = Field(default="", max_length=64)
    job_id: str = Field(default="", max_length=64)
    fps: int = Field(default=30, ge=12, le=60)
    total_duration_sec: float = Field(default=0.0, ge=0.0, le=3600.0)
    entries: list[NarrationTimelineEntry] = Field(default_factory=list, max_length=1024)
    default_padding_sec: float = Field(default=0.05, ge=0.0, le=2.0)
    default_pre_roll_sec: float = Field(default=0.0, ge=0.0, le=2.0)
    default_post_roll_sec: float = Field(default=0.0, ge=0.0, le=2.0)
    strategy: DurationReconciliationStrategy = DurationReconciliationStrategy.FOLLOW_AUDIO
    warnings: list[str] = Field(default_factory=list, max_length=256)
    failures: list[str] = Field(default_factory=list, max_length=256)
    metadata: dict[str, Any] = Field(default_factory=dict)
    created_at: datetime = Field(default_factory=datetime.utcnow)

    def to_dict(self) -> dict[str, Any]:
        return self.model_dump(mode="json")


# ============================================================================
# VoiceResolution + ResolutionEvent (PROMPT 8 §15)
# ============================================================================

class VoiceResolution(BaseModel):
    """The result of resolving a NarrationRequirement to a VoiceDefinition.

    Records every step of the resolution so the decision is auditable.
    """
    resolution_id: str = Field(min_length=1, max_length=64)
    narration_id: str = Field(min_length=1, max_length=64)
    resolved_voice_id: str = Field(min_length=1, max_length=64)
    resolved_provider: TtsProviderName
    strategy: str = Field(default="explicit", max_length=32,
                           description="explicit | default | compatible | fallback | mock")
    settings_used: VoiceSettings
    events: list[str] = Field(default_factory=list, max_length=64,
                                description="Ordered log of resolution decisions.")
    fallback_used: bool = False
    mock_used: bool = False
    warnings: list[str] = Field(default_factory=list, max_length=64)
    metadata: dict[str, Any] = Field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return self.model_dump(mode="json")


class ResolutionEvent(BaseModel):
    """One auditable voice resolution event (PROMPT 8 §15, §32)."""
    event_id: str = Field(min_length=1, max_length=64)
    narration_id: str = Field(min_length=1, max_length=64)
    requested_voice_id: str | None = None
    resolved_voice_id: str = Field(min_length=1, max_length=64)
    strategy: str = Field(default="explicit", max_length=32)
    provider: TtsProviderName
    environment: TtsEnvironment
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    detail: dict[str, Any] = Field(default_factory=dict)


# ============================================================================
# Exports
# ============================================================================

__all__ = [
    # Enums
    "VoiceLifecycleStatus",
    "VoiceGender",
    "VoiceStyle",
    "TtsProviderName",
    "TtsEnvironment",
    "AudioArtifactStatus",
    "TimestampSource",
    "DurationReconciliationStrategy",
    "SpeakerRole",
    # Voice
    "VoiceSettings",
    "PronunciationHint",
    "EmphasisHint",
    "VoiceDefinition",
    "VoiceInstance",
    "VoiceRegistryEntry",
    "VoiceRegistry",
    # Narration
    "NarrationUnit",
    "NarrationScript",
    # Provider capability
    "ProviderCapability",
    # Audio
    "AudioArtifact",
    "SpeechTiming",
    "WordTiming",
    "SegmentTiming",
    # Timeline
    "NarrationTimeline",
    "NarrationTimelineEntry",
    # Resolution
    "VoiceResolution",
    "ResolutionEvent",
    # Fingerprinting helpers
    "compute_text_hash",
    "compute_voice_config_hash",
    "compute_audio_fingerprint",
]
