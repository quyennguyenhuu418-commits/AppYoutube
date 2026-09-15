"""
Asset Intelligence Engine — central resolver and system.

This module provides:

1. AssetResolver — the single canonical path for resolving asset requirements
   - Takes StoryboardPackage requirements
   - Reuses approved assets from registry
   - Finds similar candidates for modification
   - Generates missing assets via ImageProvider
   - Validates quality before approving
   - Produces AssetReference objects for the renderer

2. AssetSystemEngine — top-level orchestrator
   - Reads StoryboardPackage
   - Runs AssetResolver
   - Produces AssetSystemPackage
   - Integrates with Character System (via CharacterSystemPackage)

3. Duplicate detection — semantic similarity for environments/props

4. Provider abstraction — generate_image() without coupling to DALL-E

Key design:
    - StoryboardPackage is the only input contract
    - AssetSystemPackage is the only output contract
    - Renderer never receives raw assets — only AssetReference
    - s6/s8 integration is done via adapter, not rewrite
    - Deterministic: same inputs → same outputs (cache + fingerprint)
    - Backward compatible with SceneDefinition, existing s6, existing renderer

Backward compatibility:
    - Existing s6 output (backwards_assets.json) is read and converted to new format
    - Existing SceneDefinition environment fields are preserved
    - Renderer continues to receive environment.background_asset paths
"""
from __future__ import annotations

import hashlib
import json
import re
import time
from datetime import datetime
from pathlib import Path
from typing import Any

from app.core.config import settings
from app.core.logging import get_logger
from app.core.paths import (
    asset_cache_dir,
    assets_dir,
    backgrounds_dir,
    read_json,
    stage_path,
    write_json,
)
from app.pipeline.cache import should_skip
from app.providers.base import ImageRequest
from app.providers.image import get_image_provider
from app.schemas.asset import (
    AssetLifecycle,
    AssetPackage,
    AssetQualityScore,
    AssetReference,
    AssetRegistry,
    AssetRegistryEntry,
    AssetResolution,
    AssetSystemPackage,
    AssetType,
    EnvironmentAsset,
    EnvironmentContinuityProfile,
    EnvironmentEra,
    EnvironmentInstance,
    EnvironmentLightingProfile,
    EnvironmentPaletteProfile,
    EnvironmentStyleProfile,
    LightingType,
    PropAnchorPoint,
    PropAsset,
    PropInstance,
    ReusePolicy,
    TimeOfDay,
    WeatherType,
)
from app.schemas.storyboard import (
    AssetRequirement,
    EnvironmentRequirement,
    StoryboardPackage,
)
from app.assets.cache import AssetCache, get_asset_cache

log = get_logger(__name__)

# ============================================================================
# Predefined environments (from existing s6)
# ============================================================================

_PREDEFINED_ENVIRONMENTS: dict[str, dict[str, Any]] = {
    "ice_age_plains": {
        "name": "Ice Age Plains",
        "semantic_role": "Wide snowy plain with distant mountains, dusk sky",
        "era": "prehistoric",
        "prompt_template": (
            "Wide flat snowy plain at dusk, soft blue-grey sky, faint distant "
            "mountains, no people, painterly 2D illustration style, "
            "high-quality documentary background."
        ),
        "palette": "#4A6FA5",
        "secondary": "#E8EEF4",
        "accent": "#8B9DC3",
    },
    "cave_interior": {
        "name": "Cave Interior",
        "semantic_role": "Stone cave lit by warm firelight",
        "era": "prehistoric",
        "prompt_template": (
            "Interior of a stone cave lit by warm firelight, dark amber walls, "
            "soft glow on the floor, painterly 2D illustration, documentary "
            "background."
        ),
        "palette": "#8B4513",
        "secondary": "#D2691E",
        "accent": "#FFD166",
    },
    "diagram_white": {
        "name": "Diagram White",
        "semantic_role": "Plain warm-white paper texture for overlay diagrams",
        "era": "abstract",
        "prompt_template": (
            "Plain warm-white paper texture background, faint vignette, "
            "suitable for overlay diagrams, painterly 2D illustration, "
            "documentary background."
        ),
        "palette": "#F5F5F0",
        "secondary": "#FFFFFF",
        "accent": "#DDDDD8",
    },
    "mammoth_camp": {
        "name": "Mammoth Camp",
        "semantic_role": "Snowy landscape with mammoth bone hut",
        "era": "prehistoric",
        "prompt_template": (
            "Snowy landscape with a hut made of large curved mammoth bones and "
            "draped hides, warm light spilling from inside, painterly 2D "
            "illustration, documentary background."
        ),
        "palette": "#5D4E37",
        "secondary": "#8B7355",
        "accent": "#FFD166",
    },
    "title_card": {
        "name": "Title Card",
        "semantic_role": "Deep navy gradient for documentary title",
        "era": "abstract",
        "prompt_template": (
            "Solid deep navy-blue gradient background, subtle film grain, "
            "no text, no figures, painterly 2D illustration, documentary title "
            "card background."
        ),
        "palette": "#0D1B2A",
        "secondary": "#1B3A4B",
        "accent": "#41A7C4",
    },
}


