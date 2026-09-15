/**
 * Tiny API client for the FastAPI backend. All routes use `/api/*` which
 * Next.js rewrites to `http://localhost:8000/*` (see next.config.js).
 */

export type StageStatus = "pending" | "running" | "completed" | "failed" | "skipped";
export type JobStatus = "pending" | "running" | "completed" | "failed";

export interface StageInfo {
  name: string;
  label: string;
  status: StageStatus;
  started_at: string | null;
  finished_at: string | null;
  error: string | null;
  output_path: string | null;
}

export interface JobSummary {
  id: string;
  topic: string;
  title: string | null;
  status: JobStatus;
  created_at: string;
  finished_at: string | null;
  error: string | null;
}

export interface JobDetail extends JobSummary {
  stages: StageInfo[];
  artifacts: Record<string, string>;
}

async function http<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(path, {
    ...init,
    headers: { "content-type": "application/json", ...(init?.headers ?? {}) },
    cache: "no-store",
  });
  if (!res.ok) {
    throw new Error(`${res.status} ${res.statusText}: ${await res.text()}`);
  }
  return res.json() as Promise<T>;
}

export const api = {
  health: () => http<{ status: string; openai_configured: boolean; elevenlabs_configured: boolean }>(
    "/api/health"
  ),
  createJob: (topic: string) => http<JobDetail>("/api/jobs", {
    method: "POST",
    body: JSON.stringify({ topic }),
  }),
  listJobs: () => http<JobSummary[]>("/api/jobs"),
  getJob: (id: string) => http<JobDetail>(`/api/jobs/${id}`),
  // Storyboard endpoints
  getStoryboard: (id: string) => http<StoryboardPackage>(`/api/storyboard/${id}/package`),
  getStoryboardBeats: (id: string) => http<{ beats: StoryboardBeat[] }>(`/api/storyboard/${id}/beats`),
  getStoryboardQuality: (id: string) => http<StoryboardQuality>(`/api/storyboard/${id}/quality`),
  getStoryboardPreview: (id: string) => http<StoryboardPreview>(`/api/storyboard/${id}/preview`),
  approveStoryboard: (id: string) => http<StoryboardPackage>(`/api/storyboard/${id}/approve`, { method: "POST" }),
  rejectStoryboard: (id: string, notes: string = "") => http<StoryboardPackage>(`/api/storyboard/${id}/reject?notes=${encodeURIComponent(notes)}`, { method: "POST" }),
};

// ---- Character System types ----

export interface CharacterPreview {
  job_id: string;
  character_count: number;
  instance_count: number;
  wardrobe_count: number;
  pose_count: number;
  expression_count: number;
  asset_package_count: number;
  overall_quality_score: number;
  status: string;
  warnings: string[];
  failures: string[];
}

export interface CharacterQualityScore {
  identity_consistency: number;
  proportion_consistency: number;
  silhouette_quality: number;
  style_consistency: number;
  wardrobe_consistency: number;
  pose_coverage: number;
  expression_coverage: number;
  component_completeness: number;
  animation_readiness: number;
  asset_format_quality: number;
  continuity_readiness: number;
  overall_score: number;
  dimension_scores: Record<string, number>;
  warnings: string[];
  failures: string[];
  recommendations: string[];
}

export interface CharacterInfo {
  character_id: string;
  name: string;
  role: string;
  category: string;
  color: string;
  default_pose: string;
  default_expression: string;
  version: string;
  status: string;
  description: string;
  created_at: string;
}

export interface CharacterListResponse {
  count: number;
  characters: CharacterInfo[];
}

// ---- Character API methods ----

