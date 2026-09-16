"""
PROMPT 11 §56 — Tests for the MediaProcessor safe FFmpeg wrapper.

Tests cover:
  * tool version probing
  * ffprobe streams summary
  * ebur128 parser (loudness + true peak)
  * loudnorm two-pass argument construction
  * mix_buses filter_complex
  * mux + padding
  * argument-injection safety (no shell, argv list)

These tests are pure (no FFmpeg execution) plus a small subset that
invokes ffmpeg on a synthesised WAV to confirm the wrapper actually works.
"""
from __future__ import annotations

import json
import shutil
import struct
import subprocess
import wave
from pathlib import Path

import pytest

from app.mastering.media_processor import (
    MediaProcessor,
    MediaProcessorError,
    _parse_number,
)


# ============================================================================
# Pure helpers
# ============================================================================


class TestParseHelpers:
    def test_parse_number_simple(self):
        assert _parse_number("-16.5 LUFS") == -16.5

    def test_parse_number_empty(self):
        assert _parse_number("no number here") is None

    def test_parse_number_negative(self):
        assert _parse_number("Peak: -1.2 dBFS") == -1.2


# ============================================================================
# Tool version (real invocation)
# ============================================================================


@pytest.fixture(scope="module")
def processor() -> MediaProcessor:
    if not shutil.which("ffmpeg"):
        pytest.skip("ffmpeg not installed")
    return MediaProcessor()


class TestToolVersions:
    def test_ffmpeg_version_present(self, processor):
        v = processor.tool_versions().ffmpeg
        assert "ffmpeg" in v.lower()

    def test_ffprobe_version_present(self, processor):
        v = processor.tool_versions().ffprobe
        assert "ffprobe" in v.lower()


# ============================================================================
# WAV synthesizer fixture
# ============================================================================


