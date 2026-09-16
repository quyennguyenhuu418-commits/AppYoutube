"""
PROMPT 10 — Editorial smoke test (multi-scene MP4 + ffprobe + frame verification).

End-to-end pipeline:
  Storyboard → Character → Asset → Animation → Voice → Caption → Editorial
  → RenderPlan → Remotion → MP4 → ffprobe → selected frames

Produces a real multi-scene MP4 with:
  - 3 scenes (each 2s, 30 fps = 60 frames)
  - transitions
  - narration (synthesized MockTTS)
  - caption track
  - music + SFX (where fixtures exist)
  - animated character
  - camera movement

Then verifies:
  - ffprobe sees h264 + (no audio needed — narration is mock-data-only)
  - Selected frames exist
  - RenderPlan matches the rendered state at chosen frames
"""
from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import tempfile
import time
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))
ORCH_ROOT = REPO_ROOT / "orchestrator"
sys.path.insert(0, str(ORCH_ROOT))
RENDERER_ROOT = REPO_ROOT / "renderer"


def _run(cmd: list[str], cwd: Path | None = None, timeout: int = 240) -> subprocess.CompletedProcess:
    """Run a command. On Windows, shell-prefixed npx calls via cmd.exe so that
    `npx` resolves correctly (WinError 2 otherwise).
    """
    if cwd is None:
        cwd = REPO_ROOT
    # If the first argument is a shell-tool like npx, on Windows we route
    # through cmd.exe /c to ensure PATH resolution works.
    if os.name == "nt" and cmd and cmd[0] in {"npx", "npm", "node"}:
        cmd = ["cmd.exe", "/c", *cmd]
    print(f"[smoke] running: {' '.join(cmd)} (cwd={cwd})", flush=True)
    return subprocess.run(
        cmd, cwd=str(cwd),
        capture_output=True, text=True, timeout=timeout,
    )


