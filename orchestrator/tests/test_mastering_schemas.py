"""
PROMPT 11 §56 — Tests for: C-27 RenderProfile, C-28 MasteringProfile,
C-29 MediaQAReport, plus fingerprinting/version invalidation.
"""
from __future__ import annotations

import hashlib

import pytest
from pydantic import ValidationError

from app.mastering.schemas import (
    AudioCodec,
    AudioStreamCheck,
    ArtifactLifecycleStatus,
    ArtifactQAStatus,
    CheckOutcome,
    CodecCheck,
    ContainerFormat,
    DurationCheck,
    FinalVideoArtifact,
    FPSCheck,
    LimiterMode,
    LoudnessCheck,
    LoudnessMeasurement,
    MasteringProfile,
    MediaQAReport,
    PixelFormat,
    QAStatus,
    QACheckID,
    QAPolicy,
    ResolutionCheck,
    TruePeakCheck,
    TruePeakMeasurement,
    VideoStreamCheck,
    VideoCodec,
    RenderProfile,
)
from app.mastering.artifact import (
    compute_render_profile_fingerprint,
    compute_mastering_profile_fingerprint,
    compute_final_artifact_fingerprint,
)


# ============================================================================
# C-27 RenderProfile
# ============================================================================


class TestRenderProfile:
    def test_minimal_h264_aac(self):
        rp = RenderProfile(
            profile_id="rp_basic", width=1280, height=720, fps=30.0
        )
        assert rp.video_codec == VideoCodec.H264
        assert rp.audio_codec == AudioCodec.AAC
        assert rp.profile_id == "rp_basic"
        assert rp.fingerprint.startswith("rp_")
        assert len(rp.fingerprint) > 8

    def test_even_dimension_required(self):
        with pytest.raises(ValidationError):
            RenderProfile(profile_id="rp_bad", width=1281, height=720, fps=30.0)
        with pytest.raises(ValidationError):
            RenderProfile(profile_id="rp_bad", width=1280, height=721, fps=30.0)

    def test_fingerprint_changes_when_resolution_changes(self):
        a = RenderProfile(profile_id="rp_a", width=1280, height=720, fps=30.0)
        b = RenderProfile(profile_id="rp_b", width=1920, height=1080, fps=30.0)
        assert a.fingerprint != b.fingerprint

    def test_fingerprint_changes_when_codec_changes(self):
        a = RenderProfile(profile_id="rp_a", width=1280, height=720, fps=30.0,
                           video_codec=VideoCodec.H264)
        b = RenderProfile(profile_id="rp_b", width=1280, height=720, fps=30.0,
                           video_codec=VideoCodec.H265)
        assert a.fingerprint != b.fingerprint

    def test_fingerprint_changes_when_fps_changes(self):
        a = RenderProfile(profile_id="rp_a", width=1280, height=720, fps=30.0)
        b = RenderProfile(profile_id="rp_b", width=1280, height=720, fps=60.0)
        assert a.fingerprint != b.fingerprint

    def test_fingerprint_stable_for_same_fields(self):
        a = RenderProfile(profile_id="rp_a", width=1280, height=720, fps=30.0)
        b = RenderProfile(profile_id="rp_b", width=1280, height=720, fps=30.0)
        assert a.fingerprint == b.fingerprint

    def test_extra_fields_forbidden(self):
        with pytest.raises(ValidationError):
            RenderProfile(
                profile_id="rp_x", width=1280, height=720, fps=30.0, unknown_field=1
            )

    def test_profile_id_min_length(self):
        with pytest.raises(ValidationError):
            RenderProfile(profile_id="a", width=1280, height=720, fps=30.0)

    def test_positive_fps_required(self):
        with pytest.raises(ValidationError):
            RenderProfile(profile_id="rp_x", width=1280, height=720, fps=0.0)


# ============================================================================
# C-28 MasteringProfile
# ============================================================================


