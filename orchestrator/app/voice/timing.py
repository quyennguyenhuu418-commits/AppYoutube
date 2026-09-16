"""SpeechTiming parser + helpers (PROMPT 8 §24–§25).

Pure helpers for assembling a canonical `SpeechTiming` from a
provider's `word_timestamps` list. Never fabricates timestamps — if the
provider returned nothing, the resulting `SpeechTiming` is honest about
`UNAVAILABLE` status.
"""
from __future__ import annotations

from app.voice.audio_validator import parse_timestamps_from_response
from app.voice.schemas import (
    SpeechTiming,
    SegmentTiming,
    TimestampSource,
    TtsProviderName,
    WordTiming,
)


def build_speech_timing(
    *,
    timing_id: str,
    artifact_id: str,
    narration_id: str,
    provider: TtsProviderName,
    language: str,
    word_timestamps: list[dict],
    duration_sec: float,
) -> SpeechTiming:
    """Build a canonical SpeechTiming from a provider's word timestamps."""
    words, source = parse_timestamps_from_response(
        word_timestamps, duration_sec, declared_format="wav",
    )
    segments = _build_segments(words)
    return SpeechTiming(
        timing_id=timing_id,
        artifact_id=artifact_id,
        narration_id=narration_id,
        language=language,
        timestamp_source=source,
        words=words,
        segments=segments,
        duration_sec=duration_sec,
        provider=provider,
    )


def _build_segments(words: list[WordTiming]) -> list[SegmentTiming]:
    """Group words into segments (one per ~12-word block).

    This is a coarse heuristic; the captions engine in PROMPT 9 will
    override per-project.
    """
    if not words:
        return []
    segments: list[SegmentTiming] = []
    chunk = 12
    for i in range(0, len(words), chunk):
        chunk_words = words[i : i + chunk]
        if not chunk_words:
            continue
        text = " ".join(w.word for w in chunk_words)
        start_sec = chunk_words[0].start_sec
        end_sec = chunk_words[-1].end_sec
        segments.append(SegmentTiming(text=text, start_sec=start_sec, end_sec=end_sec))
    return segments


__all__ = ["build_speech_timing"]
