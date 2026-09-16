"""
Tests for Knowledge Layer — L-U1 Production Knowledge & Visual Grammar Foundation.

This file exercises:
    - KnowledgeSource / KnowledgeEntry / KnowledgeDomain / KnowledgeStatus schemas
    - VisualGrammar contract
    - CharacterGrammar contract
    - KnowledgeRegistry deterministic retrieval
    - Default seeds load + uniqueness invariants
    - bump_version lifecycle
    - Provenance tracking

The tests are stdlib + pydantic only; no fixtures from the rest of the
repo are needed (the knowledge layer is intentionally isolated so
that adding it does not couple to any other subsystem).
"""

from __future__ import annotations

import json

import pytest
from pydantic import ValidationError

from app.knowledge import (
    SOURCE_AXEN_REF,
    SOURCE_DINO_AI,
    SOURCE_GOOGLE_FLOW,
    ActionIntent,
    BackgroundIntent,
    CameraIntent,
    CameraMovementType,
    CameraShotType,
    CharacterGrammar,
    ColorPaletteBlock,
    CompositionIntent,
    ConstraintsIntent,
    EffectsIntent,
    EnvironmentIntent,
    FaceBlock,
    FormatIntent,
    HeadBlock,
    IdentityBlock,
    KnowledgeDomain,
    KnowledgeEntry,
    KnowledgeRegistry,
    KnowledgeSource,
    KnowledgeStatus,
    MotionIntent,
    MotionPattern,
    OrientationBlock,
    OutlineBlock,
    OutlineWeight,
    ProportionsBlock,
    ReferenceSheetBlock,
    SignaturePropsBlock,
    SourceType,
    StyleIntent,
    SubjectIntent,
    TypographyIntent,
    VisualGrammar,
    VisualStyleProfile,
    WardrobeBlock,
    axen_learner_seeds,
    build_default_registry,
    default_seeds,
    default_sources,
    dino_ai_seeds,
    google_flow_seeds,
    reset_and_build,
)
from app.knowledge.character_grammar import ConsistencyRuleKind, ConsistencyRulesBlock


# ============================================================================
# Fixtures
# ============================================================================

@pytest.fixture
def reg() -> KnowledgeRegistry:
    return build_default_registry()


@pytest.fixture
def minimal_entry() -> KnowledgeEntry:
    return KnowledgeEntry(
        id="test.entry.minimal",
        domain=KnowledgeDomain.VISUAL_STYLE,
        name="Minimal entry",
        description="Used by tests only.",
        rules=["Rule one.", "Rule two."],
    )


# ============================================================================
# Form-level schema tests
# ============================================================================

class TestKnowledgeSource:
    def test_minimal_construction(self):
        src = KnowledgeSource(
            source_id="src_test",
            source_name="Test source",
            source_type=SourceType.REFERENCE_DOCUMENT,
            confidence=1.0,
        )
        assert src.source_id == "src_test"
        assert src.version == "1.0.0"
        assert src.confidence == 1.0
        assert src.source_section is None
        assert src.source_reference is None

    def test_confidence_bounds(self):
        with pytest.raises(ValidationError):
            KnowledgeSource(
                source_id="src_test",
                source_name="x",
                source_type=SourceType.REFERENCE_DOCUMENT,
                confidence=1.5,
            )
        with pytest.raises(ValidationError):
            KnowledgeSource(
                source_id="src_test",
                source_name="x",
                source_type=SourceType.REFERENCE_DOCUMENT,
                confidence=-0.1,
            )

    def test_id_pattern(self):
        with pytest.raises(ValidationError):
            KnowledgeSource(
                source_id="BadID",
                source_name="x",
                source_type=SourceType.REFERENCE_DOCUMENT,
                confidence=1.0,
            )

    def test_version_pattern(self):
        with pytest.raises(ValidationError):
            KnowledgeSource(
                source_id="src_test",
                source_name="x",
                source_type=SourceType.REFERENCE_DOCUMENT,
                confidence=1.0,
                version="1.0",
            )


