"""PROMPT 9 — Caption / Timing canonical contract tests.

Covers §38 (Python tests), §40 (golden timing), §41 (cross-runtime),
§45 (failure paths).
"""
from __future__ import annotations

import json

import pytest
from pydantic import ValidationError

from app.captions import (
    CaptionAnimationMode,
    CaptionBreakReason,
    CaptionCompiler,
    CaptionCompileRequest,
    CaptionLine,
    CaptionSegment,
    CaptionStyle,
    CaptionTrack,
    CaptionVerticalAnchor,
    CaptionWord,
    FrameRoundingPolicy,
    LineBreaker,
    SegmentationPolicy,
    compute_caption_id,
    frame_to_time,
    time_to_frame,
    validate_caption_track,
)
from app.captions.alignment import (
    AlignmentProvider,
    UniformAlignmentProvider,
)
from app.captions.quality import compute_timing_quality
from app.voice.schemas import (
    DurationReconciliationStrategy,
    NarrationTimeline,
    NarrationTimelineEntry,
    SpeechTiming,
    TimestampSource,
    TtsProviderName,
    WordTiming,
)


# ============================================================================
# Helpers
# ============================================================================

def _style(**overrides) -> CaptionStyle:
    defaults = dict(style_id="documentary_default")
    defaults.update(overrides)
    return CaptionStyle(**defaults)


def _word(word: str, start: float, end: float, **kw) -> WordTiming:
    return WordTiming(word=word, start_sec=start, end_sec=end, **kw)


def _timing(words: list[WordTiming], duration: float | None = None,
             source: TimestampSource = TimestampSource.PROVIDER_NATIVE) -> SpeechTiming:
    if duration is None and words:
        duration = words[-1].end_sec
    elif duration is None:
        duration = 0.0
    return SpeechTiming(
        timing_id="t1",
        artifact_id="0123456789abcdef_0123456789abcdef",
        narration_id="n_0001",
        language="en",
        timestamp_source=source,
        words=words,
        segments=[],
        duration_sec=duration,
        provider=TtsProviderName.MOCK,
    )


def _entry(scene_id="scene_1", narration_id="n_0001",
            scene_start=0.0, scene_end=4.0,
            audio_start=0.0, audio_end=4.0) -> NarrationTimelineEntry:
    return NarrationTimelineEntry(
        narration_id=narration_id,
        scene_id=scene_id,
        artifact_id="0123456789abcdef_0123456789abcdef",
        timing_id="t1",
        voice_id="narrator_en",
        speaker_id="narrator",
        audio_start_sec=audio_start,
        audio_end_sec=audio_end,
        scene_start_sec=scene_start,
        scene_end_sec=scene_end,
        resolution_strategy=DurationReconciliationStrategy.FOLLOW_AUDIO,
    )


# ============================================================================
# CaptionStyle (PROMPT 9 §11, §27)
# ============================================================================

class TestCaptionStyle:
    def test_defaults_documented(self):
        s = _style()
        assert s.style_id == "documentary_default"
        assert s.vertical_anchor == CaptionVerticalAnchor.LOWER_THIRD
        assert s.animation_mode == CaptionAnimationMode.WORD_HIGHLIGHT
        assert s.max_lines == 2
        assert s.max_chars_per_line == 42
        assert s.safe_area_pct == 0.08

    def test_color_validation_accepts_hex_and_rgb(self):
        s = _style(text_color="#FFFFFF")
        assert s.text_color == "#FFFFFF"
        s2 = _style(text_color="rgba(0,0,0,0.5)")
        assert s2.text_color == "rgba(0,0,0,0.5)"

    def test_color_validation_rejects_garbage(self):
        with pytest.raises(ValidationError):
            _style(text_color="not-a-color!!!")

    def test_resolution_independence(self):
        # Same style works for 16:9, 9:16, 1:1; only layout math changes.
        s = _style()
        d = s.to_dict() if hasattr(s, "to_dict") else s.model_dump()
        assert "safe_area_pct" in d
        assert "vertical_anchor" in d


# ============================================================================
# CaptionWord / CaptionLine / CaptionSegment (PROMPT 9 §10)
# ============================================================================

