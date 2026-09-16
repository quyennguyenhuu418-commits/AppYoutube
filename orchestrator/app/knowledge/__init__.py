"""
Knowledge Layer — L-U1 / L-U2 / L-U3.

Public API
----------
L-U1 — Foundation
    KnowledgeSource      (schemas.py)
    KnowledgeEntry       (schemas.py)
    KnowledgeDomain      (schemas.py)
    KnowledgeStatus      (schemas.py)
    SourceType           (schemas.py)
    ExtractionStatus     (schemas.py)
    KnowledgeRegistry    (registry.py)
    VisualGrammar        (visual_grammar.py)
    CharacterGrammar     (character_grammar.py)
    default_seeds        (seeds.py)
    default_sources      (seeds.py)
    build_default_registry (builder.py)

L-U2 — Storyboard integration
    KnowledgeStoryboardAdapter  (storyboard_adapter.py)

L-U3 — Canonical Consumption Architecture
    KnowledgeQuery        (query.py)     — immutable query contract
    KnowledgeResult       (result.py)    — immutable view + provenance
    KnowledgeProvenance   (result.py)
    KnowledgeResolver     (resolver.py)  — composable, domain-agnostic
    KnowledgeContext      (context.py)   — lifecycle + fallback policy
    FallbackPolicy        (context.py)
    KnowledgeError        (errors.py)    — base error class
    KnowledgeInvalidQuery (errors.py)
    KnowledgeVersionMismatch (errors.py)
    KnowledgeConflict     (errors.py)
    KnowledgeUnavailable  (errors.py)

Architectural rule
------------------
The Knowledge Layer is **additive** and **read-only** for consumers:

    1. The Knowledge Layer does not import any production engine.
    2. Consumers receive a `KnowledgeContext` (not a registry directly).
    3. The resolver is the single canonical read path.
    4. Domain-specific adapters (e.g. KnowledgeStoryboardAdapter) are
       thin wrappers that translate `KnowledgeResult` into
       subsystem-specific values.

Forward direction
-----------------
Production subsystem
        ↓
KnowledgeContext
        ↓
KnowledgeResolver
        ↓
KnowledgeRegistry

NEVER:
KnowledgeLayer
        ↓
Production subsystem
"""

from .builder import build_default_registry, reset_and_build
from .character_grammar import (
    CharacterGrammar,
    ColorPaletteBlock,
    ConsistencyRuleKind,
    ConsistencyRulesBlock,
    FaceBlock,
    HeadBlock,
    IdentityBlock,
    OrientationBlock,
    OutlineBlock,
    OutlineWeight,
    ProportionsBlock,
    ReferenceSheetBlock,
    SignaturePropsBlock,
    WardrobeBlock,
)
from .context import FallbackPolicy, KnowledgeContext
from .errors import (
    KnowledgeConflict,
    KnowledgeError,
    KnowledgeInvalidQuery,
    KnowledgeUnavailable,
    KnowledgeVersionMismatch,
)
from .query import KnowledgeQuery
from .registry import KnowledgeRegistry
from .resolver import KnowledgeResolver
from .result import (
    KnowledgeNotFound,
    KnowledgeProvenance,
    KnowledgeResult,
    sort_results,
)
from .schemas import (
    ExtractionStatus,
    KnowledgeDomain,
    KnowledgeEntry,
    KnowledgeSource,
    KnowledgeStatus,
    SourceType,
)
from .seeds import (
    SOURCE_AXEN_REF,
    SOURCE_DINO_AI,
    SOURCE_GOOGLE_FLOW,
    axen_learner_seeds,
    default_seeds,
    default_sources,
    dino_ai_seeds,
    google_flow_seeds,
)
from .storyboard_adapter import KnowledgeStoryboardAdapter
from .visual_grammar import (
    ActionIntent,
    BackgroundIntent,
    CameraIntent,
    CameraMovementType,
    CameraShotType,
    CompositionIntent,
    ConstraintsIntent,
    EffectsIntent,
    EnvironmentIntent,
    FormatIntent,
    MotionIntent,
    MotionPattern,
    StyleIntent,
    SubjectIntent,
    TypographyIntent,
    VisualGrammar,
    VisualStyleProfile,
)


__all__ = [
    # Schemas (L-U1)
    "KnowledgeSource",
    "KnowledgeEntry",
    "KnowledgeDomain",
    "KnowledgeStatus",
    "SourceType",
    "ExtractionStatus",
    # Registry (L-U1)
    "KnowledgeRegistry",
    # Visual grammar (L-U1)
    "VisualGrammar",
    "StyleIntent",
    "SubjectIntent",
    "EnvironmentIntent",
    "CompositionIntent",
    "ActionIntent",
    "EffectsIntent",
    "CameraIntent",
    "CameraShotType",
    "CameraMovementType",
    "MotionIntent",
    "MotionPattern",
    "BackgroundIntent",
    "TypographyIntent",
    "ConstraintsIntent",
    "FormatIntent",
    "VisualStyleProfile",
    # Character grammar (L-U1)
    "CharacterGrammar",
    "IdentityBlock",
    "HeadBlock",
    "FaceBlock",
    "ProportionsBlock",
    "OutlineBlock",
    "OutlineWeight",
    "ColorPaletteBlock",
    "WardrobeBlock",
    "SignaturePropsBlock",
    "OrientationBlock",
    "ReferenceSheetBlock",
    "ConsistencyRulesBlock",
    "ConsistencyRuleKind",
    # Seeds / builder (L-U1)
    "SOURCE_GOOGLE_FLOW",
    "SOURCE_DINO_AI",
    "SOURCE_AXEN_REF",
    "google_flow_seeds",
    "dino_ai_seeds",
    "axen_learner_seeds",
    "default_seeds",
    "default_sources",
    "build_default_registry",
    "reset_and_build",
    # Storyboard adapter (L-U2)
    "KnowledgeStoryboardAdapter",
    # Canonical consumption (L-U3)
    "KnowledgeQuery",
    "KnowledgeResult",
    "KnowledgeProvenance",
    "KnowledgeNotFound",
    "sort_results",
    "KnowledgeResolver",
    "KnowledgeContext",
    "FallbackPolicy",
    # Errors (L-U3)
    "KnowledgeError",
    "KnowledgeInvalidQuery",
    "KnowledgeVersionMismatch",
    "KnowledgeConflict",
    "KnowledgeUnavailable",
]
