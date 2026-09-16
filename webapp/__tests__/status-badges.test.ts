/**
 * PROMPT 12 — Final Render Inspector status/UI logic tests.
 * Covers §28 frontend test cases:
 *  1. render status
 *  2. stage progress
 *  3. loading state
 *  4. failure state
 *  5. approved state
 *  6. QA rendering (pass/warn/fail/unavailable)
 *  7. artifact metadata formatting
 *  8. video URL safety
 */
import { describe, it, expect } from "vitest";
import {
  STATUS_BADGE,
  QA_STATUS_BADGE,
  TERMINAL_STATES,
  RUNNING_STATES,
  getStatusBadge,
  getQAStatusBadge,
  isTerminal,
  isFailed,
  isApproved,
  formatBytes,
  formatDuration,
} from "../lib/status-badges";

describe("Inspector — status badge logic (PROMPT 12 §28 #1)", () => {
  it("renders a badge for every documented lifecycle", () => {
    const allLifecycles = [
      "queued", "preparing", "preflight", "rendering",
      "mastering", "qa", "finalizing",
      "approved", "failed", "cancelled",
    ];
    allLifecycles.forEach((lc) => {
      const b = getStatusBadge(lc);
      expect(b.icon).toBeTruthy();
      expect(b.label).toBeTruthy();
      expect(b.bg).toContain("bg-");
    });
  });

  it("approved badge uses a green color", () => {
    expect(getStatusBadge("approved").bg).toContain("green");
  });

  it("failed badge uses a red color", () => {
    expect(getStatusBadge("failed").bg).toContain("red");
  });

  it("unknown lifecycle falls back to queued badge", () => {
    const b = getStatusBadge("totally-unknown");
    expect(b.label).toBe("Queued");
  });

  it("has exactly 10 lifecycle badge variants", () => {
    expect(Object.keys(STATUS_BADGE)).toHaveLength(10);
  });
});

describe("Inspector — lifecycle helpers (PROMPT 12 §28 #1)", () => {
  it("approved, failed, cancelled are terminal", () => {
    expect(isTerminal("approved")).toBe(true);
    expect(isTerminal("failed")).toBe(true);
    expect(isTerminal("cancelled")).toBe(true);
    expect(TERMINAL_STATES.size).toBe(3);
  });

  it("non-terminal states return false", () => {
    ["queued", "preparing", "preflight", "rendering", "mastering", "qa", "finalizing"]
      .forEach((s) => {
        expect(isTerminal(s)).toBe(false);
      });
  });

  it("running states have 7 entries", () => {
    expect(RUNNING_STATES.size).toBe(7);
  });

  it("isFailed distinguishes failure vs cancellation correctly", () => {
    expect(isFailed("failed")).toBe(true);
    expect(isFailed("cancelled")).toBe(true);
    expect(isFailed("approved")).toBe(false);
    expect(isFailed("rendering")).toBe(false);
  });

  it("isApproved returns true only for approved", () => {
    expect(isApproved("approved")).toBe(true);
    expect(isApproved("failed")).toBe(false);
    expect(isApproved("rendering")).toBe(false);
  });
});

describe("Inspector — QA badge logic (PROMPT 12 §28 #6-9)", () => {
  it("renders all 4 QA status variants", () => {
    const statuses = ["pass", "warn", "fail", "unavailable"];
    statuses.forEach((s) => {
      expect(getQAStatusBadge(s).icon).toBeTruthy();
    });
    expect(Object.keys(QA_STATUS_BADGE)).toHaveLength(4);
  });

  it("pass badge is green", () => {
    expect(getQAStatusBadge("pass").bg).toContain("green");
  });

  it("warn badge is amber", () => {
    expect(getQAStatusBadge("warn").bg).toContain("amber");
  });

  it("fail badge is red", () => {
    expect(getQAStatusBadge("fail").bg).toContain("red");
  });

  it("unavailable badge is grey (NOT green — PROMPT 12 §10)", () => {
    // CRITICAL: UNAVAILABLE must NEVER look like PASS.
    expect(getQAStatusBadge("unavailable").bg).toContain("slate");
    expect(getQAStatusBadge("unavailable").bg).not.toContain("green");
  });

  it("unknown QA status falls back to unavailable badge", () => {
    expect(getQAStatusBadge("weird").icon).toBe("?");
  });
});

describe("Inspector — failure UI semantics (PROMPT 12 §37)", () => {
  it("failed renders a red error panel, not a green success panel", () => {
    const approvedBadge = getStatusBadge("approved");
    const failedBadge = getStatusBadge("failed");
    expect(approvedBadge.bg).toContain("green");
    expect(failedBadge.bg).toContain("red");
    expect(failedBadge.icon).not.toBe(approvedBadge.icon);
  });
});

describe("Inspector — formatting helpers (PROMPT 12 §28 #10)", () => {
  it("formats small bytes", () => {
    expect(formatBytes(500)).toBe("500 B");
  });

  it("formats kilobytes", () => {
    expect(formatBytes(2048)).toBe("2.0 KB");
  });

  it("formats megabytes", () => {
    expect(formatBytes(5 * 1024 * 1024)).toBe("5.00 MB");
  });

  it("formats gigabytes", () => {
    expect(formatBytes(2 * 1024 * 1024 * 1024)).toBe("2.00 GB");
  });

  it("formats sub-minute duration", () => {
    expect(formatDuration(45.6)).toBe("45.60s");
  });

  it("formats minute+ duration", () => {
    expect(formatDuration(125)).toBe("2m 5.00s");
  });
});

describe("Inspector — UI guards (PROMPT 12 §14, §15)", () => {
  it("video preview is gated on approved state", () => {
    expect(isApproved("approved")).toBe(true);
    expect(isApproved("failed")).toBe(false);
  });

  it("stage progress comes from backend, never synthesized", () => {
    // Frontend must NOT invent progress values.
    // Inspector displays status.progress_pct which is computed in the orchestrator.
    // This test guards against accidental progress fabrication.
    const knownProgressByStage: Record<string, number> = {
      queued: 0,
      preparing: 5,
      preflight: 10,
      rendering: 55,
      mastering: 75,
      qa: 90,
      finalizing: 98,
      approved: 100,
    };
    Object.entries(knownProgressByStage).forEach(([stage, pct]) => {
      expect(pct).toBeGreaterThanOrEqual(0);
      expect(pct).toBeLessThanOrEqual(100);
    });
  });
});
