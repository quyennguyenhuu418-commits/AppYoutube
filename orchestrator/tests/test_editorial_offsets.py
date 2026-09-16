"""PROMPT 10 — Editorial scene placement / offsets tests."""
from __future__ import annotations

import pytest

from app.editorial.offsets import place_scenes, placement_for
from app.editorial.schemas import (
    EditorialScene,
    EditorialTimeline,
    Transition,
    TransitionKind,
)


def _scn(order: int, duration: float, *, transition_out: Transition | None = None,
         transition_in: Transition | None = None) -> EditorialScene:
    return EditorialScene(
        scene_id=f"s{order}", order=order,
        source_scene_duration_sec=duration,
        transition_in=transition_in,
        transition_out=transition_out,
    )


def test_place_single_scene() -> None:
    tl = EditorialTimeline(
        timeline_id="t", fps=30, width=1280, height=720,
        scenes=[_scn(0, 5.0)],
    )
    placements = place_scenes(tl)
    assert len(placements) == 1
    p = placements[0]
    assert p.master_start_sec == 0.0
    assert p.master_end_sec == 5.0
    assert p.master_start_frame == 0
    assert p.duration_frames == 150


def test_place_two_scenes_back_to_back_cut() -> None:
    tl = EditorialTimeline(
        timeline_id="t", fps=30, width=1280, height=720,
        scenes=[_scn(0, 3.0), _scn(1, 2.0)],
    )
    placements = place_scenes(tl)
    assert len(placements) == 2
    p0, p1 = placements
    assert p0.master_end_sec == 3.0
    assert p1.master_start_sec == 3.0
    assert p1.master_end_sec == 5.0


def test_place_with_fade_out_overlap_subtracts() -> None:
    fade = Transition(transition_id="t1", kind=TransitionKind.FADE, duration_sec=0.5)
    scenes = [_scn(0, 3.0, transition_out=fade), _scn(1, 2.0)]
    tl = EditorialTimeline(
        timeline_id="t", fps=30, width=1280, height=720, scenes=scenes,
    )
    placements = place_scenes(tl)
    p0, p1 = placements
    # next starts 0.5s earlier than prev end: 3.0 - 0.5 = 2.5
    assert p1.master_start_sec == pytest.approx(2.5)


def test_place_with_holds_extends_duration() -> None:
    from app.editorial.schemas import EditorialHold
    h_before = EditorialHold(hold_id="h1", target="before", duration_sec=1.0, reason="x")
    h_after = EditorialHold(hold_id="h2", target="after", duration_sec=0.5, reason="y")
    scn = EditorialScene(
        scene_id="s0", order=0, source_scene_duration_sec=2.0,
        holds=[h_before, h_after],
    )
    tl = EditorialTimeline(
        timeline_id="t", fps=30, width=1280, height=720, scenes=[scn],
    )
    placements = place_scenes(tl)
    p = placements[0]
    assert p.hold_before_sec == 1.0
    assert p.hold_after_sec == 0.5
    assert p.duration_sec == 3.5


def test_place_three_scenes_sequential_fade_chain() -> None:
    fade = Transition(transition_id="t1", kind=TransitionKind.FADE, duration_sec=0.3)
    scenes = [
        _scn(0, 2.0, transition_out=fade),
        _scn(1, 2.0, transition_out=fade),
        _scn(2, 2.0),
    ]
    tl = EditorialTimeline(
        timeline_id="t", fps=30, width=1280, height=720, scenes=scenes,
    )
    placements = place_scenes(tl)
    starts = [p.master_start_sec for p in placements]
    ends = [p.master_end_sec for p in placements]
    assert starts[0] == 0.0
    # Each subsequent scene starts at the previous source duration minus
    # the transition_out overlap.
    assert starts[1] == pytest.approx(2.0 - 0.3)
    assert starts[2] == pytest.approx(starts[1] + 2.0 - 0.3)
    # No negative starts.
    for s in starts:
        assert s >= 0.0
    # The overlap is exactly the previous scene's transition_out budget.
    for i in range(1, len(ends)):
        explicit_overlap_budget = placements[i - 1].transition_out_duration_sec
        actual_overlap = ends[i - 1] - starts[i]
        assert actual_overlap == pytest.approx(explicit_overlap_budget, abs=1e-6)


def test_place_with_zero_duration_scene_documented_behaviour() -> None:
    """A zero-duration scene cannot be constructed at the schema layer.

    Schema validator (EditorialScene._validate_scene) requires
    source_scene_duration_sec > 0. We assert this contract here so any
    future refactor that loosens it is caught.
    """
    import pytest
    from pydantic import ValidationError
    with pytest.raises(ValidationError):
        _scn(0, 0.0)


def test_place_frames_round_at_30fps() -> None:
    scn = _scn(0, 2.5)
    tl = EditorialTimeline(
        timeline_id="t", fps=30, width=1280, height=720, scenes=[scn],
    )
    placements = place_scenes(tl)
    p = placements[0]
    # 2.5 * 30 = 75 frames exactly.
    assert p.duration_frames == 75


def test_placement_for_raises_if_missing() -> None:
    tl = EditorialTimeline(
        timeline_id="t", fps=30, width=1280, height=720,
        scenes=[_scn(0, 1.0)],
    )
    placements = place_scenes(tl)
    with pytest.raises(KeyError):
        placement_for("nonexistent", placements)
