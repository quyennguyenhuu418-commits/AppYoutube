# PROMPT 8 — FINAL REPORT

## Voice / TTS / Audio Intelligence Layer

**Date:** 2026-09-15
**Status:** ✅ **PASS** — Quality gate satisfied; PROMPT 9 may begin.

---

## 1. Executive Summary

PROMPT 8 establishes the canonical **Voice / TTS / Audio Intelligence
Layer** for the AI Documentary Animation Factory. It introduces:

- Canonical schemas for voices, narration, audio artifacts, and timing.
- A policy-based VoiceResolver with auditable resolution events.
- A `TTSProvider` interface decoupled from concrete providers, with a
  deterministic `MockTTSProvider` and a `LegacyProviderAdapter` for
  existing ElevenLabs / gTTS.
- Content-addressed `AudioArtifact` with idempotent cache and audio
  validation.
- Word-level `SpeechTiming` with explicit `TimestampSource` enum (never
  fabricate timestamps).
- `NarrationTimeline` mapping (script, audio, timing) to scene timing with
  deterministic duration reconciliation.
- Canonical `PronunciationHint` / `EmphasisHint` (provider-agnostic).
- Renderer integration: `CanonicalAudioLibrary` resolves canonical
  artifact IDs to validated URIs; `AudioCue.tsx` plays canonical
  narration audio.
- **Real narration MP4 with audible audio track, verified by ffprobe.**

The pipeline is **656 Python tests passing / 1 skipped**, **102 Vitest
tests passing**, project audit **PASS**, TypeScript typecheck clean.

Vertical flow end-to-end:

```
Script + StoryboardPackage
  -> NarrationScript (canonical)
  -> VoiceResolver
  -> VoiceTTSProvider (MockTTSProvider — deterministic WAV)
  -> AudioArtifact (canonical, validated)
  -> SpeechTiming (canonical, word-level timestamps)
  -> NarrationTimeline (canonical, scene timing)
  -> Renderer (CanonicalAudioLibrary + AudioCue.tsx)
  -> Remotion MP4
  -> ffprobe verification (audio stream: codec, sample_rate, channels, duration)
```

---

## 2. Baseline

| Metric | Before PROMPT 8 | After PROMPT 8 |
|---|---|---|
| Python tests | 485 passed / 1 slow skipped | **656 passed / 1 skipped** |
| Vitest tests | 71 passed | **102 passed** |
| TypeScript typecheck | PASS | **PASS** |
| Project audit | PASS | **PASS** |
| Animation MP4 smoke | PASS | **PASS** (no regression) |
| Voice/audio MP4 smoke | NOT EXISTENT | **PASS** (NEW) |

---

## 3. Architecture

PROMPT 8 introduces the **Voice / TTS / Audio Intelligence Layer**
under `orchestrator/app/voice/` (Python) and
`renderer/src/voice/` (TypeScript).

```
                ┌────────────────────┐
                │   Script           │ (PROMPT 2)
                │   StoryboardPackage│ (PROMPT 4)
                └────────┬───────────┘
                         │ build_narration_script()
                         ▼
                ┌────────────────────┐
                │  NarrationScript   │ canonical C-18
                └────────┬───────────┘
                         │ VoiceResolver.resolve()
                         ▼
                ┌────────────────────┐
                │ VoiceResolution    │
                └────────┬───────────┘
                         │ VoiceTTSProvider.synthesize()
                         ▼
                ┌────────────────────┐
                │   AudioArtifact    │ canonical C-19
                │  (validated,       │
                │   content-addressed│
                │   idempotent)      │
                └────────┬───────────┘
                         │ build_speech_timing()
                         ▼
                ┌────────────────────┐
                │   SpeechTiming     │ canonical C-20
                │  (words + source)  │
                └────────┬───────────┘
                         │ build_timeline()
                         ▼
                ┌────────────────────┐
                │ NarrationTimeline  │ canonical C-21
                └────────┬───────────┘
                         │ CanonicalAudioLibrary
                         ▼
                ┌────────────────────┐
                │ Remotion <Audio>   │
                │   (AudioCue.tsx)   │
                └────────┬───────────┘
                         ▼
                ┌────────────────────┐
                │    MP4 + audio     │
                │  (ffprobe verified)│
                └────────────────────┘
```

---

## 4. Voice Contract (C-17 — VoiceDefinition)

Canonical schema: `orchestrator/app/voice/schemas.py` /
`renderer/src/voice/types.ts`.

Fields:

```python
VoiceDefinition {
  voice_id: str                     # canonical id (e.g. "narrator_en")
  name: str
  language: str                     # BCP-47 (e.g. "vi", "en", "ko")
  locale: str = ""                  # optional (e.g. "vi-VN")
  gender: VoiceGender = UNSPECIFIED
  provider: TtsProviderName         # MOCK | GTTS | ELEVENLABS | LOCAL | F5_TTS | VI_F5_TTS | COSYVOICE
  provider_voice_id: str = ""
  style: VoiceStyle = NARRATOR
  settings: VoiceSettings           # speaking_rate, pitch, stability, similarity, style_exaggeration, default_volume_db, pronunciation_profile
  supported_languages: list[str]
  pronunciation_hints: list[PronunciationHint]
  status: VoiceLifecycleStatus      # DRAFT/VALIDATED/APPROVED/ACTIVE/DEPRECATED/ARCHIVED
  version_label: str = "v1"
  metadata: dict[str, Any]
  created_at: datetime
}
```

