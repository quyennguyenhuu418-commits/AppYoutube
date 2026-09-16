#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
PROMPT 6.5 - Actual Renderer Smoke Test

This script creates a minimal fixture SceneDefinition with canonical asset
references and invokes the actual Remotion renderer to produce a video.

Usage:
    python scripts/render_smoke_test.py [--keep-output]

Output:
    workspace/render_smoke_test_<timestamp>/output.mp4

This script:
1. Creates a fixture SceneDefinition file
2. Creates a minimal background PNG (placeholder)
3. Invokes: npx tsx renderer/src/index.ts <job_id>
4. Verifies the output MP4 exists and is non-zero size
5. Optionally verifies basic media metadata via ffprobe
"""
from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path

# ---------------------------------------------------------------------------
# Setup paths
# ---------------------------------------------------------------------------

ORCH_ROOT = Path(__file__).resolve().parents[1]
RENDERER_DIR = ORCH_ROOT / "renderer"
WORKSPACE_DIR = ORCH_ROOT / "workspace"


def make_background_png(target: Path, color: str) -> None:
    """Create a minimal valid PNG file (solid color).

    Uses raw bytes to avoid Pillow dependency. The PNG format spec allows
    minimal IDAT chunks for solid colors.
    """
    import struct
    import zlib

    # Parse hex color
    r = int(color[1:3], 16)
    g = int(color[3:5], 16)
    b = int(color[5:7], 16)

    width, height = 192, 108  # Small but valid
    # PNG signature
    signature = b'\x89PNG\r\n\x1a\n'

    def png_chunk(chunk_type: bytes, data: bytes) -> bytes:
        chunk = chunk_type + data
        return struct.pack('>I', len(data)) + chunk + struct.pack('>I', zlib.crc32(chunk))

    # IHDR
    ihdr_data = struct.pack('>IIBBBBB', width, height, 8, 2, 0, 0, 0)
    ihdr = png_chunk(b'IHDR', ihdr_data)

    # IDAT - solid color (filter byte 0 + RGB per pixel)
    raw_data = b''
    for _ in range(height):
        raw_data += b'\x00' + bytes([r, g, b]) * width
    idat = png_chunk(b'IDAT', zlib.compress(raw_data, 9))

    # IEND
    iend = png_chunk(b'IEND', b'')

    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_bytes(signature + ihdr + idat + iend)


def create_fixture_scene_definition(job_dir: Path) -> None:
    """Create a minimal valid SceneDefinition fixture."""
    # Minimal SceneDefinition with one environment + one scene
    sd = {
        "meta": {
            "title": "PROMPT 6.5 Render Smoke Test",
            "description": "Minimal fixture to verify renderer pipeline",
            "fps": 30,
            "width": 640,
            "height": 360,
            "target_duration_sec": 5.0,
        },
        "style": {
            "primary_color": "#FF6B35",
            "accent_color": "#FFD166",
            "background_color": "#1D1D2C",
            "text_color": "#FFFFFF",
            "font_family": "Inter",
        },
        "characters": [
            {
                "id": "narrator",
                "name": "Narrator",
                "color": "#8B4513",
                "default_pose": "stand",
                "description": "Test narrator character",
            }
        ],
        "environments": [
            {
                "id": "diagram_white",
                "name": "Test Environment",
                "background_asset": "backgrounds/test_env.png",
                "mood": "calm",
            }
        ],
        "scenes": [
            {
                "id": "scene_1",
                "kind": "title",
                "start_sec": 0.0,
                "end_sec": 5.0,
                "environment_id": "diagram_white",
                "narration_text": "",
                "narration_words": [],
                "camera": {
                    "pan_x": 0.5,
                    "pan_y": 0.5,
                    "zoom": 1.0,
                    "easing": "ease_in_out",
                },
                "actors": [],
                "props": [],
                "overlay_text": [
                    {
                        "text": "PROMPT 6.5",
                        "x": 0.5,
                        "y": 0.4,
                        "font_size": 56,
                        "enter_at_sec": 0.5,
                        "exit_at_sec": None,
                        "color": "#FFFFFF",
                    },
                    {
                        "text": "Render Smoke Test",
                        "x": 0.5,
                        "y": 0.6,
                        "font_size": 28,
                        "enter_at_sec": 1.0,
                        "exit_at_sec": None,
                        "color": "#FFD166",
                    },
                ],
                "sfx": [],
                "music": None,
            }
        ],
    }

    # Write scene_definition.json
    sd_path = job_dir / "scene_definition.json"
    sd_path.parent.mkdir(parents=True, exist_ok=True)
    sd_path.write_text(json.dumps(sd, indent=2), encoding="utf-8")


def create_asset_system_package(job_dir: Path) -> None:
    """Create minimal asset_system_package.json fixture."""
    asset_pkg = {
        "job_id": job_dir.name,
        "project_id": "",
        "version": "1.0.0",
        "schema_version": "1.0.0",
        "environments": [
            {
                "asset_id": "diagram_white",
                "name": "Test Environment",
                "semantic_role": "Test environment",
                "era": "abstract",
                "primary_asset_uri": "backgrounds/test_env.png",
                "palette_profile": {"primary": "#F5F5F0"},
                "lighting_profile": {"primary": "natural", "weather": "clear", "time_of_day": "midday"},
                "lifecycle": "generated",
                "version": "1.0.0",
            }
        ],
        "props": [],
        "asset_references": [],
        "resolutions": [],
        "registry": {"assets": [], "global_assets": [], "project_id": "", "updated_at": datetime.utcnow().isoformat()},
        "asset_packages": [],
        "overall_quality_score": 0.5,
        "quality_scores": {},
        "warnings": [],
        "failures": [],
        "created_at": datetime.utcnow().isoformat(),
        "updated_at": datetime.utcnow().isoformat(),
        "lifecycle": "generated",
    }

    pkg_path = job_dir / "asset_system_package.json"
    pkg_path.write_text(json.dumps(asset_pkg, indent=2), encoding="utf-8")


def run_renderer(job_id: str, job_dir: Path) -> dict:
    """Run the renderer as a subprocess. Returns result dict."""
    print("[smoke] invoking renderer for job_id=%s..." % job_id)
    env_start = time.time()

    # Use the smoke_render_cli entrypoint which uses bundle()
    cmd = "npx tsx src/render_cli.tsx \"%s\"" % str(job_dir)

    # Use shell=True on Windows for proper executable resolution
    result = subprocess.run(
        cmd,
        cwd=str(RENDERER_DIR),
        capture_output=True,
        text=True,
        timeout=300,
        shell=True,
    )

    duration = time.time() - env_start
    print(f"[smoke] renderer completed in {duration:.1f}s")
    print(f"[smoke] stdout (last 30 lines):")
    for line in result.stdout.splitlines()[-30:]:
        print(f"  | {line}")
    if result.returncode != 0:
        print(f"[smoke] stderr:")
        for line in result.stderr.splitlines()[-30:]:
            print(f"  | {line}")

    return {
        "returncode": result.returncode,
        "stdout": result.stdout,
        "stderr": result.stderr,
        "duration_sec": duration,
    }


def verify_output(output_path: Path) -> dict:
    """Verify output.mp4 exists and is non-zero."""
    print(f"[smoke] verifying output: {output_path}")
    if not output_path.exists():
        return {"exists": False, "size_bytes": 0, "error": "output.mp4 not found"}

    size = output_path.stat().st_size
    print(f"[smoke] output size: {size} bytes ({size / 1024:.1f} KB)")

    return {
        "exists": True,
        "size_bytes": size,
        "size_kb": round(size / 1024, 1),
    }


def probe_media(output_path: Path) -> dict:
    """Optional ffprobe verification."""
    print(f"[smoke] running ffprobe...")
    try:
        result = subprocess.run(
            [
                "ffprobe",
                "-v", "error",
                "-show_entries", "format=duration:stream=width,height,codec_name",
                "-of", "default=noprint_wrappers=1",
                str(output_path),
            ],
            capture_output=True,
            text=True,
            timeout=10,
        )
        if result.returncode == 0:
            return {"available": True, "metadata": result.stdout}
        else:
            return {"available": False, "error": result.stderr}
    except FileNotFoundError:
        return {"available": False, "error": "ffprobe not installed"}


def main() -> int:
    parser = argparse.ArgumentParser(description="Render smoke test for PROMPT 6.5")
    parser.add_argument("--keep-output", action="store_true",
                        help="Keep output after test (otherwise cleaned up)")
    parser.add_argument("--job-id", type=str, default=None,
                        help="Custom job ID (otherwise auto-generated)")
    args = parser.parse_args()

    job_id = args.job_id or f"render_smoke_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
    job_dir = WORKSPACE_DIR / job_id

    print("[smoke] === PROMPT 6.5 Render Smoke Test ===")
    print("[smoke] job_id: %s" % job_id)
    print("[smoke] job_dir: %s" % job_dir)

    # Setup fixture
    print("[smoke] setting up fixture...")
    job_dir.mkdir(parents=True, exist_ok=True)

    # Create backgrounds directory with test PNG
    backgrounds_dir = job_dir / "backgrounds"
    backgrounds_dir.mkdir(exist_ok=True)
    background_path = backgrounds_dir / "test_env.png"
    make_background_png(background_path, "#F5F5F0")
    print("[smoke] created test background: %s" % background_path)

    # Create SceneDefinition fixture
    create_fixture_scene_definition(job_dir)
    print("[smoke] created scene_definition.json")

    # Create asset_system_package fixture
    create_asset_system_package(job_dir)
    print("[smoke] created asset_system_package.json")

    # Run renderer
    try:
        result = run_renderer(job_id, job_dir)
        if result["returncode"] != 0:
            print("[smoke] FAILED: renderer returned non-zero (%d)" % result["returncode"])
            return 1
    except subprocess.TimeoutExpired:
        print("[smoke] FAILED: renderer timed out")
        return 2
    except Exception as exc:
        print("[smoke] FAILED: %s" % exc)
        return 3

    # Verify output
    output_path = job_dir / "output.mp4"
    verification = verify_output(output_path)

    if not verification["exists"]:
        print("[smoke] FAILED: output.mp4 not produced")
        return 4

    if verification["size_bytes"] == 0:
        print("[smoke] FAILED: output.mp4 is zero bytes")
        return 5

    # Probe media
    probe = probe_media(output_path)
    if probe.get("available"):
        print("[smoke] ffprobe metadata:")
        for line in probe["metadata"].splitlines():
            print("  | %s" % line)

    # Summary
    print("[smoke] === RESULTS ===")
    print("[smoke] output.mp4 produced: %s KB" % verification["size_kb"])
    print("[smoke] render duration: %.1fs" % result["duration_sec"])

    if not args.keep_output:
        # Cleanup
        try:
            shutil.rmtree(job_dir)
            print("[smoke] cleaned up workspace")
        except Exception:
            pass

    print("[smoke] PASS: Render smoke test completed successfully")
    return 0


if __name__ == "__main__":
    sys.exit(main())