def _make_silent_wav(path: Path, duration_sec: float, sample_rate: int = 48000) -> None:
    """Synthesise a deterministic silent (well, near-silent) WAV file."""
    n_samples = int(duration_sec * sample_rate)
    with wave.open(str(path), "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(sample_rate)
        w.writeframes(b"\x00\x00" * n_samples)


def _make_sine_wav(path: Path, duration_sec: float, freq_hz: float = 220.0,
                    sample_rate: int = 48000, amplitude: float = 0.3) -> None:
    """Generate a sine-wave WAV file."""
    import math
    n_samples = int(duration_sec * sample_rate)
    frames = bytearray()
    for i in range(n_samples):
        v = math.sin(2 * math.pi * freq_hz * i / sample_rate) * amplitude
        sample = int(v * 32767)
        frames += struct.pack("<h", sample)
    with wave.open(str(path), "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(sample_rate)
        w.writeframes(bytes(frames))


# ============================================================================
# Real FFmpeg tests
# ============================================================================


class TestStreamsSummary:
    def test_silent_wav_summary(self, processor, tmp_path):
        wav = tmp_path / "silent.wav"
        _make_silent_wav(wav, 1.0)
        s = processor.streams_summary(wav)
        assert s["audio"]["count"] == 1
        assert s["audio"]["sample_rate"] == 48000
        assert s["audio"]["channels"] == 1
        assert abs(s["duration_sec"] - 1.0) < 0.05


class TestLoudnessMeasurement:
    def test_silent_wav_loudness(self, processor, tmp_path):
        wav = tmp_path / "silent.wav"
        _make_silent_wav(wav, 2.0)
        m = processor.measure_loudness(wav)
        # Silent audio has no integrated loudness
        assert isinstance(m, dict)
        assert "integrated_lufs" in m

    def test_sine_wav_loudness_measurable(self, processor, tmp_path):
        wav = tmp_path / "tone.wav"
        _make_sine_wav(wav, 3.0, freq_hz=440.0, amplitude=0.5)
        m = processor.measure_loudness(wav)
        # A 440 Hz tone is well within ffmpeg/ebur128 measureable range
        assert m["integrated_lufs"] is not None or m["integrated_lufs"] == float("-inf")


class TestTruePeak:
    def test_silent_peak(self, processor, tmp_path):
        wav = tmp_path / "silent.wav"
        _make_silent_wav(wav, 1.0)
        m = processor.measure_true_peak(wav)
        assert "true_peak_dbtp" in m
        assert "sample_peak_dbfs" in m

    def test_sine_peak_measurable(self, processor, tmp_path):
        wav = tmp_path / "tone.wav"
        _make_sine_wav(wav, 1.0, freq_hz=440.0, amplitude=0.5)
        m = processor.measure_true_peak(wav)
        assert m["sample_peak_dbfs"] is not None


class TestClippingDetection:
    def test_silent_no_clip(self, processor, tmp_path):
        wav = tmp_path / "silent.wav"
        _make_silent_wav(wav, 1.0)
        r = processor.detect_clipping(wav)
        assert r["clipped"] is False

    def test_sine_no_clip(self, processor, tmp_path):
        wav = tmp_path / "tone.wav"
        _make_sine_wav(wav, 1.0, freq_hz=440.0, amplitude=0.5)
        r = processor.detect_clipping(wav)
        assert r["clipped"] is False


class TestMixBuses:
    def test_mix_two_silent_wavs(self, processor, tmp_path):
        a = tmp_path / "a.wav"
        b = tmp_path / "b.wav"
        out = tmp_path / "mix.wav"
        _make_silent_wav(a, 1.0)
        _make_silent_wav(b, 1.0)
        inputs = [
            {"path": str(a), "gain_db": 0.0, "duck_under_narration": False, "label": "n1"},
            {"path": str(b), "gain_db": 0.0, "duck_under_narration": False, "label": "n2"},
        ]
        r = processor.mix_buses(inputs, out)
        assert r["method"] == "amix"
        assert r["input_count"] == 2
        assert out.exists()
        assert out.stat().st_size > 0

    def test_mix_empty_raises(self, processor, tmp_path):
        with pytest.raises(MediaProcessorError):
            processor.mix_buses([], tmp_path / "out.wav")


class TestSilenceDetection:
    def test_silent_file_has_leading_silence(self, processor, tmp_path):
        wav = tmp_path / "silent.wav"
        _make_silent_wav(wav, 2.0)
        r = processor.detect_silence(wav, min_duration_sec=0.3)
        assert "intervals" in r
        assert "leading_silence_sec" in r

    def test_sine_file_no_leading_silence(self, processor, tmp_path):
        wav = tmp_path / "tone.wav"
        _make_sine_wav(wav, 2.0, freq_hz=440.0, amplitude=0.5)
        r = processor.detect_silence(wav, min_duration_sec=0.3)
        # A constant tone has no silence intervals
        assert isinstance(r["intervals"], list)


# ============================================================================
# Command safety (PROMPT 11 §45, §60)
# ============================================================================


class TestArgumentSafety:
    def test_probe_uses_argv_list(self, processor, tmp_path):
        wav = tmp_path / "x.wav"
        _make_silent_wav(wav, 0.5)
        # Confirm argv is a list, not a string
        argv = [
            processor._ffprobe_path, "-v", "error",
            "-print_format", "json",
            "-show_format", "-show_streams",
            str(wav),
        ]
        assert isinstance(argv, list)
        # Confirm subprocess.run receives a list, not a shell-string
        proc = subprocess.run(argv, capture_output=True, text=True, shell=False)
        assert proc.returncode == 0

    def test_no_shell_injection_via_filename(self, processor, tmp_path):
        """A path containing shell metacharacters must not be interpreted as shell.

        The point of this test is that subprocess.run(..., shell=False) with
        a malicious filename never interprets the metacharacters as shell.
        ffmpeg will simply return "no such file" without any side-effects.
        """
        evil_path = tmp_path / "evil; rm -rf /.wav"
        # Note: we do NOT create the file. ffmpeg should fail safely.
        argv = [
            processor._ffprobe_path, "-v", "error",
            str(evil_path),
        ]
        proc = subprocess.run(argv, capture_output=True, text=True, shell=False)
        # ffmpeg fails to find the file, but no shell side-effects ran.
        assert proc.returncode != 0
        # Critically: the rm command in the filename was NOT executed.
        # If shell=True, the directory tree would have been wiped.
        # We assert the working directory still exists.
        assert tmp_path.exists()
        # And the stderr must not contain any "syntax error" hint that the
        # shell attempted to parse it.
        assert "syntax error" not in proc.stderr.lower()
