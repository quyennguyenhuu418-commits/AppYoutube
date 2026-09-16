# PROVIDER_REGISTRY

Every external capability the orchestrator depends on. Classified by
runtime readiness — never by documentation claim.

Readiness values:
- `REAL` — production-ready, requires API key, code implements the ABC
  fully.
- `PARTIAL` — implemented but limited (e.g., no error handling on edge
  cases, degraded output).
- `MOCK` / `TEST_ONLY` — never call from production; used by tests.
- `UNVERIFIED` — written but never exercised end-to-end.
- `DEPRECATED` — do not use; kept only for compat.

---

## LLM

### `OpenAILLMProvider`
- File: `orchestrator/app/providers/openai_llm.py:103`
- ABC: `LLMProvider` (`base.py:132`)
- Tasks: research, scriptwriter, JSON-agent, storyboard, titles system prompts
- Models: `OPENAI_LLM_MODEL` (default: in `.env.example`), `OPENAI_LLM_MODEL_LARGE`
- Configuration: `OPENAI_API_KEY` required
- Tests: indirectly via `test_mock_providers.py`, `test_research_engine.py`
- Fallback: `MockLLMProvider` if `OPENAI_API_KEY == ""`
- Readiness: REAL
- Known issues: none

### `MockLLMProvider`
- File: `orchestrator/app/providers/mock_llm.py:617`
- ABC: `LLMProvider`
- Tasks: canned `MOCK_RESEARCH`, `MOCK_THESIS`, `MOCK_TITLES`, `MOCK_SCRIPT`,
  `MOCK_STORYBOARD`, `MOCK_RESEARCH_PACKAGE`, `_mock_scene_json()`
- Tests: `test_mock_providers.py`
- Readiness: TEST_ONLY

---

## TTS

### `ElevenLabsTTSProvider`
- File: `orchestrator/app/providers/elevenlabs_tts.py:87`
- ABC: `TTSProvider`
- Endpoint: `/v1/text-to-speech/{voice_id}/with-timestamps`
- Models: `ELEVENLABS_MODEL_ID`
- Configuration: `ELEVENLABS_API_KEY`, `ELEVENLABS_VOICE_ID`
- Tests: none
- Fallback: `GTTSTTSProvider` if `ELEVENLABS_API_KEY == ""`
- Readiness: REAL
- Known issues: untested end-to-end on this dev host

### `GTTSTTSProvider`
- File: `orchestrator/app/providers/gtts_tts.py:73`
- ABC: `TTSProvider`
- Configuration: none required (uses `gTTS` package)
- Tests: none
- Word alignment: uniform per-word timestamps by duration / n words;
  `pydub` probe with byte-size fallback
- Readiness: REAL

---

## Image

### `DALLEImageProvider`
- File: `orchestrator/app/providers/dalle_image.py:66`
- ABC: `ImageProvider`
- Model: `OPENAI_IMAGE_MODEL` (DALL-E 3)
- Configuration: `OPENAI_API_KEY`
- Output: PNG saved to `backgrounds/`
- Readiness: REAL
- Known issues: slow, costs money

### `PlaceholderImageProvider`
- File: `orchestrator/app/providers/placeholder_image.py:72`
- ABC: `ImageProvider`
- Implementation: pure Python PNG generator, no Pillow; MD5-hashed palette
- Output: solid-color PNG
- Tests: indirectly via pipeline integration
- Readiness: PARTIAL — visually inert; useful as a test stand-in

---

## Search

### `DuckDuckGoSearchProvider`
- File: `orchestrator/app/providers/research_providers.py:200`
- ABC: `SearchProvider`
- Library: `duckduckgo-search`
- Configuration: none required
- Tests: NONE — never runtime-verified end-to-end
- Fallback: `MockSearchProvider`
- Readiness: UNVERIFIED

### `MockSearchProvider`
- File: `orchestrator/app/providers/mock_research.py:140`
- ABC: `SearchProvider`
- Coverage: structural fixtures for all tiers + URLs
- Tests: `test_research_engine.py`
- Readiness: TEST_ONLY

---

## Content Fetch

### `RequestsContentFetchProvider`
- File: `orchestrator/app/providers/research_providers.py:200`
- ABC: `ContentFetchProvider`
- Implementation: `httpx` GET + regex HTML strip (script/style/nav/footer
  removed)
- Tier mapping: hardcoded domain → tier
- Tests: NONE — never runtime-verified end-to-end
- Readiness: UNVERIFIED
- Known issues:
  - Regex strip misses JS-heavy pages (returns shell only)
  - Tier mapping is hardcoded and brittle
  - See `docs/KNOWN_LIMITATIONS.md`