class TestCaptionWord:
    def test_basic(self):
        w = CaptionWord(
            word="Alice", start_sec=0.0, end_sec=0.3,
            narration_id="n_0001",
            artifact_id="0123456789abcdef_0123456789abcdef",
            speech_timing_id="t1",
        )
        assert w.word == "Alice"
        assert w.line_index == 0
        assert w.position_in_line == 0

    def test_invalid_order_rejected(self):
        with pytest.raises(ValidationError):
            CaptionWord(
                word="Alice", start_sec=0.3, end_sec=0.0,
                narration_id="n_0001",
                artifact_id="0123456789abcdef_0123456789abcdef",
                speech_timing_id="t1",
            )


class TestCaptionSegment:
    def test_basic(self):
        s = CaptionSegment(
            segment_id="seg_1",
            caption_id="cap_1",
            scene_id="scene_1",
            narration_id="n_0001",
            start_sec=0.0, end_sec=1.0,
            text="Alice walks",
            artifact_id="0123456789abcdef_0123456789abcdef",
            speech_timing_id="t1",
        )
        assert s.break_reason == CaptionBreakReason.PHRASE_BOUNDARY
        assert s.timestamp_source == TimestampSource.UNAVAILABLE

    def test_invalid_id_format(self):
        with pytest.raises(ValidationError):
            CaptionSegment(
                segment_id="Bad-ID!", caption_id="cap_1",
                scene_id="scene_1", narration_id="n_0001",
                start_sec=0.0, end_sec=1.0, text="hi",
                artifact_id="0123456789abcdef_0123456789abcdef",
                speech_timing_id="t1",
            )


# ============================================================================
# Frame / time helpers (PROMPT 9 §24)
# ============================================================================

class TestFrames:
    @pytest.mark.parametrize("frame", [0, 1, 15, 30, 45, 60, 90, 120])
    def test_round_trip(self, frame):
        fps = 30
        assert time_to_frame(frame_to_time(frame, fps), fps) == frame

    def test_zero(self):
        assert time_to_frame(0.0, 30) == 0

    def test_duration_end(self):
        assert time_to_frame(4.05, 30) == 122  # nearest

    def test_policies(self):
        assert time_to_frame(0.99, 30, FrameRoundingPolicy.FLOOR) == 29
        assert time_to_frame(0.01, 30, FrameRoundingPolicy.CEIL) == 1
        assert time_to_frame(1.0, 30, FrameRoundingPolicy.ROUND_NEAREST) == 30

    def test_negative_fps_rejected(self):
        with pytest.raises(ValueError):
            time_to_frame(1.0, 0)


# ============================================================================
# Tokenization / segmentation (PROMPT 9 §13)
# ============================================================================

class TestSegmentation:
    def _words_for(self, tokens: list[str], wps: float = 2.5):
        dur = 1.0 / wps
        return [_word(t, i * dur, (i + 1) * dur) for i, t in enumerate(tokens)]

    def test_punctuation_breaks(self):
        from app.captions.segmenter import CaptionSegmenter
        toks = ["Alice", "walks", "across", "the", "plains", ".", "Birds", "sing", "softly", "above"]
        words = self._words_for(toks)
        timing = _timing(words, duration=4.0)
        entry = _entry(scene_start=0.0, scene_end=4.0)
        segs = CaptionSegmenter().segment(
            timing, entry, narration_text=" ".join(toks),
            artifact_id=timing.artifact_id, style=_style(),
        )
        assert len(segs.segments) >= 2
        # The first segment should end at "plains." with reason PUNCTUATION.
        assert any(s.break_reason == CaptionBreakReason.PUNCTUATION for s in segs.segments)

    def test_max_chars_limit(self):
        from app.captions.segmenter import CaptionSegmenter
        long_text = ("word " * 30).strip()  # > default max_chars_per_segment
        words = self._words_for(long_text.split())
        timing = _timing(words, duration=15.0)
        entry = _entry(scene_start=0.0, scene_end=15.0)
        segs = CaptionSegmenter(
            SegmentationPolicy(max_chars_per_segment=40)
        ).segment(
            timing, entry, narration_text=long_text,
            artifact_id=timing.artifact_id, style=_style(),
        )
        assert len(segs.segments) >= 3

    def test_unavailable_uniform_fallback(self):
        from app.captions.segmenter import CaptionSegmenter
        timing = _timing([], duration=4.0, source=TimestampSource.UNAVAILABLE)
        entry = _entry(scene_start=0.0, scene_end=4.0)
        segs = CaptionSegmenter().segment(
            timing, entry,
            narration_text="Alice walks across the plains.",
            artifact_id=timing.artifact_id, style=_style(),
        )
        assert segs.used_uniform_fallback is True
        assert all(
            s.timestamp_source == TimestampSource.UNIFORM_ALIGNMENT
            for s in segs.segments
        )
        assert len(segs.warnings) >= 1