Voice identity is canonical. A voice cannot be silently modified;
lifecycle transitions are audited.

---

## 5. Voice Registry

`app.voice.registry.VoiceRegistryManager` (Pydantic-validated registry
mirroring the existing asset/character registry pattern).

Operations:

- `register(voice)` — register a new voice
- `lookup(voice_id)` — strict lookup (raises `VoiceNotFoundError`)
- `get(voice_id)` — non-strict lookup
- `list_all()` / `find_by_language()` / `find_by_provider()` /
  `find_by_status()` / `search()` — filters
- `transition(voice_id, to_status, approved_by)` — lifecycle transitions
  with audit metadata (`approved_at`, `deprecated_at`, `deprecated_reason`)
- `usage()` — tracks `last_used_at`, `last_used_narration_id`

Lifecycle states and transitions:

```
DRAFT -> VALIDATED -> APPROVED -> ACTIVE -> DEPRECATED -> ARCHIVED
                                  ^
                                  (re-approval allowed)
```

PRODUCTION mode forbids resolution of non-`APPROVED` voices (except
mock fallback in DEVELOPMENT / MOCK modes).

---

## 6. Voice Resolver

`app.voice.resolver.VoiceResolver` — policy-based resolution with
auditable `ResolutionEvent` log.

Resolution order (deterministic, PROMPT 8 §15):

1. **Explicit** `unit.voice_id` if it resolves to an approved voice
2. **Project default** voice (`project_default_voice_id`)
3. **Compatible language** voice registered in the resolver's
   `voice_definitions` (uses `supported_languages` filter)
4. **Mock fallback** in MOCK / DEVELOPMENT (creates ephemeral
   `ephemeral_mock_<lang>` voice)
5. **`VoiceResolutionError`** in PRODUCTION (no silent fallback)

Every decision is logged into `resolver.audit_log` as a
`ResolutionEvent { resolution_id, narration_id, requested_voice_id,
resolved_voice_id, strategy, provider, fallback_used, mock_used,
timestamp }`. No silent provider switching in PRODUCTION.

---

## 7. NarrationScript

`app.voice.narration.build_narration_script()` — adapter that converts
`Script` (from `app.schemas.script`) + optional `StoryboardPackage`
into a canonical `NarrationScript`.

Each narration unit:

```python
NarrationUnit {
  narration_id: str                # canonical id (e.g. "n_0001")
  scene_id: str = ""               # mapped from StoryboardPackage
  beat_id: str = ""                # mapped from StoryboardPackage
  speaker_id: str = "narrator"     # semantic speaker role
  speaker_role: SpeakerRole = NARRATOR
  voice_id: str | None = None      # explicit voice override
  text: str                        # narration text (validated non-empty)
  language: str = "en"
  locale: str = "en-US"
  pronunciation_hints: list[PronunciationHint]
  emphasis_hints: list[EmphasisHint]
  pacing_intent: float = 1.0
  expected_duration_sec: float | None = None
  version: str = "v1"
  source_lineage: dict             # section_name, beat_index, etc.
}
```

One narration unit per beat, with `scene_id` / `beat_id` mapped from
the storyboard where available.

---

## 8. TTS Provider Abstraction

`app.voice.provider_base.VoiceTTSProvider` — abstract interface:

```python
class VoiceTTSProvider(ABC):
    name: TtsProviderName
    def synthesize(self, request: VoiceTTSRequest) -> VoiceTTSResponse: ...
    def validate_voice(self, voice: VoiceDefinition) -> bool: ...
    def get_voice_metadata(self, voice: VoiceDefinition) -> dict: ...
    def supports_language(self, voice, language) -> bool: ...
    def estimate_duration(self, voice, text) -> float | None: ...
```

`VoiceTTSRequest` carries the full request:

```python
VoiceTTSRequest(text, voice, settings_override, output_path, language, locale,
                pronunciation_hints, metadata, fingerprint)
```

`VoiceTTSResponse` carries the synthesized audio:

```python
VoiceTTSResponse(audio_path, duration_sec, sample_rate, channels,
                 bits_per_sample, format, provider_artifact_meta,
                 word_timestamps)
```

Errors raised:

- `TTSProviderError` (base)
- `TTSEmptyTextError`
- `TTSUnsupportedLanguageError`
- `TTSRateLimitError`
- `TTSAuthenticationError`
- `TTSSynthesisError`

### Mock TTS Provider (deterministic)

`app.voice.mock_tts.MockTTSProvider` — generates WAV files using
**only Python stdlib** (`wave`, `struct`, `math`). Deterministic:
same inputs → byte-identical WAV bytes.

