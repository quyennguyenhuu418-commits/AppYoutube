"""
Placeholder image provider — used when no OPENAI_API_KEY is configured.

It writes a solid-color PNG (no Pillow dependency required). The renderer
is designed to composite these gracefully — they're just background fills.

We hash the prompt to pick a deterministic hue, so two requests with the
same prompt produce visually identical (but distinct across prompts) images.
"""
from __future__ import annotations

import hashlib
import struct
import zlib
from pathlib import Path

from app.providers.base import ImageProvider, ImageRequest, ImageResponse


# Color palettes the LLM is "encouraged" to use via style tokens. The
# renderer uses the same palette, so backgrounds match foreground.
_PALETTE = [
    (29, 29, 44),     # background_color default
    (255, 107, 53),   # primary_color
    (255, 209, 102),  # accent_color
    (240, 235, 220),  # warm parchment
    (200, 220, 240),  # cold sky
    (60, 50, 40),     # dark cave
]


class PlaceholderImageProvider(ImageProvider):
    name = "placeholder"

    def generate(self, request: ImageRequest) -> ImageResponse:
        out = Path(request.output_path)
        out.parent.mkdir(parents=True, exist_ok=True)
        h = hashlib.md5(request.prompt.encode("utf-8")).digest()
        # First two bytes pick a palette entry.
        idx = h[0] % len(_PALETTE)
        base_rgb = _PALETTE[idx]
        # Mix in a subtle gradient by hashing the prompt further.
        v_shift = (h[1] % 16) - 8
        rgb = tuple(max(0, min(255, c + v_shift)) for c in base_rgb)

        _write_png(out, request.width, request.height, rgb)
        return ImageResponse(image_path=str(out))


def _write_png(path: Path, width: int, height: int, rgb: tuple[int, int, int]) -> None:
    """Write a solid-color PNG without external dependencies.

    Implements just enough of the PNG spec to produce a valid file: a
    single IDAT chunk containing the raw (filtered) RGB rows.
    """
    def chunk(tag: bytes, data: bytes) -> bytes:
        return (
            struct.pack(">I", len(data))
            + tag
            + data
            + struct.pack(">I", zlib.crc32(tag + data) & 0xFFFFFFFF)
        )

    sig = b"\x89PNG\r\n\x1a\n"
    ihdr = struct.pack(">IIBBBBB", width, height, 8, 2, 0, 0, 0)  # 8-bit RGB
    # Raw pixel data: each row prefixed with a filter byte (0 = None).
    row = bytes([0]) + bytes(rgb) * width
    raw = row * height
    idat = zlib.compress(raw, level=6)

    data = sig + chunk(b"IHDR", ihdr) + chunk(b"IDAT", idat) + chunk(b"IEND", b"")
    path.write_bytes(data)
