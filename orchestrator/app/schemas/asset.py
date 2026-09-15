"""
Asset Intelligence System — canonical schemas for Environment, Prop, Diagram, Overlay,
and the unified AssetReference / AssetPackage / AssetRegistry system.

Architecture:
    Character System owns: character identities, poses, expressions, wardrobes (Prompt 5)
    Asset System owns: environment, prop, diagram, overlay, shared assets

The Asset System provides:
    1. Unified AssetReference contract (renderer-consumable)
    2. EnvironmentSystem: persistent environment identities with continuity rules
    3. PropSystem: reusable prop identities with anchor points
    4. AssetResolver: resolves StoryboardPackage requirements → canonical assets
    5. AssetRegistry: global/project asset management
    6. AssetLifecycle: draft → generated → validated → approved → deprecated
    7. AssetQuality: deterministic quality scoring per asset type

Key design decisions:
    - AssetDefinition is the base type; EnvironmentAsset and PropAsset inherit
    - AssetReference is the ONLY object passed to the renderer
    - AssetResolver is the single canonical path for asset resolution
    - Duplicate detection uses semantic identity keys (hashing)
    - All assets are versioned; reuse is explicit
    - Cache keys are content-addressed (SHA-256/16-char)
    - Backward compatible with existing SceneDefinition (no breaking changes)
    - Backward compatible with s6_assets.py output (backwards_assets.json)

External contracts:
    - SceneDefinition (C-01): environment/character/prop fields
    - StoryboardPackage (C-13): AssetRequirement, EnvironmentRequirement, PropRequirement
    - CharacterSystemPackage (C-14): characters owned by Character System
    - renderer/src/components/Props.tsx: 12 hardcoded PropKind values
    - renderer/src/scenes/types.ts: TS mirrors of Environment, PropKind
"""
from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Any

from pydantic import BaseModel, Field, model_validator


# ============================================================================
# Enums — Asset domain vocabulary
# ============================================================================

class AssetType(str, Enum):
    """The canonical asset type hierarchy."""
    CHARACTER = "character"
    ENVIRONMENT = "environment"
    PROP = "prop"
    DIAGRAM = "diagram"
    OVERLAY = "overlay"
    TEXT = "text"


class AssetLifecycle(str, Enum):
    """Production lifecycle — an asset must reach APPROVED before final render."""
    DRAFT = "draft"
    GENERATING = "generating"
    GENERATED = "generated"
    VALIDATED = "validated"
    REVIEW = "review"
    APPROVED = "approved"
    REJECTED = "rejected"
    DEPRECATED = "deprecated"
    ARCHIVED = "archived"


class ReusePolicy(str, Enum):
    """Asset reuse strategy — how aggressively the resolver reuses this asset."""
    REUSE_ALWAYS = "reuse_always"       # Never create a new instance; always reference
    REUSE_PREFERRED = "reuse_preferred"  # Prefer reuse; create only if no match
    REUSE_ALLOWED = "reuse_allowed"     # Check for matches first
    SCENE_LOCAL = "scene_local"          # Never reuse across scenes
    NEVER_REUSE = "never_reuse"          # Always generate new


class AssetStatus(str, Enum):
    """Status for registry entries."""
    ACTIVE = "active"
    REVIEW = "review"
    APPROVED = "approved"
    DEPRECATED = "deprecated"
    ARCHIVED = "archived"


class EnvironmentEra(str, Enum):
    """Historical era of the environment."""
    PREHISTORIC = "prehistoric"
    ANCIENT = "ancient"
    CLASSICAL = "classical"
    MEDIEVAL = "medieval"
    EARLY_MODERN = "early_modern"
    INDUSTRIAL = "industrial"
    MODERN = "modern"
    FUTURE = "future"
    ABSTRACT = "abstract"
    UNKNOWN = "unknown"


class EnvironmentScale(str, Enum):
    """Scale of the environment."""
    MICRO = "micro"      # e.g. table top
    INTIMATE = "intimate" # e.g. room
    HUMAN = "human"      # e.g. street
    LANDSCAPE = "landscape"  # e.g. city
    REGIONAL = "regional"    # e.g. region
    CONTINENTAL = "continental"
    GLOBAL = "global"


