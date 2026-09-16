"""
P13 — Caption adapter for vertical (9:16) video.

When converting 16:9 horizontal content to 9:16 vertical shorts,
captions must be repositioned:
- Move from center to lower third (0.75-0.85 of height)
- Scale font size to be legible on mobile
- Adjust line width to fit narrow format

This adapter transforms CaptionTrack (from P9) into a vertical-optimized format.
"""

from __future__ import annotations

from typing import Any

from app.shorts.schemas import CaptionPositionOverride


# =============================================================================
# Vertical caption repositioning
# =============================================================================


class VerticalCaptionAdapter:
    """Adapt horizontal captions for vertical video.

    The adapter reads a CaptionTrack (horizontal layout) and produces
    a VerticalCaptionTrack with adjusted positions for 9:16 display.
    """

    def __init__(
        self,
        position_override: CaptionPositionOverride | None = None,
    ) -> None:
        self.position_override = position_override or CaptionPositionOverride(
            vertical_position=0.78,  # Lower third
            horizontal_align="center",
            font_scale=1.1,
            max_width_pct=0.85,
        )

    def adapt(
        self,
        caption_track: dict[str, Any],
        source_height: int,
        source_width: int,
        target_height: int,
        target_width: int,
        crop_center_x: float = 0.5,
        crop_center_y: float = 0.5,
    ) -> dict[str, Any]:
        """Adapt a CaptionTrack for vertical video.

        This does NOT modify the caption text or timing — only positioning.

        Parameters:
            caption_track: CaptionTrack as dict (from P9)
            source_height: Original video height
            source_width: Original video width
            target_height: Target (vertical) video height
            target_width: Target (vertical) video width
            crop_center_x: Horizontal center of the crop (0.0-1.0)
            crop_center_y: Vertical center of the crop (0.0-1.0)

        Returns:
            Adapted caption track with vertical-optimized positioning
        """
        # Vertical scale factor
        # When cropping 16:9 to 9:16:
        # source_crop_width = source_height * 9/16
        source_crop_width = source_height * 9.0 / 16.0
        # Scale factor between crop and target
        scale_x = target_width / source_crop_width
        scale_y = target_height / source_height

        # Adjust crop offset (where in the source we're cropping from)
        crop_x_offset = (source_width - source_crop_width) * crop_center_x

        # Adapt each segment
        segments = caption_track.get("segments", [])
        adapted_segments = [
            self._adapt_segment(
                seg, scale_x, scale_y, crop_x_offset,
                source_height, source_width,
                target_height, target_width,
            )
            for seg in segments
        ]

        return {
            **caption_track,
            "segments": adapted_segments,
            "_vertical_adapted": True,
            "_crop_center_x": crop_center_x,
            "_crop_center_y": crop_center_y,
            "_position_override": {
                "vertical_position": self.position_override.vertical_position,
                "horizontal_align": self.position_override.horizontal_align,
                "font_scale": self.position_override.font_scale,
                "max_width_pct": self.position_override.max_width_pct,
            },
        }

    def _adapt_segment(
        self,
        segment: dict[str, Any],
        scale_x: float,
        scale_y: float,
        crop_x_offset: float,
        source_height: int,
        source_width: int,
        target_height: int,
        target_width: int,
    ) -> dict[str, Any]:
        """Adapt a single caption segment for vertical layout."""
        # Vertical position: map from source position to target position,
        # with override applied
        source_y = segment.get("y", 0.5)  # Default center
        # Scale the y position
        scaled_y = source_y * scale_y

        # Apply vertical position override
        # The override is a fraction of target height
        override_y = self.position_override.vertical_position

        # For lower-third positioning, push caption down
        # Source captions are typically at y=0.5 (center) or y=0.85 (lower third)
        # For vertical, we want them at y=0.78-0.85 (lower third)
        if source_y > 0.7:
            # Caption was in lower third — keep it there but adjust
            target_y = min(0.88, override_y + 0.05)
        elif source_y < 0.3:
            # Caption was in upper third — move to lower third
            target_y = override_y
        else:
            # Center caption — move to lower third
            target_y = override_y

        # Horizontal position: account for crop offset
        source_x = segment.get("x", 0.5)
        # Shift x based on where we cropped
        target_x = (source_x * source_width - crop_x_offset) * scale_x / target_width
        target_x = max(0.05, min(0.95, target_x))

        # Font size scale
        # Captions should be slightly larger on mobile
        font_scale = self.position_override.font_scale
        source_font_size = segment.get("font_size", 24)
        target_font_size = int(source_font_size * font_scale)

        # Line width: captions can take more width on vertical (0.85 of target width)
        source_line_width = segment.get("line_width", 0.8)
        target_line_width = min(
            source_line_width * scale_x,
            self.position_override.max_width_pct,
        )

        return {
            **segment,
            "x": round(target_x, 4),
            "y": round(target_y, 4),
            "font_size": target_font_size,
            "line_width": round(target_line_width, 4),
            "_horizontal_align": self.position_override.horizontal_align,
            "_source_x": source_x,
            "_source_y": source_y,
        }


# =============================================================================
# SRT/JSON export for vertical captions
# =============================================================================


def export_vertical_srt(
    caption_track: dict[str, Any],
    target_height: int,
    target_width: int,
) -> str:
    """Export caption track as SRT format with vertical-optimized positioning.

    Note: SRT format doesn't support positioning natively.
    This function is for documentation/backup purposes.
    The actual rendering happens in Remotion with the adapted segment data.
    """
    segments = caption_track.get("segments", [])
    srt_lines: list[str] = []

    for i, seg in enumerate(segments, start=1):
        words = seg.get("words", [])
        if not words:
            continue

        start_time = _seconds_to_srt_time(words[0].get("start_sec", 0))
        end_time = _seconds_to_srt_time(words[-1].get("end_sec", 0))
        text = " ".join(w.get("text", "") for w in words)

        srt_lines.extend([
            str(i),
            f"{start_time} --> {end_time}",
            text,
            "",
        ])

    return "\n".join(srt_lines)


def _seconds_to_srt_time(seconds: float) -> str:
    """Convert seconds to SRT timestamp format (HH:MM:SS,mmm)."""
    import datetime
    td = datetime.timedelta(seconds=seconds)
    hours = td.seconds // 3600
    minutes = (td.seconds % 3600) // 60
    secs = td.seconds % 60
    millis = td.microseconds // 1000
    return f"{hours:02d}:{minutes:02d}:{secs:02d},{millis:03d}"


__all__ = [
    "VerticalCaptionAdapter",
    "export_vertical_srt",
]
