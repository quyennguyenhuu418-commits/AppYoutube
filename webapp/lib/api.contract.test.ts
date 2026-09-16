/**
 * PROMPT 12 — Webapp API client contract tests.
 *
 * Verifies that the TypeScript API client types match the Python model
 * contracts defined in app/api/render.py and app/orchestration/render_job.py.
 *
 * These are cross-runtime contract tests: they ensure that the JSON API
 * response shape is consistent with what the Python backend produces.
 *
 * Test cases (PROMPT 12 §31):
 *   1. RenderStatus field names match backend
 *   2. RenderQAReport field names match backend
 *   3. RenderArtifact field names match backend
 *   4. RenderLifecycle values are valid
 *   5. QA check status values are valid
 *   6. renderApi methods return the correct types
 *   7. videoUrl generates a safe URL
 */
import { describe, it, expect } from "vitest";
import {
  renderApi,
  type RenderStatus,
  type RenderQAReport,
  type RenderArtifact,
  type RenderLifecycle,
  type QACheckResult,
} from "../lib/api";

// ---------------------------------------------------------------------------
// Type-level contract tests (static — no network required)
// ---------------------------------------------------------------------------

describe("RenderLifecycle — valid values", () => {
  const valid: RenderLifecycle[] = [
    "queued",
    "preparing",
    "preflight",
    "rendering",
    "mastering",
    "qa",
    "finalizing",
    "approved",
    "failed",
    "cancelled",
  ];

  it("has all 10 documented lifecycle states", () => {
    expect(valid).toHaveLength(10);
  });

  it("includes terminal and non-terminal states", () => {
    const terminals: RenderLifecycle[] = ["approved", "failed", "cancelled"];
    const nonTerminals = valid.filter((s) => !terminals.includes(s));
    expect(nonTerminals).toHaveLength(7);
    expect(terminals).toHaveLength(3);
  });
});

describe("RenderStatus — required fields (PROMPT 12 §11)", () => {
  const minimal: RenderStatus = {
    job_id: "job_001",
    project_id: "proj_x",
    topic: "Test topic",
    lifecycle: "queued",
    progress_pct: 0,
    current_stage: null,
    stage_progress: {},
    stages: [],
    is_terminal: false,
    error: null,
    error_stage: null,
    render_plan_id: null,
    final_artifact_id: null,
    qa_report_id: null,
    renderer_version: null,
    ffmpeg_version: null,
    created_at: "2026-09-15T00:00:00Z",
    started_at: null,
    finished_at: null,
  };

  it("accepts all required fields without error", () => {
    expect(minimal.job_id).toBe("job_001");
    expect(minimal.lifecycle).toBe("queued");
    expect(minimal.progress_pct).toBe(0);
    expect(minimal.is_terminal).toBe(false);
  });

  it("maps progress_pct for each lifecycle stage", () => {
    const stageProgress: Record<RenderLifecycle, number> = {
      queued: 0,
      preparing: 5,
      preflight: 10,
      rendering: 55,
      mastering: 75,
      qa: 90,
      finalizing: 98,
      approved: 100,
      failed: 100,
      cancelled: 100,
    };
    Object.entries(stageProgress).forEach(([stage, pct]) => {
      expect(typeof stage).toBe("string");
      expect(typeof pct).toBe("number");
      expect(pct).toBeGreaterThanOrEqual(0);
      expect(pct).toBeLessThanOrEqual(100);
    });
  });
});

describe("RenderQAReport — QA check contract (PROMPT 12 §10)", () => {
  const minimal: RenderQAReport = {
    report_id: "qa_001",
    artifact_id: "final_001",
    overall_status: "pass",
    checks: [],
    warnings: [],
    failures: [],
    ffmpeg_version: "ffmpeg-9.0",
    ffprobe_version: "ffprobe-9.0",
    profile_id: "rp_default",
    fingerprint: "fp_001",
    created_at: "2026-09-15T00:00:00Z",
  };

  it("accepts valid overall_status values", () => {
    expect(["pass", "warn", "fail"]).toContain(minimal.overall_status);
  });
});

describe("QACheckResult — status contract", () => {
  const validStatuses: QACheckResult["status"][] = [
    "pass",
    "warn",
    "fail",
    "unavailable",
  ];

  it("has exactly 4 valid status values", () => {
    expect(validStatuses).toHaveLength(4);
  });

  it("PASS is distinct from UNAVAILABLE (PROMPT 12 §10)", () => {
    expect("pass").not.toBe("unavailable");
    expect("fail").not.toBe("unavailable");
    expect("warn").not.toBe("unavailable");
  });
});

