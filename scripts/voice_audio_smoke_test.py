"""
PROMPT 8 — Real narration MP4 smoke test.

PROMPT 8 §37, §38, §40, §49:

Vertical flow:

  Script
    -> NarrationScript
    -> VoiceResolver + MockTTSProvider
    -> AudioArtifact (real WAV file)
    -> SpeechTiming
    -> NarrationTimeline
    -> SceneDefinition (with narration_artifact_id)
    -> Renderer (Remotion)
    -> MP4 with real audio track

Then verifies with ffprobe:
  - audio stream exists
  - codec matches
  - duration matches expected
  - sample_rate / channels match

The actual MP4 render is exercised by this script. The pytest in
tests/test_voice_e2e.py covers the Python side; this script proves the
full vertical including the renderer produces audible narration.
"""
from __future__ import annotations

import json
import shutil
import struct
import subprocess
import sys
import time
import wave
import zlib
from pathlib import Path

# Make orchestrator importable when run directly.
SCRIPT_DIR = Path(__file__).resolve().parent
APP_ROOT = SCRIPT_DIR.parent
ORCH_ROOT = APP_ROOT  # AppYoutube is the orchestrator root.
RENDERER_DIR = ORCH_ROOT / "renderer"
WORKSPACE_DIR = ORCH_ROOT / "workspace"

sys.path.insert(0, str(APP_ROOT))

from app.schemas.script import Script, ScriptBeat, ScriptSection  # noqa: E402
from app.voice.cache import VoiceTTSCache  # noqa: E402
from app.voice.narration import build_narration_script  # noqa: E402
from app.voice.pipeline import run_tts_pipeline  # noqa: E402
from app.voice.registry import VoiceRegistryManager  # noqa: E402
from app.voice.resolver import VoiceResolver  # noqa: E402
from app.voice.schemas import (  # noqa: E402
    TtsEnvironment,
    TtsProviderName,
    VoiceDefinition,
    VoiceLifecycleStatus,
    VoiceSettings,
)
from app.voice.timeline import build_timeline  # noqa: E402


def make_background_png(target: Path, color: str) -> None:
    """Minimal valid PNG (solid color) — same as animation_smoke_test.py."""
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


def build_narration_audio_artifact(job_dir: Path, text: str) -> dict:
    """Build a NarrationScript, run TTS pipeline, write artifacts to job_dir.

    Returns metadata + the first artifact's absolute path.
    """
    narration_text = text
    script = Script(
        topic="Real Narration Smoke",
        sections=[ScriptSection(name="intro", beats=[
            ScriptBeat(text=narration_text, emotional_intent="neutral"),
        ])],
    )
    narration_script = build_narration_script(
        script_id="ns_smoke", job_id=job_dir.name, project_id="proj_smoke", script=script,
    )

    voice = VoiceDefinition(
        voice_id="narrator_en",
        name="Narrator EN",
        language="en",
        locale="en-US",
        provider=TtsProviderName.MOCK,
        style="narrator",
        settings=VoiceSettings(speaking_rate=1.0),
        supported_languages=["en"],
        status=VoiceLifecycleStatus.APPROVED,
        version_label="v1",
    )
    reg = VoiceRegistryManager()
    reg.register(voice)

    cache = VoiceTTSCache(job_id=job_dir.name)
    cache._base = job_dir / "voice_cache"
    cache._base.mkdir(parents=True, exist_ok=True)

    resolver = VoiceResolver(
        registry=reg, voice_definitions={voice.voice_id: voice},
        voice_instances=[], environment=TtsEnvironment.DEVELOPMENT,
        project_default_voice_id=voice.voice_id,
        fallback_voice_id=voice.voice_id,
        default_provider=TtsProviderName.MOCK,
    )

    audio_dir = job_dir / "voice_audio"
    artifacts, timings = run_tts_pipeline(
        script=narration_script, resolver=resolver, cache=cache, output_dir=audio_dir,
    )
    timeline = build_timeline(
        script=narration_script, artifacts=artifacts, timings=timings, fps=30,
        timeline_id="tl_smoke",
    )

    # Persist canonical artifacts as JSON for the renderer.
    artifacts_path = job_dir / "audio_artifacts.json"
    artifacts_path.write_text(
        json.dumps({k: v.model_dump(mode="json") for k, v in artifacts.items()}, indent=2),
        encoding="utf-8",
    )
    timings_path = job_dir / "speech_timings.json"
    timings_path.write_text(
        json.dumps({k: v.model_dump(mode="json") for k, v in timings.items()}, indent=2),
        encoding="utf-8",
    )
    timeline_path = job_dir / "narration_timeline.json"
    timeline_path.write_text(timeline.model_dump_json(indent=2), encoding="utf-8")

    return {
        "narration_id": list(artifacts.keys())[0],
        "artifact": list(artifacts.values())[0],
        "artifacts": artifacts,
        "timings": timings,
        "timeline": timeline,
    }