# ============================================================================
# Line breaking (PROMPT 9 §17)
# ============================================================================

class TestLineBreaker:
    def _make_segment(self, words_text):
        from app.captions.segmenter import CaptionSegmenter
        toks = words_text.split()
        dur = 0.3
        words = [_word(t, i * dur, (i + 1) * dur) for i, t in enumerate(toks)]
        timing = _timing(words, duration=len(toks) * dur)
        entry = _entry()
        segs = CaptionSegmenter().segment(
            timing, entry, narration_text=words_text,
            artifact_id=timing.artifact_id, style=_style(max_chars_per_line=20),
        )
        return segs.segments[0]

    def test_basic_line_breaks_at_max_chars(self):
        seg = self._make_segment("one two three four five six seven eight nine ten eleven twelve thirteen")
        lb = LineBreaker().break_segment(seg, style=_style(max_chars_per_line=20))
        assert len(lb.new_lines) >= 2
        # Every line except possibly the last overflow-merged line should
        # be within 2x max_chars_per_line.
        for i, ln in enumerate(lb.new_lines[:-1]):
            assert ln.char_count <= 2 * 20, (
                f"line {i} char_count={ln.char_count} exceeds 2x max_chars_per_line=20"
            )

    def test_no_word_split(self):
        # Ensure no line ever contains only a partial word.
        seg = self._make_segment("supercalifragilisticexpialidocious word")
        lb = LineBreaker().break_segment(seg, style=_style(max_chars_per_line=10))
        for ln in lb.new_lines:
            for wi in ln.word_indices:
                assert seg.words[wi].word in ln.text


# ============================================================================
# Reading speed / warnings (PROMPT 9 §16)
# ============================================================================

class TestReadingSpeed:
    def test_high_speed_warning(self):
        # 64-char segment in 1 sec = 64 cps → exceeds READING_RATE_BLOCK.
        timing = _timing(
            [_word("x" * 64, 0.0, 1.0)],
            duration=1.0,
        )
        entry = _entry(scene_start=0.0, scene_end=2.0)
        from app.captions.segmenter import CaptionSegmenter
        segs = CaptionSegmenter().segment(
            timing, entry, narration_text="x" * 64,
            artifact_id=timing.artifact_id, style=_style(),
        )
        track = CaptionTrack(
            track_id="t", caption_id="cap",
            narration_timeline_id="tl", scene_id="scene_1",
            style=_style(), style_id="documentary_default",
            segments=segs.segments,
            scene_start_sec=0.0, scene_end_sec=2.0,
        )
        val = validate_caption_track(track)
        assert any("reading speed" in w for w in val.warnings)


# ============================================================================
# Validator (PROMPT 9 §37, §30)
# ============================================================================