export const characterApi = {
  getPreview: (jobId: string) =>
    http<CharacterPreview>(`/api/characters/${jobId}/preview`),

  listCharacters: (jobId: string) =>
    http<CharacterListResponse>(`/api/characters/${jobId}/characters`),

  getCharacter: (jobId: string, characterId: string) =>
    http<CharacterInfo>(`/api/characters/${jobId}/characters/${characterId}`),

  getQuality: (jobId: string, characterId: string) =>
    http<CharacterQualityScore>(`/api/characters/${jobId}/characters/${characterId}/quality`),

  getPoses: (jobId: string, characterId: string) =>
    http<{ character_id: string; count: number; poses: unknown[] }>(
      `/api/characters/${jobId}/characters/${characterId}/poses`
    ),

  getExpressions: (jobId: string, characterId: string) =>
    http<{ character_id: string; count: number; expressions: unknown[] }>(
      `/api/characters/${jobId}/characters/${characterId}/expressions`
    ),

  getWardrobes: (jobId: string, characterId: string) =>
    http<{ character_id: string; count: number; wardrobes: unknown[] }>(
      `/api/characters/${jobId}/characters/${characterId}/wardrobes`
    ),

  getPreviewSvg: (jobId: string, characterId: string) =>
    http<string>(`/api/characters/${jobId}/characters/${characterId}/preview`),

  approveCharacter: (jobId: string, characterId: string) =>
    http<CharacterInfo>(
      `/api/characters/${jobId}/characters/${characterId}/approve`,
      { method: "POST" }
    ),

  deprecateCharacter: (jobId: string, characterId: string, reason: string = "") =>
    http<CharacterInfo>(
      `/api/characters/${jobId}/characters/${characterId}/deprecate?reason=${encodeURIComponent(reason)}`,
      { method: "POST" }
    ),
};


export interface StoryboardMetadata {
  storyboard_package_id: string;
  story_package_id: string;
  topic: string;
  status: string;
  created_at: string;
}

export interface StoryboardCharacterRequirement {
  character_id: string;
  required_pose: string;
  required_action: string;
  screen_position: string;
}

export interface StoryboardCameraPlan {
  camera_id: string;
  type: string;
  duration_sec: number;
  reason: string;
  start_zoom: number;
  end_zoom: number;
}

export interface StoryboardMotionItem {
  motion_type: string;
  target: string;
  duration_sec: number;
  purpose: string;
}

export interface StoryboardAssetRequirement {
  asset_id: string;
  asset_class: string;
  type: string;
  purpose: string;
  requirement: string;
  reuse_priority: number;
}

export interface StoryboardBeat {
  beat_id: string;
  segment_id: string;
  order: number;
  start_time: number;
  end_time: number;
  duration: number;
  purpose: string;
  visual_function: string;
  visual_mode: string;
  visual_rationale: string;
  action: string;
  characters: StoryboardCharacterRequirement[];
  camera: StoryboardCameraPlan | null;
  motion: StoryboardMotionItem[];
  transition: string;
  source_ids: string[];
  claim_ids: string[];
  asset_requirements: string[];
}

export interface StoryboardQuality {
  overall_score: number;
  dimension_scores: Record<string, number>;
  warnings: string[];
  failures: string[];
  recommendations: string[];
}

export interface StoryboardPreview {
  storyboard_package_id: string;
  story_package_id: string;
  status: string;
  beat_count: number;
  scene_candidate_count: number;
  asset_count: number;
  continuity_issue_count: number;
  quality_overall: number;
  warnings: string[];
  failures: string[];
}

export interface StoryboardPackage {
  metadata: StoryboardMetadata;
  story_package_id: string;
  story_version: string;
  segments: string[];
  visual_beats: StoryboardBeat[];
  asset_requirements: StoryboardAssetRequirement[];
  storyboard_quality_score: StoryboardQuality | null;
  warnings: string[];
  failures: string[];
  status: string;
  version: string;
  created_at: string;
  updated_at: string;
}

// ---- Asset System types (Prompt 6) ----

export interface AssetPreview {
  job_id: string;
  environment_count: number;
  prop_count: number;
  asset_reference_count: number;
  resolution_count: number;
  overall_quality_score: number;
  lifecycle: string;
  warnings: string[];
  failures: string[];
}

export interface AssetQualityScore {
  identity_consistency: number;
  semantic_correctness: number;
  style_consistency: number;
  composition_quality: number;
  resolution_quality: number;
  format_quality: number;
  continuity_readiness: number;
  reuse_quality: number;
  renderer_compatibility: number;
  metadata_completeness: number;
  animation_readiness: number;
  overall_score: number;
  dimension_scores: Record<string, number>;
  warnings: string[];
  failures: string[];
  recommendations: string[];
}