class LightingType(str, Enum):
    """Lighting conditions."""
    NATURAL = "natural"
    WARM = "warm"
    COOL = "cool"
    DRAMATIC = "dramatic"
    MOOD = "mood"
    MOONLIGHT = "moonlight"
    FIRELIGHT = "firelight"
    OVERCAST = "overcast"
    HARSH = "harsh"
    SOFT = "soft"


class WeatherType(str, Enum):
    """Weather conditions."""
    CLEAR = "clear"
    CLOUDY = "cloudy"
    OVERCAST = "overcast"
    RAIN = "rain"
    SNOW = "snow"
    FOG = "fog"
    STORM = "storm"
    WIND = "wind"


class TimeOfDay(str, Enum):
    """Time of day."""
    DAWN = "dawn"
    MORNING = "morning"
    MIDDAY = "midday"
    AFTERNOON = "afternoon"
    DUSK = "dusk"
    NIGHT = "night"
    MIDNIGHT = "midnight"


class PropCategory(str, Enum):
    """Prop semantic category."""
    WEAPON = "weapon"
    TOOL = "tool"
    FURNITURE = "furniture"
    DOCUMENT = "document"
    FOOD = "food"
    CLOTHING = "clothing"
    STRUCTURE = "structure"
    NATURE = "nature"
    ANIMAL = "animal"
    VEHICLE = "vehicle"
    SYMBOL = "symbol"
    ABSTRACT = "abstract"


# ============================================================================
# Asset Quality Score — deterministic quality per asset type
# ============================================================================

class AssetQualityScore(BaseModel):
    """Deterministic quality score for an asset.

    All dimensions derive from asset definition fields — no randomness.
    Each asset type has its own dimension set.
    """
    # --- Common dimensions ---
    identity_consistency: float = Field(ge=0.0, le=1.0, default=0.0)
    semantic_correctness: float = Field(ge=0.0, le=1.0, default=0.0)
    style_consistency: float = Field(ge=0.0, le=1.0, default=0.0)
    composition_quality: float = Field(ge=0.0, le=1.0, default=0.0)
    resolution_quality: float = Field(ge=0.0, le=1.0, default=0.0)
    format_quality: float = Field(ge=0.0, le=1.0, default=0.0)
    continuity_readiness: float = Field(ge=0.0, le=1.0, default=0.0)
    reuse_quality: float = Field(ge=0.0, le=1.0, default=0.0)
    renderer_compatibility: float = Field(ge=0.0, le=1.0, default=0.0)
    metadata_completeness: float = Field(ge=0.0, le=1.0, default=0.0)
    animation_readiness: float = Field(ge=0.0, le=1.0, default=0.0)

    # --- Aggregated ---
    overall_score: float = Field(ge=0.0, le=1.0, default=0.0)
    dimension_scores: dict[str, float] = Field(default_factory=dict)
    warnings: list[str] = Field(default_factory=list)
    failures: list[str] = Field(default_factory=list)
    recommendations: list[str] = Field(default_factory=list)

    @model_validator(mode="after")
    def _normalize_overall(self) -> "AssetQualityScore":
        if self.dimension_scores:
            vals = list(self.dimension_scores.values())
            object.__setattr__(self, "overall_score", round(sum(vals) / len(vals), 3))
        elif self.overall_score == 0.0:
            fields = [
                self.identity_consistency,
                self.semantic_correctness,
                self.style_consistency,
                self.composition_quality,
                self.resolution_quality,
                self.format_quality,
                self.continuity_readiness,
                self.reuse_quality,
                self.renderer_compatibility,
                self.metadata_completeness,
                self.animation_readiness,
            ]
            object.__setattr__(self, "overall_score", round(sum(fields) / len(fields), 3))
        return self


# ============================================================================
# AssetPackage — filesystem contract
# ============================================================================