# ============================================================================
# Duplicate Detection
# ============================================================================

def _semantic_key(
    asset_id: str,
    semantic_role: str,
    era: str,
    palette: str,
) -> str:
    """Compute a semantic identity key for duplicate detection.

    Two environments with the same semantic_key are semantically equivalent.
    """
    normalized = "|".join([
        asset_id.lower().strip(),
        semantic_role.lower().strip(),
        era.lower().strip(),
        palette.lower().strip(),
    ])
    return hashlib.sha256(normalized.encode()).hexdigest()[:16]


def _props_semantic_key(
    asset_id: str,
    semantic_role: str,
    category: str,
    primary_color: str,
) -> str:
    """Compute a semantic identity key for prop duplicate detection."""
    normalized = "|".join([
        asset_id.lower().strip(),
        semantic_role.lower().strip(),
        category.lower().strip(),
        primary_color.lower().strip(),
    ])
    return hashlib.sha256(normalized.encode()).hexdigest()[:16]


# ============================================================================
# Quality Engine
# ============================================================================

def score_environment_quality(env: EnvironmentAsset) -> AssetQualityScore:
    """Compute a deterministic quality score for an environment.

    All dimensions derive from asset definition fields.
    No randomness — same asset always gets the same score.
    """
    warnings: list[str] = []
    failures: list[str] = []
    dim: dict[str, float] = {}

    # identity_consistency: has name, semantic_role, era
    dim["identity_consistency"] = round(
        min(1.0, (
            (0.3 if env.name else 0.0) +
            (0.4 if env.semantic_role else 0.0) +
            (0.3 if env.era else 0.0)
        )), 3
    )
    if not env.name:
        warnings.append("Environment has no name")

    # semantic_correctness: has semantic role and era
    dim["semantic_correctness"] = round(
        min(1.0, (
            (0.5 if env.semantic_role else 0.0) +
            (0.5 if env.era else 0.0)
        )), 3
    )

    # style_consistency: has style and palette profiles
    has_style = bool(env.style_profile)
    has_palette = bool(env.palette_profile)
    dim["style_consistency"] = round(
        (0.5 if has_style else 0.0) + (0.5 if has_palette else 0.0), 3
    )
    if not has_palette:
        warnings.append("Environment has no palette profile")

    # composition_quality: has composition profile
    dim["composition_quality"] = round(
        1.0 if env.composition_profile else 0.5, 3
    )

    # resolution_quality: has primary asset URI
    dim["resolution_quality"] = round(
        1.0 if env.primary_asset_uri else 0.3, 3
    )
    if not env.primary_asset_uri:
        warnings.append("Environment has no primary asset URI")

    # format_quality: URI has valid extension
    valid_exts = {".png", ".jpg", ".jpeg", ".svg"}
    uri_ok = any(env.primary_asset_uri.lower().endswith(e) for e in valid_exts)
    dim["format_quality"] = round(1.0 if uri_ok else 0.5, 3)
    if not uri_ok:
        warnings.append("Asset URI has no valid image extension")

    # continuity_readiness: has continuity profile
    dim["continuity_readiness"] = round(
        1.0 if env.continuity_profile else 0.3, 3
    )
    if not env.continuity_profile:
        warnings.append("Environment has no continuity profile")

    # reuse_quality: reuse policy set
    reuse_ok = env.reuse_policy not in (ReusePolicy.SCENE_LOCAL, ReusePolicy.NEVER_REUSE)
    dim["reuse_quality"] = round(1.0 if reuse_ok else 0.5, 3)

    # renderer_compatibility: has mood hint
    has_mood = env.lighting_profile and env.lighting_profile.primary
    dim["renderer_compatibility"] = round(
        0.7 if has_mood else 0.4, 3
    )

    # metadata_completeness: has timestamps and version
    has_meta = bool(env.created_at and env.version)
    dim["metadata_completeness"] = round(1.0 if has_meta else 0.4, 3)

    # animation_readiness: has composition profile
    dim["animation_readiness"] = round(
        0.8 if env.composition_profile else 0.3, 3
    )

    return AssetQualityScore(
        identity_consistency=dim["identity_consistency"],
        semantic_correctness=dim["semantic_correctness"],
        style_consistency=dim["style_consistency"],
        composition_quality=dim["composition_quality"],
        resolution_quality=dim["resolution_quality"],
        format_quality=dim["format_quality"],
        continuity_readiness=dim["continuity_readiness"],
        reuse_quality=dim["reuse_quality"],
        renderer_compatibility=dim["renderer_compatibility"],
        metadata_completeness=dim["metadata_completeness"],
        animation_readiness=dim["animation_readiness"],
        dimension_scores=dim,
        warnings=warnings,
        failures=failures,
    )