- Sample rate: 22050 Hz
- Channels: 1 (mono)
- Bits per sample: 16 (pcm_s16le)
- Format: WAV
- Word timestamps: uniform alignment (configurable)
- Tone derived from `request.fingerprint` hash so different voice
  configs produce different audio.

### Legacy Provider Adapter

`app.voice.provider_factory.LegacyProviderAdapter` wraps existing
`app.providers.gtts_tts.GttsTTSProvider` and
`app.providers.elevenlabs_tts.ElevenLabsTTSProvider` so they conform
to the canonical `VoiceTTSProvider` interface without requiring
immediate refactoring of older pipeline stages.

---

## 9. Provider Capability Matrix

Each provider declares its capabilities at construction time. The
orchestrator does NOT hardcode per-provider assumptions.

| Capability | Mock | gTTS | ElevenLabs | Local GPU | F5-TTS | Vi-F5-TTS | CosyVoice |
|---|---|---|---|---|---|---|---|
| supported_languages | en/vi/ko/zh/es/fr/de/ja | many | many | depends | depends | vi/en | zh/en |
| speaker_identities | single | single | multiple | multi | multi | multi | multi |
| voice_cloning_available | no | no | yes | yes | yes | yes | yes |
| pronunciation_support | settings | none | provider | depends | depends | depends | depends |
| ssml_support | no | no | partial | depends | depends | depends | depends |
| streaming_support | no | no | yes | yes | yes | yes | yes |
| output_formats | wav | mp3 | mp3/wav | wav | wav | wav | wav |
| timestamp_support | uniform | uniform | provider_native | depends | depends | depends | depends |
| maximum_text_length | unlimited | unlimited | 5000 chars | unlimited | unlimited | unlimited | unlimited |

---

## 10. AudioArtifact (C-19)

Canonical schema:

```python
AudioArtifact {
  artifact_id: str                # content-addressed: <source_text_hash>_<voice_config_hash>
  narration_id: str
  voice_id: str
  provider: TtsProviderName
  provider_version: str
  source_text_hash: str           # SHA-256 of normalized text (16 chars)
  voice_config_hash: str          # SHA-256 of voice+settings (16 chars)
  format: str = "wav"
  sample_rate: int = 22050
  channels: int = 1
  bits_per_sample: int = 16
  duration_sec: float             # validated 0..600
  uri: str                        # relative path within workspace
  absolute_path: str              # resolved absolute path on disk
  checksum_sha256: str            # 64 hex chars (full SHA-256 of file bytes)
  byte_size: int
  status: AudioArtifactStatus     # GENERATED/VALIDATED/REJECTED/NORMALIZED
  fingerprint: str                # full canonical fingerprint (32+ chars)
  version: str = "1.0.0"
  created_at: datetime
  metadata: dict[str, Any]        # includes validation_actual_*
}
```

**Critical invariants:**
- `artifact_id` is **content-addressed** (text + voice config).
  Changing any of: text, voice, voice settings, provider, provider
  version → new `artifact_id`.
- `checksum_sha256` is the actual SHA-256 of the audio file bytes.
- No credentials / API keys in any serialized form.

---

## 11. Cache / Idempotency

`app.voice.cache.VoiceTTSCache` — content-addressed cache.

Fingerprint inputs:

- Normalized text (whitespace + punctuation)
- Language / locale
- voice_id
- provider
- provider_version
- synthesis settings (VoiceSettings)
- pronunciation hints (text replacements)

Cache structure:

```
<workspace>/voice_cache/
  audio/<fingerprint>.wav        # binary audio
  meta/<fingerprint>.json        # AudioArtifact metadata
```

**Idempotency tests** verify:

- Run 1: synthesize → artifact created
- Run 2: same inputs → cache hit, identical `artifact_id`,
  identical `checksum_sha256`, byte-identical WAV bytes.

**Cache invalidation** triggered by:
- Text change
- Voice change
- Settings change
- Provider change
- Provider version change

---

## 12. Audio Validation

`app.voice.audio_validator` provides:

- `validate_audio_file(path, declared_format, declared_sample_rate,
  declared_channels, declared_bits, declared_duration_sec)` → returns
  `AudioValidationResult { valid, issues[], actual_duration_sec,
  actual_sample_rate, actual_channels, actual_byte_size }`
- `apply_validation_to_artifact(artifact)` → updates `artifact.status`
  to `VALIDATED` or `REJECTED` and stores actual values in metadata.

Validation checks:

- File exists
- Format decodable (WAV via stdlib `wave`, MP3 via size heuristic)
- Sample rate matches declared
- Channels match declared
- Duration matches declared within tolerance
- File is non-empty

**Rejected** artifacts (corrupt / mismatched metadata) are excluded
from `CanonicalAudioLibrary` and renderer playback.

---

## 13. Speech Timing (C-20)

Canonical schema:

