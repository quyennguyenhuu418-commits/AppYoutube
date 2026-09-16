"""Lightweight SceneDefinition stub used across Editorial tests.

We deliberately do NOT depend on the real Pydantic SceneDefinition schema to
keep the editorial tests fast and isolated. The Editorial layer only reads
canonical scenes via attribute access, so a duck-typed stub is sufficient.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class StubScene:
    id: str
    kind: str = "narration"
    start_sec: float = 0.0
    end_sec: float = 0.0
    environment_id: str = ""
    narration_text: str = ""
    narration_words: list[Any] = field(default_factory=list)
    audioSrc: str | None = None
    camera: Any = None
    actors: list[Any] = field(default_factory=list)
    props: list[Any] = field(default_factory=list)
    overlay_text: list[Any] = field(default_factory=list)
    sfx: list[Any] = field(default_factory=list)
    music: Any = None


@dataclass
class StubCharacter:
    id: str = "char1"
    name: str = "C"
    color: str = "#000000"
    default_pose: str = "stand"
    description: str = ""


@dataclass
class StubEnvironment:
    id: str = "env1"
    name: str = "E"
    background_asset: str = "b.png"
    mood: str = "calm"


@dataclass
class StubActor:
    character_id: str = "char1"
    x: float = 0.5
    y: float = 0.5
    scale: float = 1.0
    rotation_deg: float = 0.0
    pose: str = "stand"
    enter_anim: str = "fade_in"
    exit_anim: str = "none"


@dataclass
class StubProp:
    kind: str = "tree_pine"
    x: float = 0.5
    y: float = 0.5
    scale: float = 1.0
    rotation_deg: float = 0.0
    enter_anim: str = "fade_in"


@dataclass
class StubSceneDefinition:
    """A duck-typed stub of SceneDefinition suitable for editorial unit tests."""
    meta: Any = None
    style: Any = None
    characters: list[Any] = field(default_factory=list)
    environments: list[Any] = field(default_factory=list)
    scenes: list[Any] = field(default_factory=list)


def make_scene_definition(
    *,
    n_scenes: int = 2,
    env_ids: tuple[str, ...] = ("env1",),
    character_ids: tuple[str, ...] = ("alice",),
    prop_kinds: tuple[str, ...] = ("tree_pine",),
    scene_durations: tuple[float, ...] = (3.0, 3.0),
) -> StubSceneDefinition:
    """Build a SceneDefinition-like stub with `n_scenes` sequential scenes."""
    sd = StubSceneDefinition(
        characters=[StubCharacter(id=cid) for cid in character_ids],
        environments=[StubEnvironment(id=eid) for eid in env_ids],
    )
    cursor = 0.0
    for i in range(n_scenes):
        dur = scene_durations[i] if i < len(scene_durations) else 3.0
        env_id = env_ids[i % len(env_ids)]
        scene = StubScene(
            id=f"scene_{i+1}",
            kind="narration",
            start_sec=cursor,
            end_sec=cursor + dur,
            environment_id=env_id,
            actors=[StubActor(character_id=character_ids[i % len(character_ids)])],
            props=[StubProp(kind=prop_kinds[i % len(prop_kinds)])] if prop_kinds else [],
        )
        sd.scenes.append(scene)
        cursor += dur
    return sd


__all__ = [
    "StubScene",
    "StubCharacter",
    "StubEnvironment",
    "StubActor",
    "StubProp",
    "StubSceneDefinition",
    "make_scene_definition",
]
