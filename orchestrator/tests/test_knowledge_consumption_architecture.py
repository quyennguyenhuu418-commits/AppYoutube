"""
Architecture tests for L-U3 — Knowledge Consumption Architecture.

These tests verify the architectural invariants of the Knowledge Layer:

    1. The Knowledge Layer does NOT import production engines.
    2. The resolver is deterministic.
    3. The resolver is read-only (no registry mutation).
    4. There is no global mutable singleton.
    5. There is no service locator.
    6. No circular imports exist.
    7. Production consumers receive `KnowledgeContext`, not registry directly.
    8. Version semantics are explicit.
    9. Provenance is preserved.
    10. Deterministic ordering is guaranteed.
    11. Fallback policy is respected.
    12. Lifecycle is explicit (no implicit construction).

If any of these tests fail, the architecture has regressed.
"""

from __future__ import annotations

import importlib
import inspect
import sys

import pytest

from app.knowledge import (
    FallbackPolicy,
    KnowledgeContext,
    KnowledgeDomain,
    KnowledgeEntry,
    KnowledgeQuery,
    KnowledgeRegistry,
    KnowledgeResolver,
    KnowledgeResult,
    KnowledgeSource,
    KnowledgeStatus,
    build_default_registry,
    default_sources,
    KnowledgeStoryboardAdapter,
)
from app.knowledge.errors import (
    KnowledgeError,
    KnowledgeInvalidQuery,
    KnowledgeUnavailable,
    KnowledgeVersionMismatch,
)


# ============================================================================
# Test 1: Knowledge Layer does NOT import production engines
# ============================================================================

class TestKnowledgeLayerIsolation:
    """Verify the Knowledge Layer never imports production engines.

    Allowed imports within `app.knowledge.*`:
        - Pydantic
        - typing / stdlib
        - other `app.knowledge.*` modules
        - `app.schemas.storyboard` (needed for enum mapping)

    Forbidden imports:
        - app.story / app.storyboard / app.character / app.asset
        - app.animation / app.voice / app.editorial
        - app.mastering / app.render
        - any provider modules
    """

    FORBIDDEN_MODULES = [
        "app.story",
        "app.storyboard",
        "app.character",
        "app.asset",
        "app.animation",
        "app.voice",
        "app.editorial",
        "app.mastering",
        "app.render",
        "app.providers",
        "app.pipeline",
    ]

    @pytest.mark.parametrize("module_name", [
        "app.knowledge.query",
        "app.knowledge.result",
        "app.knowledge.resolver",
        "app.knowledge.context",
        "app.knowledge.errors",
        "app.knowledge.storyboard_adapter",
    ])
    def test_module_does_not_import_forbidden_modules(self, module_name):
        module = importlib.import_module(module_name)
        forbidden = []
        for name, value in vars(module).items():
            if name.startswith("_"):
                continue
            # Check class/function __module__ attribute
            mod = None
            if hasattr(value, "__module__"):
                mod = getattr(value, "__module__", None)
            if mod is None and inspect.isclass(value):
                mod = value.__class__.__module__
            if mod and any(mod.startswith(fm + ".") or mod == fm for fm in self.FORBIDDEN_MODULES):
                forbidden.append((name, mod))
        assert not forbidden, (
            f"{module_name} imports forbidden modules: {forbidden}. "
            f"The Knowledge Layer must not depend on production engines."
        )


# ============================================================================
# Test 2: Resolver determinism
# ============================================================================

class TestResolverDeterminism:
    """resolve(query) is a pure function of (registry, query, context)."""

    def test_same_query_same_result(self):
        registry = build_default_registry()
        resolver = KnowledgeResolver(registry, sources={s.source_id: s for s in default_sources()})
        q = KnowledgeQuery.by_domain(KnowledgeDomain.CAMERA)
        r1 = resolver.resolve(q)
        r2 = resolver.resolve(q)
        assert r1 == r2

    def test_ordering_deterministic(self):
        registry = build_default_registry()
        resolver = KnowledgeResolver(registry, sources={s.source_id: s for s in default_sources()})
        q = KnowledgeQuery(domain=None)
        r1 = resolver.resolve(q)
        r2 = resolver.resolve(q)
        # Same order, same length
        assert len(r1) == len(r2)
        for a, b in zip(r1, r2):
            assert a.knowledge_id == b.knowledge_id
            assert a.version == b.version

    def test_resolve_pure_no_state(self):
        """Resolver does not cache or mutate state."""
        registry = build_default_registry()
        resolver = KnowledgeResolver(registry, sources={s.source_id: s for s in default_sources()})
        before = resolver.resolve(KnowledgeQuery(domain=None))
        # Re-resolve with a different query
        resolver.resolve(KnowledgeQuery.by_domain(KnowledgeDomain.CAMERA))
        # Original query should still return same thing
        after = resolver.resolve(KnowledgeQuery(domain=None))
        assert before == after


# ============================================================================
# Test 3: Read-only guarantee
# ============================================================================

