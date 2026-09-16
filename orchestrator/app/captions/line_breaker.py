"""Caption line breaking (PROMPT 9 §17).

Convert a ``CaptionSegment.words`` into visual ``CaptionLine``s.

Priority order:

1. Natural punctuation boundary
2. Phrase boundary (configurable word list)
3. Word boundary
4. Hard split only as final fallback

Hard split is never used inside a word. We respect
``CaptionStyle.max_chars_per_line`` and ``max_lines``.

The line breaker is pure and deterministic.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Sequence

from app.captions.schemas import (
    CaptionBreakReason,
    CaptionLine,
    CaptionSegment,
    CaptionStyle,
    CaptionWord,
)


_NATURAL_BREAK_AFTER: set[str] = {
    "and", "but", "or", "so", "because", "however", "then",
}


@dataclass(frozen=True)
class LineBreakPolicy:
    """Per-call overrides (defaults pulled from CaptionStyle)."""
    max_chars_per_line: int
    max_lines: int
    prefer_phrase_breaks: bool = True


@dataclass(frozen=True)
class LineBreakResult:
    new_lines: list[CaptionLine]
    hard_split_used: bool
    warnings: list[str]


class LineBreaker:
    """Deterministic caption line breaker (PROMPT 9 §17)."""

    @staticmethod
    def break_segment(
        segment: CaptionSegment,
        style: CaptionStyle | None = None,
        policy: LineBreakPolicy | None = None,
    ) -> LineBreakResult:
        # Resolve policy.
        if policy is None:
            if style is None:
                raise ValueError("Either style or policy must be provided")
            policy = LineBreakPolicy(
                max_chars_per_line=style.max_chars_per_line,
                max_lines=style.max_lines,
                prefer_phrase_breaks=True,
            )
        max_chars = policy.max_chars_per_line
        max_lines = policy.max_lines

        if max_chars < 8:
            return LineBreakResult(
                new_lines=list(segment.lines),
                hard_split_used=False,
                warnings=[f"max_chars_per_line ({max_chars}) is below safe minimum"],
            )

        words = segment.words
        if not words:
            return LineBreakResult(
                new_lines=list(segment.lines),
                hard_split_used=False,
                warnings=["no words"],
            )

        # Group into line runs.
        lines: list[list[CaptionWord]] = []
        cur: list[CaptionWord] = []
        cur_chars = 0

        def push_line(line_words: list[CaptionWord], reason: CaptionBreakReason) -> None:
            if not line_words:
                return
            text = " ".join(w.word for w in line_words)
            lines.append((line_words, text, reason))

        for w in words:
            tentative = cur + [w]
            tentative_text = " ".join(x.word for x in tentative)
            tentative_chars = len(tentative_text)

            if not cur:
                cur.append(w)
                cur_chars = len(w.word)
                continue

            # Punctuation hard break.
            last_char = w.word.rstrip()
            if last_char and last_char[-1] in ".!?;:":
                cur.append(w)
                push_line(cur, CaptionBreakReason.PUNCTUATION)
                cur = []
                cur_chars = 0
                continue

            # Char limit.
            if tentative_chars > max_chars:
                # Try phrase boundary first.
                if (
                    policy.prefer_phrase_breaks
                    and w.word.lower().strip(",.;:!?") in _NATURAL_BREAK_AFTER
                ):
                    cur.append(w)
                    push_line(cur, CaptionBreakReason.PHRASE_BOUNDARY)
                    cur = []
                    cur_chars = 0
                    continue
                # Else break at word boundary.
                push_line(cur, CaptionBreakReason.MAX_CHARS)
                cur = [w]
                cur_chars = len(w.word)
                continue

            cur.append(w)
            cur_chars = tentative_chars

        if cur:
            push_line(cur, CaptionBreakReason.NARration_END)

        # Enforce max_lines by merging overflow into last line (never hard split a word).
        hard_split_used = False
        warnings: list[str] = []
        if len(lines) > max_lines:
            head = lines[: max_lines - 1]
            tail_words: list[CaptionWord] = []
            tail_text_parts: list[str] = []
            tail_reason = CaptionBreakReason.HARD_SPLIT
            for ln_words, ln_text, ln_reason in lines[max_lines - 1:]:
                tail_words.extend(ln_words)
                tail_text_parts.append(ln_text)
                tail_reason = ln_reason
            tail_text = " ".join(tail_text_parts)
            if sum(len(x.word) for x in tail_words) > max_chars * 2:
                hard_split_used = True
                warnings.append(
                    f"overflow exceeds 2*max_chars ({2 * max_chars}); "
                    f"overflowing into last line without hard-split"
                )
            lines = head + [(tail_words, tail_text, tail_reason)]

        # Build CaptionLine objects and update word.line_index/position_in_line.
        new_lines: list[CaptionLine] = []
        for line_idx, (line_words, line_text, reason) in enumerate(lines):
            char_count = len(line_text)
            new_lines.append(
                CaptionLine(
                    line_index=line_idx,
                    text=line_text,
                    word_count=len(line_words),
                    char_count=char_count,
                    break_reason=reason,
                    word_indices=[],  # filled below
                )
            )
            for pos, w in enumerate(line_words):
                w.line_index = line_idx
                w.position_in_line = pos

        # Resolve word_indices now that line indices are stable.
        # Walk segments.words once in order, pushing indices.
        cursor = 0
        for ln_words, _t, _r in lines:
            new_lines[cursor].word_indices = list(
                range(cursor, cursor + len(ln_words))
            )
            cursor += 1
        # Also remap words into segments by line_index (in-place assignment).
        # We need to map back to the original word list. Since CaptionWord is
        # a pydantic model, we mutate the model itself via attribute setting.
        # But CaptionWord is also referenced inside the segment.words list.
        # The segment returned below uses the SAME word instances, so mutations
        # already apply.
        return LineBreakResult(
            new_lines=new_lines,
            hard_split_used=hard_split_used,
            warnings=warnings,
        )


__all__ = ["LineBreaker", "LineBreakPolicy", "LineBreakResult"]
