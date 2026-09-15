"""Tests for the SceneDefinition schema validator.

These tests guard the LLM contract. If the schema changes, update both
the Pydantic model and the mirrored TypeScript type in `renderer/src/scenes/types.ts`.
"""
from __future__ import annotations

import pytest
from pydantic import ValidationError

from app.providers.mock_llm import _mock_scene_json
from app.schemas.scene_definition import (
    Camera, Character, Environment, Meta, Pose, Prop, Scene, SceneDefinition, Style,
)


def test_mock_scene_json_is_valid() -> None:
    """The mock fixture should always satisfy the schema."""
    sd = SceneDefinition.model_validate(_mock_scene_json())
    assert len(sd.scenes) >= 1
    assert sd.meta.target_duration_sec > 0


def test_scenes_must_be_contiguous() -> None:
    """Two overlapping scenes should fail validation."""
    meta = Meta(title="t")
    char = Character(id="n", name="n", color="#000000")
    env = Environment(id="e", name="e")
    scenes = [
        Scene(id="s1", kind="title", start_sec=0.0, end_sec=10.0, environment_id="e"),
        # overlap with s1
        Scene(id="s2", kind="title", start_sec=9.0, end_sec=20.0, environment_id="e"),
    ]
    with pytest.raises(ValidationError):
        SceneDefinition(meta=meta, characters=[char], environments=[env], scenes=scenes)


def test_unknown_environment_reference_fails() -> None:
    meta = Meta(title="t")
    char = Character(id="n", name="n", color="#000000")
    env = Environment(id="e", name="e")
    scenes = [
        Scene(id="s1", kind="title", start_sec=0.0, end_sec=10.0, environment_id="unknown"),
    ]
    with pytest.raises(ValidationError):
        SceneDefinition(meta=meta, characters=[char], environments=[env], scenes=scenes)


def test_word_timestamps_must_be_inside_scene() -> None:
    """A word starting after the scene ends must fail."""
    meta = Meta(title="t")
    char = Character(id="n", name="n", color="#000000")
    env = Environment(id="e", name="e")
    from app.schemas.scene_definition import WordTimestamp
    scenes = [
        Scene(
            id="s1", kind="narration", start_sec=0.0, end_sec=5.0, environment_id="e",
            narration_words=[WordTimestamp(word="x", start_sec=4.0, end_sec=6.0)],
        ),
    ]
    with pytest.raises(ValidationError):
        SceneDefinition(meta=meta, characters=[char], environments=[env], scenes=scenes)


def test_total_duration_must_match_target() -> None:
    """A scene that's wildly off target duration should fail."""
    meta = Meta(title="t", target_duration_sec=120.0)
    char = Character(id="n", name="n", color="#000000")
    env = Environment(id="e", name="e")
    scenes = [
        Scene(id="s1", kind="title", start_sec=0.0, end_sec=10.0, environment_id="e"),
        Scene(id="s2", kind="title", start_sec=10.0, end_sec=15.0, environment_id="e"),
    ]
    with pytest.raises(ValidationError):
        SceneDefinition(meta=meta, characters=[char], environments=[env], scenes=scenes)


def test_color_must_be_hex() -> None:
    with pytest.raises(ValidationError):
        Style(primary_color="not-a-color")


def test_pose_enum() -> None:
    """`pose` field is a strict enum; bad values are rejected."""
    from app.schemas.scene_definition import Actor
    with pytest.raises(ValidationError):
        Actor(character_id="n", x=0.5, y=0.5, pose="flying")