class TestResolverReadOnly:
    """The resolver never mutates the registry."""

    def test_resolve_does_not_modify_registry(self):
        registry = build_default_registry()
        before_entries = dict(registry.entries)
        before_sources = list(registry.sources_loaded)
        resolver = KnowledgeResolver(registry, sources={s.source_id: s for s in default_sources()})
        # Run many queries
        for q in [
            KnowledgeQuery(domain=None),
            KnowledgeQuery.by_domain(KnowledgeDomain.CAMERA),
            KnowledgeQuery.by_id("dino.camera.push_in"),
            KnowledgeQuery(tags=frozenset({"google_flow"})),
        ]:
            resolver.resolve(q)
        # Registry is unchanged
        assert registry.entries == before_entries
        assert registry.sources_loaded == before_sources


# ============================================================================
# Test 4: No global singleton / no service locator
# ============================================================================

class TestNoGlobalState:
    """There must be no module-level mutable registry."""

    def test_no_global_registry_in_knowledge_module(self):
        import app.knowledge as km
        # Check there is no module-level mutable singleton
        for name in dir(km):
            if name.startswith("_"):
                continue
            value = getattr(km, name)
            # A registry is a pydantic model with an `entries` dict
            if isinstance(value, KnowledgeRegistry):
                pytest.fail(
                    f"Found module-level KnowledgeRegistry at app.knowledge.{name}. "
                    "This is a global singleton — must be injected instead."
                )

    def test_no_get_global_function(self):
        """No `get_current_*` / `get_global_*` / `get_service_*` in knowledge."""
        import app.knowledge as km
        forbidden_prefixes = ("get_global_", "get_current_", "get_service_", "get_default_")
        for name in dir(km):
            if name.startswith("_"):
                continue
            if any(name.startswith(p) for p in forbidden_prefixes):
                value = getattr(km, name)
                if callable(value):
                    pytest.fail(
                        f"Found service-locator-style function app.knowledge.{name}. "
                        "Dependencies must be injected explicitly."
                    )


# ============================================================================
# Test 5: KnowledgeContext lifecycle
# ============================================================================

class TestKnowledgeContextLifecycle:
    """KnowledgeContext bundles resolver + fallback policy + sources."""

    def test_disabled_context_returns_empty(self):
        ctx = KnowledgeContext.disabled()
        assert ctx.resolver.is_active() is False
        assert ctx.resolver.resolve(KnowledgeQuery(domain=None)) == []

    def test_from_registry_attaches_sources(self):
        registry = build_default_registry()
        sources = default_sources()
        ctx = KnowledgeContext.from_registry(registry, sources=sources)
        assert ctx.resolver.is_active()
        assert ctx.fallback_policy == FallbackPolicy.ENGINE_DEFAULT

    def test_context_is_immutable(self):
        ctx = KnowledgeContext.disabled()
        with pytest.raises(Exception):  # pydantic ValidationError on frozen
            ctx.name = "modified"

    def test_context_carries_fallback_policy(self):
        ctx = KnowledgeContext.from_registry(
            build_default_registry(),
            fallback_policy=FallbackPolicy.WARN,
        )
        assert ctx.fallback_policy == FallbackPolicy.WARN


# ============================================================================
# Test 6: KnowledgeQuery immutability + determinism
# ============================================================================

class TestKnowledgeQueryContract:
    """KnowledgeQuery is frozen and deterministic."""

    def test_query_is_frozen(self):
        q = KnowledgeQuery.by_domain(KnowledgeDomain.CAMERA)
        with pytest.raises(Exception):  # pydantic ValidationError on frozen
            q.domain = KnowledgeDomain.MOTION

    def test_query_by_id(self):
        q = KnowledgeQuery.by_id("dino.camera.push_in")
        assert q.knowledge_id == "dino.camera.push_in"
        assert q.domain is None

    def test_query_by_tag(self):
        q = KnowledgeQuery.by_tag("google_flow")
        assert "google_flow" in q.tags

    def test_query_by_applicability(self):
        q = KnowledgeQuery.by_applicability("image_prompt")
        assert "image_prompt" in q.applicability

    def test_query_with_version_pin(self):
        q = KnowledgeQuery(version_pin="1.0.0")
        assert q.version_pin == "1.0.0"


# ============================================================================
# Test 7: KnowledgeResult provenance preservation
# ============================================================================

class TestKnowledgeResultProvenance:
    """KnowledgeResult carries full provenance."""

    def test_result_has_provenance(self):
        registry = build_default_registry()
        resolver = KnowledgeResolver(registry, sources={s.source_id: s for s in default_sources()})
        results = resolver.resolve(KnowledgeQuery.by_domain(KnowledgeDomain.CAMERA))
        assert results
        for r in results:
            assert r.provenance is not None
            assert r.provenance.source_id
            assert r.provenance.source_version
            assert r.provenance.confidence >= 0.0

    def test_result_is_frozen(self):
        registry = build_default_registry()
        resolver = KnowledgeResolver(registry, sources={s.source_id: s for s in default_sources()})
        results = resolver.resolve(KnowledgeQuery.by_domain(KnowledgeDomain.CAMERA))
        assert results
        r = results[0]
        with pytest.raises(Exception):
            r.knowledge_id = "modified"

    def test_provenance_label_format(self):
        registry = build_default_registry()
        resolver = KnowledgeResolver(registry, sources={s.source_id: s for s in default_sources()})
        results = resolver.resolve(KnowledgeQuery(domain=None))
        assert results
        label = results[0].provenance_label
        assert "@" in label
        assert "via" in label


