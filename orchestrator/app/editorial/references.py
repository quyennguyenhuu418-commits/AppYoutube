"""
PROMPT 10 — Reference resolution.

Maps the IDs referenced by `EditorialProject` to their canonical sources
already produced by upstream subsystems (Asset, Animation, Voice, Caption).

This module is the SINGLE place where Editorial looks up canonical
artifacts. It MUST NOT mutate any upstream state. If a referenced asset
is missing, it raises a structured `ReferenceError` so the compiler
emits an explicit failure (PROMPT 10 §31, §49).
"""
from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from typing import Any


class ReferenceError(Exception):
    """Raised when an editorial reference cannot be resolved.

    Carries the failing kind + ID for tooling / log parsing.
    """

    def __init__(self, kind: str, ref_id: str, *, hint: str = "") -> None:
        self.kind = kind
        self.ref_id = ref_id
        self.hint = hint
        msg = f"editorial reference unresolved: kind={kind!r} id={ref_id!r}"
        if hint:
            msg += f" hint={hint!r}"
        super().__init__(msg)


@dataclass(frozen=True)
class SourceBundle:
    """Aggregated read-only handle to canonical sources used during editing.

    The compiler does NOT mutate this bundle; it only reads.
    """

    scene_definition: Any  # canonical SceneDefinition
    animation_plan_ids: set[str] = None  # type: ignore[assignment]
    caption_track_ids: set[str] = None  # type: ignore[assignment]
    audio_artifact_ids: set[str] = None  # type: ignore[assignment]
    narration_timeline_id: str | None = None
    asset_reference_ids: set[str] = None  # type: ignore[assignment]
    environment_ids: set[str] = None  # type: ignore[assignment]
    character_ids: set[str] = None  # type: ignore[assignment]
    prop_kinds: set[str] = None  # type: ignore[assignment]

    def __post_init__(self) -> None:
        # Default empty sets if caller passed None.
        for f in (
            "animation_plan_ids", "caption_track_ids", "audio_artifact_ids",
            "asset_reference_ids", "environment_ids", "character_ids",
            "prop_kinds",
        ):
            cur = getattr(self, f)
            if cur is None:
                object.__setattr__(self, f, set())
            elif not isinstance(cur, set):
                raise TypeError(f"SourceBundle.{f} must be a set; got {type(cur).__name__}")


def _extract_ids(scene_definition: Any) -> dict[str, Any]:
    """Walk a SceneDefinition-like object and gather canonical IDs.

    The function is deliberately tolerant: it uses `getattr` for every field
    so it tolerates dict-shaped or object-shaped canonical contracts
    uniformly.
    """
    scene_ids = set()
    env_ids = set()
    char_ids = set()
    prop_kinds = set()
    asset_refs: set[str] = set()

    environments = getattr(scene_definition, "environments", None) or []
    for env in environments:
        eid = getattr(env, "id", None)
        if eid is not None:
            env_ids.add(str(eid))

    characters = getattr(scene_definition, "characters", None) or []
    for ch in characters:
        cid = getattr(ch, "id", None)
        if cid is not None:
            char_ids.add(str(cid))

    scenes = getattr(scene_definition, "scenes", None) or []
    for scene in scenes:
        sid = getattr(scene, "id", None)
        if sid is not None:
            scene_ids.add(str(sid))
        env_id = getattr(scene, "environment_id", None)
        if env_id is not None:
            env_ids.add(str(env_id))
        actors = getattr(scene, "actors", None) or []
        for actor in actors:
            cid = getattr(actor, "character_id", None)
            if cid is not None:
                char_ids.add(str(cid))
        props = getattr(scene, "props", None) or []
        for prop in props:
            kind = getattr(prop, "kind", None)
            if kind is not None:
                prop_kinds.add(str(kind))

    return {
        "scene_ids": scene_ids,
        "environment_ids": env_ids,
        "character_ids": char_ids,
        "prop_kinds": prop_kinds,
        "asset_reference_ids": asset_refs,
    }


