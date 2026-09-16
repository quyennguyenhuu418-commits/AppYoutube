"""Caption segmentation (PROMPT 9 §13, §14).

Convert word-level ``SpeechTiming`` → readable ``CaptionSegment`` list.

Design constraints:

- Word-agnostic to language *tokenization* but language-aware at
  punctuation: we use a punctuation list per language.
- Never split inside a word.
- Hard split only as last resort (PROMPT 9 §17).
- All limits are configurable via ``SegmentationPolicy``.
- ``UNAVAILABLE`` timestamps fall back to character-estimated uniform
  pacing (PROMPT 9 §35) so segments are still readable.

The segmenter is a pure function of
``(SpeechTiming, NarrationTimelineEntry, SegmentationPolicy, CaptionStyle)``.
"""
from __future__ import annotations

import re
from dataclasses import dataclass

from app.captions.schemas import (
    CaptionBreakReason,
    CaptionSegment,
    CaptionStyle,
    CaptionWord,
)
from app.voice.schemas import (
    NarrationTimelineEntry,
    SpeechTiming,
    TimestampSource,
    WordTiming,
)


# Punctuation per language (PROMPT 9 §14). Extending this list is safe;
# the segmenter iterates per-character.
_PUNCT_BY_LANG: dict[str, set[str]] = {
    "en": set(".!?;:"),
    "vi": set(".!?;:"),
    "ko": set(".!?;:…"),
    "zh": set("。！？；："),
}

# Words that should usually end a segment in many languages.
_NATURAL_BREAK_AFTER: set[str] = {
    "and", "but", "or", "so", "because", "however", "then",
    "the", "a", "an",
}


@dataclass(frozen=True)
class SegmentationPolicy:
    """Configurable limits (PROMPT 9 §15)."""
    max_chars_per_segment: int = 84
    max_words_per_segment: int = 14
    max_segment_duration_sec: float = 4.5
    min_segment_duration_sec: float = 0.8
    fallback_reading_chars_per_sec: float = 16.0
    prefer_phrase_breaks: bool = True

    def __post_init__(self) -> None:
        if self.max_chars_per_segment < 8:
            raise ValueError("max_chars_per_segment must be >= 8")
        if self.max_words_per_segment < 1:
            raise ValueError("max_words_per_segment must be >= 1")
        if self.min_segment_duration_sec <= 0:
            raise ValueError("min_segment_duration_sec must be > 0")
        if self.max_segment_duration_sec < self.min_segment_duration_sec:
            raise ValueError("max_segment_duration_sec < min_segment_duration_sec")


@dataclass(frozen=True)
class SegmentationResult:
    """Segmentation output (before scene-anchoring)."""
    segments: list[CaptionSegment]
    used_uniform_fallback: bool
    warnings: list[str]


def _punct_set(language: str) -> set[str]:
    return _PUNCT_BY_LANG.get(language, _PUNCT_BY_LANG["en"])


def _strip_punct(tok: str) -> str:
    """Remove leading/trailing punctuation characters from a token.

    Used to compute ``char_count`` correctly. Punctuation stays attached
    to the *word* so the renderer can render it inline.
    """
    return tok.strip("".join(_PUNCT_BY_LANG["en"] | _PUNCT_BY_LANG.get("ko", set())
                              | _PUNCT_BY_LANG.get("zh", set())))


def _ends_with_punct(tok: str, punct: set[str]) -> str | None:
    """Return the trailing punctuation character if present."""
    s = tok.rstrip()
    if not s:
        return None
    last = s[-1]
    return last if last in punct else None


def _is_natural_phrase_break(word_text: str, prefer: bool) -> bool:
    if not prefer:
        return False
    return word_text.lower().strip(",.;:!?") in _NATURAL_BREAK_AFTER