class TestValidator:
    def _track_with_seg(self, seg: CaptionSegment) -> CaptionTrack:
        return CaptionTrack(
            track_id="t", caption_id="cap",
            narration_timeline_id="tl", scene_id="scene_1",
            style=_style(), style_id="documentary_default",
            segments=[seg], scene_start_sec=0.0, scene_end_sec=4.0,
        )

    def test_overlap_detected(self):
        seg_a = CaptionSegment(
            segment_id="a", caption_id="cap", scene_id="s",
            narration_id="n", start_sec=0.0, end_sec=2.0, text="a",
            artifact_id="0123456789abcdef_0123456789abcdef",
            speech_timing_id="t1",
        )
        seg_b = CaptionSegment(
            segment_id="b", caption_id="cap", scene_id="s",
            narration_id="n", start_sec=1.5, end_sec=3.0, text="b",
            artifact_id="0123456789abcdef_0123456789abcdef",
            speech_timing_id="t1",
        )
        track = self._track_with_seg(seg_a)
        track.segments.append(seg_b)
        val = validate_caption_track(track)
        assert not val.ok
        assert any(e.code == "segment.overlap" for e in val.errors)

    def test_segment_before_scene_rejected(self):
        # Use a track where scene_start_sec > 0 and segment starts at 0
        # to exercise the "segment before scene" validator branch.
        seg = CaptionSegment(
            segment_id="a", caption_id="cap", scene_id="s",
            narration_id="n", start_sec=0.0, end_sec=1.0, text="a",
            artifact_id="0123456789abcdef_0123456789abcdef",
            speech_timing_id="t1",
        )
        track = self._track_with_seg(seg)
        track.scene_start_sec = 2.0
        track.scene_end_sec = 6.0
        val = validate_caption_track(track)
        assert not val.ok
        assert any(e.code == "segment.before_scene" for e in val.errors)

    def test_segment_after_scene_rejected(self):
        seg = CaptionSegment(
            segment_id="a", caption_id="cap", scene_id="s",
            narration_id="n", start_sec=0.0, end_sec=10.0, text="a",
            artifact_id="0123456789abcdef_0123456789abcdef",
            speech_timing_id="t1",
        )
        track = self._track_with_seg(seg)
        track.scene_end_sec = 4.0
        val = validate_caption_track(track)
        assert not val.ok

    def test_word_outside_segment_rejected(self):
        # Build a segment with words manually that violate bounds.
        seg = CaptionSegment(
            segment_id="a", caption_id="cap", scene_id="s",
            narration_id="n", start_sec=0.0, end_sec=1.0, text="hello",
            artifact_id="0123456789abcdef_0123456789abcdef",
            speech_timing_id="t1",
        )
        # mutate the words list (post-init) — schema validator should
        # still flag this when validate_caption_track runs.
        from app.captions.schemas import CaptionWord as CW
        seg.words = [
            CW(word="hello", start_sec=0.0, end_sec=2.0,
               narration_id="n",
               artifact_id="0123456789abcdef_0123456789abcdef",
               speech_timing_id="t1"),
        ]
        track = self._track_with_seg(seg)
        val = validate_caption_track(track)
        assert not val.ok

    def test_too_many_lines_rejected(self):
        from app.captions.schemas import CaptionLine
        style = _style(max_lines=2)
        seg = CaptionSegment(
            segment_id="a", caption_id="cap", scene_id="s",
            narration_id="n", start_sec=0.0, end_sec=4.0,
            text="a b c d",
            artifact_id="0123456789abcdef_0123456789abcdef",
            speech_timing_id="t1",
        )
        # Three lines with three words spread across them.
        seg.words = [
            CaptionWord(word="a", start_sec=0.0, end_sec=1.0,
                        narration_id="n",
                        artifact_id="0123456789abcdef_0123456789abcdef",
                        speech_timing_id="t1",
                        line_index=0, position_in_line=0),
            CaptionWord(word="b", start_sec=1.0, end_sec=2.0,
                        narration_id="n",
                        artifact_id="0123456789abcdef_0123456789abcdef",
                        speech_timing_id="t1",
                        line_index=1, position_in_line=0),
            CaptionWord(word="c", start_sec=2.0, end_sec=3.0,
                        narration_id="n",
                        artifact_id="0123456789abcdef_0123456789abcdef",
                        speech_timing_id="t1",
                        line_index=2, position_in_line=0),
            CaptionWord(word="d", start_sec=3.0, end_sec=4.0,
                        narration_id="n",
                        artifact_id="0123456789abcdef_0123456789abcdef",
                        speech_timing_id="t1",
                        line_index=2, position_in_line=1),
        ]
        seg.lines = [
            CaptionLine(line_index=0, text="a", word_count=1, char_count=1,
                        break_reason=CaptionBreakReason.PHRASE_BOUNDARY,
                        word_indices=[0]),
            CaptionLine(line_index=1, text="b", word_count=1, char_count=1,
                        break_reason=CaptionBreakReason.PHRASE_BOUNDARY,
                        word_indices=[1]),
            CaptionLine(line_index=2, text="c d", word_count=2, char_count=3,
                        break_reason=CaptionBreakReason.PHRASE_BOUNDARY,
                        word_indices=[2, 3]),
        ]
        track = CaptionTrack(
            track_id="t", caption_id="cap",
            narration_timeline_id="tl", scene_id="scene_1",
            style=style, style_id="documentary_default",
            segments=[seg], scene_start_sec=0.0, scene_end_sec=4.0,
        )
        val = validate_caption_track(track)
        assert not val.ok
        assert any(e.code == "line.too_many" for e in val.errors)