class AssetPackage(BaseModel):
    """The on-disk package structure for a canonical asset.

    Path: {workspace}/assets/{asset_type}/{asset_id}/v{version}/
    """
    asset_id: str = Field(min_length=1, max_length=64)
    asset_type: AssetType
    version: str = Field(default="1.0.0", max_length=16)
    package_version: str = Field(default="1.0.0", max_length=16)

    # Files (relative paths inside the package directory)
    manifest_file: str = Field(default="manifest.json", max_length=128)
    identity_file: str = Field(default="identity.json", max_length=128)
    design_file: str = Field(default="design.json", max_length=128)
    metadata_file: str = Field(default="metadata.json", max_length=128)
    quality_file: str = Field(default="quality.json", max_length=128)

    # Optional preview
    preview_svg: str = Field(default="", max_length=500)
    preview_png: str = Field(default="", max_length=256)

    # Asset file paths
    asset_file: str = Field(default="", max_length=256,
                             description="Primary asset file (PNG/SVG path)")
    variant_dir: str = Field(default="variants/", max_length=128)

    # Quality
    quality_score: float | None = Field(default=None, ge=0.0, le=1.0)
    design_approved: bool = Field(default=False)

    # Provenance
    input_hash: str = Field(default="", max_length=64,
                             description="Hash of inputs that produced this asset")
    provider: str = Field(default="", max_length=64,
                            description="Which ImageProvider generated this")
    created_at: datetime = Field(default_factory=datetime.utcnow)


# ============================================================================
# AssetReference — the ONLY object passed to the renderer
# ============================================================================

class AssetReference(BaseModel):
    """A stable reference to a canonical asset for the renderer.

    This is the ONLY object type that crosses the pipeline→renderer boundary
    for non-character assets. It contains everything the renderer needs to
    locate and use the asset — no arbitrary objects, no inline SVG from LLM.

    Backward compatible with existing SceneDefinition:
      - environment_id maps to environment asset
      - prop references map to prop assets
      - background_asset maps to environment.asset_file
    """
    asset_id: str = Field(min_length=1, max_length=64)
    asset_type: AssetType

    # Version — renderer should cache by (asset_id, version)
    version: str = Field(default="1.0.0", max_length=16)

    # Filesystem path relative to workspace root
    uri: str = Field(default="", max_length=256,
                      description="Relative path from workspace root, e.g. 'assets/environments/ice_age_plains/v1/preview.png'")

    # Format info
    format: str = Field(default="png", max_length=16)  # png | svg | json
    width: int | None = Field(default=None, ge=1)
    height: int | None = Field(default=None, ge=1)

    # Semantic metadata (for renderer decision-making)
    name: str = Field(default="", max_length=64)
    description: str = Field(default="", max_length=300)
    mood: str = Field(default="", max_length=32)  # calm | tense | triumphant | mysterious | warm

    # Style tags (for filtering)
    style_tags: list[str] = Field(default_factory=list)

    # Continuity metadata
    reuse_policy: ReusePolicy = ReusePolicy.REUSE_PREFERRED
    continuity_locked: bool = Field(default=False)

    # Quality
    quality_score: float | None = Field(default=None, ge=0.0, le=1.0)
    lifecycle: AssetLifecycle = AssetLifecycle.DRAFT

    # Renderer hints
    renderer_hints: dict[str, Any] = Field(default_factory=dict,
                                          description="Type-specific renderer hints")

    @model_validator(mode="after")
    def _validate_uri_or_format(self) -> "AssetReference":
        """Either uri or format must be present."""
        if not self.uri and not self.format:
            object.__setattr__(self, "format", "png")
        return self

    def to_scene_definition_environment(self) -> dict[str, Any]:
        """Convert to SceneDefinition.Environment-compatible dict."""
        return {
            "id": self.asset_id,
            "name": self.name or self.asset_id,
            "background_asset": self.uri,
            "mood": self.mood or "calm",
        }


# ============================================================================
# EnvironmentAsset — canonical persistent environment identity
# ============================================================================

