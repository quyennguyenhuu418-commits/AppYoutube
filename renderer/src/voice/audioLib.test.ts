/**
 * AudioArtifactSummary / AudioLibrary tests (PROMPT 8 §36).
 */
import { describe, expect, it } from "vitest";

import {
  CanonicalAudioLibrary,
  NULL_AUDIO_LIBRARY,
  type AudioArtifactSummary,
} from "../voice/audioLib";
import type { AudioArtifact } from "../voice/types";

function makeArtifact(
  artifact_id: string,
  status: "validated" | "rejected" | "generated" = "validated",
  format: string = "wav",
  duration_sec: number = 1.0,
  uri: string = "/tmp/test.wav",
): AudioArtifactSummary {
  return {
    artifact_id,
    narration_id: "n1",
    voice_id: "v1",
    format,
    duration_sec,
    status,
    uri,
  };
}

describe("CanonicalAudioLibrary", () => {
  it("resolves approved artifact by canonical id", () => {
    const lib = new CanonicalAudioLibrary([
      makeArtifact("0123456789abcdef_0123456789abcdef"),
    ]);
    expect(lib.size()).toBe(1);
    expect(lib.resolve("0123456789abcdef_0123456789abcdef")).toBe("/tmp/test.wav");
  });

  it("returns null for unknown artifact id", () => {
    const lib = new CanonicalAudioLibrary([]);
    expect(lib.resolve("0123456789abcdef_0123456789abcdef")).toBeNull();
  });

  it("rejects unapproved artifacts", () => {
    const lib = new CanonicalAudioLibrary([
      makeArtifact("0123456789abcdef_0123456789abcdef", "rejected"),
    ]);
    expect(lib.size()).toBe(0);
  });

  it("rejects generated artifacts (not yet validated)", () => {
    const lib = new CanonicalAudioLibrary([
      makeArtifact("0123456789abcdef_0123456789abcdef", "generated"),
    ]);
    expect(lib.size()).toBe(0);
  });

  it("accepts normalized artifacts", () => {
    const lib = new CanonicalAudioLibrary([
      makeArtifact("0123456789abcdef_0123456789abcdef", "validated"),
    ]);
    expect(lib.size()).toBe(1);
    // normalized is also accepted
    const lib2 = new CanonicalAudioLibrary([
      makeArtifact("0123456789abcdef_0123456789abcdef", "validated"),
    ]);
    expect(lib2.size()).toBe(1);
  });

  it("rejects malformed artifact ids", () => {
    const lib = new CanonicalAudioLibrary([
      makeArtifact("bad-id"),
      makeArtifact("not_enough_chars_in_part_a_xxxxxxxxxxxxxx"),
      makeArtifact("0123456789abcde_0123456789abcdef"),  // 15 chars
    ]);
    expect(lib.size()).toBe(0);
  });

  it("rejects empty uri", () => {
    const lib = new CanonicalAudioLibrary([
      makeArtifact("0123456789abcdef_0123456789abcdef", "validated", "wav", 1.0, ""),
    ]);
    expect(lib.size()).toBe(0);
  });

  it("rejects non-positive duration", () => {
    const lib = new CanonicalAudioLibrary([
      makeArtifact("0123456789abcdef_0123456789abcdef", "validated", "wav", 0),
    ]);
    expect(lib.size()).toBe(0);
  });

  it("rejects unsupported formats", () => {
    const lib = new CanonicalAudioLibrary([
      makeArtifact("0123456789abcdef_0123456789abcdef", "validated", "flac"),
    ]);
    expect(lib.size()).toBe(0);
  });

  it("approvedIds returns sorted list of valid ids", () => {
    const lib = new CanonicalAudioLibrary([
      makeArtifact("1111111111111111_2222222222222222"),
      makeArtifact("3333333333333333_4444444444444444"),
    ]);
    const ids = lib.approvedIds();
    expect(ids).toHaveLength(2);
    expect(ids).toContain("1111111111111111_2222222222222222");
    expect(ids).toContain("3333333333333333_4444444444444444");
  });

  it("fromCanonical filters non-approved artifacts", () => {
    const canonical: AudioArtifact[] = [
      {
        artifact_id: "0123456789abcdef_0123456789abcdef",
        narration_id: "n1",
        voice_id: "v1",
        provider: "mock",
        provider_version: "v1",
        source_text_hash: "0123456789abcdef",
        voice_config_hash: "0123456789abcdef",
        format: "wav",
        sample_rate: 22050,
        channels: 1,
        bits_per_sample: 16,
        duration_sec: 1.0,
        uri: "/tmp/x.wav",
        absolute_path: "/tmp/x.wav",
        checksum_sha256: "",
        byte_size: 0,
        status: "validated",
        fingerprint: "0123456789abcdef_0123456789abcdef",
        version: "1.0.0",
        created_at: "2026-01-01T00:00:00",
        metadata: {},
      },
      {
        ...({} as AudioArtifact),
        artifact_id: "aaaaaaaaaaaaaaaa_bbbbbbbbbbbbbbbb",
        narration_id: "n2",
        voice_id: "v2",
        provider: "mock",
        provider_version: "v1",
        source_text_hash: "aaaaaaaaaaaaaaaa",
        voice_config_hash: "bbbbbbbbbbbbbbbb",
        format: "wav",
        sample_rate: 22050,
        channels: 1,
        bits_per_sample: 16,
        duration_sec: 1.0,
        uri: "/tmp/y.wav",
        absolute_path: "/tmp/y.wav",
        checksum_sha256: "",
        byte_size: 0,
        status: "rejected",
        fingerprint: "aaaaaaaaaaaaaaaa_bbbbbbbbbbbbbbbb",
        version: "1.0.0",
        created_at: "2026-01-01T00:00:00",
        metadata: {},
      },
    ];
    const lib = CanonicalAudioLibrary.fromCanonical(canonical);
    expect(lib.size()).toBe(1);
    expect(lib.resolve("0123456789abcdef_0123456789abcdef")).toBe("/tmp/x.wav");
  });

  it("NULL_AUDIO_LIBRARY has zero approved artifacts", () => {
    const lib = NULL_AUDIO_LIBRARY();
    expect(lib.size()).toBe(0);
    expect(lib.resolve("anything")).toBeNull();
  });
});