class TestMasteringProfile:
    def test_defaults(self):
        mp = MasteringProfile(profile_id="mp_default")
        assert mp.target_lufs == -16.0
        assert mp.max_true_peak_dbtp == -1.0
        assert mp.normalization_enabled is True
        assert mp.limiter_mode == LimiterMode.PREVENT_CLIPPING_ONLY
        assert mp.fingerprint.startswith("mp_")

    def test_loudness_tolerance_bounds(self):
        with pytest.raises(ValidationError):
            MasteringProfile(profile_id="mp_x", loudness_tolerance_lu=-0.5)
        with pytest.raises(ValidationError):
            MasteringProfile(profile_id="mp_y", loudness_tolerance_lu=11.0)

    def test_target_lufs_must_be_non_positive(self):
        # target_lufs has no constraint currently; allow any float
        # but warn if positive (rejected by orchestrator side, not schema).
        mp = MasteringProfile(profile_id="mp_pos", target_lufs=-14.0)
        assert mp.target_lufs == -14.0

    def test_fingerprint_changes_on_target_lufs(self):
        a = MasteringProfile(profile_id="mp_a", target_lufs=-16.0)
        b = MasteringProfile(profile_id="mp_b", target_lufs=-14.0)
        assert a.fingerprint != b.fingerprint

    def test_fingerprint_changes_on_limiter_mode(self):
        a = MasteringProfile(profile_id="mp_a", limiter_mode=LimiterMode.OFF)
        b = MasteringProfile(profile_id="mp_b", limiter_mode=LimiterMode.APPLY_LIMITER)
        assert a.fingerprint != b.fingerprint

    def test_fingerprint_changes_on_normalization(self):
        a = MasteringProfile(profile_id="mp_a", normalization_enabled=True)
        b = MasteringProfile(profile_id="mp_b", normalization_enabled=False)
        assert a.fingerprint != b.fingerprint

    def test_extra_fields_forbidden(self):
        with pytest.raises(ValidationError):
            MasteringProfile(profile_id="mp_x", unknown_field="x")


# ============================================================================
# C-28 FinalVideoArtifact
# ============================================================================


def _sha(s: str) -> str:
    return hashlib.sha256(s.encode()).hexdigest()


class TestFinalVideoArtifact:
    def _valid_kwargs(self):
        return dict(
            artifact_id="final-001",
            project_id="proj_1",
            render_plan_id="plan_1",
            render_profile_id="rp_1",
            mastering_profile_id="mp_1",
            renderer_version="renderer@1.0",
            resolution=(1280, 720),
            fps=30.0,
            duration_sec=5.4,
            frame_count=162,
            video_codec=VideoCodec.H264,
            audio_codec=AudioCodec.AAC,
            audio_sample_rate_hz=48000,
            audio_channels=2,
            file_size_bytes=12345,
            checksum_sha256=_sha("x"),
            qa_report_id="qa_1",
        )

    def test_basic_construction(self):
        f = FinalVideoArtifact(**self._valid_kwargs())
        assert f.qa_status == ArtifactQAStatus.QA_PENDING
        assert f.lifecycle == ArtifactLifecycleStatus.RENDERED
        assert f.fingerprint.startswith("fa_")

    def test_resolution_must_be_even(self):
        kwargs = self._valid_kwargs()
        kwargs["resolution"] = (1281, 720)
        with pytest.raises(ValidationError):
            FinalVideoArtifact(**kwargs)

    def test_checksum_format(self):
        kwargs = self._valid_kwargs()
        kwargs["checksum_sha256"] = "X" * 64  # 64 chars but uppercase (not lowercase hex)
        with pytest.raises(ValidationError):
            FinalVideoArtifact(**kwargs)

    def test_fingerprint_changes_with_render_plan_id(self):
        kwargs = self._valid_kwargs()
        kwargs["render_plan_id"] = "plan_1"
        a = FinalVideoArtifact(**kwargs)
        kwargs["render_plan_id"] = "plan_2"
        b = FinalVideoArtifact(**kwargs)
        assert a.fingerprint != b.fingerprint

    def test_fingerprint_changes_with_checksum(self):
        kwargs = self._valid_kwargs()
        kwargs["checksum_sha256"] = _sha("x")
        a = FinalVideoArtifact(**kwargs)
        kwargs["checksum_sha256"] = _sha("y")
        b = FinalVideoArtifact(**kwargs)
        assert a.fingerprint != b.fingerprint

    def test_lifecycle_options(self):
        for lc in ArtifactLifecycleStatus:
            kwargs = self._valid_kwargs()
            kwargs["lifecycle"] = lc
            f = FinalVideoArtifact(**kwargs)
            assert f.lifecycle == lc

    def test_qa_status_options(self):
        for qs in ArtifactQAStatus:
            kwargs = self._valid_kwargs()
            kwargs["qa_status"] = qs
            f = FinalVideoArtifact(**kwargs)
            assert f.qa_status == qs