class EnvironmentStyleProfile(BaseModel):
    """Style configuration for an environment."""
    illustration_style: str = Field(default="painterly_2d",
                                    max_length=32)  # painterly_2d | flat | realistic | schematic
    line_weight: float = Field(default=2.0, ge=0.0, le=8.0)
    shading_level: str = Field(default="minimal", max_length=16)  # none | minimal | moderate | full
    color_temperature: str = Field(default="neutral", max_length=16)  # warm | cool | neutral


class EnvironmentLightingProfile(BaseModel):
    """Lighting configuration for an environment."""
    primary: LightingType = LightingType.NATURAL
    secondary: LightingType | None = None
    intensity: float = Field(default=0.7, ge=0.0, le=1.0)
    color_overlay: str | None = Field(default=None, pattern=r"^#[0-9A-Fa-f]{6}$")
    time_of_day: TimeOfDay = TimeOfDay.MIDDAY
    season: str = Field(default="", max_length=32)
    weather: WeatherType = WeatherType.CLEAR


class EnvironmentCompositionProfile(BaseModel):
    """Camera-safe composition rules for an environment."""
    safe_area_x: float = Field(default=0.1, ge=0.0, le=0.5,
                                description="Fraction of edges to keep clear")
    safe_area_y: float = Field(default=0.1, ge=0.0, le=0.5)
    focal_point_x: float = Field(default=0.5, ge=0.0, le=1.0)
    focal_point_y: float = Field(default=0.5, ge=0.0, le=1.0)
    depth_layers: int = Field(default=3, ge=1, le=5,
                              description="Number of depth layers (background/mid/foreground)")
    horizon_ratio: float = Field(default=0.5, ge=0.0, le=1.0,
                                   description="Where the horizon sits (0=top, 1=bottom)")


class EnvironmentPaletteProfile(BaseModel):
    """Color palette for an environment."""
    primary: str = Field(pattern=r"^#[0-9A-Fa-f]{6}$")
    secondary: str | None = Field(default=None, pattern=r"^#[0-9A-Fa-f]{6}$")
    accent: str | None = Field(default=None, pattern=r"^#[0-9A-Fa-f]{6}$")
    sky: str | None = Field(default=None, pattern=r"^#[0-9A-Fa-f]{6}$")
    ground: str | None = Field(default=None, pattern=r"^#[0-9A-Fa-f]{6}$")
    mood_tint: str | None = Field(default=None, pattern=r"^#[0-9A-Fa-f]{6}$")


class EnvironmentContinuityProfile(BaseModel):
    """Continuity rules for an environment.

    Defines which properties are locked (must not change across scenes) and
    which are permitted to vary per scene.
    """
    identity_locked: bool = True
    palette_locked: bool = True
    architecture_locked: bool = True
    major_landmarks_locked: bool = True
    historical_era_locked: bool = True
    permitted_scene_changes: list[str] = Field(
        default_factory=lambda: [
            "camera", "lighting", "weather", "time_of_day",
            "foreground", "character", "prop",
        ],
        description="Properties a scene IS allowed to change"
    )