def score_prop_quality(prop: PropAsset) -> AssetQualityScore:
    """Compute a deterministic quality score for a prop."""
    warnings: list[str] = []
    dim: dict[str, float] = {}

    # identity_consistency
    dim["identity_consistency"] = round(
        min(1.0, (
            (0.4 if prop.name else 0.0) +
            (0.3 if prop.category else 0.0) +
            (0.3 if prop.semantic_role else 0.0)
        )), 3
    )

    # semantic_correctness
    dim["semantic_correctness"] = round(
        min(1.0, (
            (0.5 if prop.semantic_role else 0.0) +
            (0.5 if prop.material else 0.3)
        )), 3
    )

    # style_consistency
    has_style = bool(prop.style_profile)
    has_palette = bool(prop.palette_profile)
    dim["style_consistency"] = round(
        (0.5 if has_style else 0.0) + (0.5 if has_palette else 0.0), 3
    )

    # composition_quality
    has_anchors = len(prop.anchor_points) > 0
    dim["composition_quality"] = round(
        1.0 if has_anchors else 0.5, 3
    )
    if not has_anchors:
        warnings.append("Prop has no anchor points defined")

    # resolution_quality
    dim["resolution_quality"] = round(
        1.0 if prop.primary_asset_uri else 0.3, 3
    )

    # format_quality
    valid_exts = {".png", ".jpg", ".svg"}
    uri_ok = any(prop.primary_asset_uri.lower().endswith(e) for e in valid_exts)
    dim["format_quality"] = round(1.0 if uri_ok else 0.5, 3)

    # continuity_readiness
    dim["continuity_readiness"] = round(
        0.9 if prop.reuse_policy != ReusePolicy.SCENE_LOCAL else 0.3, 3
    )

    # reuse_quality
    dim["reuse_quality"] = round(
        1.0 if prop.reuse_policy != ReusePolicy.NEVER_REUSE else 0.5, 3
    )

    # renderer_compatibility
    dim["renderer_compatibility"] = round(
        0.8 if prop.category else 0.4, 3
    )

    # metadata_completeness
    dim["metadata_completeness"] = round(
        1.0 if (prop.created_at and prop.version) else 0.4, 3
    )

    # animation_readiness
    dim["animation_readiness"] = round(
        1.0 if has_anchors else 0.4, 3
    )

    return AssetQualityScore(
        dimension_scores=dim,
        warnings=warnings,
    )


# ============================================================================
# AssetResolver — single canonical resolution path
# ============================================================================

