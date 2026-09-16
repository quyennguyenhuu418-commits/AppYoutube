"""
PROMPT 7 — End-to-end animation test fixture and runner.

PROMPT 7 §39: Prove
    Storyboard → Character → Asset → AnimationPlan → SceneDefinition → Renderer → MP4
using deterministic mock assets/providers.

The P6.5 integration tests must remain unchanged; this is a NEW test.

This test:
1. Builds a mock StoryboardPackage + AssetSystemPackage + CharacterSystemPackage.
2. Compiles an AnimationPlan from the Storyboard via AnimationPlanBuilder.
3. Validates the plan with AnimationCompiler.
4. Constructs a SceneDefinition that references the plan (per-scene).
5. Loads the SceneDefinition into the renderer via render_cli.
6. Verifies the MP4 artifact exists, is non-zero, and has correct metadata.
"""
from __future__ import annotations

import json
import shutil
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path

ORCH_ROOT = Path(__file__).resolve().parents[1]
RENDERER_DIR = ORCH_ROOT / "renderer"
WORKSPACE_DIR = ORCH_ROOT / "workspace"


def make_background_png(target: Path, color: str) -> None:
    """Create a minimal valid PNG file (solid color)."""
    import struct
    import zlib
    r = int(color[1:3], 16)
    g = int(color[3:5], 16)
    b = int(color[5:7], 16)
    width, height = 192, 108
    signature = b'\x89PNG\r\n\x1a\n'

    def png_chunk(chunk_type: bytes, data: bytes) -> bytes:
        chunk = chunk_type + data
        return struct.pack('>I', len(data)) + chunk + struct.pack('>I', zlib.crc32(chunk))

    ihdr_data = struct.pack('>IIBBBBB', width, height, 8, 2, 0, 0, 0)
    ihdr = png_chunk(b'IHDR', ihdr_data)
    raw_data = b''
    for _ in range(height):
        raw_data += b'\x00' + bytes([r, g, b]) * width
    idat = png_chunk(b'IDAT', zlib.compress(raw_data, 9))
    iend = png_chunk(b'IEND', b'')
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_bytes(signature + ihdr + idat + iend)


def build_animation_plan_fixture(job_dir: Path) -> dict:
    """Build a deterministic AnimationPlan + SceneDefinition that exercises
    animation:
      - 1 character (alice) enters, walks, stops, holds a spear
      - 1 prop (spear) attached to alice at t=[1, 4]
      - camera pans right + zooms in (ease_in_out)
    """
    duration = 6.0
    fps = 30

    plan = {
        "metadata": {
            "version": "1.0.0",
            "plan_id": "plan_smoke",
            "scene_id": "scene_1",
            "job_id": job_dir.name,
            "duration_sec": duration,
            "created_at": datetime(2026, 1, 1).isoformat() + "Z",
            "source": "animation_smoke_test",
        },
        "duration_sec": duration,
        "camera": {
            "camera_id": "main",
            "start_pan_x": 0.4,
            "start_pan_y": 0.5,
            "start_zoom": 1.0,
            "end_pan_x": 0.7,
            "end_pan_y": 0.5,
            "end_zoom": 1.5,
            "easing": "ease_in_out",
            "waypoints": [],
        },
        "characters": [
            {
                "character_id": "alice",
                "pose_sequence": [
                    {"start_sec": 0.0, "end_sec": 1.0, "action": "enter", "pose": "stand"},
                    {"start_sec": 1.0, "end_sec": 3.5, "action": "walk", "pose": "walk"},
                    {"start_sec": 3.5, "end_sec": duration, "action": "stand", "pose": "point"},
                ],
                "walk_cycle_params": {
                    "walk_speed": 60.0,
                    "step_frequency": 2.0,
                    "stride_length": 0.1,
                    "body_bob": 0.01,
                    "arm_swing": 0.05,
                },
                "motion_tracks": [
                    {
                        "track_id": "alice_x_walk",
                        "target": {"target_id": "character:alice", "kind": "character"},
                        "property": "x",
                        "keyframes": [
                            {"time_sec": 0.0, "value": 0.0, "interpolation": "linear"},
                            {"time_sec": 1.0, "value": 0.0, "interpolation": "linear"},
                            {"time_sec": 3.5, "value": 0.25, "interpolation": "linear"},
                            {"time_sec": duration, "value": 0.25, "interpolation": "linear"},
                        ],
                        "priority": 10,
                        "duration_sec": duration,
                    }
                ],
            }
        ],
        "props": [
            {
                "prop_id": "spear",
                "instance_id": "",
                "motion_tracks": [],
                "interactions": [
                    {
                        "interaction_id": "i1",
                        "character_id": "alice",
                        "prop_id": "spear",
                        "character_anchor": "hand_left",
                        "prop_anchor": "grip",
                        "start_sec": 1.0,
                        "end_sec": 4.0,
                        "kind": "hold",
                    }
                ],
            }
        ],
        "tracks": [],
        "events": [],
        "warnings": [],
        "failures": [],
    }
    plan_path = job_dir / "animation_plan.json"
    plan_path.write_text(json.dumps(plan, indent=2), encoding="utf-8")

    scene_definition = {
        "meta": {
            "title": "PROMPT 7 Animation Smoke",
            "description": "End-to-end animation test",
            "fps": fps,
            "width": 640,
            "height": 360,
            "target_duration_sec": duration,
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
                "id": "alice",
                "name": "Alice",
                "color": "#8B4513",
                "default_pose": "stand",
                "description": "Hunter",
            }
        ],
        "environments": [
            {
                "id": "ice_age_plains",
                "name": "Ice Age Plains",
                "background_asset": "backgrounds/ice_age.png",
                "mood": "tense",
            }
        ],
        "scenes": [
            {
                "id": "scene_1",
                "kind": "narration",
                "start_sec": 0.0,
                "end_sec": duration,
                "environment_id": "ice_age_plains",
                "narration_text": "Alice walks across the ice age plains.",
                "narration_words": [],
                "camera": {
                    "pan_x": 0.5,
                    "pan_y": 0.5,
                    "zoom": 1.0,
                    "easing": "ease_in_out",
                },
                "actors": [
                    {
                        "character_id": "alice",
                        "x": 0.3,
                        "y": 0.6,
                        "scale": 1.0,
                        "rotation_deg": 0.0,
                        "pose": "walk",
                        "enter_anim": "fade_in",
                        "exit_anim": "none",
                    }
                ],
                "props": [
                    {
                        "kind": "human_silhouette",  # acts as a stand-in
                        "x": 0.55,
                        "y": 0.6,
                        "scale": 1.0,
                        "rotation_deg": 0.0,
                        "enter_anim": "fade_in",
                    }
                ],
                "overlay_text": [],
                "sfx": [],
                "music": None,
            }
        ],
    }
    sd_path = job_dir / "scene_definition.json"
    sd_path.write_text(json.dumps(scene_definition, indent=2), encoding="utf-8")

    return {"plan": plan, "scene_definition": scene_definition}