class EnvironmentAsset(BaseModel):
    """Canonical persistent environment identity.

    An environment is NOT a generated image. It is a production entity with:
    - Identity (semantic role, era, geography)
    - Visual style (palette, lighting, composition)
    - Continuity rules (what must stay consistent)
    - Asset references (the actual image files)
    - Version and quality metadata
    """
    # --- Identity ---
    asset_id: str = Field(min_length=1, max_length=64, pattern=r"^[a-z0-9_]+$")
    name: str = Field(min_length=1, max_length=64)
    semantic_role: str = Field(default="", max_length=200,
                                description="e.g. 'Ice Age plains where hunters gather'")

    # --- Context ---
    era: EnvironmentEra = EnvironmentEra.PREHISTORIC
    scale: EnvironmentScale = EnvironmentScale.LANDSCAPE
    world_context: str = Field(default="", max_length=200,
                                description="Geographic/historical context")
    historical_context: str = Field(default="", max_length=200)

    # --- Visual style ---
    style_profile: EnvironmentStyleProfile = Field(default_factory=EnvironmentStyleProfile)
    palette_profile: EnvironmentPaletteProfile = Field(default_factory=lambda: EnvironmentPaletteProfile(primary="#4A5568"))
    lighting_profile: EnvironmentLightingProfile = Field(default_factory=EnvironmentLightingProfile)
    composition_profile: EnvironmentCompositionProfile = Field(default_factory=EnvironmentCompositionProfile)
    continuity_profile: EnvironmentContinuityProfile = Field(default_factory=EnvironmentContinuityProfile)

    # --- Asset references ---
    primary_asset_uri: str = Field(default="", max_length=256)
    thumbnail_uri: str = Field(default="", max_length=256)
    variant_uris: dict[str, str] = Field(default_factory=dict,
                                          description="Named variants: {'dawn': '...', 'dusk': '...'}")

    # --- Reuse ---
    reuse_policy: ReusePolicy = ReusePolicy.REUSE_PREFERRED

    # --- Lifecycle ---
    lifecycle: AssetLifecycle = AssetLifecycle.DRAFT
    status: AssetStatus = AssetStatus.ACTIVE

    # --- Versioning ---
    version: str = Field(default="1.0.0", max_length=16)
    input_hash: str = Field(default="", max_length=64)
    style_version: str = Field(default="1.0.0", max_length=16)

    # --- Quality ---
    quality_score: AssetQualityScore | None = None

    # --- Approval ---
    approved_by: str = Field(default="", max_length=64)
    approved_at: datetime | None = None

    # --- Timestamps ---
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)

    def to_asset_reference(self) -> AssetReference:
        """Convert to a renderer-consumable AssetReference."""
        return AssetReference(
            asset_id=self.asset_id,
            asset_type=AssetType.ENVIRONMENT,
            version=self.version,
            uri=self.primary_asset_uri,
            name=self.name,
            description=self.semantic_role,
            mood=self.lighting_profile.primary.value if self.lighting_profile else "calm",
            reuse_policy=self.reuse_policy,
            continuity_locked=self.continuity_profile.identity_locked,
            quality_score=self.quality_score.overall_score if self.quality_score else None,
            lifecycle=self.lifecycle,
            renderer_hints={
                "lighting": self.lighting_profile.primary.value if self.lighting_profile else "natural",
                "weather": self.lighting_profile.weather.value if self.lighting_profile else "clear",
                "time_of_day": self.lighting_profile.time_of_day.value if self.lighting_profile else "midday",
                "palette": self.palette_profile.primary if self.palette_profile else None,
            },
        )


class EnvironmentInstance(BaseModel):
    """A scene-specific environment configuration.

    Unlike EnvironmentAsset (persistent identity), an instance captures the
    specific camera, lighting, weather, and time-of-day for ONE scene.
    """
    asset_id: str = Field(min_length=1, max_length=64)
    scene_id: str = Field(min_length=1, max_length=64)

    # Override lighting for this scene
    lighting_override: LightingType | None = None
    time_override: TimeOfDay | None = None
    weather_override: WeatherType | None = None
    season_override: str = Field(default="", max_length=32)

    # Camera overrides
    camera_pan_x: float = Field(default=0.5, ge=0.0, le=1.0)
    camera_pan_y: float = Field(default=0.5, ge=0.0, le=1.0)
    camera_zoom: float = Field(default=1.0, ge=0.5, le=3.0)

    # Continuity overrides (explicitly allowed changes)
    continuity_overrides: dict[str, Any] = Field(default_factory=dict)

    def to_asset_reference(self, base: EnvironmentAsset) -> AssetReference:
        """Convert to AssetReference with instance-specific overrides."""
        ref = base.to_asset_reference()
        # Apply overrides
        if self.lighting_override:
            ref.renderer_hints["lighting"] = self.lighting_override.value
        if self.time_override:
            ref.renderer_hints["time_of_day"] = self.time_override.value
        if self.weather_override:
            ref.renderer_hints["weather"] = self.weather_override.value
        if self.season_override:
            ref.renderer_hints["season"] = self.season_override
        ref.renderer_hints["camera_pan_x"] = self.camera_pan_x
        ref.renderer_hints["camera_pan_y"] = self.camera_pan_y
        ref.renderer_hints["camera_zoom"] = self.camera_zoom
        return ref