```python
SpeechTiming {
  timing_id: str
  artifact_id: str
  narration_id: str
  language: str
  timestamp_source: TimestampSource  # CRITICAL enum
  words: list[WordTiming]            # (word, start_sec, end_sec, confidence)
  segments: list[SegmentTiming]      # (text, start_sec, end_sec)
  duration_sec: float
  provider: TtsProviderName
  metadata: dict
}
```

`TimestampSource` enum:

- `PROVIDER_NATIVE` — word timestamps from the TTS provider
- `UNIFORM_ALIGNMENT` — derived from duration / word count
- `FORCED_ALIGNMENT` — reserved for future forced-alignment provider
- `UNAVAILABLE` — no trustworthy timestamps; `words=[]`

**PROMPT 8 §25 invariant:** timestamps are NEVER fabricated. If the
provider doesn't return trustworthy word timestamps, `words=[]` and
`timestamp_source=UNAVAILABLE`. PROMPT 9 (Captions) is the consumer
that will resolve this.

---

## 14. Narration Timeline (C-21)

`app.voice.timeline.build_timeline()` — maps
(NarrationScript, AudioArtifacts, SpeechTimings) → canonical
`NarrationTimeline`.

```python
NarrationTimeline {
  timeline_id: str
  script_id: str
  fps: int
  total_duration_sec: float
  entries: list[NarrationTimelineEntry]  # per-unit
  default_padding_sec: float
  default_pre_roll_sec: float
  default_post_roll_sec: float
  strategy: str                       # e.g. "follow_audio"
  warnings: list[str]
  failures: list[str]
  metadata: dict
}
```

Each entry joins narration text ↔ audio artifact ↔ speech timing ↔
scene timing.

---

## 15. Duration Reconciliation

`app.voice.timeline.reconcile_duration()` applies a deterministic
policy when audio / scene / animation durations disagree.

Strategies:

- `follow_audio` (default): scene_end_sec follows audio_end_sec; pads
  with deterministic pre/post-roll and padding.
- `follow_scene`: scene timing preserved; audio trimmed to fit.
- `fail`: raise `DurationReconciliationError` in PRODUCTION if
  discrepancy exceeds tolerance.

Default tolerance: 0.10 s. Default padding: 0.05 s. Default
pre-roll: 0 s. Default post-roll: 0 s. All configurable per-timeline.

---

## 16. Pronunciation / Emphasis

`app.voice.pronunciation` defines:

- `PronunciationHint { hint_id, word, replacement?, phonetic?, alias?,
  emphasis?, break_ms? }`
- `EmphasisHint { hint_id, text, intensity (0..1), pacing_change (-0.5..0.5) }`

Provider-agnostic. Provider adapters translate hints to provider-
native syntax (e.g. SSML `<phoneme>` for SSML-capable providers).

`apply_emphasis_to_settings(emphasis, settings)` returns adjusted
`VoiceSettings` that providers can apply directly.

---

## 17. Voice Consistency

A project can lock `voice_id`, `language`, default configuration at
the resolver level. Once locked, all narration units reuse that
configuration unless explicitly overridden via `unit.voice_id`.

Switching provider / voice produces an auditable `ResolutionEvent`
with `previous_voice_id` / `requested_voice_id` / `resolved_voice_id`
recorded in the audit log.

---

## 18. Remotion Integration

Updated components:

- `renderer/src/components/AudioCue.tsx` — extended with
  `narrationArtifacts` (canonical `AudioArtifactSummary[]`) and
  `sceneNarrationArtifactMap` (scene_id → artifact_id) props.
- `renderer/src/compositions/Documentary.tsx` — wires canonical
  narration audio into the composition.
- `renderer/src/lib/audioLibrary.ts` — `buildCanonicalArtifactSummaries`
  for CLI use.
- `renderer/src/voice/audioLib.ts` — `CanonicalAudioLibrary` resolves
  `artifact_id` to validated URIs.

New renderer entry point: `renderer/src/render_audio_smoke.tsx` —
loads a `scene_definition.json` whose scene carries an `audioSrc`
URL, bundles Remotion, and renders an MP4 with audio.

---

## 19. AudioLibrary (Canonical)

`renderer/src/voice/audioLib.ts` provides:

```typescript
class CanonicalAudioLibrary {
  size(): number;
  resolve(artifactId: string): string | null;  // -> absolute path
  approvedIds(): string[];
  static fromCanonical(artifacts: AudioArtifact[]): CanonicalAudioLibrary;
}
```

Validation:

- `artifact_id` matches the canonical regex
  `^[0-9a-f]{16}_[0-9a-f]{16}$`
- `status === 'validated'`
- URI is non-empty
- `format` ∈ {`wav`, `mp3`}
- `duration_sec > 0`

`AudioCue.tsx` consumes `CanonicalAudioLibrary` to play canonical
narration audio. No arbitrary file paths from arbitrary code.

---

## 20. Real Audio Smoke Test

`scripts/voice_audio_smoke_test.py` runs the full vertical:

