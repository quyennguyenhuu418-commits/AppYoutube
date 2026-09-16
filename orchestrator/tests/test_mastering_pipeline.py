"""
PROMPT 11 §56, §57 — Tests for the MasteringPipeline orchestrator and cross-runtime.

Verifies:
  * preflight catches missing files
  * mix_audio + atomic finalize work
  * fingerprint includes all relevant inputs
  * the cross-runtime RenderPlan dict → Typed pipeline interface
"""
from __future__ import annotations

import shutil
import struct
import wave
from pathlib import Path

import pytest

from app.mastering import (
    RenderProfile, MasteringProfile, QAPolicy, VideoCodec, AudioCodec,
    MasteringPipeline,
)
from app.mastering.schemas import (
    ArtifactQAStatus, QAStatus, QACheckID, FinalVideoArtifact,
    MediaQAReport,
)
from app.mastering.artifact import (
    RawRenderArtifact,
    save_raw_artifact, load_raw_artifact,
    save_final_artifact, load_final_artifact,
    save_qa_report, load_qa_report,
    save_render_profile, load_render_profile,
    save_mastering_profile, load_mastering_profile,
)


def _make_wav(path: Path, duration_sec: float, freq_hz: float = 440.0,
              amplitude: float = 0.5, sample_rate: int = 48000) -> None:
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


def _make_mp4(ffmpeg_bin: str, wav_in: Path, mp4_out: Path,
              duration_sec: float = 3.0, width: int = 320, height: int = 240) -> None:
    import subprocess
    argv = [
        ffmpeg_bin, "-y", "-hide_banner",
        "-f", "lavfi", "-i", f"color=c=red:size={width}x{height}:duration={duration_sec}:rate=30",
        "-i", str(wav_in),
        "-c:v", "libx264", "-pix_fmt", "yuv420p",
        "-c:a", "aac", "-b:a", "192k",
        "-shortest",
        str(mp4_out),
    ]
    proc = subprocess.run(argv, capture_output=True, text=True, shell=False, timeout=120)
    assert proc.returncode == 0, proc.stderr


@pytest.fixture(scope="module")
def ffmpeg_bin():
    bin_ = shutil.which("ffmpeg")
    if not bin_:
        pytest.skip("ffmpeg not installed")
    return bin_


@pytest.fixture(scope="module")
def media_assets(tmp_path_factory, ffmpeg_bin):
    """Build a small h264+aac MP4 + 2 WAV artifacts for the pipeline."""
    d = tmp_path_factory.mktemp("pipeline_assets")
    wav1 = d / "n1.wav"
    wav2 = d / "m1.wav"
    _make_wav(wav1, 2.0)
    _make_wav(wav2, 2.0)
    # Build a tiny MP4 with audio
    raw = d / "raw.mp4"
    _make_mp4(ffmpeg_bin, wav1, raw, duration_sec=2.0)
    return {
        "raw": raw,
        "wav1": wav1,
        "wav2": wav2,
        "dir": d,
    }


class TestPreflight:
    def test_preflight_missing_render_plan(self, tmp_path):
        from app.mastering.pipeline import preflight_validate
        rp = RenderProfile(profile_id="rp_001", width=1280, height=720, fps=30.0)
        mp = MasteringProfile(profile_id="mp_001")
        errors = preflight_validate(
            render_plan_path=tmp_path / "missing.json",
            render_profile=rp,
            mastering_profile=mp,
            audio_artifact_paths={},
        )
        assert any("RenderPlan" in e for e in errors)

    def test_preflight_missing_audio(self, tmp_path):
        from app.mastering.pipeline import preflight_validate
        rp = RenderProfile(profile_id="rp_001", width=1280, height=720, fps=30.0)
        mp = MasteringProfile(profile_id="mp_001")
        errors = preflight_validate(
            render_plan_path=tmp_path / "x.json",
            render_profile=rp,
            mastering_profile=mp,
            audio_artifact_paths={"c1": str(tmp_path / "missing.wav")},
        )
        assert any("missing" in e for e in errors)

    def test_preflight_ok(self, tmp_path):
        from app.mastering.pipeline import preflight_validate
        plan_path = tmp_path / "plan.json"
        plan_path.write_text("{}", encoding="utf-8")
        wav = tmp_path / "a.wav"
        wav.write_bytes(b"")
        rp = RenderProfile(profile_id="rp_001", width=1280, height=720, fps=30.0)
        mp = MasteringProfile(profile_id="mp_001")
        errors = preflight_validate(
            render_plan_path=plan_path,
            render_profile=rp,
            mastering_profile=mp,
            audio_artifact_paths={"c1": str(wav)},
        )
        assert errors == []