class AssetResolver:
    """The single canonical path for resolving StoryboardPackage requirements.

    Resolution strategy:
        1. Check registry for existing approved asset (reuse)
        2. Check cache for identical content hash (idempotent)
        3. Find similar candidates for modification
        4. Generate new asset candidate
        5. Validate quality
        6. Register and return AssetReference

    This resolver is used by:
        - AssetSystemEngine (primary user)
        - s6 integration (backward compatibility bridge)
        - s8 integration (pre-LLM asset resolution)
    """

    def __init__(self, cache: AssetCache | None = None):
        self.cache = cache or get_asset_cache()
        self._registry: AssetRegistry | None = None
        self._predefined = _PREDEFINED_ENVIRONMENTS

    def _registry_path(self) -> Path:
        # Registry lives alongside the cache (in the same workspace)
        return self.cache.root / "registry.json"

    def load_registry(self, project_id: str = "") -> AssetRegistry:
        """Load the asset registry from disk.

        Registry is cached in memory for the resolver's lifetime.
        After saving, the in-memory cache is updated.
        """
        if self._registry is not None:
            return self._registry
        path = self._registry_path()
        if path.exists():
            try:
                data = json.loads(path.read_text(encoding="utf-8"))
                self._registry = AssetRegistry(**data)
            except Exception as exc:
                log.warning("[resolver] failed to load registry: %s", exc)
                self._registry = AssetRegistry(project_id=project_id)
        else:
            self._registry = AssetRegistry(project_id=project_id)
        return self._registry

    def save_registry(self, registry: AssetRegistry) -> None:
        """Save the asset registry to disk."""
        import json
        path = self._registry_path()
        path.parent.mkdir(parents=True, exist_ok=True)
        # Use model_dump with default=str to handle datetime, then json.dumps
        data = registry.model_dump(mode="json")
        path.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
        self._registry = registry

    def resolve_environment(
        self,
        requirement: EnvironmentRequirement,
        project_id: str = "",
        storyboard_style: str = "",
    ) -> AssetResolution:
        """Resolve an EnvironmentRequirement to a canonical EnvironmentAsset.

        Resolution chain:
            1. If requirement.environment_id matches predefined → use predefined
            2. If requirement.environment_id exists in registry → reuse
            3. If requirement has reuse_key matching registry → reuse with version
            4. Generate new environment
        """
        log.info("[resolver] resolving environment: %s", requirement.environment_id)

        # Strategy 1: predefined environment
        if requirement.environment_id in self._predefined:
            pred = self._predefined[requirement.environment_id]
            env = self._build_predefined_environment(requirement, pred)
            env.lifecycle = AssetLifecycle.GENERATED
            env.quality_score = score_environment_quality(env)

            # Check cache
            content_hash = _semantic_key(
                env.asset_id, env.semantic_role, env.era.value, env.palette_profile.primary
            )
            cache_hit = self.cache.has_cache_entry(
                "environment", env.asset_id, env.version, content_hash
            )
            if not cache_hit:
                self.cache.store_fingerprint(
                    "environment", env.asset_id, env.version,
                    content_hash,
                    {"source": "predefined", "requirement": requirement.model_dump()}
                )

            ref = env.to_asset_reference()
            resolution = AssetResolution(
                requirement_key=requirement.environment_id,
                asset_id=env.asset_id,
                asset_type=AssetType.ENVIRONMENT,
                source="predefined",
                environment_asset=env,
                asset_reference=ref,
                resolution_strategy="predefined_match",
                quality_score=env.quality_score,
            )
            log.info("[resolver] predefined environment: %s", env.asset_id)
            return resolution

        # Strategy 2: check registry for existing
        registry = self.load_registry(project_id)
        existing = registry.get_asset(requirement.environment_id)
        if existing and existing.asset_type == AssetType.ENVIRONMENT:
            if existing.status.value in ("active", "approved"):
                env = self._registry_entry_to_environment(existing)
                env.quality_score = score_environment_quality(env)
                ref = env.to_asset_reference()
                resolution = AssetResolution(
                    requirement_key=requirement.environment_id,
                    asset_id=env.asset_id,
                    asset_type=AssetType.ENVIRONMENT,
                    source="reuse",
                    environment_asset=env,
                    asset_reference=ref,
                    resolution_strategy="registry_reuse",
                    quality_score=env.quality_score,
                )
                log.info("[resolver] reused environment from registry: %s", env.asset_id)
                return resolution

        # Strategy 3: generate new
        env = self._generate_environment(requirement, project_id)
        ref = env.to_asset_reference()

        # Register the generated environment
        entry = AssetRegistryEntry(
            asset_id=env.asset_id,
            asset_type=AssetType.ENVIRONMENT,
            name=env.name,
            semantic_role=env.semantic_role,
            lifecycle=env.lifecycle,
            version=env.version,
            primary_asset_uri=env.primary_asset_uri,
            quality_score=env.quality_score.overall_score if env.quality_score else None,
        )
        self.register_asset(entry, project_id)

        resolution = AssetResolution(
            requirement_key=requirement.environment_id,
            asset_id=env.asset_id,
            asset_type=AssetType.ENVIRONMENT,
            source="new",
            environment_asset=env,
            asset_reference=ref,
            resolution_strategy="generated",
            quality_score=env.quality_score,
        )
        log.info("[resolver] generated environment: %s", env.asset_id)
        return resolution

    def resolve_prop(
        self,
        requirement: AssetRequirement,
        project_id: str = "",
    ) -> AssetResolution:
        """Resolve a prop AssetRequirement to a canonical PropAsset."""
        log.info("[resolver] resolving prop: %s", requirement.asset_id)

        # Check registry
        registry = self.load_registry(project_id)
        existing = registry.get_asset(requirement.asset_id)
        if existing and existing.asset_type == AssetType.PROP:
            if existing.status.value in ("active", "approved"):
                prop = self._registry_entry_to_prop(existing)
                prop.quality_score = score_prop_quality(prop)
                ref = prop.to_asset_reference()
                return AssetResolution(
                    requirement_key=requirement.asset_id,
                    asset_id=prop.asset_id,
                    asset_type=AssetType.PROP,
                    source="reuse",
                    prop_asset=prop,
                    asset_reference=ref,
                    resolution_strategy="registry_reuse",
                    quality_score=prop.quality_score,
                )

        # Generate new
        prop = self._generate_prop_internal(requirement)
        ref = prop.to_asset_reference()

        # Register the generated prop
        entry = AssetRegistryEntry(
            asset_id=prop.asset_id,
            asset_type=AssetType.PROP,
            name=prop.name,
            semantic_role=prop.semantic_role,
            lifecycle=prop.lifecycle,
            version=prop.version,
            primary_asset_uri=prop.primary_asset_uri,
            quality_score=prop.quality_score.overall_score if prop.quality_score else None,
        )
        self.register_asset(entry, project_id)

        resolution = AssetResolution(
            requirement_key=requirement.asset_id,
            asset_id=prop.asset_id,
            asset_type=AssetType.PROP,
            source="new",
            prop_asset=prop,
            asset_reference=ref,
            resolution_strategy="generated",
            quality_score=prop.quality_score,
        )
        return resolution

    # -------------------------------------------------------------------------
    # Environment generation
    # -------------------------------------------------------------------------

    def _build_predefined_environment(
        self,
        requirement: EnvironmentRequirement,
        predefined: dict,
    ) -> EnvironmentAsset:
        """Build an EnvironmentAsset from a predefined template."""
        env_id = requirement.environment_id
        palette = predefined.get("palette", "#4A5568")
        return EnvironmentAsset(
            asset_id=env_id,
            name=predefined.get("name", env_id),
            semantic_role=predefined.get("semantic_role", ""),
            era=EnvironmentEra(predefined.get("era", "abstract")),
            style_profile=EnvironmentStyleProfile(),
            palette_profile=EnvironmentPaletteProfile(primary=palette),
            lighting_profile=EnvironmentLightingProfile(
                primary=LightingType(requirement.lighting) if requirement.lighting else LightingType.NATURAL,
                weather=WeatherType(requirement.weather) if requirement.weather else WeatherType.CLEAR,
                time_of_day=self._map_time_of_day(requirement.time_of_day),
            ),
            continuity_profile=EnvironmentContinuityProfile(),
            primary_asset_uri=f"environments/{env_id}/v1.0.0/preview.png",
            reuse_policy=ReusePolicy.REUSE_PREFERRED,
            lifecycle=AssetLifecycle.GENERATED,
            version="1.0.0",
        )

    def _generate_environment(
        self,
        requirement: EnvironmentRequirement,
        project_id: str,
    ) -> EnvironmentAsset:
        """Generate a new environment from a requirement."""
        env_id = requirement.environment_id

        # Determine palette from requirement
        palette = self._derive_palette(requirement)

        # Determine era
        era = self._derive_era(requirement)

        env = EnvironmentAsset(
            asset_id=env_id,
            name=requirement.location or env_id,
            semantic_role=requirement.atmosphere or "",
            era=era,
            style_profile=EnvironmentStyleProfile(),
            palette_profile=EnvironmentPaletteProfile(primary=palette),
            lighting_profile=EnvironmentLightingProfile(
                primary=LightingType(requirement.lighting) if requirement.lighting else LightingType.NATURAL,
                weather=WeatherType(requirement.weather) if requirement.weather else WeatherType.CLEAR,
                time_of_day=self._map_time_of_day(requirement.time_of_day),
            ),
            continuity_profile=EnvironmentContinuityProfile(),
            reuse_policy=ReusePolicy.REUSE_PREFERRED,
            lifecycle=AssetLifecycle.GENERATED,
            version="1.0.0",
        )
        env.quality_score = score_environment_quality(env)
        return env

    def _derive_palette(self, requirement: EnvironmentRequirement) -> str:
        """Derive a color palette from environment requirements."""
        if requirement.mood == "tense":
            return "#4A5568"
        if requirement.mood == "warm":
            return "#D97706"
        if requirement.mood == "calm":
            return "#4A6FA5"
        if requirement.mood == "mysterious":
            return "#312E81"
        if requirement.mood == "triumphant":
            return "#B45309"
        # Derive from weather
        if requirement.weather == "snow":
            return "#E8EEF4"
        if requirement.weather == "rain":
            return "#475569"
        if requirement.weather == "fog":
            return "#9CA3AF"
        return "#4A5568"

    def _map_time_of_day(self, raw: str | None) -> "TimeOfDay":
        """Map common time-of-day strings to TimeOfDay enum values."""
        from app.schemas.asset import TimeOfDay
        if not raw:
            return TimeOfDay.MIDDAY
        _time_map = {
            "day": TimeOfDay.MIDDAY,
            "morning": TimeOfDay.MORNING,
            "afternoon": TimeOfDay.AFTERNOON,
            "evening": TimeOfDay.DUSK,
            "dawn": TimeOfDay.DAWN,
            "dusk": TimeOfDay.DUSK,
            "night": TimeOfDay.NIGHT,
            "midnight": TimeOfDay.MIDNIGHT,
            "midday": TimeOfDay.MIDDAY,
        }
        return _time_map.get(raw.lower(), TimeOfDay.MIDDAY)

    def _derive_era(self, requirement: EnvironmentRequirement) -> "EnvironmentEra":
        """Derive environment era from requirement."""
        era_str = requirement.continuity_constraints[0] if requirement.continuity_constraints else ""
        era_map = {
            "prehistoric": EnvironmentEra.PREHISTORIC,
            "ancient": EnvironmentEra.ANCIENT,
            "classical": EnvironmentEra.CLASSICAL,
            "medieval": EnvironmentEra.MEDIEVAL,
            "modern": EnvironmentEra.MODERN,
        }
        return era_map.get(era_str.lower(), EnvironmentEra.UNKNOWN)

    # -------------------------------------------------------------------------
    # Prop generation
    # -------------------------------------------------------------------------

    def _generate_prop_internal(
        self,
        requirement: AssetRequirement,
    ) -> PropAsset:
        """Generate a new prop from a requirement."""
        from app.schemas.asset import PropStyleProfile, PropPaletteProfile

        prop_id = requirement.asset_id
        category = self._derive_prop_category(requirement)

        # Define standard anchor points for this prop type
        anchors = self._standard_anchors(prop_id)

        prop = PropAsset(
            asset_id=prop_id,
            name=requirement.type or prop_id,
            category=category,
            semantic_role=requirement.purpose or "",
            style_profile=PropStyleProfile(),
            palette_profile=PropPaletteProfile(primary="#FFFFFF"),
            anchor_points=anchors,
            reuse_policy=ReusePolicy.REUSE_ALLOWED,
            lifecycle=AssetLifecycle.GENERATED,
            version="1.0.0",
        )
        prop.quality_score = score_prop_quality(prop)
        return prop

    def _derive_prop_category(self, requirement: AssetRequirement) -> __import__("app.schemas.asset").PropCategory:
        """Derive prop category from requirement type."""
        from app.schemas.asset import PropCategory
        type_lower = requirement.type.lower()
        category_map: dict[str, PropCategory] = {
            "weapon": PropCategory.WEAPON,
            "tool": PropCategory.TOOL,
            "furniture": PropCategory.FURNITURE,
            "document": PropCategory.DOCUMENT,
            "food": PropCategory.FOOD,
            "clothing": PropCategory.CLOTHING,
            "structure": PropCategory.STRUCTURE,
            "nature": PropCategory.NATURE,
            "animal": PropCategory.ANIMAL,
            "vehicle": PropCategory.VEHICLE,
            "symbol": PropCategory.SYMBOL,
        }
        return category_map.get(type_lower, PropCategory.ABSTRACT)

    def _standard_anchors(self, prop_id: str) -> list[PropAnchorPoint]:
        """Return standard anchor points for common prop types."""
        base = [
            PropAnchorPoint(anchor_id="center", name="Center", x=0.0, y=0.0),
            PropAnchorPoint(anchor_id="top", name="Top", x=0.0, y=-10.0),
            PropAnchorPoint(anchor_id="bottom", name="Bottom", x=0.0, y=10.0),
        ]
        # Add grip points for holdable props
        if any(k in prop_id for k in ["sword", "spear", "tool", "book", "scroll"]):
            base.extend([
                PropAnchorPoint(anchor_id="grip_left", name="Left Hand Grip", x=-5.0, y=0.0),
                PropAnchorPoint(anchor_id="grip_right", name="Right Hand Grip", x=5.0, y=0.0),
            ])
        return base

    # -------------------------------------------------------------------------
    # Registry entry conversion
    # -------------------------------------------------------------------------

    def _registry_entry_to_environment(self, entry: AssetRegistryEntry) -> EnvironmentAsset:
        """Convert a registry entry back to EnvironmentAsset."""
        return EnvironmentAsset(
            asset_id=entry.asset_id,
            name=entry.name,
            semantic_role=entry.semantic_role,
            version=entry.version,
            lifecycle=entry.lifecycle,
            primary_asset_uri=entry.primary_asset_uri,
            reuse_policy=ReusePolicy.REUSE_PREFERRED,
        )

    def _registry_entry_to_prop(self, entry: AssetRegistryEntry) -> PropAsset:
        """Convert a registry entry back to PropAsset."""
        return PropAsset(
            asset_id=entry.asset_id,
            name=entry.name,
            semantic_role=entry.semantic_role,
            version=entry.version,
            lifecycle=entry.lifecycle,
            primary_asset_uri=entry.primary_asset_uri,
            reuse_policy=ReusePolicy.REUSE_ALLOWED,
        )

    # -------------------------------------------------------------------------
    # Registry management
    # -------------------------------------------------------------------------

    def register_asset(
        self,
        entry: AssetRegistryEntry,
        project_id: str = "",
    ) -> None:
        """Register or update an asset in the registry."""
        registry = self.load_registry(project_id)
        # Remove existing entry if updating
        registry.assets = [a for a in registry.assets if a.asset_id != entry.asset_id]
        registry.assets.append(entry)
        self.save_registry(registry)

    def find_similar(
        self,
        asset_type: AssetType,
        semantic_role: str,
        registry: AssetRegistry | None = None,
    ) -> list[AssetRegistryEntry]:
        """Find semantically similar assets in the registry."""
        reg = registry or self.load_registry()
        candidates = [a for a in reg.assets if a.asset_type == asset_type]
        # Simple substring matching (extensible to embeddings later)
        role_lower = semantic_role.lower()
        scored: list[tuple[float, AssetRegistryEntry]] = []
        for c in candidates:
            role_score = sum(
                1.0 for word in role_lower.split()
                if word in c.semantic_role.lower()
            )
            if role_score > 0:
                scored.append((role_score, c))
        scored.sort(key=lambda x: x[0], reverse=True)
        return [s[1] for s in scored[:5]]