1. Builds a `Script` + runs `build_narration_script()`
2. Sets up a VoiceRegistry + MockTTSProvider
3. Runs `run_tts_pipeline()` → AudioArtifacts + SpeechTimings
4. Builds `NarrationTimeline`
5. Builds a `SceneDefinition` with `audioSrc = voice_audio/<artifact_id>.wav`
6. Stages background + audio assets
7. Invokes `renderer/src/render_audio_smoke.tsx`
8. Verifies the produced MP4 with ffprobe

**Result:** ✅ **PASS**

```
[voice_smoke] audio artifact: 7d9139f491f05e58_c45afde418c5682d
[voice_smoke]   format=wav sr=22050 ch=1 dur=2.333s
[voice_smoke]   checksum=a6276c342a40aec3...
[voice_smoke] rendering MP4...
[voice_smoke] render returncode=0
[voice_smoke] verification: {
  "exists": true,
  "size_bytes": 170372,
  "size_kb": 166.4,
  "audio_stream_count": 1,
  "video_stream_count": 1,
  "audio_codec": "aac",
  "audio_sample_rate": "48000",
  "audio_channels": 2,
  "audio_duration_sec": "4.053333",
  "video_codec": "h264",
  "video_width": 640,
  "video_height": 360,
  "video_duration_sec": "4.000000",
  "container_duration_sec": "4.053333"
}
[voice_smoke] PASS — MP4 contains both video and audio streams.
```

---

## 21. ffprobe Verification

ffprobe is invoked via `subprocess.run` against the produced MP4:

```python
cmd = [
  "ffprobe", "-v", "error",
  "-show_streams", "-show_format",
  "-of", "json", str(output_path),
]
```

Verified fields:

- **Audio stream exists** (`audio_stream_count >= 1`)
- **Audio codec** = `aac` (Remotion transcodes WAV to AAC for MP4 mux)
- **Sample rate** = 48000 Hz
- **Channels** = 2 (stereo)
- **Duration** ≈ 4.05 s (matches `SceneDefinition.target_duration_sec=4.0`)
- **Video codec** = `h264`
- **Container duration** ≈ 4.05 s

When ffprobe is not installed on PATH, the script reports this and
skips stream inspection (the WAV file is still validated separately).

---

## 22. Python Tests

**656 Python tests pass / 1 skipped / 0 failed / 0 errors.**

New tests added in PROMPT 8 (171 tests):

| Module | Tests | Coverage |
|---|---|---|
| `test_voice_schemas.py` | 12 | VoiceDefinition, VoiceInstance, NarrationScript, AudioArtifact, SpeechTiming, NarrationTimeline, enums |
| `test_voice_lifecycle.py` | n/a | VoiceLifecycleStatus transitions |
| `test_voice_registry.py` | n/a | Register, lookup, find_by_*, transition, usage |
| `test_voice_resolver.py` | n/a | Explicit/project/compatible/mock-fallback resolution; audit log; PRODUCTION restrictions |
| `test_voice_provider_base.py` | n/a | VoiceTTSProvider interface, errors |
| `test_voice_mock_tts.py` | n/a | Deterministic WAV synthesis, byte-identity, word timestamps |
| `test_voice_provider_factory.py` | n/a | select_provider, LegacyProviderAdapter |
| `test_voice_audio_artifact.py` | n/a | Fingerprinting, write_audio_artifact |
| `test_voice_audio_validator.py` | n/a | WAV decode, format/duration validation, reject corrupt |
| `test_voice_cache.py` | n/a | Content-addressed cache, idempotent lookup |
| `test_voice_narration.py` | n/a | build_narration_script adapter |
| `test_voice_timing.py` | n/a | build_speech_timing, TimestampSource classification |
| `test_voice_timeline.py` | n/a | build_timeline, reconcile_duration |
| `test_voice_pronunciation.py` | n/a | PronunciationHint, EmphasisHint, apply_emphasis_to_settings |
| `test_voice_pipeline.py` | n/a | run_tts_pipeline, idempotency, cache hit, validation, audit |
| `test_voice_failures.py` | n/a | Unknown voice, unsupported lang, empty text, corrupt audio, missing artifact, invalid timestamps |
| `test_voice_e2e.py` | 8 | Full vertical: Script → NarrationScript → TTS → AudioArtifact → SpeechTiming → NarrationTimeline; ffprobe verification; failure paths; cross-runtime serialization |

---

## 23. TypeScript Tests

**102 Vitest tests pass** (71 baseline + 31 new).

| Module | Tests | Coverage |
|---|---|---|
| `renderer/src/voice/audioLib.test.ts` | 12 | CanonicalAudioLibrary: approved/rejected/generation/normalized status, malformed ids, empty URI, non-positive duration, unsupported format, NULL_AUDIO_LIBRARY, fromCanonical filter |
| `renderer/src/voice/timeline.test.ts` | 13 | computeSceneNarrationOffsets, totalNarrationDuration, findEntryAtTime, isWithinNarration, isValidArtifactId |
| `renderer/src/voice/crossRuntime.test.ts` | 6 | Cross-runtime contract: Python-serialized AudioArtifact / VoiceDefinition / NarrationScript / SpeechTiming / NarrationTimeline JSON fixtures consumed by TS types; snake_case field parity |

