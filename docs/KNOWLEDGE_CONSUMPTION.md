# Knowledge Consumption Architecture (L-U3)

> **Status:** IMPLEMENTED. VERIFIED. PRODUCTION_READY (for L-U1, L-U2
> scope). Future consumer adapters (L-U4, L-U5, L-U6) inherit this
> architecture without modification.

## Purpose

This document describes how production subsystems **consume** the
Knowledge Layer (L-U1) without creating:

- adapter explosion (one adapter per subsystem)
- duplicated knowledge access logic
- circular dependencies
- hidden business logic
- uncontrolled coupling

The canonical pattern is:

```
KnowledgeRegistry (L-U1)
        |
        v
KnowledgeResolver   <-- single, composable, domain-agnostic
        |
        v
KnowledgeContext    <-- lifecycle + fallback policy
        |
        v
Domain adapter      <-- thin wrapper, e.g. KnowledgeStoryboardAdapter
        |
        v
Production engine   <-- StoryboardEngine, CharacterEngine, ...
```

## Why a separate layer

L-U1 established the **data layer**: `KnowledgeRegistry`,
`KnowledgeEntry`, `KnowledgeSource`.

L-U2 proved that a single specialized adapter (`KnowledgeStoryboardAdapter`)
can integrate the registry with one consumer (`StoryboardEngine`).

Without a canonical consumption architecture, scaling to N consumers
would require:

| Subsystem | Adapter |
|---|---|
| Storyboard | KnowledgeStoryboardAdapter |
| Character | KnowledgeCharacterAdapter |
| Asset | KnowledgeAssetAdapter |
| Prompt | KnowledgePromptAdapter |
| Animation | KnowledgeAnimationAdapter |
| Editorial | KnowledgeEditorialAdapter |
| ... | ... |

Each adapter would have to re-implement the same:

- read-only enforcement
- deterministic ordering
- version handling
- provenance preservation
- fallback policy
- domain filtering

L-U3 collapses that duplication into one resolver + one context. The
remaining "adapter" code (e.g. `KnowledgeStoryboardAdapter`) becomes
a **thin translation layer** that turns `KnowledgeResult` into
subsystem-specific values.

## Canonical contracts

### `KnowledgeQuery` (immutable)

A deterministic specification of "which knowledge am I asking for?".

```python
from app.knowledge import KnowledgeQuery, KnowledgeDomain

q = KnowledgeQuery(
    domain=KnowledgeDomain.CAMERA,
    tags=frozenset({"character"}),
    applicability=frozenset({"character"}),
)
```

Convenience constructors:

```python
KnowledgeQuery.by_id("dino.camera.shot_types")
KnowledgeQuery.by_domain(KnowledgeDomain.CHARACTER)
KnowledgeQuery.by_tag("google_flow")
KnowledgeQuery.by_applicability("image_prompt")
```

`KnowledgeQuery` is **frozen** — once constructed, its fields are
immutable. This guarantees determinism.

### `KnowledgeResult` (immutable view)

What a consumer actually receives:

```python
KnowledgeResult(
    knowledge_id: str,
    domain: KnowledgeDomain,
    name: str,
    status: KnowledgeStatus,
    rules: FrozenSet[str],
    examples: FrozenSet[str],
    tags: FrozenSet[str],
    applicability: FrozenSet[str],
    version: str,                  # semver
    provenance: KnowledgeProvenance,
    found: bool = True,
)
```

`KnowledgeResult` is also **frozen**. A consumer cannot mutate a
result — they must build a new one if they need different data.

### `KnowledgeProvenance` (compact)

```python
KnowledgeProvenance(
    source_id: str,           # e.g. "src_google_flow_v1"
    source_type: str,         # e.g. "system_prompt"
    source_reference: str,    # URL / path / ADR
    source_version: str,      # semver
    confidence: float,        # 0.0 - 1.0
)
```

Provenance is **mandatory** on every result. This is what makes the
Knowledge Layer traceable — a downstream consumer can always answer
"which source produced this rule?".

### `KnowledgeResolver` (the canonical read path)

```python
from app.knowledge import KnowledgeResolver, build_default_registry

registry = build_default_registry()
resolver = KnowledgeResolver(
    registry,
    sources={s.source_id: s for s in default_sources()},
)

results = resolver.resolve(KnowledgeQuery.by_domain(KnowledgeDomain.CAMERA))
first = resolver.resolve_one(KnowledgeQuery.by_id("dino.camera.shot_types"))
```

`KnowledgeResolver` is:

- **READ-ONLY** — never mutates the registry.
- **DETERMINISTIC** — same query + same registry -> same result.
- **DOMAIN-AGNOSTIC** — does not know about Storyboard or Character.
- **NO DEFAULTS** — returns empty results, never engine defaults.

### `KnowledgeContext` (lifecycle wrapper)

```python
from app.knowledge import KnowledgeContext, FallbackPolicy

ctx = KnowledgeContext.from_registry(
    build_default_registry(),
    sources=default_sources(),
    fallback_policy=FallbackPolicy.ENGINE_DEFAULT,
    name="storyboard-pipeline",
)
```

`KnowledgeContext` bundles:

- the resolver
- the fallback policy (ENGINE_DEFAULT / WARN / REJECT / SILENT)
- the source provenance map
- an observability `name`

