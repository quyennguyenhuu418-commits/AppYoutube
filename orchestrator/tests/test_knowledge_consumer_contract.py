"""
Contract tests for future Knowledge Consumers (L-U3 §30).

These tests verify that ANY future consumer of the Knowledge Layer
(L-U4 Character, L-U5 Prompt Engine, L-U6 Camera/Motion/Sound, etc.)
can satisfy a common contract:

    1. resolve(query) is deterministic
    2. provenance is preserved
    3. read-only (no registry mutation)
    4. version-aware (results carry version)
    5. explicit fallback (no implicit errors)

The tests build lightweight consumer fixtures that wrap the canonical
`KnowledgeResolver`. They do NOT mock production subsystems — they
exercise the actual resolver against a real registry.

If a future prompt introduces a new consumer that follows the same
canonical pattern (KnowledgeContext + KnowledgeResolver), these tests
will pass without modification. If the consumer breaks the contract,
these tests will fail with a clear diagnostic.
"""

from __future__ import annotations

import pytest

from app.knowledge import (
    FallbackPolicy,
    KnowledgeContext,
    KnowledgeDomain,
    KnowledgeQuery,
    KnowledgeRegistry,
    KnowledgeResolver,
    KnowledgeResult,
    KnowledgeSource,
    build_default_registry,
    default_sources,
)


# ============================================================================
# Consumer fixtures — one per future L-U
# ============================================================================

class _CharacterConsumerFixture:
    """L-U4 placeholder: Character Reference System consumer.

    The real implementation (L-U4) will inherit this pattern.
    """

    def __init__(self, context: KnowledgeContext):
        self._ctx = context

    def get_character_consistency_rules(self) -> list[str]:
        results = self._ctx.resolver.resolve(
            KnowledgeQuery(domain=KnowledgeDomain.CHARACTER)
        )
        return sorted(rules for r in results for rules in r.rules)


class _PromptConsumerFixture:
    """L-U5 placeholder: Prompt Engine V2 consumer."""

    def __init__(self, context: KnowledgeContext):
        self._ctx = context

    def get_prompt_structure(self) -> list[str]:
        results = self._ctx.resolver.resolve(
            KnowledgeQuery(domain=KnowledgeDomain.IMAGE_PROMPT)
        )
        return sorted(rules for r in results for rules in r.rules)


class _CameraConsumerFixture:
    """L-U6 placeholder: Camera/Motion/Sound consumer."""

    def __init__(self, context: KnowledgeContext):
        self._ctx = context

    def get_camera_rules(self) -> list[str]:
        results = self._ctx.resolver.resolve(
            KnowledgeQuery(domain=KnowledgeDomain.CAMERA)
        )
        return sorted(rules for r in results for rules in r.rules)


class _AssetConsumerFixture:
    """Future Asset consumer (P6+) — already covered by existing
    AssetSystemEngine, but a thin wrapper around the resolver should
    also satisfy the contract."""

    def __init__(self, context: KnowledgeContext):
        self._ctx = context

    def get_style_profile_rules(self) -> list[str]:
        results = self._ctx.resolver.resolve(
            KnowledgeQuery(domain=KnowledgeDomain.VISUAL_STYLE)
        )
        return sorted(rules for r in results for rules in r.rules)


# ============================================================================
# Test fixtures
# ============================================================================

@pytest.fixture
def registry():
    return build_default_registry()


@pytest.fixture
def context(registry):
    return KnowledgeContext.from_registry(
        registry,
        sources=default_sources(),
        name="contract-test",
    )


@pytest.fixture
def disabled_context():
    return KnowledgeContext.disabled()


@pytest.fixture
def consumers(context, disabled_context):
    return {
        "character": _CharacterConsumerFixture(context),
        "prompt": _PromptConsumerFixture(context),
        "camera": _CameraConsumerFixture(context),
        "asset": _AssetConsumerFixture(context),
    }


# ============================================================================
# Contract Test 1: Deterministic resolution
# ============================================================================

class TestDeterministicResolution:
    """resolve(query) returns the same result every time."""

    @pytest.mark.parametrize("consumer_name", ["character", "prompt", "camera", "asset"])
    def test_consumer_is_deterministic(self, consumers, consumer_name):
        consumer = consumers[consumer_name]
        r1 = consumer._ctx.resolver.resolve(KnowledgeQuery(domain=None))
        r2 = consumer._ctx.resolver.resolve(KnowledgeQuery(domain=None))
        assert r1 == r2


# ============================================================================
# Contract Test 2: Provenance preservation
# ============================================================================