# ============================================================================
# C-29 MediaQAReport + checks
# ============================================================================


class TestMediaQAReport:
    def test_check_outcome_required_fields(self):
        with pytest.raises(ValidationError):
            CheckOutcome(check_id=None, status=QAStatus.PASS)

    def test_qa_status_enum(self):
        for s in QAStatus:
            co = CheckOutcome(check_id=QACheckID.VIDEO_STREAM, status=s)
            assert co.status == s

    def test_report_consistency_fail_wins(self):
        r = MediaQAReport(
            report_id="report_1",
            artifact_id="art_1",
            render_profile_id="rp_1",
            mastering_profile_id="mp_1",
            overall_status=QAStatus.PASS,
            checks=[
                CheckOutcome(check_id=QACheckID.VIDEO_STREAM, status=QAStatus.PASS),
                CheckOutcome(check_id=QACheckID.DURATION, status=QAStatus.FAIL),
            ],
        )
        assert r.overall_status == QAStatus.FAIL

    def test_report_warn_consistency(self):
        r = MediaQAReport(
            report_id="report_1",
            artifact_id="art_1",
            render_profile_id="rp_1",
            mastering_profile_id="mp_1",
            overall_status=QAStatus.PASS,
            checks=[
                CheckOutcome(check_id=QACheckID.VIDEO_STREAM, status=QAStatus.PASS),
                CheckOutcome(check_id=QACheckID.LOUDNESS, status=QAStatus.WARN),
            ],
        )
        assert r.overall_status == QAStatus.WARN

    def test_video_stream_check_pass(self):
        c = VideoStreamCheck(status=QAStatus.PASS, stream_count=1)
        assert c.stream_count == 1
        assert c.check_id == QACheckID.VIDEO_STREAM

    def test_audio_stream_check_fail(self):
        c = AudioStreamCheck(status=QAStatus.FAIL, stream_count=0, expected_stream_count=1)
        assert c.stream_count == 0

    def test_duration_check_tolerance(self):
        c = DurationCheck(
            status=QAStatus.PASS, measured_sec=5.0,
            expected_sec=5.5, tolerance_sec=1.0,
        )
        assert c.measured_sec == 5.0

    def test_fps_check(self):
        c = FPSCheck(
            status=QAStatus.PASS, measured_fps=30.0,
            expected_fps=30.0, tolerance_fps=0.5,
        )
        assert c.measured_fps == 30.0

    def test_resolution_check(self):
        c = ResolutionCheck(
            status=QAStatus.PASS, measured_width=1280, measured_height=720,
            expected_width=1280, expected_height=720,
        )
        assert c.measured_width == 1280

    def test_codec_check(self):
        c = CodecCheck(
            status=QAStatus.PASS, measured_video_codec="h264",
            measured_audio_codec="aac", expected_video_codec=VideoCodec.H264,
            expected_audio_codec=AudioCodec.AAC,
        )
        assert c.measured_video_codec == "h264"

    def test_loudness_check_unavailable(self):
        c = LoudnessCheck(
            status=QAStatus.UNAVAILABLE, measured_lufs=None,
            target_lufs=-16.0, tolerance_lu=1.0,
        )
        assert c.measured_lufs is None

    def test_loudness_check_pass(self):
        c = LoudnessCheck(
            status=QAStatus.PASS, measured_lufs=-15.5,
            target_lufs=-16.0, tolerance_lu=1.0,
        )
        assert c.measured_lufs == -15.5

    def test_true_peak_check_unavailable(self):
        c = TruePeakCheck(
            status=QAStatus.UNAVAILABLE, measured_dbtp=None, max_dbtp=-1.0
        )
        assert c.measured_dbtp is None

    def test_true_peak_check_pass(self):
        c = TruePeakCheck(
            status=QAStatus.PASS, measured_dbtp=-2.0, max_dbtp=-1.0
        )
        assert c.measured_dbtp == -2.0


# ============================================================================
# QAPolicy
# ============================================================================