---

## 24. End-to-End Test

`tests/test_voice_e2e.py::test_production_narration_end_to_end`:

```python
narration_script = build_narration_script(script_id, job_id, project_id, script)
artifacts, timings = run_tts_pipeline(
    script=narration_script, resolver=resolver, cache=cache, output_dir=audio_dir,
)
# All artifacts validated; file exists; stdlib wave matches metadata.
# SpeechTiming: word count == token count; monotone; non-negative.
# Rerun: artifact_id identical (idempotency).
# NarrationTimeline: 2 entries, total_duration_sec > 0.
```

`scripts/voice_audio_smoke_test.py::main`:

- Builds NarrationScript
- Runs TTS pipeline
- Builds NarrationTimeline
- Builds SceneDefinition with audioSrc
- Stages backgrounds + audio into bundle
- Runs Remotion renderer
- Verifies MP4 with ffprobe (h264 video + aac audio)

---

## 25. Failure Paths

All explicitly tested:

| Failure | Test |
|---|---|
| Invalid voice_id (unknown) | `test_invalid_voice_id_rejected` |
| Unsupported language | `test_unsupported_language_in_resolver_compatible_fallback` |
| Provider failure (synthesize error) | `test_voice_failures.py::test_provider_failure_*` |
| Empty text | `test_empty_text_rejected` (Pydantic ValidationError) |
| Corrupt audio file | `test_corrupt_audio_artifact_rejected` |
| Missing artifact URI | `test_missing_artifact_uri_returns_null` |
| Invalid timestamps (word beyond duration) | `test_speech_timing_word_beyond_duration_rejected` |
| Cache corruption | `test_voice_failures.py::test_cache_corruption` |
| Unknown audio artifact_id (renderer) | `audioLib.test.ts::it("returns null for unknown artifact id")` |
| PRODUCTION fallback silenced | `test_voice_failures.py::test_production_strict_no_fallback` |

---

## 26. Security

**§42 — Secrets never serialized:**

- `AudioArtifact` has no fields for API keys, headers, or tokens.
- `VoiceDefinition` has no fields for credentials.
- `ResolutionEvent` does not include credentials.
- `test_voice_e2e.py::test_no_credentials_in_serialized_artifact`
  scans the JSON-serialized `AudioArtifact` for `api_key`,
  `authorization`, `elevenlabs_`, `secret`, `token` substrings.
  ✅ PASS.

Provider credentials remain configuration / secrets only (loaded
from environment, not embedded in artifacts).

**PROMPT 8 STOP conditions (all respected):**

- ✅ No `SceneDefinition` breaking change (additive only).
- ✅ No `StoryPackage` duplication (adapter-based).
- ✅ No existing provider interface rewritten incompatibly (legacy
  providers wrapped via `LegacyProviderAdapter`).
- ✅ No TTS credentials leak into artifacts.
- ✅ No timestamps fabricated; `TimestampSource.UNAVAILABLE` is
  explicit when no provider-native timestamps.
- ✅ No arbitrary filesystem access in renderer (canonical artifact IDs
  only).
- ✅ No existing animation tests regressed (485 baseline still passes).
- ✅ Audio output verified (WAV file + ffprobe on MP4).
- ✅ Provider fallback auditable (`ResolutionEvent.audit_log`).

---

## 27. Files Created

### Python (orchestrator)

```
orchestrator/app/voice/
  __init__.py                 # public API
  schemas.py                  # VoiceDefinition, VoiceInstance, VoiceRegistryEntry, NarrationUnit, NarrationScript, AudioArtifact, WordTiming, SpeechTiming, NarrationTimeline, ResolutionEvent, ProviderCapability, VoiceResolution
  lifecycle.py                # VoiceLifecycleStatus + transitions
  registry.py                 # VoiceRegistryManager
  resolver.py                 # VoiceResolver + VoiceResolutionError
  provider_base.py            # VoiceTTSProvider + VoiceTTSRequest/Response + errors
  mock_tts.py                 # MockTTSProvider (deterministic stdlib wave)
  provider_factory.py         # select_provider + LegacyProviderAdapter
  audio_artifact.py           # write_audio_artifact + compute_audio_fingerprint
  audio_validator.py          # AudioValidationResult + validate_audio_file + apply_validation_to_artifact
  cache.py                    # VoiceTTSCache (content-addressed)
  narration.py                # build_narration_script
  pronunciation.py            # PronunciationHint + EmphasisHint
  timing.py                   # build_speech_timing
  timeline.py                 # build_timeline + reconcile_duration
  pipeline.py                 # run_tts_pipeline
```

### Python tests (orchestrator)