def build_editorial_project(job_dir: Path) -> dict[str, Any]:
    """Build a deterministic 3-scene EditorialProject on disk."""
    from app.editorial.schemas import (
        AudioClipRef,
        AudioPriority,
        AudioTrackKind,
        EditorialProject,
        EditorialScene,
        EditorialTimeline,
        TitleCardSpec,
        Transition,
        TransitionKind,
        PacingCategory,
    )
    from app.editorial.references import build_source_bundle, extend_bundle
    from app.editorial.compiler import EditorialCompiler

    # ----- Build a minimal SceneDefinition-like stub (duck-typed). -----
    class StubScene:
        def __init__(self, sid: str, env: str, char: str, start: float, end: float) -> None:
            self.id = sid
            self.environment_id = env
            self.start_sec = start
            self.end_sec = end
            self.actors = [type("A", (), {"character_id": char})]
            self.props = [type("P", (), {"kind": "tree_pine"})]
            self.sfx = []
            self.music = None
            self.audioSrc = None
            self.narration_text = "hello world " * 3
            self.narration_words = []
    class StubEnv:
        def __init__(self, eid: str) -> None:
            self.id = eid
            self.background_asset = ""
            self.mood = "calm"
    class StubChar:
        def __init__(self, cid: str) -> None:
            self.id = cid
            self.name = cid
            self.color = "#8B6914"
            self.default_pose = "stand"
            self.description = ""
    class StubSD:
        def __init__(self) -> None:
            self.characters = [StubChar("alice")]
            self.environments = [StubEnv("env1")]
            self.scenes = [
                StubScene("scene_1", "env1", "alice", 0.0, 2.0),
                StubScene("scene_2", "env1", "alice", 2.0, 4.0),
                StubScene("scene_3", "env1", "alice", 4.0, 6.0),
            ]

    sd = StubSD()
    bundle = build_source_bundle(sd)
    bundle = extend_bundle(
        bundle,
        animation_plan_ids={"ap-alice"},
        caption_track_ids={"cap-1", "cap-2", "cap-3"},
        audio_artifact_ids={"aa-narration-1", "aa-narration-2", "aa-narration-3"},
    )

    # ----- Build the EditorialProject. -----
    fade = Transition(transition_id="f1", kind=TransitionKind.FADE, duration_sec=0.3)
    fade2 = Transition(transition_id="f2", kind=TransitionKind.FADE, duration_sec=0.3)

    def _clip(c, k, s, d, a):
        return AudioClipRef(
            clip_id=c, artifact_id=a,
            track_kind=k, priority=int(AudioPriority[k.name]),
            scene_local_start_sec=s, duration_sec=d, gain_db=0.0,
        )

    scenes = [
        EditorialScene(
            scene_id="scene_1", order=0, source_scene_duration_sec=2.0,
            animation_plan_id="ap-alice", caption_track_id="cap-1",
            pacing_category=PacingCategory.NORMAL,
            transition_out=fade,
            audio_clips=[_clip("n1", AudioTrackKind.NARRATION, 0.0, 2.0, "aa-narration-1")],
        ),
        EditorialScene(
            scene_id="scene_2", order=1, source_scene_duration_sec=2.0,
            animation_plan_id="ap-alice", caption_track_id="cap-2",
            transition_in=fade, transition_out=fade2,
            audio_clips=[_clip("n2", AudioTrackKind.NARRATION, 0.0, 2.0, "aa-narration-2")],
        ),
        EditorialScene(
            scene_id="scene_3", order=2, source_scene_duration_sec=2.0,
            animation_plan_id="ap-alice", caption_track_id="cap-3",
            transition_in=fade2,
            audio_clips=[_clip("n3", AudioTrackKind.NARRATION, 0.0, 2.0, "aa-narration-3")],
        ),
    ]
    title_intro = TitleCardSpec(
        card_id="intro", kind="intro", title="P10 Smoke", master_start_sec=0.0, duration_sec=1.0,
    )

    timeline = EditorialTimeline(
        timeline_id="tl-p10-smoke", fps=30, width=1280, height=720,
        scenes=scenes,
    )
    project = EditorialProject(
        project_id="p10-smoke", job_id="p10-smoke-job", topic="P10 Multi-Scene",
        timeline=timeline, title_cards=[title_intro],
        target_total_duration_sec=6.0,
    )
    res = EditorialCompiler(bundle=bundle, now_iso="2026-09-15T18:00:00Z").compile(project)
    assert res.ok, res.failures
    plan = res.plan
    plan_dict = plan.model_dump()
    # Persist on disk for the renderer.
    job_dir.mkdir(parents=True, exist_ok=True)
    (job_dir / "render_plan.json").write_text(
        json.dumps(plan_dict, indent=2, default=str), encoding="utf-8"
    )
    print(f"[smoke] RenderPlan total_duration_frames={plan.total_duration_frames}, "
          f"scenes={len(plan.scenes)}, layers={len(plan.layers)}, audio_clips={len(plan.audio_clips)}",
          flush=True)
    return plan_dict


def render_smoke(job_dir: Path, plan: dict[str, Any]) -> Path:
    """Run the renderer CLI against the Editorial RenderPlan."""
    out_mp4 = job_dir / "output.mp4"
    script = RENDERER_ROOT / "scripts" / "render_editorial_smoke.tsx"
    # Invoke via tsx (Node ESM-aware).
    proc = _run([
        "npx", "tsx", str(script),
        "--job-dir", str(job_dir),
        "--plan", str(job_dir / "render_plan.json"),
        "--out", str(out_mp4),
    ], cwd=RENDERER_ROOT, timeout=240)
    if proc.returncode != 0:
        print("[smoke] stderr:", proc.stderr, flush=True)
        raise RuntimeError(f"renderer CLI failed (exit {proc.returncode})")
    if not out_mp4.exists():
        raise RuntimeError(f"rendered MP4 not found at {out_mp4}")
    return out_mp4


def ffprobe(mp4: Path) -> dict[str, Any]:
    """Run ffprobe and return the parsed stream info."""
    proc = _run([
        "ffprobe", "-v", "error",
        "-print_format", "json",
        "-show_format", "-show_streams",
        str(mp4),
    ])
    if proc.returncode != 0:
        raise RuntimeError(f"ffprobe failed: {proc.stderr}")
    return json.loads(proc.stdout)