export interface AssetInfo {
  asset_id: string;
  asset_type: string;
  name: string;
  semantic_role: string;
  lifecycle: string;
  status: string;
  version: string;
  primary_asset_uri: string;
  quality_score: number | null;
  scene_count: number;
  created_at: string;
}

export interface AssetListResponse {
  assets: AssetInfo[];
  total: number;
}

export interface EnvironmentInfo extends AssetInfo {
  asset_type: "environment";
  era: string;
  primary_color: string;
}

export interface PropInfo extends AssetInfo {
  asset_type: "prop";
  category: string;
  primary_color: string;
  anchor_count: number;
}

export interface RegistryInfo {
  project_id: string;
  asset_count: number;
  global_assets: string[];
  updated_at: string;
}

// ---- Asset API methods ----

export const assetApi = {
  listAssets: (projectId: string = "", assetType?: string, limit = 100) =>
    http<AssetListResponse>(
      `/api/assets?project_id=${encodeURIComponent(projectId)}${assetType ? `&asset_type=${encodeURIComponent(assetType)}` : ""}&limit=${limit}`
    ),

  getAsset: (assetId: string, projectId: string = "") =>
    http<AssetInfo>(`/api/assets/${encodeURIComponent(assetId)}?project_id=${encodeURIComponent(projectId)}`),

  listVersions: (assetId: string, projectId: string = "") =>
    http<{ asset_id: string; versions: unknown[] }>(
      `/api/assets/${encodeURIComponent(assetId)}/versions?project_id=${encodeURIComponent(projectId)}`
    ),

  resolveAsset: (body: { asset_id: string; asset_type: string; requirement: Record<string, unknown> }) =>
    http<unknown>(`/api/assets/resolve`, {
      method: "POST",
      body: JSON.stringify(body),
      headers: { "Content-Type": "application/json" },
    }),

  generateAsset: (body: {
    asset_id: string;
    asset_type: string;
    prompt: string;
    style_profile?: Record<string, unknown>;
    width?: number;
    height?: number;
  }) =>
    http<unknown>(`/api/assets/generate`, {
      method: "POST",
      body: JSON.stringify(body),
      headers: { "Content-Type": "application/json" },
    }),

  validateAsset: (assetId: string, projectId: string = "") =>
    http<{ asset_id: string; is_valid: boolean; quality_score: AssetQualityScore | null; warnings: string[]; failures: string[] }>(
      `/api/assets/${encodeURIComponent(assetId)}/validate?project_id=${encodeURIComponent(projectId)}`
    ),

  approveAsset: (assetId: string, approvedBy: string = "system") =>
    http<unknown>(`/api/assets/${encodeURIComponent(assetId)}/approve?approved_by=${encodeURIComponent(approvedBy)}`, {
      method: "POST",
    }),

  deprecateAsset: (assetId: string, reason: string = "") =>
    http<unknown>(`/api/assets/${encodeURIComponent(assetId)}/deprecate?reason=${encodeURIComponent(reason)}`, {
      method: "POST",
    }),

  getRegistry: (projectId: string = "") =>
    http<RegistryInfo>(`/api/assets/registry?project_id=${encodeURIComponent(projectId)}`),

  getQuality: (assetId: string, projectId: string = "") =>
    http<{ asset_id: string; quality_score: number | null; warnings: string[] }>(
      `/api/assets/quality/${encodeURIComponent(assetId)}?project_id=${encodeURIComponent(projectId)}`
    ),

  getUsage: (assetId: string, projectId: string = "") =>
    http<{ asset_id: string; projects_using: string[]; scene_count: number }>(
      `/api/assets/${encodeURIComponent(assetId)}/usage?project_id=${encodeURIComponent(projectId)}`
    ),

  listEnvironments: (projectId: string = "") =>
    http<{ environments: EnvironmentInfo[]; total: number }>(
      `/api/assets/environments/list?project_id=${encodeURIComponent(projectId)}`
    ),

  listProps: (projectId: string = "") =>
    http<{ props: PropInfo[]; total: number }>(
      `/api/assets/props/list?project_id=${encodeURIComponent(projectId)}`
    ),
};