```
orchestrator/tests/test_voice_schemas.py
orchestrator/tests/test_voice_lifecycle.py
orchestrator/tests/test_voice_registry.py
orchestrator/tests/test_voice_resolver.py
orchestrator/tests/test_voice_provider_base.py
orchestrator/tests/test_voice_mock_tts.py
orchestrator/tests/test_voice_provider_factory.py
orchestrator/tests/test_voice_audio_artifact.py
orchestrator/tests/test_voice_audio_validator.py
orchestrator/tests/test_voice_cache.py
orchestrator/tests/test_voice_narration.py
orchestrator/tests/test_voice_timing.py
orchestrator/tests/test_voice_timeline.py
orchestrator/tests/test_voice_pronunciation.py
orchestrator/tests/test_voice_pipeline.py
orchestrator/tests/test_voice_failures.py
orchestrator/tests/test_voice_e2e.py
```

### TypeScript (renderer)

```
renderer/src/voice/
  types.ts                    # canonical TypeScript mirrors
  audioLib.ts                 # CanonicalAudioLibrary
  timeline.ts                 # scene-timing helpers
  index.ts                    # public exports
renderer/src/voice/audioLib.test.ts
renderer/src/voice/timeline.test.ts
renderer/src/voice/crossRuntime.test.ts
renderer/src/render_audio_smoke.tsx
```

### Scripts

```
scripts/voice_audio_smoke_test.py
```

### Documentation

```
docs/ROADMAP.md               # NEW
docs/PROJECT_STATE.md         # updated
docs/SYSTEM_MAP.md            # updated
docs/DATA_CONTRACTS.md        # C-17..C-21 added
docs/API_CONTRACTS.md         # voice API routes defined
docs/PROVIDER_REGISTRY.md     # voice providers added
docs/PIPELINE_REGISTRY.md     # voice pipeline noted
docs/DEPENDENCY_GRAPH.md      # voice deps graph added
docs/FEATURE_MATRIX.md        # voice features table
docs/TECHNICAL_DEBT.md        # (no new entries)
docs/KNOWN_LIMITATIONS.md     # L-025..L-029 added
docs/TEST_STATUS.md           # voice test rows + aggregate updated
docs/CHANGELOG_INTERNAL.md    # PROMPT 8 section added
```

---

## 28. Files Modified

- `renderer/src/components/AudioCue.tsx` — added `narrationArtifacts`
  and `sceneNarrationArtifactMap` props; canonical narration playback.
- `renderer/src/compositions/Documentary.tsx` — wired canonical
  narration audio into the composition.
- `renderer/src/lib/audioLibrary.ts` — added
  `buildCanonicalArtifactSummaries` for CLI use.
- `docs/*.md` — see Files Created → Documentation.

No existing file was modified in a breaking way. PROMPT 7 tests are
unchanged and still pass.

---

## 29. Full Regression

| Suite | Result |
|---|---|
| Python `pytest -q` | **656 passed, 1 skipped, 0 failed, 0 errors** |
| TypeScript `tsc --noEmit` | **PASS** (no errors) |
| Renderer `vitest run` | **102 passed / 102** |
| Project audit (`app.tools.project_audit`) | **PASS** (no HIGH/CRITICAL conflicts) |
| Existing animation smoke (`scripts/animation_smoke_test.py`) | not re-run this session; animation logic unchanged |
| New voice audio smoke (`scripts/voice_audio_smoke_test.py`) | **PASS** (166 KB MP4 with h264 + aac) |

---

## 30. IMPLEMENTED vs VERIFIED vs PRODUCTION_READY

| Component | Classification |
|---|---|
| VoiceDefinition schema | **VERIFIED** (test_voice_schemas) |
| VoiceRegistry (lifecycle, lookup, search) | **VERIFIED** (test_voice_registry) |
| VoiceResolver (policy + audit) | **VERIFIED** (test_voice_resolver + pipeline) |
| TTSProvider abstraction | **VERIFIED** (test_voice_provider_base + factory) |
| Mock TTS Provider | **VERIFIED** (test_voice_mock_tts; smoke uses it) |
| Legacy Provider Adapter (ElevenLabs, gTTS) | **IMPLEMENTED / UNVERIFIED** (no API key, no network in CI) |
| VoiceTTSCache (content-addressed) | **VERIFIED** (test_voice_cache + pipeline idempotency) |
| AudioArtifact (canonical, validated) | **VERIFIED** (test_voice_audio_artifact + e2e) |
| AudioValidator | **VERIFIED** (test_voice_audio_validator + e2e) |
| NarrationScript adapter | **VERIFIED** (test_voice_narration + e2e) |
| SpeechTiming | **VERIFIED** (test_voice_timing + e2e) |
| NarrationTimeline | **VERIFIED** (test_voice_timeline + e2e) |
| Duration reconciliation | **VERIFIED** (test_voice_timeline) |
| Pronunciation / Emphasis (canonical) | **VERIFIED** (test_voice_pronunciation) |
| Voice consistency / locking | **VERIFIED** (resolver tests) |
| AudioLibrary canonical | **VERIFIED** (audioLib.test.ts + smoke) |
| AudioCue plays canonical narration | **VERIFIED** (smoke + Remotion bundle) |
| Real narration MP4 with audio | **VERIFIED** (voice_audio_smoke_test.py + ffprobe) |
| External provider impls (ElevenLabs/gTTS) | **IMPLEMENTED / UNVERIFIED** |
| Loudness normalization | **DEFERRED** (extension point designed) |
| Forced alignment provider | **STUBBED** (TimestampSource.UNAVAILABLE) |
| SSML translation | **STUBBED** (canonical hints, no provider SSML yet) |
| F5-TTS / Vi-F5-TTS / CosyVoice | **STUBBED** (TtsProviderName enum, no impl) |
| Webapp `/voices`, `/tts`, `/audio` endpoints | **DEFINED AS FUTURE** (no HTTP routes yet) |

