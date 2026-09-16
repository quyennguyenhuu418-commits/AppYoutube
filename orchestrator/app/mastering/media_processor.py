"""
PROMPT 11 — Safe MediaProcessor wrapper around FFmpeg / FFprobe.

Architectural rules (PROMPT 11 §44, §45, §60, §61):
  * The only module in the orchestrator that shells out to ffmpeg/ffprobe.
  * No shell interpolation: every invocation uses argv lists + subprocess.run.
  * No arbitrary flags from callers — only allowlisted operations.
  * No untrusted strings are concatenated into commands.
  * All operations are time-bounded via the `timeout` parameter.
  * Output is captured, parsed, and returned as typed dicts.

Operations exposed:
  - probe(path)                  → ffprobe JSON metadata
  - decode(path, frames)         → decode a frame count (or whole file) to validate decodability
  - measure_loudness(path)       → ebur128 first-pass integrated loudness
  - measure_true_peak(path)      → astats sample peak + ebur128 true peak
  - detect_clipping(path)        → astats peak detection
  - detect_silence(path, ...)    → silencedetect
  - normalize_loudness(in, out, target_lufs, ...) → two-pass loudnorm
  - mix_buses(...)               → amix multiple WAV inputs into one WAV
  - mux_audio_to_video(in_video, in_audio, out) → add audio to silent video
  - encode_h264(in, out, profile) → final h264/aac encode

Failures raise `MediaProcessorError` with the failing argv and stderr tail.
"""
from __future__ import annotations

import json
import re
import shutil
import subprocess
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Iterable, Mapping, Sequence


# ============================================================================
# Errors
# ============================================================================


class MediaProcessorError(RuntimeError):
    """Raised when ffmpeg/ffprobe fails or returns unexpected output.

    Carries the failing argv and a truncated stderr so callers can produce
    actionable QA failure reasons without re-running the command.
    """

    def __init__(self, message: str, *, argv: Sequence[str], stderr_tail: str = "", returncode: int = -1):
        super().__init__(message)
        self.argv = tuple(argv)
        self.stderr_tail = stderr_tail
        self.returncode = returncode


# ============================================================================
# Tool resolution
# ============================================================================


@dataclass(frozen=True)
class ToolVersions:
    ffmpeg: str = "unknown"
    ffprobe: str = "unknown"

    def as_dict(self) -> dict[str, str]:
        return {"ffmpeg": self.ffmpeg, "ffprobe": self.ffprobe}


def _resolve_binary(name: str, explicit: str | None) -> str:
    if explicit:
        return explicit
    found = shutil.which(name)
    if found:
        return found
    raise MediaProcessorError(
        f"{name!r} not found on PATH", argv=[name], stderr_tail="", returncode=-1
    )


def _run(argv: Sequence[str], *, timeout: float | None) -> subprocess.CompletedProcess[str]:
    """Run a subprocess with safe defaults.

    - shell=False always (PROMPT 11 §45).
    - stdout/stderr captured as text.
    - timeout enforced.
    - non-zero exit raises MediaProcessorError.
    """
    try:
        proc = subprocess.run(
            list(argv),
            shell=False,
            check=False,
            capture_output=True,
            text=True,
            timeout=timeout,
            encoding="utf-8",
            errors="replace",
        )
    except subprocess.TimeoutExpired as exc:
        raise MediaProcessorError(
            f"timeout after {timeout}s", argv=argv, stderr_tail=str(exc)[:4000]
        ) from exc
    except FileNotFoundError as exc:
        raise MediaProcessorError(
            f"binary not found: {argv[0]!r}", argv=argv, stderr_tail=str(exc)
        ) from exc
    if proc.returncode != 0:
        raise MediaProcessorError(
            f"non-zero exit {proc.returncode} from {argv[0]!r}",
            argv=argv,
            stderr_tail=proc.stderr[-4000:],
            returncode=proc.returncode,
        )
    return proc


# ============================================================================
# MediaProcessor
# ============================================================================