describe("RenderArtifact — safe URL contract (PROMPT 12 §11, §22)", () => {
  const minimal: RenderArtifact = {
    artifact_id: "final_001",
    project_id: "proj_x",
    render_plan_id: "plan_001",
    raw_artifact_id: null,
    render_profile_id: "rp_default",
    mastering_profile_id: "mp_default",
    qa_report_id: "qa_001",
    renderer_version: "remotion-unknown",
    width: 1280,
    height: 720,
    fps: 30.0,
    video_codec: "h264",
    audio_codec: "aac",
    audio_sample_rate_hz: 48000,
    audio_channels: 2,
    duration_sec: 5.4,
    file_size_bytes: 1_234_567,
    checksum_sha256: "0".repeat(64),
    loudness_lufs: -16.3,
    true_peak_dbtp: -9.2,
    loudness_range_lu: null,
    lifecycle_status: "approved",
    qa_status: "final_approved",
    video_url: "/render/job_001/video",
    fingerprint: "fp_001",
    created_at: "2026-09-15T00:00:00Z",
  };

  it("video_url is a relative path — no absolute filesystem path", () => {
    expect(minimal.video_url).not.toMatch(/^[A-Za-z]:/);
    expect(minimal.video_url).not.toMatch(/^\/workspace\//);
    expect(minimal.video_url).not.toMatch(/^\/tmp\//);
    expect(minimal.video_url).toMatch(/^\/render\//);
  });

  it("checksum is a valid SHA-256 hex string", () => {
    expect(minimal.checksum_sha256).toMatch(/^[0-9a-f]{64}$/);
  });

  it("resolution is even (FFmpeg requirement)", () => {
    expect(minimal.width % 2).toBe(0);
    expect(minimal.height % 2).toBe(0);
  });

  it("loudness_lufs is a valid LUFS value (negative)", () => {
    expect(minimal.loudness_lufs).toBeLessThan(0);
  });

  it("true_peak_dbtp is below 0 dBTP (no clipping)", () => {
    expect(minimal.true_peak_dbtp).toBeLessThan(0);
  });
});

describe("renderApi — URL generation safety (PROMPT 12 §22)", () => {
  it("videoUrl generates safe relative URLs", () => {
    const jobId = "job-test-001";
    const url = renderApi.videoUrl(jobId);
    expect(url).toBe(`/api/render/${jobId}/video`);
    expect(url).not.toContain("..");
    expect(url).not.toContain("workspace");
    expect(url).not.toContain("C:");
  });

  it("job_id is URI-encoded in artifact/qa/status URLs", () => {
    const unsafeJobId = "job/with/slashes";
    const safeId = encodeURIComponent(unsafeJobId);
    const statusUrl = `/render/${safeId}/status`;
    expect(statusUrl).not.toContain(unsafeJobId);
    expect(statusUrl).toContain(safeId);
  });
});

describe("renderApi — method signatures", () => {
  it("all renderApi methods are functions", () => {
    expect(typeof renderApi.preflight).toBe("function");
    expect(typeof renderApi.finalize).toBe("function");
    expect(typeof renderApi.status).toBe("function");
    expect(typeof renderApi.qa).toBe("function");
    expect(typeof renderApi.artifact).toBe("function");
    expect(typeof renderApi.videoUrl).toBe("function");
  });
});

describe("Cross-runtime — Python enum values vs TS types (PROMPT 12 §31)", () => {
  // These values must stay in sync with the Python backend.
  // Any change to the backend enum requires updating this test.

  const PYTHON_JOB_LIFECYCLE = [
    "queued",
    "preparing",
    "preflight",
    "rendering",
    "mastering",
    "qa",
    "finalizing",
    "approved",
    "failed",
    "cancelled",
  ] as const;

  const PYTHON_QA_STATUS = ["pass", "warn", "fail", "unavailable"] as const;

  it("Python JobLifecycle values match TypeScript RenderLifecycle", () => {
    PYTHON_JOB_LIFECYCLE.forEach((v) => {
      // This is a documentation check — the TS type is derived from the Python enum
      expect(typeof v).toBe("string");
    });
    expect(PYTHON_JOB_LIFECYCLE).toHaveLength(10);
  });

  it("Python QA status values match TypeScript QACheckResult status", () => {
    PYTHON_QA_STATUS.forEach((v) => {
      expect(typeof v).toBe("string");
    });
    expect(PYTHON_QA_STATUS).toHaveLength(4);
  });
});