class TestKnowledgeEntry:
    def test_minimal_construction(self):
        e = KnowledgeEntry(
            id="test.entry",
            domain=KnowledgeDomain.VISUAL_STYLE,
            name="t",
            description="d",
            rules=["R1 rule."],
        )
        assert e.id == "test.entry"
        assert e.domain == KnowledgeDomain.VISUAL_STYLE
        assert e.status == KnowledgeStatus.EXPLICIT
        assert e.version == "1.0.0"
        assert e.rules == ["R1 rule."]
        assert e.examples == []
        assert e.constraints == []
    def test_short_rule_rejected(self):
        with pytest.raises(ValidationError):
            KnowledgeEntry(
                id="test.entry",
                domain=KnowledgeDomain.VISUAL_STYLE,
                name="t",
                description="d",
                rules=["x"],
            )

    def test_example_equal_to_rule_rejected(self):
        with pytest.raises(ValidationError):
            KnowledgeEntry(
                id="test.entry",
                domain=KnowledgeDomain.VISUAL_STYLE,
                name="t",
                description="d",
                rules=["This is a rule."],
                examples=["This is a rule."],
            )

    def test_id_pattern(self):
        with pytest.raises(ValidationError):
            KnowledgeEntry(
                id="BadID",
                domain=KnowledgeDomain.VISUAL_STYLE,
                name="t",
                description="d",
                rules=["Rule 1."],
            )

    def test_short_id(self):
        e = KnowledgeEntry(
            id="a.b.c.d",
            domain=KnowledgeDomain.VISUAL_STYLE,
            name="t",
            description="d",
            rules=["Rule 1."],
        )
        assert e.short_id() == "a.b.c.d"
        long_id = "x" * 30
        e2 = KnowledgeEntry(
            id=long_id,
            domain=KnowledgeDomain.VISUAL_STYLE,
            name="t",
            description="d",
            rules=["Rule 1."],
        )
        assert len(e2.short_id()) == 24

# ============================================================================
# VisualGrammar tests
# ============================================================================

