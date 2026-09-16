"""
P13 — Shorts Production Package.

Intelligent 9:16 vertical clip extraction from horizontal video.
"""

from app.shorts.schemas import (
    CaptionPositionOverride,
    CropMode,
    SceneCropSpec,
    ShortsAspectRatio,
    ShortsCompilationResult,
    ShortsOutputFormat,
    ShortsPlan,
    ShortsQuality,
    ShortsRenderSettings,
    ShortsSourceContext,
    ShortsTargetPlatform,
    ShortsQAReport,
)
from app.shorts.compiler import ShortsCompiler, shorts_plan_fingerprint
from app.shorts.vertical_caption_adapter import VerticalCaptionAdapter, export_vertical_srt

__all__ = [
    # Schemas
    "ShortsAspectRatio",
    "ShortsTargetPlatform",
    "CropMode",
    "ShortsOutputFormat",
    "ShortsQuality",
    "ShortsRenderSettings",
    "CaptionPositionOverride",
    "SceneCropSpec",
    "ShortsSourceContext",
    "ShortsCompilationResult",
    "ShortsPlan",
    "ShortsQAReport",
    # Compiler
    "ShortsCompiler",
    "shorts_plan_fingerprint",
    # Caption adapter
    "VerticalCaptionAdapter",
    "export_vertical_srt",
]