# ============================================================================
# PropAsset — canonical persistent prop identity
# ============================================================================

class PropAnchorPoint(BaseModel):
    """An anchor point on a prop for interaction."""
    anchor_id: str = Field(min_length=1, max_length=32)
    name: str = Field(min_length=1, max_length=64)
    x: float = Field(ge=-100.0, le=100.0,
                      description="Local X offset from prop origin")
    y: float = Field(ge=-100.0, le=100.0,
                      description="Local Y offset from prop origin")
    interaction_type: str = Field(default="grip", max_length=32)
    parent_anchor: str | None = Field(default=None, max_length=32,
                                      description="Optional parent anchor for hierarchy")


class PropStyleProfile(BaseModel):
    """Style configuration for a prop."""
    illustration_style: str = Field(default="painterly_2d", max_length=32)
    line_weight: float = Field(default=2.0, ge=0.0, le=8.0)
    shading_level: str = Field(default="minimal", max_length=16)


class PropPaletteProfile(BaseModel):
    """Color palette for a prop."""
    primary: str = Field(pattern=r"^#[0-9A-Fa-f]{6}$")
    secondary: str | None = Field(default=None, pattern=r"^#[0-9A-Fa-f]{6}$")
    outline: str = Field(default="#222222", pattern=r"^#[0-9A-Fa-f]{6}$")


class PropAsset(BaseModel):
    """Canonical persistent prop identity.

    A prop is NOT a generated image. It is a reusable production entity with:
    - Identity (semantic role, category, material)
    - Anchor points for character interaction
    - Visual style
    - Version and quality metadata

    Compatible with the 12 existing PropKind values in renderer/src/components/Props.tsx:
      human_silhouette, cave, fire, tree_pine, snowflake, arrow, timeline,
      chart_axes, animal_mammoth, sun, mountain, question_mark

    Additional prop kinds can be registered beyond these 12.
    """
    # --- Identity ---
    asset_id: str = Field(min_length=1, max_length=64, pattern=r"^[a-z0-9_]+$")
    name: str = Field(min_length=1, max_length=64)
    category: PropCategory = PropCategory.ABSTRACT
    semantic_role: str = Field(default="", max_length=200)

    # --- Physical properties ---
    material: str = Field(default="", max_length=64)
    primary_color: str = Field(default="#FFFFFF", pattern=r"^#[0-9A-Fa-f]{6}$")
    secondary_color: str | None = Field(default=None, pattern=r"^#[0-9A-Fa-f]{6}$")
    scale_hint: str = Field(default="medium", max_length=16)  # tiny / small / medium / large / huge

    # --- Visual style ---
    style_profile: PropStyleProfile = Field(default_factory=PropStyleProfile)
    palette_profile: PropPaletteProfile = Field(
        default_factory=lambda: PropPaletteProfile(primary="#FFFFFF")
    )

    # --- Interaction anchors ---
    anchor_points: list[PropAnchorPoint] = Field(default_factory=list)

    # --- Historical context ---
    historical_context: str = Field(default="", max_length=200)
    era_hint: str = Field(default="", max_length=64)

    # --- Asset references ---
    primary_asset_uri: str = Field(default="", max_length=256)
    thumbnail_uri: str = Field(default="", max_length=256)

    # --- Reuse ---
    reuse_policy: ReusePolicy = ReusePolicy.REUSE_ALLOWED

    # --- Lifecycle ---
    lifecycle: AssetLifecycle = AssetLifecycle.DRAFT
    status: AssetStatus = AssetStatus.ACTIVE

    # --- Versioning ---
    version: str = Field(default="1.0.0", max_length=16)
    input_hash: str = Field(default="", max_length=64)
    style_version: str = Field(default="1.0.0", max_length=16)

    # --- Quality ---
    quality_score: AssetQualityScore | None = None

    # --- Approval ---
    approved_by: str = Field(default="", max_length=64)
    approved_at: datetime | None = None

    # --- Timestamps ---
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)

    def to_asset_reference(self) -> AssetReference:
        """Convert to a renderer-consumable AssetReference."""
        return AssetReference(
            asset_id=self.asset_id,
            asset_type=AssetType.PROP,
            version=self.version,
            uri=self.primary_asset_uri,
            name=self.name,
            description=self.semantic_role,
            reuse_policy=self.reuse_policy,
            quality_score=self.quality_score.overall_score if self.quality_score else None,
            lifecycle=self.lifecycle,
            renderer_hints={
                "category": self.category.value,
                "primary_color": self.primary_color,
                "scale_hint": self.scale_hint,
                "anchors": [
                    {"id": a.anchor_id, "name": a.name, "x": a.x, "y": a.y}
                    for a in self.anchor_points
                ],
            },
        )