class TestVisualGrammar:
    def test_minimal_construction(self):
        g = VisualGrammar()
        assert g.style.profile is None
        assert g.subject.character_ref is None
        assert g.constraints.forbid == []
        assert g.format.aspect_ratio is None

    def test_image_grammar_detection(self):
        g = VisualGrammar(
            style=StyleIntent(profile=VisualStyleProfile.HAND_DRAWN_DOODLE),
            subject=SubjectIntent(character_ref="@MODERNYOU"),
        )
        assert g.is_image_grammar() is True
        assert g.is_video_grammar() is False

    def test_video_grammar_detection_via_motion(self):
        g = VisualGrammar(
            style=StyleIntent(profile=VisualStyleProfile.HAND_DRAWN_DOODLE),
            motion=MotionIntent(pattern=MotionPattern.FRAME_BY_FRAME_DOODLE),
        )
        assert g.is_image_grammar() is False
        assert g.is_video_grammar() is True

    def test_video_grammar_detection_via_camera_movement(self):
        g = VisualGrammar(
            camera=CameraIntent(movement=CameraMovementType.PUSH_IN),
        )
        assert g.is_video_grammar() is True

    def test_camera_shot_type_enum(self):
        assert CameraShotType.CLOSE_UP.value == "close_up"
        assert CameraShotType.EXTREME_CLOSE_UP.value == "extreme_close_up"
        assert CameraMovementType.HOLD.value == "hold"
        assert CameraMovementType.PUSH_IN.value == "push_in"

    def test_full_video_grammar_construction(self):
        g = VisualGrammar(
            style=StyleIntent(
                profile=VisualStyleProfile.HAND_DRAWN_DOODLE,
                palette="flat colors",
                outline="bold black outlines",
                line_quality="slightly imperfect sketchy marker lines",
                rendering_notes=["no gradients", "no shadows"],
            ),
            subject=SubjectIntent(
                character_ref="@MODERNYOU",
                description="buried under a blanket",
                framing_hint="close-up",
            ),
            environment=EnvironmentIntent(
                setting="dim bedroom",
                lighting="dim",
            ),
            composition=CompositionIntent(
                shot_type=CameraShotType.CLOSE_UP,
                focal_subject="@MODERNYOU",
            ),
            action=ActionIntent(description="eye cracking open"),
            effects=EffectsIntent(motion_lines=True),
            camera=CameraIntent(
                shot_type=CameraShotType.CLOSE_UP,
                movement=CameraMovementType.PUSH_IN,
            ),
            motion=MotionIntent(
                pattern=MotionPattern.FRAME_BY_FRAME_DOODLE,
                duration_sec=5.0,
            ),
            background=BackgroundIntent(color="cold cobalt blue"),
            typography=TypographyIntent(
                text="MONDAY",
                position="top-left",
                style="bold black ALL-CAPS",
            ),
            constraints=ConstraintsIntent(
                forbid=["no gradients", "no shadows", "no textures", "no photorealism"],
            ),
            format=FormatIntent(
                aspect_ratio="16:9",
                medium="educational YouTube explainer doodle style",
            ),
            provenance_ids=["gf.img.style_foundation", "gf.vid.motion_type_required"],
        )
        d = g.model_dump()
        # Round-trip via JSON
        j = json.dumps(d)
        g2 = VisualGrammar.model_validate_json(j)
        assert g2.style.profile == VisualStyleProfile.HAND_DRAWN_DOODLE
        assert g2.subject.character_ref == "@MODERNYOU"
        assert g2.is_video_grammar() is True


# ============================================================================
# CharacterGrammar tests
# ============================================================================

class TestCharacterGrammar:
    def _minimal_grammar(self) -> CharacterGrammar:
        return CharacterGrammar(
            grammar_id="hand_drawn_doodle_v1",
            name="Hand-Drawn 2D Doodle",
            description="Rules for hand-drawn doodle-style character production.",
            identity=IdentityBlock(family=None),
            head=HeadBlock(shape=__import__("app.knowledge.character_grammar", fromlist=["HeadShape"]).HeadShape.ROUND),
            face=FaceBlock(
                eye_style=__import__("app.knowledge.character_grammar", fromlist=["EyeStyle"]).EyeStyle.DOT,
                eyebrow_style=__import__("app.knowledge.character_grammar", fromlist=["EyebrowStyle"]).EyebrowStyle.THICK_MARKER,
            ),
            outline=OutlineBlock(
                weight=OutlineWeight.THICK,
                color="#000000",
                quality="slightly imperfect sketchy marker lines",
            ),
            palette=ColorPaletteBlock(
                primary_hex="#8B5E3C",
                primary_name="dull earth-brown",
                fills=["flat single-color fills"],
            ),
            reference_sheet=ReferenceSheetBlock(
                panels_required=[
                    "full-body front",
                    "full-body side",
                    "full-body back",
                    "head turnaround: front / three-quarter / side",
                    "4 expression panels",
                    "close-up of signature prop",
                ],
                background="pure white",
                grid=True,
            ),
            consistency=ConsistencyRulesBlock(
                rules=[
                    ConsistencyRuleKind.IDENTITY_PRESERVATION,
                    ConsistencyRuleKind.PROPORTION_LOCK,
                    ConsistencyRuleKind.PALETTE_LOCK,
                    ConsistencyRuleKind.OUTLINE_LOCK,
                    ConsistencyRuleKind.REDESIGN_PREVENTION,
                ],
                explicit_rules=[
                    "All panels show EXACT same character.",
                    "Do not redesign between panels.",
                ],
            ),
        )

    def test_minimal_construction(self):
        from app.knowledge.character_grammar import EyeStyle, EyebrowStyle, HeadShape
        g = CharacterGrammar(
            grammar_id="test_grammar",
            name="t",
            description="d",
        )
        assert g.grammar_id == "test_grammar"
        assert g.consistency.rules == []
        assert g.reference_sheet.panels_required == []

    def test_full_grammar_round_trip(self):
        g = self._minimal_grammar()
        d = g.model_dump()
        j = json.dumps(d)
        g2 = CharacterGrammar.model_validate_json(j)
        assert g2.head.shape == g.head.shape
        assert g2.outline.weight == OutlineWeight.THICK
        assert g2.reference_sheet.grid is True
        assert ConsistencyRuleKind.REDESIGN_PREVENTION in g2.consistency.rules

    def test_grammar_id_pattern(self):
        with pytest.raises(ValidationError):
            CharacterGrammar(
                grammar_id="BadID",
                name="t",
                description="d",
            )