It is **immutable**. There is no `set_resolver()` method. To change
the context, construct a new one.

### `FallbackPolicy` (per-subsystem choice)

| Policy | Behaviour |
|---|---|
| `ENGINE_DEFAULT` | Use the subsystem's pre-L-U3 default. (L-U2 behaviour.) |
| `WARN` | Log a warning, then fall back to default. |
| `REJECT` | Treat "no knowledge" as a hard error. |
| `SILENT` | Silently use the default. |

Choice is **per-subsystem**, not global. Storyboard may prefer
`ENGINE_DEFAULT`; Prompt may prefer `WARN`; Production QA may prefer
`REJECT`.

## How a new subsystem consumes knowledge

Concrete recipe — this is the answer to L-U3 §36:

```python
# 1. Obtain a KnowledgeRegistry (e.g. via app.tools.knowledge_loader)
from app.knowledge import (
    build_default_registry,
    default_sources,
    KnowledgeContext,
    KnowledgeQuery,
    KnowledgeResolver,
)

registry = build_default_registry()

# 2. Construct a KnowledgeContext (canonical L-U3)
context = KnowledgeContext.from_registry(
    registry,
    sources=default_sources(),
    name="my-subsystem",
    fallback_policy=FallbackPolicy.ENGINE_DEFAULT,
)

# 3. Inject the context into the subsystem (DI)
class MySubsystem:
    def __init__(self, knowledge_context: KnowledgeContext | None = None):
        self._knowledge = knowledge_context or KnowledgeContext.disabled()

# 4. Query relevant domain via the resolver
def get_rules(self) -> list[str]:
    results = self._knowledge.resolver.resolve(
        KnowledgeQuery(domain=KnowledgeDomain.CHARACTER)
    )
    return sorted(rules for r in results for rules in r.rules)

# 5. Apply subsystem-specific interpretation
def derive_decision(self, beat):
    rules = self.get_rules()
    # translate rules into a subsystem-specific value
    ...

# 6. Produce existing canonical production contract
def produce_scene_definition(self, beat):
    decision = self.derive_decision(beat)
    return SceneDefinition(...)  # unchanged contract
```

No other code path is allowed. Production subsystems MUST NOT
import `KnowledgeRegistry` directly; they MUST go through
`KnowledgeContext`.

## L-U2 migration decision

`KnowledgeStoryboardAdapter` was kept as a thin translation layer:

- It now accepts either a `KnowledgeContext` (canonical L-U3) or a
  `KnowledgeRegistry` (legacy L-U2) — backward-compatible.
- All lookups go through the `KnowledgeResolver`, not the registry.
- Its public API (`get_camera_for_mode`, `get_motion_for_mode`,
  etc.) is unchanged.
- All 30 existing L-U2 tests pass without modification.

This decision keeps the L-U2 contract intact while routing all
knowledge access through the canonical resolver. Future consumer
adapters will follow the same pattern.

## Critical invariants

These are verified by automated tests in
`tests/test_knowledge_consumption_architecture.py`:

1. **Knowledge Layer never imports production engines.** Verified by
   `TestKnowledgeLayerIsolation`.
2. **No global mutable registry.** Verified by
   `TestNoGlobalState::test_no_global_registry_in_knowledge_module`.
3. **No service locator.** Verified by
   `TestNoGlobalState::test_no_get_global_function`.
4. **Resolver is read-only.** Verified by
   `TestResolverReadOnly::test_resolve_does_not_modify_registry`.
5. **Resolver is deterministic.** Verified by
   `TestResolverDeterminism`.
6. **`KnowledgeQuery` and `KnowledgeResult` are frozen.** Verified by
   their respective test classes.
7. **Version-pinned queries return empty on mismatch.** Verified by
   `TestVersionSemantics::test_version_pin_mismatch_returns_empty`.

## Future consumer support

The architecture supports L-U4, L-U5, L-U6, and beyond without
modification. The pattern is documented above and exercised by:

`tests/test_knowledge_consumer_contract.py` — 24 contract tests that
build lightweight consumer fixtures (Character, Prompt, Camera,
Asset) and verify they all satisfy the common contract:

- deterministic resolution
- provenance preservation
- read-only behaviour
- version-awareness
- explicit fallback

These tests are the **acceptance test** for any future consumer.

## What is NOT in this layer

L-U3 deliberately does **not** include:

- A `KnowledgeManager` god object (L-U3 §7).
- A vector database (L-U3 §22).
- A web API (L-U3 §23).
- An LLM call (L-U3 §0).
- External AI providers (L-U3 §0).
- A service locator (L-U3 §21).
- A global mutable registry (L-U3 §20).

Each of these is **deferred** with a documented reason. See
`plans/PROMPT_LU3_FINAL_REPORT.md` for the deferred-work
discipline.

## Related documents

- `docs/KNOWLEDGE_LAYER.md` — L-U1 documentation
- `plans/L-U1_FINAL_REPORT.md` — L-U1 final report
- `plans/L-U2_FINAL_REPORT.md` — L-U2 final report
- `plans/PROMPT_LU3_FINAL_REPORT.md` — L-U3 final report
- `docs/ARCHITECTURE_DECISIONS.md` — ADR-011 (L-U3)