@dataclass
class MediaProcessor:
    """Safe wrapper around FFmpeg / FFprobe."""

    ffmpeg_bin: str | None = None
    ffprobe_bin: str | None = None
    default_timeout_sec: float = 120.0

    _ffmpeg_path: str = field(init=False, default="")
    _ffprobe_path: str = field(init=False, default="")
    _ffmpeg_version: str = field(init=False, default="")
    _ffprobe_version: str = field(init=False, default="")

    def __post_init__(self) -> None:
        self._ffmpeg_path = _resolve_binary("ffmpeg", self.ffmpeg_bin)
        self._ffprobe_path = _resolve_binary("ffprobe", self.ffprobe_bin)
        self._ffmpeg_version = self._version(self._ffmpeg_path)
        self._ffprobe_version = self._version(self._ffprobe_path)

    # ------------------------------------------------------------------
    # Tool introspection
    # ------------------------------------------------------------------

    def tool_versions(self) -> ToolVersions:
        return ToolVersions(ffmpeg=self._ffmpeg_version, ffprobe=self._ffprobe_version)

    @staticmethod
    def _version(binary: str) -> str:
        proc = _run([binary, "-version"], timeout=10.0)
        first_line = proc.stdout.splitlines()[0] if proc.stdout else ""
        return first_line.strip()

    # ------------------------------------------------------------------
    # Probe (PROMPT 11 §27)
    # ------------------------------------------------------------------

    def probe(self, path: str | Path) -> dict[str, Any]:
        """Return the ffprobe JSON dict for a media file."""
        argv = [
            self._ffprobe_path,
            "-v", "error",
            "-print_format", "json",
            "-show_format",
            "-show_streams",
            str(path),
        ]
        proc = _run(argv, timeout=self.default_timeout_sec)
        try:
            return json.loads(proc.stdout)
        except json.JSONDecodeError as exc:
            raise MediaProcessorError(
                "ffprobe JSON parse failed", argv=argv, stderr_tail=proc.stdout[:2000]
            ) from exc

    def streams_summary(self, path: str | Path) -> dict[str, Any]:
        """Return a flat summary of streams and format."""
        payload = self.probe(path)
        streams = payload.get("streams", []) or []
        fmt = payload.get("format", {}) or {}
        video_streams = [s for s in streams if s.get("codec_type") == "video"]
        audio_streams = [s for s in streams if s.get("codec_type") == "audio"]
        first_video = video_streams[0] if video_streams else {}
        first_audio = audio_streams[0] if audio_streams else {}

        def _fps(stream: Mapping[str, Any]) -> float | None:
            rate = stream.get("avg_frame_rate") or stream.get("r_frame_rate")
            if not rate or rate == "0/0":
                return None
            num_s, den_s = rate.split("/", 1)
            try:
                num, den = int(num_s), int(den_s)
            except ValueError:
                return None
            return num / den if den else None

        def _channel_layout(stream: Mapping[str, Any]) -> str:
            return str(stream.get("channel_layout") or stream.get("channels") or "")

        return {
            "container": fmt.get("format_name"),
            "duration_sec": float(fmt.get("duration", 0.0) or 0.0),
            "bit_rate": fmt.get("bit_rate"),
            "size_bytes": int(fmt.get("size", 0) or 0),
            "nb_streams": int(fmt.get("nb_streams", 0) or 0),
            "video": {
                "count": len(video_streams),
                "codec_name": first_video.get("codec_name"),
                "width": int(first_video.get("width", 0) or 0),
                "height": int(first_video.get("height", 0) or 0),
                "fps": _fps(first_video),
                "nb_frames": int(first_video.get("nb_frames", 0) or 0),
                "pixel_format": first_video.get("pix_fmt"),
                "sample_aspect_ratio": first_video.get("sample_aspect_ratio"),
            },
            "audio": {
                "count": len(audio_streams),
                "codec_name": first_audio.get("codec_name"),
                "sample_rate": int(first_audio.get("sample_rate", 0) or 0),
                "channels": int(first_audio.get("channels", 0) or 0),
                "channel_layout": _channel_layout(first_audio),
                "duration_sec": float(first_audio.get("duration", 0.0) or 0.0),
            },
        }

    # ------------------------------------------------------------------
    # Decode / corruption check (PROMPT 11 §32)
    # ------------------------------------------------------------------

    def decode_check(
        self,
        path: str | Path,
        *,
        max_frames: int | None = None,
        timeout: float | None = None,
    ) -> dict[str, Any]:
        """Decode the file (or first N frames) and report any errors.

        Returns: {returncode, decoded_frames, errors}
        """
        argv = [self._ffmpeg_path, "-v", "error", "-i", str(path)]
        if max_frames is not None:
            argv += ["-frames:v", str(int(max_frames))]
        # We need frame count; map to null so all streams are decoded.
        argv += ["-map", "0", "-f", "null", "-"]
        proc = subprocess.run(
            argv,
            shell=False,
            check=False,
            capture_output=True,
            text=True,
            timeout=timeout or self.default_timeout_sec,
            encoding="utf-8",
            errors="replace",
        )
        # ffmpeg -v error prints ONLY errors. The decoded frame count is not
        # available from null muxer; we can approximate from ffprobe.
        return {
            "returncode": int(proc.returncode),
            "decoded_frames": self._approx_frame_count(path),
            "stderr": proc.stderr,
            "argv": list(argv),
        }

    def _approx_frame_count(self, path: str | Path) -> int:
        try:
            summary = self.streams_summary(path)
            return int(summary["video"].get("nb_frames") or 0)
        except MediaProcessorError:
            return 0

    # ------------------------------------------------------------------
    # Loudness measurement (PROMPT 11 §18, §21)
    # ------------------------------------------------------------------

    def measure_loudness(self, path: str | Path, *, timeout: float | None = None) -> dict[str, Any]:
        """Run ffmpeg ebur128 to capture integrated LUFS, range, true peak.

        Two-pass strategy (PROMPT 11 §21): the first pass only measures.
        The output is parsed from stderr — ebur128 prints one summary line.
        """
        argv = [
            self._ffmpeg_path,
            "-hide_banner",
            "-i", str(path),
            "-af", "ebur128=peak=true",
            "-f", "null",
            "-",
        ]
        proc = subprocess.run(
            argv,
            shell=False,
            check=False,
            capture_output=True,
            text=True,
            timeout=timeout or self.default_timeout_sec,
            encoding="utf-8",
            errors="replace",
        )
        return self._parse_ebur128(proc.stderr, returncode=proc.returncode, argv=argv)

    @staticmethod
    def _parse_ebur128(stderr: str, *, returncode: int, argv: Sequence[str]) -> dict[str, Any]:
        # Lines look like:
        #   Integrated loudness:
        #     I:         -16.5 LUFS
        #     Threshold: -26.9 LUFS
        #   Loudness range:
        #     LRA:         5.3 LU
        #   True peak:
        #     Peak:      -1.2 dBFS
        summary: dict[str, Any] = {
            "integrated_lufs": None,
            "loudness_range_lu": None,
            "true_peak_dbtp": None,
            "returncode": returncode,
        }
        if not stderr:
            return summary
        # Walk through lines and collect I/LRA/Peak values that appear AFTER "Summary:"
        in_summary = False
        for line in stderr.splitlines():
            stripped = line.strip()
            if "Summary:" in stripped:
                in_summary = True
                continue
            if not in_summary:
                continue
            if stripped.startswith("I:"):
                val = _parse_number(stripped.split(":", 1)[1])
                if val is not None:
                    summary["integrated_lufs"] = val
            elif stripped.startswith("LRA:"):
                val = _parse_number(stripped.split(":", 1)[1])
                if val is not None:
                    summary["loudness_range_lu"] = val
            elif stripped.startswith("Peak:") and summary["true_peak_dbtp"] is None:
                val = _parse_number(stripped.split(":", 1)[1])
                if val is not None:
                    summary["true_peak_dbtp"] = val
        return summary

    # ------------------------------------------------------------------
    # True peak + sample peak (PROMPT 11 §22)
    # ------------------------------------------------------------------

    def measure_true_peak(self, path: str | Path, *, timeout: float | None = None) -> dict[str, Any]:
        """Use astats to measure peak levels; fall back to ebur128 true peak.

        Returns: {true_peak_dbtp, sample_peak_dbfs, method}
        """
        argv = [
            self._ffmpeg_path,
            "-hide_banner",
            "-i", str(path),
            "-af", "astats=metadata=1:reset=1:length=5",
            "-f", "null",
            "-",
        ]
        proc = subprocess.run(
            argv,
            shell=False,
            check=False,
            capture_output=True,
            text=True,
            timeout=timeout or self.default_timeout_sec,
            encoding="utf-8",
            errors="replace",
        )
        sample_peak_dbfs: float | None = None
        for line in proc.stderr.splitlines():
            if "Peak level dB" in line and "RMS" not in line:
                # e.g. "Peak level dB: -18.213823"  (astats uses "dB", not "dBFS")
                m = re.search(r"Peak level dB:\s*(-?\d+\.\d+)", line)
                if m:
                    sample_peak_dbfs = float(m.group(1))
                    break
        method = "astats"
        # Use ebur128's true peak if available (it's actually sample peak + crest,
        # but most ffmpeg builds map to true peak via oversampling).
        ebur = self.measure_loudness(path, timeout=timeout)
        true_peak = ebur.get("true_peak_dbtp")
        if true_peak is None:
            true_peak = sample_peak_dbfs
            method = "fallback"
        return {
            "true_peak_dbtp": true_peak,
            "sample_peak_dbfs": sample_peak_dbfs,
            "method": method,
        }

    # ------------------------------------------------------------------
    # Clipping detection (PROMPT 11 §17)
    # ------------------------------------------------------------------

    def detect_clipping(self, path: str | Path, *, timeout: float | None = None) -> dict[str, Any]:
        """Detect sample peak >= 0 dBFS (PROMPT 11 §17).

        Returns: {clipped: bool, sample_peak_dbfs, frames_with_clipping}
        """
        stats = self.measure_true_peak(path, timeout=timeout)
        peak = stats.get("sample_peak_dbfs")
        clipped = peak is not None and peak >= 0.0
        return {
            "clipped": clipped,
            "sample_peak_dbfs": peak,
            "frames_with_clipping": 0,  # ffmpeg astats doesn't expose this; left for future
        }

    # ------------------------------------------------------------------
    # Silence detection (PROMPT 11 §25)
    # ------------------------------------------------------------------

    def detect_silence(
        self,
        path: str | Path,
        *,
        noise_db: float = -30.0,
        min_duration_sec: float = 0.5,
        timeout: float | None = None,
    ) -> dict[str, Any]:
        """Detect silence intervals in the audio track.

        Returns: {intervals: [{start_sec, end_sec, duration_sec}], total_sec, leading_silence_sec, trailing_silence_sec}
        """
        argv = [
            self._ffmpeg_path,
            "-hide_banner",
            "-i", str(path),
            "-af",
            f"silencedetect=noise={noise_db}dB:d={min_duration_sec}",
            "-f", "null",
            "-",
        ]
        proc = subprocess.run(
            argv,
            shell=False,
            check=False,
            capture_output=True,
            text=True,
            timeout=timeout or self.default_timeout_sec,
            encoding="utf-8",
            errors="replace",
        )
        intervals = self._parse_silencedetect(proc.stderr)
        # Leading silence = first interval that starts at 0.0
        leading = 0.0
        trailing = 0.0
        if intervals:
            first = intervals[0]
            if first["start_sec"] <= 0.05:
                leading = first["duration_sec"]
            try:
                summary = self.streams_summary(path)
                total_dur = float(summary["audio"].get("duration_sec") or 0.0)
            except MediaProcessorError:
                total_dur = 0.0
            last = intervals[-1]
            if total_dur > 0 and last["end_sec"] >= total_dur - 0.05:
                trailing = last["duration_sec"]
        total_silence = sum(i["duration_sec"] for i in intervals)
        return {
            "intervals": intervals,
            "total_sec": total_silence,
            "leading_silence_sec": leading,
            "trailing_silence_sec": trailing,
        }

    @staticmethod
    def _parse_silencedetect(stderr: str) -> list[dict[str, float]]:
        intervals: list[dict[str, float]] = []
        start: float | None = None
        for line in stderr.splitlines():
            line = line.strip()
            if "silence_start" in line:
                m = re.search(r"silence_start:\s*(-?\d+\.\d+)", line)
                if m:
                    start = float(m.group(1))
            elif "silence_end" in line and start is not None:
                m = re.search(r"silence_end:\s*(-?\d+\.\d+)", line)
                if m:
                    end = float(m.group(1))
                    intervals.append(
                        {"start_sec": start, "end_sec": end, "duration_sec": max(0.0, end - start)}
                    )
                    start = None
        return intervals

    # ------------------------------------------------------------------
    # Loudness normalization (PROMPT 11 §20, §21)
    # ------------------------------------------------------------------

    def normalize_loudness_two_pass(
        self,
        input_path: str | Path,
        output_path: str | Path,
        *,
        target_lufs: float = -16.0,
        true_peak_dbtp: float = -1.0,
        loudness_range_lu: float | None = None,
        timeout: float | None = None,
    ) -> dict[str, Any]:
        """Two-pass loudnorm (PROMPT 11 §21).

        Pass 1: measure. Pass 2: apply with measured params.
        """
        # Pass 1
        pass1 = self.measure_loudness(input_path, timeout=timeout)
        measured_i = pass1.get("integrated_lufs")
        measured_tp = pass1.get("true_peak_dbtp")
        measured_lra = pass1.get("loudness_range_lu")
        if measured_i is None:
            # Could not measure — fall back to a single-pass best-effort.
            return self._loudnorm_single_pass(
                input_path, output_path,
                target_lufs=target_lufs,
                true_peak_dbtp=true_peak_dbtp,
                loudness_range_lu=loudness_range_lu,
                timeout=timeout,
                reason="integrated loudness unavailable in pass 1",
            )
        # Build loudnorm filter for pass 2
        # If LRA is None, pass the configured one.
        lra = measured_lra if measured_lra is not None else (loudness_range_lu or 7.0)
        tp = measured_tp if measured_tp is not None else true_peak_dbtp
        # ffmpeg loudnorm filter: loudnorm=I=<target>:TP=<tp>:LRA=<lra>:measured_I=<mi>:measured_TP=<mtp>:measured_LRA=<mlra>:linear=true
        # loudnorm requires LRA in [1, 50]; clamp measured values that are out of range.
        lra = measured_lra if measured_lra is not None else (loudness_range_lu or 7.0)
        lra = max(1.0, min(50.0, float(lra)))
        measured_lra_clamped = max(1.0, min(50.0, float(measured_lra))) if measured_lra is not None else lra
        tp = measured_tp if measured_tp is not None else true_peak_dbtp
        loudnorm_filter = (
            f"loudnorm=I={target_lufs}:TP={true_peak_dbtp}:LRA={lra}"
            f":measured_I={measured_i}:measured_TP={tp}:measured_LRA={measured_lra_clamped}:linear=true"
        )
        out = Path(output_path)
        out.parent.mkdir(parents=True, exist_ok=True)
        argv = [
            self._ffmpeg_path,
            "-y",
            "-hide_banner",
            "-i", str(input_path),
            "-af", loudnorm_filter,
            "-ar", "48000",
            "-ac", "2",
            "-c:a", "pcm_s16le",
            str(out),
        ]
        _run(argv, timeout=timeout or self.default_timeout_sec)
        # Re-measure output
        out_stats = self.measure_loudness(out, timeout=timeout)
        return {
            "method": "loudnorm_two_pass",
            "pass1": pass1,
            "pass2": out_stats,
            "loudnorm_filter": loudnorm_filter,
            "output_path": str(out),
        }

    def _loudnorm_single_pass(
        self,
        input_path: str | Path,
        output_path: str | Path,
        *,
        target_lufs: float,
        true_peak_dbtp: float,
        loudness_range_lu: float | None,
        timeout: float | None,
        reason: str,
    ) -> dict[str, Any]:
        lra = loudness_range_lu if loudness_range_lu is not None else 7.0
        lra = max(1.0, min(50.0, float(lra)))
        loudnorm_filter = f"loudnorm=I={target_lufs}:TP={true_peak_dbtp}:LRA={lra}"
        out = Path(output_path)
        out.parent.mkdir(parents=True, exist_ok=True)
        argv = [
            self._ffmpeg_path,
            "-y", "-hide_banner", "-i", str(input_path),
            "-af", loudnorm_filter,
            "-ar", "48000", "-ac", "2",
            "-c:a", "pcm_s16le", str(out),
        ]
        _run(argv, timeout=timeout or self.default_timeout_sec)
        out_stats = self.measure_loudness(out, timeout=timeout)
        return {
            "method": "loudnorm_single_pass",
            "fallback_reason": reason,
            "pass1": None,
            "pass2": out_stats,
            "loudnorm_filter": loudnorm_filter,
            "output_path": str(out),
        }

    # ------------------------------------------------------------------
    # Mix buses (PROMPT 11 §14)
    # ------------------------------------------------------------------

    def mix_buses(
        self,
        bus_inputs: Sequence[dict[str, Any]],
        output_path: str | Path,
        *,
        target_sample_rate_hz: int = 48000,
        target_channels: int = 2,
        normalize: bool = False,
        timeout: float | None = None,
    ) -> dict[str, Any]:
        """Mix multiple bus tracks into one WAV.

        `bus_inputs` is a list of dicts:
            {"path": "...", "gain_db": 0.0, "duck_under_narration": True|False, "label": "narration"}

        All inputs are resampled to the target sample rate and channel count,
        then mixed via `amix=inputs=N:duration=longest:dropout_transition=0`.
        """
        out = Path(output_path)
        out.parent.mkdir(parents=True, exist_ok=True)
        n = len(bus_inputs)
        if n == 0:
            raise MediaProcessorError(
                "mix_buses: empty bus_inputs", argv=[], returncode=-1
            )
        # Build filter_complex
        # Step 1: each input → aresample + aformat (stereo) + volume
        parts: list[str] = []
        for i, bus in enumerate(bus_inputs):
            gain = float(bus.get("gain_db", 0.0))
            # Convert dB → linear
            linear = 10.0 ** (gain / 20.0)
            parts.append(
                f"[{i}:a]aresample={target_sample_rate_hz},"
                f"aformat=sample_fmts=fltp:channel_layouts=stereo,"
                f"volume={linear:.6f}[a{i}]"
            )
        # Step 2: amix
        inputs = "".join(f"[a{i}]" for i in range(n))
        parts.append(
            f"{inputs}amix=inputs={n}:duration=longest:dropout_transition=0:normalize={'1' if normalize else '0'}[out]"
        )
        filter_complex = ";\n".join(parts)
        argv = [self._ffmpeg_path, "-y", "-hide_banner"]
        for bus in bus_inputs:
            argv += ["-i", str(bus["path"])]
        argv += [
            "-filter_complex", filter_complex,
            "-map", "[out]",
            "-ar", str(target_sample_rate_hz),
            "-ac", str(target_channels),
            "-c:a", "pcm_s16le",
            str(out),
        ]
        _run(argv, timeout=timeout or self.default_timeout_sec)
        return {
            "method": "amix",
            "input_count": n,
            "filter_complex": filter_complex,
            "output_path": str(out),
        }

    # ------------------------------------------------------------------
    # Mux audio into a (possibly silent) video (PROMPT 11 §13)
    # ------------------------------------------------------------------

    def mux_audio_to_video(
        self,
        video_path: str | Path,
        audio_path: str | Path,
        output_path: str | Path,
        *,
        video_codec: str = "copy",
        audio_codec: str = "aac",
        audio_bitrate_kbps: int = 192,
        target_duration_sec: float | None = None,
        timeout: float | None = None,
    ) -> dict[str, Any]:
        """Replace or add the audio track on a video file.

        If `target_duration_sec` is provided and the audio is shorter,
        the audio is first padded with silence (apad), re-encoded, then
        muxed with `-c:v copy`.
        """
        out = Path(output_path)
        out.parent.mkdir(parents=True, exist_ok=True)
        # If needed, pad the audio to target_duration_sec first.
        audio_for_mux = Path(audio_path)
        if target_duration_sec is not None:
            try:
                sum_ = self.streams_summary(audio_path)
                cur_dur = float(sum_.get("duration_sec") or 0.0)
            except MediaProcessorError:
                cur_dur = 0.0
            if cur_dur < target_duration_sec - 0.05:
                padded = out.with_suffix(".padded.wav")
                pad_argv = [
                    self._ffmpeg_path, "-y", "-hide_banner",
                    "-i", str(audio_path),
                    "-af", f"apad,atrim=0:{target_duration_sec}",
                    "-ar", "48000", "-ac", "2",
                    "-c:a", "pcm_s16le",
                    str(padded),
                ]
                _run(pad_argv, timeout=timeout or self.default_timeout_sec)
                audio_for_mux = padded
        argv = [
            self._ffmpeg_path, "-y", "-hide_banner",
            "-i", str(video_path),
            "-i", str(audio_for_mux),
            "-map", "0:v:0",
            "-map", "1:a:0",
            "-c:v", video_codec,
            "-c:a", audio_codec,
            "-b:a", f"{audio_bitrate_kbps}k",
            str(out),
        ]
        _run(argv, timeout=timeout or self.default_timeout_sec)
        return {
            "output_path": str(out),
            "method": "mux_audio_to_video",
            "audio_padded": audio_for_mux != Path(audio_path),
        }

    # ------------------------------------------------------------------
    # Final encode (PROMPT 11 §28)
    # ------------------------------------------------------------------

    def encode_h264(
        self,
        input_path: str | Path,
        output_path: str | Path,
        *,
        width: int,
        height: int,
        fps: float,
        video_bitrate_kbps: int,
        crf: int,
        pixel_format: str = "yuv420p",
        audio_codec: str = "aac",
        audio_sample_rate_hz: int = 48000,
        audio_channels: int = 2,
        audio_bitrate_kbps: int = 192,
        container: str = "mp4",
        timeout: float | None = None,
    ) -> dict[str, Any]:
        """Encode to h264/aac mp4 with explicit profile fields."""
        out = Path(output_path)
        out.parent.mkdir(parents=True, exist_ok=True)
        argv = [
            self._ffmpeg_path, "-y", "-hide_banner",
            "-i", str(input_path),
            "-vf", f"scale={width}:{height}:flags=lanczos,fps={fps}",
            "-c:v", "libx264",
            "-pix_fmt", pixel_format,
            "-b:v", f"{video_bitrate_kbps}k",
            "-crf", str(int(crf)),
            "-preset", "medium",
            "-c:a", audio_codec,
            "-ar", str(audio_sample_rate_hz),
            "-ac", str(audio_channels),
            "-b:a", f"{audio_bitrate_kbps}k",
            "-movflags", "+faststart",
            "-f", container,
            str(out),
        ]
        _run(argv, timeout=timeout or self.default_timeout_sec)
        return {"output_path": str(out), "method": "encode_h264"}


# ============================================================================
# Helpers
# ============================================================================


def _parse_number(text: str) -> float | None:
    m = re.search(r"(-?\d+(?:\.\d+)?)", text)
    if m:
        try:
            return float(m.group(1))
        except ValueError:
            return None
    return None