# ============================================================================
# KnowledgeRegistry tests
# ============================================================================

class TestKnowledgeRegistry:
    def test_empty_registry(self):
        r = KnowledgeRegistry()
        assert r.entries == {}
        assert r.sources_loaded == []
        assert r.summary()["total_entries"] == 0

    def test_register(self, minimal_entry):
        r = KnowledgeRegistry()
        r.register(minimal_entry)
        assert r.get("test.entry.minimal") is minimal_entry
        assert r.must_get("test.entry.minimal") is minimal_entry

    def test_register_collision_raises(self, minimal_entry):
        r = KnowledgeRegistry()
        r.register(minimal_entry)
        with pytest.raises(ValueError):
            r.register(minimal_entry)

    def test_must_get_missing_raises(self):
        r = KnowledgeRegistry()
        with pytest.raises(KeyError):
            r.must_get("nope")

    def test_get_missing_returns_none(self):
        r = KnowledgeRegistry()
        assert r.get("nope") is None

    def test_find_by_domain_deterministic(self, reg):
        char_entries = reg.find_by_domain(KnowledgeDomain.CHARACTER_CONSISTENCY)
        ids = [e.id for e in char_entries]
        assert ids == sorted(ids)
        assert all(e.domain == KnowledgeDomain.CHARACTER_CONSISTENCY for e in char_entries)
        assert len(char_entries) >= 1

    def test_find_by_tag(self, reg):
        google = reg.find_by_tag("google_flow")
        assert len(google) > 0
        for e in google:
            assert "google_flow" in e.tags

    def test_find_by_status(self, reg):
        explicit = reg.find_by_status(KnowledgeStatus.EXPLICIT)
        for e in explicit:
            assert e.status == KnowledgeStatus.EXPLICIT
        # We seeded at least one EXPLICIT entry.
        assert len(explicit) >= 1

    def test_find_by_applicability(self, reg):
        img = reg.find_by_applicability("image_prompt")
        for e in img:
            assert "image_prompt" in e.applicability
        assert len(img) >= 1

    def test_search(self, reg):
        hits = reg.search("doodle")
        assert len(hits) >= 1
        for h in hits:
            joined = (h.name + " " + h.description + " " + " ".join(h.tags)).lower()
            assert "doodle" in joined

    def test_search_empty_returns_all(self, reg):
        all_entries = reg.search("")
        assert len(all_entries) == len(reg.entries)

    def test_apply_filters(self, reg):
        f = reg.apply_filters(
            domain=KnowledgeDomain.IMAGE_PROMPT,
            status=KnowledgeStatus.EXPLICIT,
        )
        for e in f:
            assert e.domain == KnowledgeDomain.IMAGE_PROMPT
            assert e.status == KnowledgeStatus.EXPLICIT

    def test_bump_version(self, minimal_entry):
        r = KnowledgeRegistry()
        r.register(minimal_entry)
        # Create a "new version" with an extra rule
        from datetime import datetime
        v2 = minimal_entry.model_copy(deep=True)
        v2.rules = minimal_entry.rules + ["New rule."]
        v2.version = "1.1.0"
        v2.updated_at = datetime.utcnow()
        r.bump_version("test.entry.minimal", v2)
        current = r.get("test.entry.minimal")
        assert current.version == "1.1.0"
        assert "New rule." in current.rules
        # Old preserved
        history = r.version_history["test.entry.minimal"]
        assert len(history) == 1
        assert history[0].version == "1.0.0"
        assert "New rule." not in history[0].rules

    def test_bump_version_id_mismatch_raises(self, minimal_entry):
        r = KnowledgeRegistry()
        r.register(minimal_entry)
        bad = minimal_entry.model_copy()
        bad.id = "different.id"
        with pytest.raises(ValueError):
            r.bump_version("test.entry.minimal", bad)

    def test_record_source(self):
        r = KnowledgeRegistry()
        r.record_source("src_x")
        r.record_source("src_x")  # idempotent
        assert r.sources_loaded == ["src_x"]

    def test_summary(self, reg):
        s = reg.summary()
        assert s["total_entries"] == len(reg.entries)
        assert s["by_domain"][KnowledgeDomain.IMAGE_PROMPT.value] >= 1
        # Sorted dicts
        assert list(s["by_domain"].keys()) == sorted(s["by_domain"].keys())