### `MockContentFetchProvider`
- File: `orchestrator/app/providers/mock_research.py:140`
- ABC: `ContentFetchProvider`
- Coverage: per-URL fixture content
- Tests: `test_research_engine.py`
- Readiness: TEST_ONLY

---

## Render

### `RenderStage` (subprocess invoker, not a provider)
- File: `orchestrator/app/pipeline/stages/s10_render.py:49`
- Implementation: `subprocess.run(['npx', 'tsx', 'src/index.ts', job_id], cwd=RENDERER_DIR, timeout=900)`
- Configuration: `RENDERER_DIR` (default: `../renderer` relative to orchestrator)
- Readiness: REAL
- Known issues: 15-minute timeout, no retry

---

## Shorts

### `ShortsStage` (FFmpeg invoker)
- File: `orchestrator/app/pipeline/stages/s11_short.py:88`
- Implementation: FFmpeg 9:16 crop from `output.mp4`
- Configuration: system FFmpeg on PATH
- Readiness: REAL
- Known issues: untested in this environment

---

## Quick Reference

| provider | readiness | tests | fallback |
|---|---|---|---|
| OpenAILLMProvider | REAL | indirect | MockLLMProvider |
| MockLLMProvider | TEST_ONLY | yes | n/a |
| ElevenLabsTTSProvider | REAL | none | GTTSTTSProvider |
| GTTSTTSProvider | REAL | none | n/a |
| DALLEImageProvider | REAL | none | PlaceholderImageProvider |
| PlaceholderImageProvider | PARTIAL | indirect | n/a |
| DuckDuckGoSearchProvider | UNVERIFIED | none | MockSearchProvider |
| MockSearchProvider | TEST_ONLY | yes | n/a |
| RequestsContentFetchProvider | UNVERIFIED | none | MockContentFetchProvider |
| MockContentFetchProvider | TEST_ONLY | yes | n/a |
| RenderStage | REAL | none | none |
| ShortsStage | REAL | none | none |

If a provider's readiness needs to be upgraded (UNVERIFIED → REAL or
PARTIAL → REAL), runtime evidence must be added to `docs/TEST_STATUS.md`
before the change.


---

## Voice / TTS Providers (PROMPT 8)

The Voice / TTS / Audio Intelligence Layer introduces a canonical
TTSProviderName enum and a VoiceTTSProvider interface
(orchestrator/app/voice/provider_base.py). Provider selection is
managed by pp.voice.provider_factory.select_provider().

| name | enum value | implementation | readiness | notes |
|---|---|---|---|---|
| Mock | MOCK | orchestrator/app/voice/mock_tts.py | **VERIFIED** | Deterministic stdlib wave WAV, content-addressed, used by all voice tests + smoke |
| ElevenLabs | ELEVENLABS | legacy pp/providers/elevenlabs_tts.py wrapped by LegacyProviderAdapter | **UNVERIFIED** | Requires ELEVENLABS_API_KEY; not exercised in CI |
| gTTS | GTTS | legacy pp/providers/gtts_tts.py wrapped by LegacyProviderAdapter | **UNVERIFIED** | Requires network; not exercised in CI |
| Local GPU TTS | LOCAL | stub | STUBBED | Placeholder for Vi-F5-TTS / F5-TTS / CosyVoice |
| F5-TTS | F5_TTS | stub | STUBBED | Future |
| Vi-F5-TTS | VI_F5_TTS | stub | STUBBED | Future (Vietnamese-first) |
| CosyVoice | COSYVOICE | stub | STUBBED | Future |

### VoiceTTSProvider interface (PROMPT 8)

`
synthesize(request: VoiceTTSRequest) -> VoiceTTSResponse
validate_voice(voice: VoiceDefinition) -> bool
get_voice_metadata(voice: VoiceDefinition) -> dict
estimate_duration(voice: VoiceDefinition, text: str) -> float  (optional)
supports_language(voice: VoiceDefinition, language: str) -> bool
`

### VoiceTTSRequest (canonical)

{ text, voice (VoiceDefinition), settings_override (VoiceSettings|null), output_path, language, locale, pronunciation_hints[], metadata, fingerprint }

### VoiceTTSResponse (canonical)

{ audio_path, duration_sec, sample_rate, channels, bits_per_sample, format, provider_artifact_meta, word_timestamps[] }

### Provider Capability Matrix

Capabilities are advertised by each provider implementation. PROMPT 8
intentionally does NOT hardcode per-provider assumptions in the
orchestrator � providers must declare their own capabilities.

Capabilities include:
- supported_languages
- speaker_identities
- voice_cloning_available
- pronunciation_support
- ssml_support
- streaming_support
- output_formats
- timestamp_support (PROVIDER_NATIVE / UNAVAILABLE)
- maximum_text_length

