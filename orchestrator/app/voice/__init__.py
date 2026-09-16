"""Voice / TTS / Audio Intelligence Layer.

PROMPT 8 — VOICE / TTS INTELLIGENCE & AUDIO PIPELINE.

Architecture
------------
StoryPackage
    ↓
NarrationScript  (storyboard/script adapter → canonical narration units)
    ↓
VoiceResolver    (policy-based voice selection)
    ↓
TTSProvider      (ElevenLabs / gTTS / Mock / future CosyVoice / F5-TTS)
    ↓
AudioArtifact    (content-addressed, validated, normalized)
    ↓
SpeechTiming     (word-level timestamps, provider-native or marked unavailable)
    ↓
NarrationTimeline (maps NarrationScript + AudioArtifact + SpeechTiming to scene timing)
    ↓
Renderer / Captions / Editorial

Module map
----------
- schemas         Canonical data contracts (VoiceDefinition, NarrationScript, AudioArtifact, SpeechTiming, NarrationTimeline, …)
- lifecycle       Voice status enums + transitions
- registry        VoiceRegistry (lookup, search, usage, deprecation)
- narration       NarrationScript adapter from StoryPackage + Script
- provider_base   TTSProvider ABC, ProviderCapability, ProviderFallbackPolicy
- mock_tts        Deterministic mock provider (stdlib wave, byte-identical output)
- provider_factory TTS provider selection (env-driven, audit-friendly)
- resolver        VoiceResolver + ResolutionEvent audit log
- audio_validator Deterministic audio file validation (corrupt / format / duration / sample rate)
- cache           Content-addressed TTS cache (SHA-256 fingerprint → AudioArtifact)
- audio_artifact  AudioArtifact writer + fingerprint computation
- timeline        NarrationTimeline + DurationReconciliation policy
- timing          SpeechTiming parser + normalization
- pronunciation   Pronunciation / EmphasisHint canonical model + provider translator
- pipeline        PipelineStage wrapper that produces canonical artifacts

Design principles
-----------------
1. Deterministic where possible. Provider output is marked non-deterministic;
   orchestration around it (fingerprinting, validation, normalization, caching,
   duration reconciliation) is fully deterministic.
2. Provider isolation. Provider-specific logic stays inside concrete provider
   modules. Canonical models never reference provider types directly.
3. Secret safety. API keys / secrets are configuration-only and never serialized
   into artifacts, logs, SceneDefinition, AnimationPlan, or webapp state.
4. Idempotency. Same input (text + voice config + provider version + synthesis
   settings) produces the same AudioArtifact fingerprint → cache hit.
5. Traceability. Every voice resolution, every cache decision, every artifact
   creation is recorded in an audit-friendly log.
6. Failure handling. Explicit error categories; no silent provider switching
   in PRODUCTION mode.
"""
from __future__ import annotations

from app.voice import (
    audio_artifact,
    audio_validator,
    cache,
    lifecycle,
    mock_tts,
    narration,
    pipeline,
    pronunciation,
    provider_base,
    provider_factory,
    registry,
    resolver,
    schemas,
    timing,
    timeline,
)

__all__ = [
    "audio_artifact",
    "audio_validator",
    "cache",
    "lifecycle",
    "mock_tts",
    "narration",
    "pipeline",
    "pronunciation",
    "provider_base",
    "provider_factory",
    "registry",
    "resolver",
    "schemas",
    "timing",
    "timeline",
]