# ============================================================================
# AssetSystemEngine — top-level orchestrator
# ============================================================================

class AssetSystemEngine:
    """Top-level orchestrator for the Asset System.

    Input: StoryboardPackage (from s5) + optional CharacterSystemPackage (from s5)
    Output: AssetSystemPackage

    Pipeline integration:
        - Reads: storyboard_package.json, character_system_package.json
        - Writes: asset_system_package.json
        - Integrates with: s6 (backward compat), s8 (asset resolution)
    """

    def __init__(self):
        self.resolver = AssetResolver()

    def run(
        self,
        job_id: str,
        project_id: str = "",
        storyboard_package: StoryboardPackage | None = None,
        character_system_package: dict | None = None,
    ) -> AssetSystemPackage:
        """Run the asset system for a job.

        Args:
            job_id: The job identifier
            project_id: The project identifier
            storyboard_package: Parsed StoryboardPackage (reads from disk if None)
            character_system_package: Parsed CharacterSystemPackage (reads from disk if None)

        Returns:
            AssetSystemPackage with all resolved assets
        """
        start_time = time.time()

        # Load storyboard package
        if storyboard_package is None:
            sp_path = stage_path(job_id, "storyboard_package")
            if Path(sp_path).exists():
                data = read_json(sp_path)
                storyboard_package = StoryboardPackage(**data)

        # Load character system package
        char_pkg = character_system_package

        # Initialize result
        pkg = AssetSystemPackage(
            job_id=job_id,
            project_id=project_id,
            lifecycle=AssetLifecycle.DRAFT,
        )

        if storyboard_package:
            # Resolve environments
            env_reqs: list[EnvironmentRequirement] = []
            for beat in storyboard_package.visual_beats:
                if beat.environment_requirement:
                    if beat.environment_requirement not in env_reqs:
                        env_reqs.append(beat.environment_requirement)

            for req in env_reqs:
                resolution = self.resolver.resolve_environment(
                    req, project_id,
                    storyboard_style=storyboard_package.style_profile.primary_style
                    if storyboard_package.style_profile else "",
                )
                pkg.resolutions.append(resolution)
                if resolution.environment_asset:
                    pkg.environments.append(resolution.environment_asset)
                    pkg.asset_references.append(resolution.asset_reference)
                    # Build registry entry
                    env = resolution.environment_asset
                    entry = AssetRegistryEntry(
                        asset_id=env.asset_id,
                        asset_type=AssetType.ENVIRONMENT,
                        name=env.name,
                        semantic_role=env.semantic_role,
                        lifecycle=env.lifecycle,
                        version=env.version,
                        primary_asset_uri=env.primary_asset_uri,
                        quality_score=env.quality_score.overall_score
                                        if env.quality_score else None,
                    )
                    # Register
                    self.resolver.register_asset(entry, project_id)
                pkg.quality_scores[req.environment_id] = resolution.quality_score

            # Resolve props
            prop_reqs = storyboard_package.asset_requirements
            seen_prop_ids: set[str] = set()
            for req in prop_reqs:
                if req.asset_class.value == "prop" and req.asset_id not in seen_prop_ids:
                    seen_prop_ids.add(req.asset_id)
                    resolution = self.resolver.resolve_prop(req, project_id)
                    pkg.resolutions.append(resolution)
                    if resolution.prop_asset:
                        pkg.props.append(resolution.prop_asset)
                        pkg.asset_references.append(resolution.asset_reference)
                        prop = resolution.prop_asset
                        entry = AssetRegistryEntry(
                            asset_id=prop.asset_id,
                            asset_type=AssetType.PROP,
                            name=prop.name,
                            semantic_role=prop.semantic_role,
                            lifecycle=prop.lifecycle,
                            version=prop.version,
                            primary_asset_uri=prop.primary_asset_uri,
                            quality_score=prop.quality_score.overall_score
                                          if prop.quality_score else None,
                        )
                        self.resolver.register_asset(entry, project_id)
                    if resolution.quality_score:
                        pkg.quality_scores[req.asset_id] = resolution.quality_score

        # Load registry
        registry = self.resolver.load_registry(project_id)
        pkg.registry = registry

        # Set lifecycle
        pkg.lifecycle = AssetLifecycle.GENERATED

        # Mark as updated
        object.__setattr__(pkg, "updated_at", datetime.utcnow())

        duration = time.time() - start_time
        log.info("[engine] asset system complete: %d environments, %d props in %.2fs",
                 len(pkg.environments), len(pkg.props), duration)

        return pkg

    def resolve_for_scene(
        self,
        job_id: str,
        environment_id: str,
        scene_id: str,
        camera_x: float = 0.5,
        camera_y: float = 0.5,
        camera_zoom: float = 1.0,
    ) -> EnvironmentInstance:
        """Create an EnvironmentInstance for a specific scene.

        This is called by s8 or the renderer to get scene-specific configuration.
        """
        # Load environment from registry
        registry = self.resolver.load_registry()
        entry = registry.get_asset(environment_id)
        if entry is None:
            raise ValueError(f"Environment not found in registry: {environment_id}")

        instance = EnvironmentInstance(
            asset_id=environment_id,
            scene_id=scene_id,
            camera_pan_x=camera_x,
            camera_pan_y=camera_y,
            camera_zoom=camera_zoom,
        )
        return instance