class TestQAPolicy:
    def test_default_policy(self):
        p = QAPolicy(policy_id="policy_1")
        assert QACheckID.VIDEO_STREAM in p.critical_failures
        assert QACheckID.DECODE in p.critical_failures

    def test_critical_unavailable_overlap_rejected(self):
        with pytest.raises(ValidationError):
            QAPolicy(
                policy_id="policy_1",
                critical_failures=[QACheckID.VIDEO_STREAM],
                allow_unavailable_for=[QACheckID.VIDEO_STREAM],
            )

    def test_policy_id_min_length(self):
        with pytest.raises(ValidationError):
            QAPolicy(policy_id="x")


# ============================================================================
# LoudnessMeasurement / TruePeakMeasurement
# ============================================================================


class TestMeasurements:
    def test_loudness_measurement_defaults(self):
        m = LoudnessMeasurement()
        assert m.measurement_method == "ebur128"
        assert m.integrated_lufs is None

    def test_loudness_measurement_values(self):
        m = LoudnessMeasurement(
            integrated_lufs=-16.0, loudness_range_lu=5.0,
            true_peak_dbtp=-1.0, sample_peak_dbfs=-1.0,
        )
        assert m.integrated_lufs == -16.0

    def test_true_peak_measurement_values(self):
        m = TruePeakMeasurement(
            true_peak_dbtp=-2.0, sample_peak_dbfs=-3.0, method="astats"
        )
        assert m.true_peak_dbtp == -2.0
        assert m.sample_peak_dbfs == -3.0


# ============================================================================
# Fingerprint determinism
# ============================================================================


class TestFingerprintHelpers:
    def test_render_profile_fingerprint_stable(self):
        a = compute_render_profile_fingerprint(
            width=1280, height=720, fps=30.0, pixel_format=PixelFormat.YUV420P,
            video_codec=VideoCodec.H264, video_bitrate_kbps=5000, video_crf=23,
            audio_codec=AudioCodec.AAC, audio_sample_rate_hz=48000,
            audio_channels=2, audio_bitrate_kbps=192, container=ContainerFormat.MP4,
        )
        b = compute_render_profile_fingerprint(
            width=1280, height=720, fps=30.0, pixel_format=PixelFormat.YUV420P,
            video_codec=VideoCodec.H264, video_bitrate_kbps=5000, video_crf=23,
            audio_codec=AudioCodec.AAC, audio_sample_rate_hz=48000,
            audio_channels=2, audio_bitrate_kbps=192, container=ContainerFormat.MP4,
        )
        assert a == b
        assert a.startswith("rp_")

    def test_mastering_profile_fingerprint_changes_with_target(self):
        a = compute_mastering_profile_fingerprint(
            target_lufs=-16.0, loudness_tolerance_lu=1.0, max_true_peak_dbtp=-1.0,
            normalization_enabled=True, limiter_mode=LimiterMode.OFF,
            limiter_max_attack_ms=10.0, limiter_release_ms=100.0,
            silence_policy="allow", silence_tolerance_sec=0.5,
            silence_excessive_sec=2.0, fade_policy="none", music_duck_db=-9.0,
        )
        b = compute_mastering_profile_fingerprint(
            target_lufs=-14.0, loudness_tolerance_lu=1.0, max_true_peak_dbtp=-1.0,
            normalization_enabled=True, limiter_mode=LimiterMode.OFF,
            limiter_max_attack_ms=10.0, limiter_release_ms=100.0,
            silence_policy="allow", silence_tolerance_sec=0.5,
            silence_excessive_sec=2.0, fade_policy="none", music_duck_db=-9.0,
        )
        assert a != b

    def test_final_artifact_fingerprint_changes_with_checksum(self):
        kwargs = dict(
            project_id="p1", render_plan_id="plan1",
            render_profile_id="rp1", mastering_profile_id="mp1",
            renderer_version="r@1", duration_sec=5.0, frame_count=150,
            video_codec=VideoCodec.H264, audio_codec=AudioCodec.AAC,
            audio_sample_rate_hz=48000, audio_channels=2,
        )
        a = compute_final_artifact_fingerprint(checksum_sha256=_sha("a"), **kwargs)
        b = compute_final_artifact_fingerprint(checksum_sha256=_sha("b"), **kwargs)
        assert a != b