# ============================================================================
# Test 8: Version semantics
# ============================================================================

class TestVersionSemantics:
    """Version-pinned queries either return matching entries or empty."""

    def test_version_pin_matching_returns_entry(self):
        registry = build_default_registry()
        resolver = KnowledgeResolver(registry, sources={s.source_id: s for s in default_sources()})
        results = resolver.resolve(
            KnowledgeQuery(
                knowledge_id="dino.camera.shot_types",
                version_pin="1.0.0",
            )
        )
        assert results

    def test_version_pin_mismatch_returns_empty(self):
        registry = build_default_registry()
        resolver = KnowledgeResolver(registry, sources={s.source_id: s for s in default_sources()})
        results = resolver.resolve(
            KnowledgeQuery(
                knowledge_id="dino.camera.shot_types",
                version_pin="99.99.99",
            )
        )
        assert results == []


# ============================================================================
# Test 9: Fallback policy
# ============================================================================

class TestFallbackPolicy:
    """FallbackPolicy has the four canonical values."""

    def test_policies_exist(self):
        assert FallbackPolicy.ENGINE_DEFAULT
        assert FallbackPolicy.WARN
        assert FallbackPolicy.REJECT
        assert FallbackPolicy.SILENT

    def test_policy_default(self):
        ctx = KnowledgeContext.disabled()
        assert ctx.fallback_policy == FallbackPolicy.ENGINE_DEFAULT


# ============================================================================
# Test 10: Error semantics
# ============================================================================

class TestErrorSemantics:
    """Minimal error model: 4 error types + base."""

    def test_base_error(self):
        err = KnowledgeError("base")
        assert isinstance(err, Exception)

    def test_invalid_query(self):
        err = KnowledgeInvalidQuery("bad query")
        assert isinstance(err, KnowledgeError)

    def test_version_mismatch_carries_fields(self):
        err = KnowledgeVersionMismatch("dino.camera.push_in", "99.99.99")
        assert err.knowledge_id == "dino.camera.push_in"
        assert err.version == "99.99.99"

    def test_unavailable(self):
        err = KnowledgeUnavailable("nope")
        assert isinstance(err, KnowledgeError)


# ============================================================================
# Test 11: KnowledgeStoryboardAdapter backward compatibility (L-U2)
# ============================================================================

class TestL2BackwardCompatibility:
    """L-U2 adapter still works exactly as before."""

    def test_adapter_accepts_registry(self):
        registry = build_default_registry()
        adapter = KnowledgeStoryboardAdapter(registry)
        assert adapter.is_active()
        # Camera mode returns correct enum
        from app.schemas.storyboard import StoryboardCameraType, StoryboardVisualMode
        cam = adapter.get_camera_for_mode(StoryboardVisualMode.CHARACTER)
        assert cam == StoryboardCameraType.PUSH_IN

    def test_adapter_accepts_context(self):
        ctx = KnowledgeContext.from_registry(build_default_registry())
        adapter = KnowledgeStoryboardAdapter(context=ctx)
        assert adapter.is_active()

    def test_adapter_accepts_none(self):
        adapter = KnowledgeStoryboardAdapter()
        assert not adapter.is_active()

    def test_adapter_is_resolver_backed(self):
        """L-U3: the adapter uses the resolver, not the registry directly."""
        registry = build_default_registry()
        adapter = KnowledgeStoryboardAdapter(registry)
        # The adapter exposes the resolver through its context
        assert hasattr(adapter, "context")
        assert isinstance(adapter.context, KnowledgeContext)


# ============================================================================
# Test 12: No circular imports
# ============================================================================

class TestNoCircularImports:
    """The knowledge package must not have circular imports.

    Strategy: import every module in the knowledge package; if a
    circular import exists, the import would have already failed
    during pytest collection.
    """

    @pytest.mark.parametrize("module_name", [
        "app.knowledge",
        "app.knowledge.builder",
        "app.knowledge.character_grammar",
        "app.knowledge.context",
        "app.knowledge.errors",
        "app.knowledge.query",
        "app.knowledge.registry",
        "app.knowledge.resolver",
        "app.knowledge.result",
        "app.knowledge.schemas",
        "app.knowledge.seeds",
        "app.knowledge.storyboard_adapter",
        "app.knowledge.visual_grammar",
    ])
    def test_module_imports(self, module_name):
        # If we reach here, the import succeeded — meaning no circular import.
        importlib.import_module(module_name)