class PropInstance(BaseModel):
    """A scene-specific prop placement.

    Describes how a PropAsset appears in a specific scene:
    position, scale, rotation, which anchor is used for interaction.
    """
    asset_id: str = Field(min_length=1, max_length=64)
    scene_id: str = Field(min_length=1, max_length=64)

    # Spatial (normalized 0..1)
    x: float = Field(default=0.5, ge=0.0, le=1.0)
    y: float = Field(default=0.5, ge=0.0, le=1.0)
    scale: float = Field(default=1.0, ge=0.1, le=4.0)
    rotation_deg: float = Field(default=0.0, ge=-360.0, le=360.0)

    # Interaction
    interaction_anchor: str | None = Field(default=None, max_length=32,
                                           description="Which anchor point is used for character interaction")
    held_by: str | None = Field(default=None, max_length=64,
                                 description="character_id that holds this prop")

    # Animation hint
    animation_hint: str = Field(default="", max_length=64,
                                description="e.g. 'burning', 'falling', 'static'")


# ============================================================================
# Asset Registry Entry — canonical management
# ============================================================================

class AssetRegistryEntry(BaseModel):
    """A single entry in the global/project asset registry."""
    asset_id: str = Field(min_length=1, max_length=64)
    asset_type: AssetType
    name: str = Field(min_length=1, max_length=64)
    semantic_role: str = Field(default="", max_length=200)
    scope: str = Field(default="project", max_length=16)  # project | global

    # Lifecycle
    status: AssetStatus = AssetStatus.ACTIVE
    lifecycle: AssetLifecycle = AssetLifecycle.DRAFT
    version: str = Field(default="1.0.0", max_length=16)

    # Asset paths
    package_dir: str = Field(default="", max_length=256)
    primary_asset_uri: str = Field(default="", max_length=256)

    # Quality
    quality_score: float | None = Field(default=None, ge=0.0, le=1.0)
    warnings: list[str] = Field(default_factory=list)

    # Usage tracking
    projects_using: list[str] = Field(default_factory=list)
    scene_count: int = Field(default=0, ge=0)

    # Timestamps
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
    approved_at: datetime | None = None

    @model_validator(mode="before")
    @classmethod
    def _coerce_enums(cls, data: Any) -> Any:
        """Coerce string values to enum instances after JSON deserialization."""
        if isinstance(data, dict):
            result = dict(data)
            for field_name in ("status", "lifecycle", "asset_type"):
                if field_name in result and isinstance(result[field_name], str):
                    try:
                        if field_name == "status":
                            result[field_name] = AssetStatus(result[field_name])
                        elif field_name == "lifecycle":
                            result[field_name] = AssetLifecycle(result[field_name])
                        elif field_name == "asset_type":
                            result[field_name] = AssetType(result[field_name])
                    except (ValueError, TypeError):
                        pass
            return result
        return data