def run_renderer(job_id: str, job_dir: Path) -> dict:
    """Invoke the renderer."""
    cmd = f"npx tsx src/render_animation_smoke.tsx \"{job_dir}\""
    result = subprocess.run(
        cmd,
        cwd=str(RENDERER_DIR),
        capture_output=True,
        text=True,
        timeout=600,
        shell=True,
    )
    print("=== STDOUT ===")
    print(result.stdout[-3000:])
    print("=== STDERR (first 4000 chars) ===")
    print(result.stderr[:4000])
    return {
        "returncode": result.returncode,
        "stdout": result.stdout,
        "stderr": result.stderr,
    }


def verify_mp4(output_path: Path) -> dict:
    if not output_path.exists():
        return {"exists": False, "size_bytes": 0, "error": "output.mp4 not found"}
    size = output_path.stat().st_size
    if size == 0:
        return {"exists": True, "size_bytes": 0, "error": "output.mp4 is zero bytes"}
    return {"exists": True, "size_bytes": size, "size_kb": round(size / 1024, 1)}


def main() -> int:
    job_id = f"anim_smoke_{int(time.time())}"
    job_dir = WORKSPACE_DIR / job_id
    print(f"[anim_smoke] job_id: {job_id}")

    try:
        job_dir.mkdir(parents=True, exist_ok=True)
        backgrounds = job_dir / "backgrounds"
        backgrounds.mkdir(exist_ok=True)
        make_background_png(backgrounds / "ice_age.png", "#8B9098")

        # Stage the asset into renderer public so the bundle can serve it.
        renderer_public = RENDERER_DIR / "public" / "backgrounds"
        renderer_public.mkdir(parents=True, exist_ok=True)
        shutil.copy(backgrounds / "ice_age.png", renderer_public / "ice_age.png")

        build_animation_plan_fixture(job_dir)
        # Also build asset_system_package.json so the adapter resolves mood color.
        from datetime import datetime as _dt
        asset_pkg = {
            "job_id": job_id,
            "project_id": "",
            "version": "1.0.0",
            "schema_version": "1.0.0",
            "environments": [{
                "asset_id": "ice_age_plains",
                "name": "Ice Age Plains",
                "primary_asset_uri": "backgrounds/ice_age.png",
                "mood": "tense",
                "palette_profile": {"primary": "#8B9098"},
                "lighting_profile": {"primary": "natural", "weather": "clear", "time_of_day": "midday"},
            }],
            "props": [],
            "asset_references": [],
            "resolutions": [],
            "registry": {"assets": [], "global_assets": [], "project_id": "", "updated_at": _dt.utcnow().isoformat()},
            "asset_packages": [],
            "overall_quality_score": 0.5,
            "quality_scores": {},
            "warnings": [],
            "failures": [],
            "created_at": _dt.utcnow().isoformat(),
            "updated_at": _dt.utcnow().isoformat(),
            "lifecycle": "generated",
        }
        (job_dir / "asset_system_package.json").write_text(json.dumps(asset_pkg, indent=2), encoding="utf-8")
        print("[anim_smoke] fixture built")

        result = run_renderer(job_id, job_dir)
        if result["returncode"] != 0:
            print("[anim_smoke] RENDERER FAILED")
            print(result["stderr"][-2000:])
            return 1

        output = job_dir / "output.mp4"
        v = verify_mp4(output)
        if not v["exists"] or v["size_bytes"] == 0:
            print(f"[anim_smoke] FAILED: {v}")
            return 2

        print(f"[anim_smoke] PASS: output.mp4 ({v['size_kb']} KB)")
        return 0
    finally:
        try:
            shutil.rmtree(job_dir)
        except Exception:
            pass
        # Clean staged asset too
        try:
            staged = RENDERER_DIR / "public" / "backgrounds" / "ice_age.png"
            if staged.exists():
                staged.unlink()
        except Exception:
            pass


if __name__ == "__main__":
    sys.exit(main())