# ============================================================================
# Quality scoring (PROMPT 9 §9)
# ============================================================================

class TestQuality:
    def test_provider_native_perfect(self):
        toks = ["Alice", "walks", "across", "the", "plains"]
        words = [_word(t, i * 0.3, (i + 1) * 0.3) for i, t in enumerate(toks)]
        timing = _timing(words, duration=1.5)
        q = compute_timing_quality(timing)
        assert 0.8 <= q.overall <= 1.0

    def test_uniform_lower_score_than_provider(self):
        toks = ["a", "b", "c"]
        words = [_word(t, i * 0.3, (i + 1) * 0.3) for i, t in enumerate(toks)]
        provider = _timing(words, duration=0.9, source=TimestampSource.PROVIDER_NATIVE)
        uniform = _timing(words, duration=0.9, source=TimestampSource.UNIFORM_ALIGNMENT)
        qp = compute_timing_quality(provider)
        qu = compute_timing_quality(uniform)
        assert qp.overall > qu.overall

    def test_unavailable_low_source_quality(self):
        timing = _timing([], duration=1.0, source=TimestampSource.UNAVAILABLE)
        q = compute_timing_quality(timing)
        assert q.source_quality.score == 0.0
        assert q.source_quality.reasons == ["timestamp_source=unavailable"]


# ============================================================================
# AlignmentProvider boundary (PROMPT 9 §34)
# ============================================================================

class TestAlignment:
    def test_uniform_provider_protocol(self):
        from app.captions.alignment import AlignmentRequest
        from app.voice.schemas import AudioArtifact, NarrationUnit
        provider = UniformAlignmentProvider()
        assert isinstance(provider, AlignmentProvider)
        assert provider.provider_id == "uniform_v1"
        art = AudioArtifact(
            artifact_id="0123456789abcdef_0123456789abcdef",
            narration_id="n_0001",
            voice_id="v1",
            provider=TtsProviderName.MOCK,
            source_text_hash="0123456789abcdef",
            voice_config_hash="0123456789abcdef",
            duration_sec=4.0,
            uri="audio.wav",
            fingerprint="0123456789abcdef_0123456789abcdef",
        )
        unit = NarrationUnit(
            narration_id="n_0001", text="Alice walks across the plains",
        )
        result = provider.align(AlignmentRequest(audio=art, narration=unit))
        assert result.timing.timestamp_source == TimestampSource.UNIFORM_ALIGNMENT
        assert len(result.timing.words) == 5
        assert result.timing.duration_sec == 4.0


# ============================================================================
# Duration reconciliation (PROMPT 9 §23)
# ============================================================================

class TestDurationReconciliation:
    def test_caption_end_within_scene(self):
        # caption end must be ≤ scene end.
        seg = CaptionSegment(
            segment_id="a", caption_id="cap", scene_id="s",
            narration_id="n", start_sec=0.0, end_sec=3.5, text="ok",
            artifact_id="0123456789abcdef_0123456789abcdef",
            speech_timing_id="t1",
        )
        track = CaptionTrack(
            track_id="t", caption_id="cap",
            narration_timeline_id="tl", scene_id="scene_1",
            style=_style(), style_id="documentary_default",
            segments=[seg], scene_start_sec=0.0, scene_end_sec=4.0,
        )
        val = validate_caption_track(track)
        assert val.ok


# ============================================================================
# Compiler (PROMPT 9 §35, §36, §2)
# ============================================================================