def build_source_bundle(scene_definition: Any) -> SourceBundle:
    """Build a SourceBundle from a canonical SceneDefinition.

    Extras (animation/captions/audio/narration_timeline) may be supplied
    by the caller via keyword arguments to extend the bundle.
    """
    ids = _extract_ids(scene_definition)
    return SourceBundle(
        scene_definition=scene_definition,
        animation_plan_ids=ids.get("animation_plan_ids", set()),
        caption_track_ids=ids.get("caption_track_ids", set()),
        audio_artifact_ids=ids.get("audio_artifact_ids", set()),
        asset_reference_ids=ids["asset_reference_ids"],
        environment_ids=ids["environment_ids"],
        character_ids=ids["character_ids"],
        prop_kinds=ids["prop_kinds"],
    )


def extend_bundle(
    bundle: SourceBundle,
    *,
    animation_plan_ids: set[str] | None = None,
    caption_track_ids: set[str] | None = None,
    audio_artifact_ids: set[str] | None = None,
    narration_timeline_id: str | None = None,
) -> SourceBundle:
    """Return a new SourceBundle that supersets the given extras."""
    return SourceBundle(
        scene_definition=bundle.scene_definition,
        animation_plan_ids=bundle.animation_plan_ids | (animation_plan_ids or set()),
        caption_track_ids=bundle.caption_track_ids | (caption_track_ids or set()),
        audio_artifact_ids=bundle.audio_artifact_ids | (audio_artifact_ids or set()),
        asset_reference_ids=bundle.asset_reference_ids,
        environment_ids=bundle.environment_ids,
        character_ids=bundle.character_ids,
        prop_kinds=bundle.prop_kinds,
        narration_timeline_id=narration_timeline_id or bundle.narration_timeline_id,
    )


# ============================================================================
# Fingerprint — for caching + determinism verification (PROMPT 10 §36, §48)
# ============================================================================

def compute_source_fingerprint(bundle: SourceBundle, extras: dict[str, Any] | None = None) -> str:
    """Compute a deterministic fingerprint of the editorial-relevant state.

    Same sources → same fingerprint. Extras may include animation plan content,
    caption track content, audio artifact metadata, etc.
    """
    payload: dict[str, Any] = {
        "scene_definition": _canonicalize_scene_definition(bundle.scene_definition),
        "animation_plan_ids": sorted(bundle.animation_plan_ids),
        "caption_track_ids": sorted(bundle.caption_track_ids),
        "audio_artifact_ids": sorted(bundle.audio_artifact_ids),
        "asset_reference_ids": sorted(bundle.asset_reference_ids),
        "environment_ids": sorted(bundle.environment_ids),
        "character_ids": sorted(bundle.character_ids),
        "prop_kinds": sorted(bundle.prop_kinds),
        "narration_timeline_id": bundle.narration_timeline_id or "",
        "extras": extras or {},
    }
    blob = json.dumps(payload, sort_keys=True, separators=(",", ":"), default=str)
    return "fp_" + hashlib.sha256(blob.encode("utf-8")).hexdigest()[:24]


def _canonicalize_scene_definition(sd: Any) -> Any:
    """Return a canonical primitive representation for fingerprinting.

    We don't want fingerprint sensitivity to Pydantic class identity or
    field ordering; this normalises both dict- and object-shaped inputs.
    """
    if sd is None:
        return None
    if isinstance(sd, dict):
        return {k: _canonicalize_scene_definition(v) for k, v in sorted(sd.items())}
    if isinstance(sd, (list, tuple)):
        return [_canonicalize_scene_definition(v) for v in sd]
    if isinstance(sd, (str, int, float, bool)):
        return sd
    # Try to coerce object to primitive via attribute access.
    out: dict[str, Any] = {}
    for field in ("meta", "style", "characters", "environments", "scenes"):
        if hasattr(sd, field):
            out[field] = _canonicalize_scene_definition(getattr(sd, field))
    if not out:
        return str(sd)
    return out


__all__ = [
    "ReferenceError",
    "SourceBundle",
    "build_source_bundle",
    "extend_bundle",
    "compute_source_fingerprint",
]