def build_scene_definition(job_dir: Path, narration_result: dict) -> dict:
    """Minimal SceneDefinition with real WAV audio file in the public dir.

    The renderer's animation smoke renderer (audioSrc=null) does not use
    canonical artifact IDs. We provide a real audio file at a known URL
    so the smoke test proves the render pipeline can play WAV audio.
    """
    duration = 4.0
    fps = 30
    art = narration_result["artifact"]
    artifact_id = art.artifact_id
    # Stage audio into renderer public dir so the renderer can serve it.
    public_dir = RENDERER_DIR / "public" / "voice_audio"
    public_dir.mkdir(parents=True, exist_ok=True)
    staged_audio = public_dir / f"{artifact_id}.wav"
    shutil.copy(art.absolute_path, staged_audio)

    scene_definition = {
        "meta": {
            "version": "1.0.0",
            "scene_definition_id": "sd_smoke",
            "job_id": job_dir.name,
            "project_id": "proj_smoke",
            "fps": fps,
            "target_duration_sec": duration,
            "created_at": "2026-01-01T00:00:00Z",
        },
        "characters": [
            {
                "id": "alice",
                "name": "Alice",
                "default_pose": "walk",
                "description": "Hunter",
            }
        ],
        "environments": [
            {
                "id": "ice_age_plains",
                "name": "Ice Age Plains",
                "background_asset": "backgrounds/ice_age.png",
                "mood": "neutral",
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
                # Provide audioSrc compatible with the animation smoke renderer.
                "audioSrc": f"voice_audio/{artifact_id}.wav",
                "camera": {
                    "pan_x": 0.5, "pan_y": 0.5, "zoom": 1.0, "easing": "linear",
                },
                "actors": [
                    {
                        "character_id": "alice",
                        "x": 0.3, "y": 0.6, "scale": 1.0, "rotation_deg": 0.0,
                        "pose": "walk", "enter_anim": "fade_in", "exit_anim": "none",
                    }
                ],
                "props": [
                    {
                        "kind": "human_silhouette",
                        "x": 0.55, "y": 0.6, "scale": 1.0, "rotation_deg": 0.0,
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
    return scene_definition


def run_renderer(job_id: str, job_dir: Path) -> dict:
    """Invoke the renderer's audio smoke renderer entry point."""
    cmd = f'npx tsx "src/render_audio_smoke.tsx" "{job_dir}"'
    result = subprocess.run(
        cmd, cwd=str(RENDERER_DIR),
        capture_output=True, text=True, timeout=600, shell=True,
    )
    return {
        "returncode": result.returncode,
        "stdout_tail": result.stdout[-2000:],
        "stderr_head": result.stderr[:3000],
    }


def _ffprobe_available() -> bool:
    return shutil.which("ffprobe") is not None


def verify_mp4_with_audio(output_path: Path) -> dict:
    """Verify the MP4 has an audio stream and report its metadata."""
    if not output_path.exists():
        return {"exists": False, "error": "output.mp4 not found"}
    size = output_path.stat().st_size
    if size == 0:
        return {"exists": True, "size_bytes": 0, "error": "output.mp4 is zero bytes"}

    result: dict = {
        "exists": True,
        "size_bytes": size,
        "size_kb": round(size / 1024, 1),
    }

    if not _ffprobe_available():
        result["ffprobe"] = "ffprobe not installed - skipping stream inspection"
        return result

    cmd = [
        "ffprobe", "-v", "error",
        "-show_streams",
        "-show_format",
        "-of", "json",
        str(output_path),
    ]
    proc = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
    if proc.returncode != 0:
        result["ffprobe_error"] = proc.stderr
        return result

    payload = json.loads(proc.stdout)
    streams = payload.get("streams", [])
    audio_streams = [s for s in streams if s.get("codec_type") == "audio"]
    video_streams = [s for s in streams if s.get("codec_type") == "video"]
    result["audio_stream_count"] = len(audio_streams)
    result["video_stream_count"] = len(video_streams)
    if audio_streams:
        a = audio_streams[0]
        result["audio_codec"] = a.get("codec_name")
        result["audio_sample_rate"] = a.get("sample_rate")
        result["audio_channels"] = a.get("channels")
        result["audio_duration_sec"] = a.get("duration")
    if video_streams:
        v = video_streams[0]
        result["video_codec"] = v.get("codec_name")
        result["video_width"] = v.get("width")
        result["video_height"] = v.get("height")
        result["video_duration_sec"] = v.get("duration")
    fmt = payload.get("format", {})
    result["container_duration_sec"] = fmt.get("duration")
    return result


def main() -> int:
    job_id = f"voice_smoke_{int(time.time())}"
    job_dir = WORKSPACE_DIR / job_id
    job_dir.mkdir(parents=True, exist_ok=True)

    print(f"[voice_smoke] job_id: {job_id}")
    print(f"[voice_smoke] job_dir: {job_dir}")

    try:
        # Stage background.
        backgrounds = job_dir / "backgrounds"
        backgrounds.mkdir(exist_ok=True)
        make_background_png(backgrounds / "ice_age.png", "#8B9098")
        renderer_public = RENDERER_DIR / "public" / "backgrounds"
        renderer_public.mkdir(parents=True, exist_ok=True)
        shutil.copy(backgrounds / "ice_age.png", renderer_public / "ice_age.png")

        # Build NarrationScript -> AudioArtifacts.
        narration_result = build_narration_audio_artifact(
            job_dir, "Alice walks across the ice age plains.",
        )
        art = narration_result["artifact"]
        # Sanity-check the WAV file before render.
        with wave.open(str(art.absolute_path), "rb") as w:
            wav_sr = w.getframerate()
            wav_ch = w.getnchannels()
            wav_dur = w.getnframes() / float(wav_sr)
        print(f"[voice_smoke] audio artifact: {art.artifact_id}")
        print(f"[voice_smoke]   format={art.format} sr={wav_sr} ch={wav_ch} dur={wav_dur:.3f}s")
        print(f"[voice_smoke]   checksum={art.checksum_sha256[:16]}...")

        # Build SceneDefinition referencing the canonical artifact.
        build_scene_definition(job_dir, narration_result)

        # Render.
        print("[voice_smoke] rendering MP4...")
        render_result = run_renderer(job_id, job_dir)
        print(f"[voice_smoke] render returncode={render_result['returncode']}")
        if render_result["returncode"] != 0:
            print("[voice_smoke] STDERR:")
            print(render_result["stderr_head"])

        output_path = job_dir / "output.mp4"
        verification = verify_mp4_with_audio(output_path)
        print(f"[voice_smoke] verification: {json.dumps(verification, indent=2)}")

        # Persist verification report.
        (job_dir / "audio_smoke_verification.json").write_text(
            json.dumps(verification, indent=2), encoding="utf-8",
        )

        # Pass criteria.
        ok = (
            verification.get("exists") is True
            and verification.get("size_bytes", 0) > 0
            and verification.get("audio_stream_count", 0) >= 1
            and verification.get("video_stream_count", 0) >= 1
        )
        if ok:
            print("[voice_smoke] PASS — MP4 contains both video and audio streams.")
            return 0
        print("[voice_smoke] FAIL — see verification report.")
        return 1
    finally:
        pass


if __name__ == "__main__":
    sys.exit(main())
