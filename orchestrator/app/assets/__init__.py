"""
Asset Intelligence System subpackage.

Public surface:
    Engine: AssetSystemEngine
    Resolver: AssetResolver
    Cache: AssetCache
    Schemas: all asset schemas from app.schemas.asset
"""
from app.assets.cache import AssetCache, get_asset_cache
from app.assets.engine import AssetSystemEngine, AssetResolver
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
    EnvironmentCompositionProfile,
    EnvironmentContinuityProfile,
    EnvironmentInstance,
    EnvironmentLightingProfile,
    EnvironmentPaletteProfile,
    EnvironmentStyleProfile,
    LightingType,
    PropAnchorPoint,
    PropAsset,
    PropCategory,
    PropInstance,
    PropPaletteProfile,
    PropStyleProfile,
    ReusePolicy,
    TimeOfDay,
    WeatherType,
)

__all__ = [
    "AssetCache",
    "AssetResolver",
    "AssetSystemEngine",
    "AssetLifecycle",
    "AssetPackage",
    "AssetQualityScore",
    "AssetReference",
    "AssetRegistry",
    "AssetRegistryEntry",
    "AssetResolution",
    "AssetSystemPackage",
    "AssetType",
    "EnvironmentAsset",
    "EnvironmentCompositionProfile",
    "EnvironmentContinuityProfile",
    "EnvironmentInstance",
    "EnvironmentLightingProfile",
    "EnvironmentPaletteProfile",
    "EnvironmentStyleProfile",
    "LightingType",
    "PropAnchorPoint",
    "PropAsset",
    "PropCategory",
    "PropInstance",
    "PropPaletteProfile",
    "PropStyleProfile",
    "ReusePolicy",
    "TimeOfDay",
    "WeatherType",
    "get_asset_cache",
]