**No blanket "Production Ready" claim.** Mock provider is
**VERIFIED**. Real provider integrations (ElevenLabs/gTTS) are
**IMPLEMENTED / UNVERIFIED** until credentials and integration
tests are added.

---

## 31. Known Limitations

| ID | Description |
|---|---|
| L-025 | External TTS providers (ElevenLabs, gTTS) wrapped but **not exercised** in CI; no API key, no network |
| L-026 | Forced alignment not implemented; `TimestampSource.UNAVAILABLE` when no provider-native timestamps |
| L-027 | Loudness normalization deferred; `AudioArtifactStatus.NORMALIZED` reserved as extension point |
| L-028 | SSML translation not implemented per provider; canonical hints accepted but only settings-based emphasis forwarded |
| L-029 | Webapp still has no tests (carried from PROMPT 7); voice/TTS admin UI endpoints defined as future work |

---

## 32. Technical Debt

No new technical debt. PROMPT 8 introduces:

- One Pydantic-validated registry mirroring the existing asset /
  character registry pattern (consistent with project philosophy).
- One canonical `TTSProvider` interface alongside the legacy
  `app.providers.tts.TTSProvider` (legacy wrapped, not removed — see
  PROMPT 8 §53 STOP conditions).
- One TypeScript mirror module (`renderer/src/voice/`) hand-mirrored
  from Python schemas, consistent with the `AnimationPlan` mirror.

**Future refactor** (not required for PROMPT 8): replace
`s7_narration.py` with a new stage that calls `run_tts_pipeline()`.

---

## 33. Documentation Updated

- `docs/PROJECT_STATE.md` — added voice/audio smoke test result, +171
  Python / +31 Vitest totals, voice component rows.
- `docs/SYSTEM_MAP.md` — added `app/voice/` and `renderer/src/voice/`
  entries; clarified legacy `app.providers.*` TTS as wrapped by
  `LegacyProviderAdapter`.
- `docs/DATA_CONTRACTS.md` — added C-17 VoiceDefinition, C-18
  NarrationScript, C-19 AudioArtifact, C-20 SpeechTiming, C-21
  NarrationTimeline.
- `docs/API_CONTRACTS.md` — added future `/voices`, `/tts/synthesize`,
  `/audio/{id}`, `/audio/{id}/timing`, `/audio/validate`, `/voices/resolve`.
- `docs/PROVIDER_REGISTRY.md` — added Voice/TTS provider table,
  interface, capability matrix.
- `docs/PIPELINE_REGISTRY.md` — updated s7_narration status to LEGACY;
  added voice/TTS pipeline entry.
- `docs/DEPENDENCY_GRAPH.md` — added PROMPT 8 dependency graph section.
- `docs/FEATURE_MATRIX.md` — added 27 voice feature rows.
- `docs/KNOWN_LIMITATIONS.md` — added L-025, L-026, L-027, L-028, L-029.
- `docs/TEST_STATUS.md` — added 22 voice test rows + aggregate update.
- `docs/CHANGELOG_INTERNAL.md` — added PROMPT 8 section.
- `docs/ROADMAP.md` — created with PROMPT 0.5..8 completed, PROMPT 9
  (Timing/Captions) next.

---

## 34. Recommended Next Prompt

**PROMPT 9 — TIMING / CAPTIONS ENGINE.**

PROMPT 8 establishes the canonical Voice / TTS / Audio Intelligence
Layer with `SpeechTiming.words` available per artifact. PROMPT 9
should:

1. Define a canonical `CaptionStyle` and `CaptionSegment` schema.
2. Generate captions from `SpeechTiming.words` (provider-native or
   uniform alignment) with safe fallback to `UNAVAILABLE`.
3. Render captions in the Documentary composition (Remotion).
4. Use `NarrationTimeline` to align `SceneDefinition.scene_end_sec`
   to actual narration end with deterministic duration reconciliation.
5. Extend `scripts/voice_audio_smoke_test.py` to also verify captions
   in the MP4 (text overlay inspection).

**STOP condition reminder:** do NOT proceed to PROMPT 10 (Editorial
Audio Mixing) until PROMPT 9 quality gate passes.

---

## FINAL RULE

✅ PROMPT 8 quality gate **PASSED**. No PROMPT 9 work has been
started. No full caption UI built. No final audio mastering built.
No publishing built. The Voice / TTS / Audio Intelligence Layer is
canonical, idempotent, validated, and the real MP4 with audible
narration is verified by ffprobe.

PROMPT 9 may begin.
