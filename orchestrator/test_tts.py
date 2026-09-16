"""Test TTS providers: gTTS (free) and Mock."""
import sys
sys.path.insert(0, ".")
from pathlib import Path

print("=" * 60)
print("TEST TTS PROVIDERS")
print("=" * 60)

out_dir = Path("./workspace/_test_audio")
out_dir.mkdir(parents=True, exist_ok=True)

# Test 1: MockTTSProvider
print("\n[1] MOCK TTS (always works)")
from app.voice.mock_tts import MockTTSProvider
from app.voice.provider_base import VoiceTTSRequest
from app.voice.schemas import (
    VoiceDefinition,
    VoiceSettings,
    VoiceGender,
    TtsProviderName,
    VoiceStyle,
)

try:
    mock = MockTTSProvider()
    voice = VoiceDefinition(
        voice_id="test_voice",
        name="Test",
        language="en",
        provider=TtsProviderName.MOCK,
    )
    out = str(out_dir / "mock_test.wav")
    req = VoiceTTSRequest(
        text="Hello world, this is a test.",
        voice=voice,
        settings_override=None,
        output_path=out,
        language="en",
        locale="en-US",
        pronunciation_hints=[],
    )
    resp = mock.synthesize(req)
    print(f"[OK] Audio: {resp.audio_path}")
    print(f"     Duration: {resp.duration_sec:.2f}s, Format: {resp.format}")
    print(f"     Size: {Path(resp.audio_path).stat().st_size} bytes")
except Exception as e:
    print(f"[FAIL] Mock TTS: {e}")
    import traceback
    traceback.print_exc()

# Test 2: gTTS provider
print("\n[2] gTTS (FREE)")
try:
    from app.voice.provider_factory import select_provider
    from app.voice.schemas import TtsProviderName, TtsEnvironment

    provider = select_provider(TtsProviderName.GTTS, TtsEnvironment.DEVELOPMENT)
    print(f"     Provider: {provider.name}")

    voice = VoiceDefinition(
        voice_id="gtts_voice",
        name="gTTS Default",
        language="en",
        provider=TtsProviderName.GTTS,
    )
    out = str(out_dir / "gtts_test.mp3")
    req = VoiceTTSRequest(
        text="Hello world, this is a test of the Google text to speech system.",
        voice=voice,
        settings_override=None,
        output_path=out,
        language="en",
        locale="en-US",
        pronunciation_hints=[],
    )
    resp = provider.synthesize(req)
    print(f"[OK] Audio: {resp.audio_path}")
    print(f"     Duration: {resp.duration_sec:.2f}s")
    print(f"     Size: {Path(resp.audio_path).stat().st_size} bytes")
except Exception as e:
    print(f"[FAIL] gTTS: {e}")
    import traceback
    traceback.print_exc()
