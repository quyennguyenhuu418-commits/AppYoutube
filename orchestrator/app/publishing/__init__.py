"""
P15 + P16 — Publishing Package.
"""

from app.publishing.schemas import (
    Platform,
    PublishStatus,
    ContentType,
    Visibility,
    YouTubeMetadata,
    TikTokMetadata,
    FacebookMetadata,
    PublishingMetadata,
    PlatformPublishSpec,
    PublishingPlan,
    PlatformPublishResult,
    PublishingResult,
    PublishingQAReport,
)
from app.publishing.metadata_generator import (
    YouTubeMetadataGenerator,
    TikTokMetadataGenerator,
    FacebookMetadataGenerator,
    PublishingMetadataCompiler,
    PublishingPlanBuilder,
)
# P16 — real platform clients
from app.publishing.platform_client import (
    PlatformClient,
    PlatformCredentials,
    YouTubeClient,
    TikTokClient,
    FacebookClient,
    get_platform_client,
)

__all__ = [
    # Schemas
    "Platform", "PublishStatus", "ContentType", "Visibility",
    "YouTubeMetadata", "TikTokMetadata", "FacebookMetadata",
    "PublishingMetadata", "PlatformPublishSpec",
    "PublishingPlan", "PlatformPublishResult", "PublishingResult",
    "PublishingQAReport",
    # Generators
    "YouTubeMetadataGenerator", "TikTokMetadataGenerator",
    "FacebookMetadataGenerator", "PublishingMetadataCompiler",
    "PublishingPlanBuilder",
    # Real platform clients (P16)
    "PlatformClient", "PlatformCredentials",
    "YouTubeClient", "TikTokClient", "FacebookClient",
    "get_platform_client",
]