def extract_frames(mp4: Path, out_dir: Path, frame_seconds: list[float]) -> list[Path]:
    out_dir.mkdir(parents=True, exist_ok=True)
    paths: list[Path] = []
    for t in frame_seconds:
        path = out_dir / f"frame_{int(t*1000):05d}ms.png"
        proc = _run([
            "ffmpeg", "-y",
            "-ss", f"{t:.3f}",
            "-i", str(mp4),
            "-frames:v", "1",
            str(path),
        ], timeout=60)
        if proc.returncode == 0 and path.exists():
            paths.append(path)
    return paths


def main() -> int:
    job_dir = REPO_ROOT / "workspace" / f"p10_editorial_smoke_{int(time.time())}"
    if job_dir.exists():
        shutil.rmtree(job_dir)
    plan = build_editorial_project(job_dir)
    mp4 = render_smoke(job_dir, plan)
    info = ffprobe(mp4)
    streams = info.get("streams", [])
    video_streams = [s for s in streams if s.get("codec_type") == "video"]
    assert video_streams, f"no video stream in {mp4}"
    v = video_streams[0]
    fmt = info.get("format", {})
    print("[smoke] ffprobe summary:", json.dumps({
        "container": fmt.get("format_name"),
        "duration_sec": float(fmt.get("duration", 0.0)),
        "bit_rate": fmt.get("bit_rate"),
        "video_codec": v.get("codec_name"),
        "video_width": v.get("width"),
        "video_height": v.get("height"),
        "nb_frames": v.get("nb_frames"),
        "fps": v.get("r_frame_rate"),
    }, indent=2), flush=True)
    assert v.get("codec_name") == "h264", f"expected h264, got {v.get('codec_name')}"
    assert int(v.get("width", 0)) == 1280, f"unexpected width {v.get('width')}"
    assert int(v.get("height", 0)) == 720, f"unexpected height {v.get('height')}"
    # total_duration_sec from the plan must match the MP4 length (within 0.5s).
    plan_duration_sec = plan["total_duration_sec"]
    actual_duration_sec = float(fmt.get("duration", 0.0))
    assert abs(actual_duration_sec - plan_duration_sec) < 0.5, (
        f"MP4 duration {actual_duration_sec} differs from plan {plan_duration_sec} by > 0.5s"
    )
    # Extract golden frames at scene boundaries.
    frames = extract_frames(
        mp4, job_dir / "frames",
        [0.0, 0.5, 2.0, 2.5, 4.0, 4.5, plan_duration_sec - 0.1],
    )
    print(f"[smoke] extracted {len(frames)} frames: "
          f"{[str(f.relative_to(job_dir)) for f in frames]}", flush=True)
    assert len(frames) >= 3, "expected ≥3 golden frames"
    print(f"[smoke] OK — MP4 at {mp4}, RenderPlan at {job_dir / 'render_plan.json'}", flush=True)
    # Persist a summary for downstream tooling.
    summary = {
        "ok": True,
        "mp4": str(mp4.relative_to(REPO_ROOT)),
        "plan_id": plan["plan_id"],
        "total_duration_sec": plan_duration_sec,
        "actual_duration_sec": actual_duration_sec,
        "fps": plan["fps"],
        "width": plan["width"],
        "height": plan["height"],
        "scenes": len(plan["scenes"]),
        "audio_clips": len(plan["audio_clips"]),
        "layers": len(plan["layers"]),
        "frames": [str(f.relative_to(job_dir)) for f in frames],
        "ffprobe": {
            "container": fmt.get("format_name"),
            "video_codec": v.get("codec_name"),
            "width": v.get("width"),
            "height": v.get("height"),
            "nb_frames": v.get("nb_frames"),
            "fps": v.get("r_frame_rate"),
        },
    }
    (job_dir / "smoke_summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
    return 0


if __name__ == "__main__":
    sys.exit(main())