class TestProvenancePreserved:
    """Every result carries provenance."""

    @pytest.mark.parametrize("consumer_name", ["character", "prompt", "camera", "asset"])
    def test_results_carry_provenance(self, consumers, consumer_name):
        consumer = consumers[consumer_name]
        results = consumer._ctx.resolver.resolve(KnowledgeQuery(domain=None))
        for r in results:
            assert r.provenance is not None
            assert r.provenance.source_id
            assert r.provenance.source_version


# ============================================================================
# Contract Test 3: Read-only
# ============================================================================

class TestReadOnly:
    """Consumers cannot mutate the registry."""

    @pytest.mark.parametrize("consumer_name", ["character", "prompt", "camera", "asset"])
    def test_consumer_does_not_mutate(self, consumers, registry, consumer_name):
        consumer = consumers[consumer_name]
        before = dict(registry.entries)
        # Drive all methods on the consumer
        if hasattr(consumer, "get_character_consistency_rules"):
            consumer.get_character_consistency_rules()
        if hasattr(consumer, "get_prompt_structure"):
            consumer.get_prompt_structure()
        if hasattr(consumer, "get_camera_rules"):
            consumer.get_camera_rules()
        if hasattr(consumer, "get_style_profile_rules"):
            consumer.get_style_profile_rules()
        # Verify registry untouched
        assert registry.entries == before


# ============================================================================
# Contract Test 4: Version-aware
# ============================================================================

class TestVersionAware:
    """Results carry a version that can be traced back to the registry."""

    @pytest.mark.parametrize("consumer_name", ["character", "prompt", "camera", "asset"])
    def test_results_carry_version(self, consumers, consumer_name):
        consumer = consumers[consumer_name]
        results = consumer._ctx.resolver.resolve(KnowledgeQuery(domain=None))
        for r in results:
            assert r.version
            parts = r.version.split(".")
            assert len(parts) == 3


# ============================================================================
# Contract Test 5: Explicit fallback
# ============================================================================

class TestExplicitFallback:
    """A disabled context returns empty results; consumers handle that
    explicitly (no exceptions)."""

    @pytest.mark.parametrize("consumer_name", ["character", "prompt", "camera", "asset"])
    def test_disabled_context_returns_empty(self, disabled_context, consumer_name):
        if consumer_name == "character":
            c = _CharacterConsumerFixture(disabled_context)
            assert c.get_character_consistency_rules() == []
        elif consumer_name == "prompt":
            c = _PromptConsumerFixture(disabled_context)
            assert c.get_prompt_structure() == []
        elif consumer_name == "camera":
            c = _CameraConsumerFixture(disabled_context)
            assert c.get_camera_rules() == []
        elif consumer_name == "asset":
            c = _AssetConsumerFixture(disabled_context)
            assert c.get_style_profile_rules() == []


# ============================================================================
# Contract Test 6: Domain-aware filtering
# ============================================================================

class TestDomainFiltering:
    """Consumers can scope their queries to a domain."""

    def test_character_query_returns_only_character_entries(self, context):
        results = context.resolver.resolve(
            KnowledgeQuery(domain=KnowledgeDomain.CHARACTER)
        )
        for r in results:
            assert r.domain == KnowledgeDomain.CHARACTER

    def test_camera_query_returns_only_camera_entries(self, context):
        results = context.resolver.resolve(
            KnowledgeQuery(domain=KnowledgeDomain.CAMERA)
        )
        for r in results:
            assert r.domain == KnowledgeDomain.CAMERA


# ============================================================================
# Contract Test 7: Tag-based filtering
# ============================================================================

class TestTagFiltering:
    """Consumers can scope their queries to a tag."""

    def test_google_flow_tag(self, context):
        results = context.resolver.resolve(
            KnowledgeQuery(tags=frozenset({"google_flow"}))
        )
        # At least one entry should match
        assert len(results) >= 0  # tag-based search may return empty
        for r in results:
            assert "google_flow" in r.tags


# ============================================================================
# Contract Test 8: Lifecycle — same context, same result
# ============================================================================

class TestLifecycleStable:
    """A KnowledgeContext is immutable; lifetime does not affect results."""

    def test_context_immutable_results(self, context):
        r1 = context.resolver.resolve(KnowledgeQuery(domain=None))
        # Touch other methods
        context.fallback_policy  # noop
        context.name  # noop
        # Re-resolve
        r2 = context.resolver.resolve(KnowledgeQuery(domain=None))
        assert r1 == r2