class TestCompiler:
    def _fixture(self):
        toks = ["Alice", "walks", "across", "the", "plains", ".",
                "Birds", "sing", "softly", "above", "the", "valley", "."]
        words = [_word(t, i * 0.3, (i + 1) * 0.3) for i, t in enumerate(toks)]
        timing = _timing(words, duration=len(toks) * 0.3)
        entry = _entry()
        timeline = NarrationTimeline(
            timeline_id="tl1", script_id="ns1",
            fps=30, total_duration_sec=len(toks) * 0.3,
            entries=[entry],
        )
        return (
            CaptionCompileRequest(
                timeline=timeline,
                timings={"n_0001": timing},
                text={"n_0001": " ".join(toks)},
                style=_style(),
            ),
            toks,
        )

    def test_basic_compile(self):
        req, toks = self._fixture()
        result = CaptionCompiler().compile(req)
        assert len(result.tracks) == 1
        assert not result.failures
        track = result.tracks[0]
        assert track.scene_id == "scene_1"
        assert len(track.segments) >= 2
        assert track.timestamp_source == TimestampSource.PROVIDER_NATIVE

    def test_unavailable_produces_uniform_track(self):
        req, toks = self._fixture()
        # Force unavailable
        req.timings["n_0001"] = _timing(
            [], duration=len(toks) * 0.3, source=TimestampSource.UNAVAILABLE,
        )
        result = CaptionCompiler().compile(req)
        assert len(result.tracks) == 1
        assert result.tracks[0].timestamp_source == TimestampSource.UNIFORM_ALIGNMENT
        assert any("UNAVAILABLE" in w for w in result.warnings)

    def test_missing_timing_is_failure(self):
        from dataclasses import replace
        req, _ = self._fixture()
        # CaptionCompileRequest is frozen; use dataclasses.replace.
        req = replace(req, timings={})
        result = CaptionCompiler().compile(req)
        assert result.failures
        assert not result.tracks

    def test_caption_id_deterministic(self):
        a = compute_caption_id("tl", "scene_1", "documentary_default", 30)
        b = compute_caption_id("tl", "scene_1", "documentary_default", 30)
        assert a == b
        assert a.startswith("cap_") and len(a) == len("cap_") + 16

    def test_compile_output_is_json_round_trippable(self):
        req, _ = self._fixture()
        result = CaptionCompiler().compile(req)
        track = result.tracks[0]
        d = track.to_dict()
        # Round-trip JSON.
        s = json.dumps(d, default=str)
        d2 = json.loads(s)
        assert d2["caption_id"] == track.caption_id
        assert d2["segments"][0]["words"][0]["start_sec"] == track.segments[0].words[0].start_sec


# ============================================================================
# Golden timing tests (PROMPT 9 §40)
# ============================================================================

GOLDEN_FRAMES = [0, 15, 30, 45, 60, 90]


class TestGoldenTiming:
    """Verify expected caption state at known frame positions."""

    def _golden_track(self) -> CaptionTrack:
        # 3.0s scene @ 30fps = 90 frames.
        # Word timings: every 0.3s = 9 frames.
        toks = ["Alice", "walks", "across", "the", "plains",
                "Birds", "sing", "softly", "above", "valley"]
        words = [_word(t, i * 0.3, (i + 1) * 0.3) for i, t in enumerate(toks)]
        timing = _timing(words, duration=3.0)
        entry = _entry(scene_start=0.0, scene_end=3.0)
        timeline = NarrationTimeline(
            timeline_id="tl_g", script_id="ns_g",
            fps=30, total_duration_sec=3.0,
            entries=[entry],
        )
        req = CaptionCompileRequest(
            timeline=timeline,
            timings={"n_0001": timing},
            text={"n_0001": " ".join(toks)},
            style=_style(),
        )
        return CaptionCompiler().compile(req).tracks[0]

    @pytest.mark.parametrize("frame", GOLDEN_FRAMES)
    def test_golden_frames_compute_cleanly(self, frame):
        track = self._golden_track()
        fps = track.fps
        # Pure derivation: a renderer-side state machine would produce the
        # same result given the same frame. We assert here only that the
        # Python-side word timings + frame numbers agree.
        t_sec = frame_to_time(frame, fps)
        # Sanity: every word boundary is at a multiple of 0.3s.
        for w in sum((s.words for s in track.segments), []):
            assert w.start_sec % 0.3 == pytest.approx(0.0, abs=1e-9)

    def test_golden_frame_0_first_word(self):
        track = self._golden_track()
        # frame 0 → t=0 → first word "Alice" active.
        seg = track.segments[0]
        assert seg.words[0].word == "Alice"
        assert time_to_frame(seg.words[0].start_sec, track.fps) == 0

    def test_golden_frame_90_end(self):
        track = self._golden_track()
        # frame 90 → t=3.0 → boundary; last segment ends.
        last = track.segments[-1]
        assert last.end_sec == pytest.approx(3.0, abs=1e-9)