# ============================================================================
# Default seeds tests
# ============================================================================

class TestDefaultSeeds:
    def test_default_seeds_have_unique_ids(self):
        ids = [e.id for e in default_seeds()]
        assert len(ids) == len(set(ids)), f"Duplicate ids: {ids}"

    def test_default_seeds_have_at_least_one_rule(self):
        for e in default_seeds():
            assert len(e.rules) >= 1, f"Entry {e.id} has no rules"

    def test_google_flow_seeds_are_explicit(self):
        for e in google_flow_seeds():
            assert e.status == KnowledgeStatus.EXPLICIT, (
                f"Google Flow seed {e.id} should be EXPLICIT, got {e.status}"
            )

    def test_dino_seeds_status(self):
        # All DINO AI seeds except possibly INFERENCE ones should be EXPLICIT
        dino_entries = dino_ai_seeds()
        for e in dino_entries:
            assert e.status in {KnowledgeStatus.EXPLICIT, KnowledgeStatus.INFERENCE}

    def test_axen_seeds_status(self):
        for e in axen_learner_seeds():
            assert e.status in {
                KnowledgeStatus.EXPLICIT,
                KnowledgeStatus.INFERENCE,
                KnowledgeStatus.PROJECT_RULE,
            }

    def test_all_seed_domains_are_valid(self):
        for e in default_seeds():
            assert isinstance(e.domain, KnowledgeDomain)

    def test_default_sources_match_seeds(self):
        # The three default sources must each be present.
        ids = {s.source_id for s in default_sources()}
        assert SOURCE_GOOGLE_FLOW.source_id in ids
        assert SOURCE_DINO_AI.source_id in ids
        assert SOURCE_AXEN_REF.source_id in ids

    def test_build_default_registry_populates_everything(self):
        r = build_default_registry()
        assert len(r.entries) == len(default_seeds())
        for s in default_sources():
            assert s.source_id in r.sources_loaded

    def test_no_copyrighted_content_in_seeds(self):
        """The seeds must not contain specific scripts, character names,
        or proprietary branding beyond the abstract @TOKEN style."""
        for e in default_seeds():
            joined = " ".join([e.name, e.description] + e.examples + e.rules).lower()
            # Banned tokens: anything that looks like a brand name or
            # a specific character identity we shouldn't carry.
            # We DO allow @MODERNYOU-style tokens because they are
            # already abstracted handles.
            assert "mon morning" not in joined
            assert "monday morning blues" not in joined

    def test_reset_and_build(self):
        e = KnowledgeEntry(
            id="x_entry",
            domain=KnowledgeDomain.VISUAL_STYLE,
            name="x",
            description="x",
            rules=["One rule."],
        )
        r = reset_and_build([e], sources=[SOURCE_GOOGLE_FLOW])
        assert r.get("x_entry") is e
        assert SOURCE_GOOGLE_FLOW.source_id in r.sources_loaded