def _uniform_words(
    text: str,
    scene_start: float,
    scene_end: float,
    fallback_cps: float,
    narration_id: str,
    artifact_id: str,
    timing_id: str,
) -> list[WordTiming]:
    """Generate uniform-pacing word timings when SpeechTiming is UNAVAILABLE.

    This is documented as a degraded mode; consumers can detect it via
    ``TimestampSource.UNIFORM_ALIGNMENT`` or ``UNAVAILABLE`` (PROMPT 9 §35).
    """
    tokens = [t for t in re.split(r"\s+", text.strip()) if t]
    if not tokens:
        return []
    duration = max(scene_end - scene_start, 1e-3)
    # Distribute proportional to char count.
    weights = [max(1, len(t)) for t in tokens]
    total = sum(weights)
    out: list[WordTiming] = []
    cursor = scene_start
    for tok, w in zip(tokens, weights):
        dur = (w / total) * duration
        start = cursor
        end = min(scene_end, cursor + dur)
        out.append(
            WordTiming(
                word=tok,
                start_sec=start,
                end_sec=end,
                confidence=None,
            )
        )
        cursor = end
    return out


class CaptionSegmenter:
    """Deterministic caption segmenter (PROMPT 9 §13).

    Pure function: ``(speech_timing, timeline_entry, policy, style) ->
    SegmentationResult``.
    """

    def __init__(self, policy: SegmentationPolicy | None = None) -> None:
        self._policy = policy or SegmentationPolicy()

    @property
    def policy(self) -> SegmentationPolicy:
        return self._policy

    def segment(
        self,
        speech_timing: SpeechTiming,
        timeline_entry: NarrationTimelineEntry,
        narration_text: str,
        artifact_id: str,
        style: CaptionStyle,
        style_id: str = "default",
    ) -> SegmentationResult:
        """Produce CaptionSegment[] for one narration unit."""
        policy = self._policy
        punct = _punct_set(speech_timing.language)

        # Handle UNAVAILABLE / empty (PROMPT 9 §35)
        used_uniform = False
        if (
            speech_timing.timestamp_source == TimestampSource.UNAVAILABLE
            or not speech_timing.words
        ):
            warnings = ["UNAVAILABLE timestamps; using uniform fallback"]
            words = _uniform_words(
                text=narration_text,
                scene_start=timeline_entry.scene_start_sec,
                scene_end=timeline_entry.scene_end_sec,
                fallback_cps=policy.fallback_reading_chars_per_sec,
                narration_id=timeline_entry.narration_id,
                artifact_id=artifact_id,
                timing_id=speech_timing.timing_id,
            )
            used_uniform = True
            effective_source = TimestampSource.UNIFORM_ALIGNMENT
        else:
            warnings = []
            words = list(speech_timing.words)
            effective_source = speech_timing.timestamp_source

        if not words:
            return SegmentationResult(
                segments=[],
                used_uniform_fallback=used_uniform,
                warnings=warnings + ["no words to segment"],
            )

        # Greedy segment grouping.
        segments: list[CaptionSegment] = []
        cur_words: list[WordTiming] = []
        cur_break = CaptionBreakReason.PHRASE_BOUNDARY

        def flush(reason: CaptionBreakReason) -> None:
            """Flush cur_words into a CaptionSegment."""
            nonlocal cur_words, cur_break
            if not cur_words:
                return
            text = " ".join(w.word for w in cur_words)
            seg = self._build_segment(
                cur_words=cur_words,
                text=text,
                reason=reason,
                timeline_entry=timeline_entry,
                artifact_id=artifact_id,
                speech_timing_id=speech_timing.timing_id,
                effective_source=effective_source,
                style=style,
                style_id=style_id,
            )
            segments.append(seg)
            cur_words = []
            cur_break = CaptionBreakReason.PHRASE_BOUNDARY

        for w in words:
            # If segment is empty, push first word.
            if not cur_words:
                cur_words.append(w)
                cur_break = CaptionBreakReason.PHRASE_BOUNDARY
                continue

            tentative_text = " ".join(
                [cur_words[i].word for i in range(len(cur_words))] + [w.word]
            )
            tentative_chars = len(tentative_text)
            tentative_words = len(cur_words) + 1
            tentative_dur = w.end_sec - cur_words[0].start_sec

            # Punctuation hard break.
            if _ends_with_punct(w.word, punct):
                cur_words.append(w)
                flush(CaptionBreakReason.PUNCTUATION)
                continue

            # Char limit.
            if tentative_chars > policy.max_chars_per_segment:
                flush(CaptionBreakReason.MAX_CHARS)
                cur_words.append(w)
                continue

            # Word limit.
            if tentative_words > policy.max_words_per_segment:
                flush(CaptionBreakReason.MAX_WORDS)
                cur_words.append(w)
                continue

            # Duration limit.
            if tentative_dur > policy.max_segment_duration_sec:
                flush(CaptionBreakReason.MAX_DURATION)
                cur_words.append(w)
                continue

            # Phrase boundary (weak).
            if (policy.prefer_phrase_breaks
                    and _is_natural_phrase_break(w.word, policy.prefer_phrase_breaks)):
                cur_words.append(w)
                flush(CaptionBreakReason.PHRASE_BOUNDARY)
                continue

            cur_words.append(w)

        # Final flush.
        if cur_words:
            flush(CaptionBreakReason.NARration_END)

        # Honor min_segment_duration by merging if last is too short
        # (without breaking punctuation).
        if policy.min_segment_duration_sec > 0 and len(segments) >= 2:
            last = segments[-1]
            if (last.end_sec - last.start_sec) < policy.min_segment_duration_sec:
                # Merge into previous segment.
                prev = segments[-2]
                merged_words = list(prev.words) + list(last.words)
                merged_text = " ".join(w.word for w in merged_words)
                seg_id = f"{prev.segment_id}_m{len(segments)}"
                segments[-2] = self._build_segment(
                    cur_words=merged_words,
                    text=merged_text,
                    reason=CaptionBreakReason.MIN_DURATION,
                    timeline_entry=timeline_entry,
                    artifact_id=artifact_id,
                    speech_timing_id=speech_timing.timing_id,
                    effective_source=effective_source,
                    style=style,
                    style_id=style_id,
                    seg_id_override=seg_id,
                )
                segments.pop()

        return SegmentationResult(
            segments=segments,
            used_uniform_fallback=used_uniform,
            warnings=warnings,
        )

    def _build_segment(
        self,
        cur_words: list[WordTiming],
        text: str,
        reason: CaptionBreakReason,
        timeline_entry: NarrationTimelineEntry,
        artifact_id: str,
        speech_timing_id: str,
        effective_source: TimestampSource,
        style: CaptionStyle,
        style_id: str,
        seg_id_override: str | None = None,
    ) -> CaptionSegment:
        start_sec = cur_words[0].start_sec
        end_sec = cur_words[-1].end_sec
        seg_id = seg_id_override or self._segment_id(timeline_entry, start_sec)
        # Single-line initially; LineBreaker will split if needed.
        words = [
            CaptionWord(
                word=w.word,
                start_sec=w.start_sec,
                end_sec=w.end_sec,
                confidence=w.confidence,
                line_index=0,
                position_in_line=i,
                narration_id=timeline_entry.narration_id,
                artifact_id=artifact_id,
                speech_timing_id=speech_timing_id,
            )
            for i, w in enumerate(cur_words)
        ]
        # A simple single-line placeholder; LineBreaker overwrites.
        from app.captions.schemas import CaptionLine
        line = CaptionLine(
            line_index=0,
            text=text,
            word_count=len(cur_words),
            char_count=len(text),
            break_reason=reason,
            word_indices=list(range(len(cur_words))),
        )
        return CaptionSegment(
            segment_id=seg_id,
            caption_id="",  # filled by compiler
            scene_id=timeline_entry.scene_id,
            narration_id=timeline_entry.narration_id,
            start_sec=start_sec,
            end_sec=end_sec,
            text=text,
            words=words,
            lines=[line],
            artifact_id=artifact_id,
            speech_timing_id=speech_timing_id,
            timestamp_source=effective_source,
            style_id=style_id,
            break_reason=reason,
            warnings=[],
        )

    @staticmethod
    def _segment_id(timeline_entry: NarrationTimelineEntry, start_sec: float) -> str:
        return f"{timeline_entry.narration_id}_s{int(round(start_sec * 1000)):06d}"


__all__ = [
    "CaptionSegmenter",
    "SegmentationPolicy",
    "SegmentationResult",
]