class AssetRegistry(BaseModel):
    """The canonical asset registry.

    Answers: Which assets exist? Which version? Where are they?
    Which projects use them?
    """
    project_id: str = Field(default="", max_length=64)
    assets: list[AssetRegistryEntry] = Field(default_factory=list)
    global_assets: list[str] = Field(default_factory=list,
                                      description="asset_ids that are globally reusable")
    updated_at: datetime = Field(default_factory=datetime.utcnow)

    def get_asset(self, asset_id: str) -> AssetRegistryEntry | None:
        return next(
            (a for a in self.assets if a.asset_id == asset_id),
            None
        )

    def find_by_type(self, asset_type: AssetType) -> list[AssetRegistryEntry]:
        return [a for a in self.assets if a.asset_type == asset_type]

    def find_by_role(self, semantic_role: str) -> list[AssetRegistryEntry]:
        return [a for a in self.assets if semantic_role.lower() in a.semantic_role.lower()]


# ============================================================================
# Asset Resolver Result — resolution log entry
# ============================================================================

class AssetResolution(BaseModel):
    """Resolution of one asset requirement to a canonical asset."""
    requirement_key: str = Field(min_length=1, max_length=128)
    asset_id: str = Field(min_length=1, max_length=64)
    asset_type: AssetType
    source: str = Field(default="new", max_length=16)  # "new" | "reuse" | "resolve"

    # The resolved asset (may be None if not yet generated)
    environment_asset: EnvironmentAsset | None = None
    prop_asset: PropAsset | None = None

    # Reference for renderer
    asset_reference: AssetReference | None = None

    # Resolution metadata
    resolution_strategy: str = Field(default="", max_length=64)
    matched_similarity: float | None = Field(default=None, ge=0.0, le=1.0)
    quality_score: AssetQualityScore | None = None
    warnings: list[str] = Field(default_factory=list)
    errors: list[str] = Field(default_factory=list)

    @property
    def is_successful(self) -> bool:
        return bool(self.asset_id) and self.asset_reference is not None


# ============================================================================
# Asset System Package — top-level pipeline output
# ============================================================================

class AssetSystemPackage(BaseModel):
    """The complete output of the Asset System for one project/job.

    This package is produced by the AssetResolver and consumed by s8_scene_json
    and the renderer. It provides deterministic, versioned asset references
    that the renderer can safely use.
    """
    job_id: str = Field(default="", max_length=64)
    project_id: str = Field(default="", max_length=64)
    version: str = "1.0.0"
    schema_version: str = "1.0.0"

    # All resolved environments
    environments: list[EnvironmentAsset] = Field(default_factory=list)
    environment_instances: list[EnvironmentInstance] = Field(default_factory=list)

    # All resolved props
    props: list[PropAsset] = Field(default_factory=list)
    prop_instances: list[PropInstance] = Field(default_factory=list)

    # All asset references (renderer-consumable)
    asset_references: list[AssetReference] = Field(default_factory=list)

    # Resolution log
    resolutions: list[AssetResolution] = Field(default_factory=list)

    # Registry state
    registry: AssetRegistry | None = None

    # Package metadata
    asset_packages: list[AssetPackage] = Field(default_factory=list)

    # Quality
    overall_quality_score: float = Field(ge=0.0, le=1.0, default=0.0)
    quality_scores: dict[str, AssetQualityScore] = Field(default_factory=dict)
    warnings: list[str] = Field(default_factory=list)
    failures: list[str] = Field(default_factory=list)

    # Timestamps
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
    lifecycle: AssetLifecycle = AssetLifecycle.DRAFT

    @model_validator(mode="after")
    def _compute_quality(self) -> "AssetSystemPackage":
        if self.quality_scores:
            scores = [s.overall_score for s in self.quality_scores.values()]
            object.__setattr__(
                self, "overall_quality_score",
                round(sum(scores) / len(scores), 3)
            )
        return self

    def get_environment(self, asset_id: str) -> EnvironmentAsset | None:
        return next(
            (e for e in self.environments if e.asset_id == asset_id),
            None
        )

    def get_prop(self, asset_id: str) -> PropAsset | None:
        return next(
            (p for p in self.props if p.asset_id == asset_id),
            None
        )

    def get_reference(self, asset_id: str) -> AssetReference | None:
        return next(
            (r for r in self.asset_references if r.asset_id == asset_id),
            None
        )

    def to_dict(self) -> dict[str, Any]:
        return self.model_dump(mode="json")