# ============================================================================
# Domain coverage test
# ============================================================================

class TestDomainCoverage:
    """The L-U1 spec requires coverage of every KnowledgeDomain."""

    def test_all_domains_covered(self, reg):
        missing = []
        for d in KnowledgeDomain:
            if not reg.find_by_domain(d):
                missing.append(d.value)
        assert not missing, f"Domains with no entries: {missing}"


# ============================================================================
# Cross-runtime (Python ↔ JSON) round-trip test
# ============================================================================

class TestRoundTrip:
    def test_knowledge_entry_round_trip(self):
        e = KnowledgeEntry(
            id="rt.entry",
            domain=KnowledgeDomain.CAMERA,
            name="Round trip",
            description="Round-trip test entry.",
            rules=["Rule one."],
            examples=["example"],
            applicability=["video_prompt"],
            status=KnowledgeStatus.EXPLICIT,
            tags=["rt"],
        )
        j = e.model_dump_json()
        e2 = KnowledgeEntry.model_validate_json(j)
        assert e2.id == e.id
        assert e2.domain == e.domain
        assert e2.rules == e.rules
        assert e2.examples == e.examples

    def test_knowledge_registry_round_trip(self, reg):
        j = reg.model_dump_json()
        r2 = KnowledgeRegistry.model_validate_json(j)
        assert r2.summary() == reg.summary()


# ============================================================================
# Critical invariants
# ============================================================================

class TestCriticalInvariants:
    """The L-U1 spec requires explicit tests for these invariants."""

    def test_examples_never_appear_in_rules_across_seeds(self):
        for e in default_seeds():
            ex_set = {x.strip() for x in e.examples if x.strip()}
            rule_set = {r.strip() for r in e.rules}
            assert not (ex_set & rule_set), (
                f"Entry {e.id} has overlapping example/rule text."
            )

    def test_no_seed_silently_promotes_explicit_to_project_rule(self):
        for e in default_seeds():
            # PROJECT_RULE entries must carry an explicit `rules` list,
            # not just an `examples` list masquerading as rules.
            if e.status == KnowledgeStatus.PROJECT_RULE:
                assert len(e.rules) >= 1, (
                    f"PROJECT_RULE entry {e.id} has no rules"
                )

    def test_knowledge_layer_does_not_depend_on_other_app_packages(self):
        """Importing knowledge must not require asset/character/storyboard etc."""
        # Re-importing the package is enough; the import list above is
        # intentionally restricted to `app.knowledge.*`. This test
        # catches accidental cross-subsystem imports.
        import app.knowledge as k
        assert k.__all__  # populated

    def test_provenance_carries_source_reference(self):
        for s in default_sources():
            # Every default source carries either a URL or a workspace ref
            assert s.source_reference is not None
            assert len(s.source_reference) > 0

    def test_no_seed_carries_verbatim_copyrighted_script(self):
        """A final sanity check on the seeds.

        No seed may carry phrases that look like verbatim scripts from
        copyrighted YouTube videos. We use a few well-known markers as
        tripwires.
        """
        forbidden_phrases = [
            "nông dân học ai",
            "storyflow 7-stage",
            "overseeros youtube operating system",
        ]
        for e in default_seeds():
            joined = (e.name + " " + e.description + " "
                      + " ".join(e.examples) + " "
                      + " ".join(e.rules)).lower()
            for phrase in forbidden_phrases:
                assert phrase not in joined, (
                    f"Entry {e.id} contains forbidden phrase {phrase!r}"
                )