class TestAtomicPersistence:
    def test_save_and_load_render_profile(self, tmp_path):
        rp = RenderProfile(profile_id="rp_x", width=1280, height=720, fps=30.0)
        out = tmp_path / "rp.json"
        save_render_profile(rp, out)
        loaded = load_render_profile(out)
        assert loaded.fingerprint == rp.fingerprint

    def test_save_and_load_mastering_profile(self, tmp_path):
        mp = MasteringProfile(profile_id="mp_x")
        out = tmp_path / "mp.json"
        save_mastering_profile(mp, out)
        loaded = load_mastering_profile(out)
        assert loaded.fingerprint == mp.fingerprint

    def test_save_and_load_qa_report(self, tmp_path):
        report = MediaQAReport(
            report_id="report_1", artifact_id="art_1",
            render_profile_id="rp_1", mastering_profile_id="mp_1",
            overall_status=QAStatus.PASS,
            checks=[],
        )
        out = tmp_path / "qa.json"
        save_qa_report(report, out)
        loaded = load_qa_report(out)
        assert loaded.report_id == "report_1"

    def test_save_and_load_raw_artifact(self, tmp_path):
        raw = RawRenderArtifact(
            artifact_id="raw_1", project_id="proj_1", render_plan_id="plan_1",
            render_profile_id="rp_1", renderer_version="r@1",
            raw_path="/tmp/x.mp4", file_size_bytes=100,
            duration_sec=5.0, fps=30.0, width=1280, height=720, has_audio=True,
            source_fingerprint="src_xxxxxxx",
        )
        out = tmp_path / "raw.json"
        save_raw_artifact(raw, out)
        loaded = load_raw_artifact(out)
        assert loaded.artifact_id == "raw_1"

    def test_save_and_load_final_artifact(self, tmp_path):
        import hashlib
        f = FinalVideoArtifact(
            artifact_id="final_1", project_id="proj_1", render_plan_id="plan_1",
            render_profile_id="rp_1", mastering_profile_id="mp_1",
            renderer_version="r@1", resolution=(1280, 720),
            fps=30.0, duration_sec=5.0, frame_count=150,
            video_codec=VideoCodec.H264, audio_codec=AudioCodec.AAC,
            audio_sample_rate_hz=48000, audio_channels=2,
            file_size_bytes=12345, checksum_sha256=hashlib.sha256(b"x").hexdigest(),
            qa_report_id="qa_1",
        )
        out = tmp_path / "final.json"
        save_final_artifact(f, out)
        loaded = load_final_artifact(out)
        assert loaded.artifact_id == "final_1"
        assert loaded.fingerprint == f.fingerprint


class TestCrossRuntimeDictPlan:
    """Test that the pipeline correctly handles dict-typed RenderPlan (cross-runtime)."""

    def test_mix_with_dict_plan(self, media_assets):
        pipeline = MasteringPipeline()
        rp_dict = {
            "plan_id": "plan_x",
            "audio_clips": [
                {
                    "clip_id": "n1", "artifact_id": "wav1", "track_kind": "narration",
                    "gain_db": 0.0, "duck_target_track_ids": [], "duck_gain_db": None,
                    "master_start_frame": 0, "duration_frames": 60,
                    "track_id": "t1", "scene_id": "s1",
                    "fade_in_frames": 0, "fade_out_frames": 0,
                },
                {
                    "clip_id": "m1", "artifact_id": "wav2", "track_kind": "music",
                    "gain_db": -3.0, "duck_target_track_ids": [], "duck_gain_db": None,
                    "master_start_frame": 0, "duration_frames": 60,
                    "track_id": "t2", "scene_id": "s1",
                    "fade_in_frames": 0, "fade_out_frames": 0,
                },
            ],
        }
        audio_paths = {
            "wav1": str(media_assets["wav1"]),
            "wav2": str(media_assets["wav2"]),
        }
        out_wav = media_assets["dir"] / "mixed_dict.wav"
        r = pipeline.mix_audio(
            render_plan=rp_dict,
            audio_artifact_paths=audio_paths,
            out_path=out_wav,
        )
        assert r["method"] == "amix"
        assert r["input_count"] == 2
        assert out_wav.exists()

    def test_mix_with_no_resolved_paths_fails(self):
        pipeline = MasteringPipeline()
        rp_dict = {
            "plan_id": "plan_x",
            "audio_clips": [
                {"clip_id": "n1", "artifact_id": "missing_audio_id",
                 "track_kind": "narration", "gain_db": 0.0,
                 "master_start_frame": 0, "duration_frames": 60,
                 "track_id": "t1", "scene_id": "s1",
                 "fade_in_frames": 0, "fade_out_frames": 0,
                 "duck_target_track_ids": [], "duck_gain_db": None},
            ],
        }
        from app.mastering.media_processor import MediaProcessorError
        with pytest.raises(MediaProcessorError):
            pipeline.mix_audio(
                render_plan=rp_dict,
                audio_artifact_paths={},
                out_path=Path("/tmp/missing.wav"),
            )


class TestRenderProfileValidateFingerprint:
    def test_fingerprint_determinism(self):
        a = RenderProfile(profile_id="rp_test", width=1280, height=720, fps=30.0)
        b = RenderProfile(profile_id="rp_test", width=1280, height=720, fps=30.0)
        assert a.fingerprint == b.fingerprint

    def test_fingerprint_includes_video_crf(self):
        a = RenderProfile(profile_id="rp_test", width=1280, height=720, fps=30.0, video_crf=23)
        b = RenderProfile(profile_id="rp_test", width=1280, height=720, fps=30.0, video_crf=18)
        assert a.fingerprint != b.fingerprint


class TestMasteringProfileConfigure:
    def test_can_change_loudness_tolerance(self):
        mp = MasteringProfile(profile_id="mp_x")
        mp.loudness_tolerance_lu = 4.0
        assert mp.loudness_tolerance_lu == 4.0


class TestQAPolicyValidation:
    def test_default_policy_overlap_allowed(self):
        # Default policy: no overlap between critical_failures and allow_unavailable_for
        p = QAPolicy(policy_id="policy_1")
        # Default allow_unavailable_for is [TRUE_PEAK, LOUDNESS]; neither is in default critical_failures
        for cid in p.critical_failures:
            assert cid not in p.allow_unavailable_for

    def test_warn_only_on_loudness(self):
        # Loudness in allow_warnings_on; everything else not
        p = QAPolicy(policy_id="policy_1")
        assert QACheckID.LOUDNESS in p.allow_warnings_on
        assert QACheckID.VIDEO_STREAM not in p.allow_warnings_on