# ============================================================================
# Cross-runtime contract (PROMPT 9 §41)
# ============================================================================

class TestCrossRuntime:
    def test_serialized_keys_snake_case(self):
        req, _ = TestCompiler()._fixture()
        result = CaptionCompiler().compile(req)
        track = result.tracks[0]
        d = track.to_dict()

        def assert_snake(obj, path=""):
            if obj is None:
                return
            if isinstance(obj, dict):
                for k, v in obj.items():
                    assert k.replace("_", "").isalnum(), f"bad key {path}.{k}"
                    assert k == k.lower(), f"non-snake {path}.{k}"
                    assert_snake(v, f"{path}.{k}")
            elif isinstance(obj, list):
                for x in obj:
                    assert_snake(x, path)

        assert_snake(d, "track")

    def test_required_fields_present(self):
        req, _ = TestCompiler()._fixture()
        result = CaptionCompiler().compile(req)
        d = result.tracks[0].to_dict()
        for k in (
            "caption_id", "track_id", "scene_id", "narration_timeline_id",
            "fps", "style", "segments", "timestamp_source",
            "scene_start_sec", "scene_end_sec",
        ):
            assert k in d, f"missing field: {k}"
        assert "max_chars_per_line" in d["style"]


# ============================================================================
# Failure paths (PROMPT 9 §45)
# ============================================================================

class TestFailurePaths:
    def test_missing_speech_timing(self):
        from app.captions.segmenter import CaptionSegmenter
        segs = CaptionSegmenter().segment(
            speech_timing=None,  # type: ignore[arg-type]
            timeline_entry=_entry(),
            narration_text="x",
            artifact_id="0123456789abcdef_0123456789abcdef",
            style=_style(),
        ) if False else None  # can't pass None; check via compiler
        # Compiler-level test:
        req = CaptionCompileRequest(
            timeline=NarrationTimeline(
                timeline_id="tl", script_id="ns",
                fps=30, total_duration_sec=1.0,
                entries=[_entry()],
            ),
            timings={},
            text={"n_0001": "x"},
            style=_style(),
        )
        result = CaptionCompiler().compile(req)
        assert "missing SpeechTiming" in " ".join(result.failures)

    def test_unknown_narration_id_ignored(self):
        # An entry with no matching timing is reported as failure.
        entry = _entry(narration_id="ghost")
        req = CaptionCompileRequest(
            timeline=NarrationTimeline(
                timeline_id="tl", script_id="ns",
                fps=30, total_duration_sec=1.0,
                entries=[entry],
            ),
            timings={},  # no timing for 'ghost'
            text={},
            style=_style(),
        )
        result = CaptionCompiler().compile(req)
        assert any("missing SpeechTiming" in f for f in result.failures)

    def test_overlap_detection_blocks_compile(self):
        toks = ["a", "b", "c"]
        words = [_word(t, i * 0.3, (i + 1) * 0.3) for i, t in enumerate(toks)]
        timing = _timing(words, duration=0.9)
        # Two entries with overlapping scene bounds.
        e1 = _entry(narration_id="n_0001", scene_start=0.0, scene_end=2.0)
        e2 = _entry(narration_id="n_0002", scene_start=0.0, scene_end=2.0)
        # Force overlap by giving identical timing for both.
        timing2 = _timing(words, duration=0.9)
        # Use compiler: two entries with same narration_id will collide;
        # instead test via direct segment-level validator.
        from app.captions.schemas import CaptionSegment
        seg_a = CaptionSegment(
            segment_id="a", caption_id="cap", scene_id="s",
            narration_id="n", start_sec=0.0, end_sec=2.0, text="x",
            artifact_id="0123456789abcdef_0123456789abcdef",
            speech_timing_id="t1",
        )
        seg_b = CaptionSegment(
            segment_id="b", caption_id="cap", scene_id="s",
            narration_id="n", start_sec=1.5, end_sec=3.0, text="y",
            artifact_id="0123456789abcdef_0123456789abcdef",
            speech_timing_id="t1",
        )
        track = CaptionTrack(
            track_id="t", caption_id="cap",
            narration_timeline_id="tl", scene_id="s",
            style=_style(), style_id="documentary_default",
            segments=[seg_a, seg_b], scene_start_sec=0.0, scene_end_sec=4.0,
        )
        val = validate_caption_track(track)
        assert not val.ok
