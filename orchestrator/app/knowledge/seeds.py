"""
Knowledge Source Seeds — L-U1 production knowledge.

This module contains the **initial seeds** for the knowledge registry.
These are the entries explicitly extracted from the documented sources:

    S1: Google Flow AI Creative Studio (Character Reference Sheets,
        Image Prompt Structure, Video Prompt Structure, @CHARACTER
        Reference System)
    S2: DINO AI Cinematic Dictionary (Camera Angles, Camera Movements)
    S3: Axen Reference Video Learner (PROMPT 11 — composition rules,
        voice rules)

Each seed function returns a list of KnowledgeEntry. The seed module
also returns the KnowledgeSource records so callers can register
provenance.

CRITICAL
--------
These seeds are **PRODUCTION-REFERENCE ONLY**. They do not embed any
copyrighted material — they capture reproducible production rules.
The entries are deliberately abstract (no specific scripts, scenes,
characters, branding, or assets are stored). Examples are
illustrative patterns, not specific verbatim text.

If a concept is INFERRED rather than EXPLICITLY stated by the source,
it is marked with `KnowledgeStatus.INFERENCE`.
"""

from __future__ import annotations

from typing import Iterable

from .schemas import (
    ExtractionStatus,
    KnowledgeDomain,
    KnowledgeEntry,
    KnowledgeSource,
    KnowledgeStatus,
    SourceType,
)


# ============================================================================
# Sources
# ============================================================================

SOURCE_GOOGLE_FLOW = KnowledgeSource(
    source_id="src_google_flow_v1",
    source_name="Google Flow AI Creative Studio — Character Reference & Prompt Patterns",
    source_type=SourceType.SYSTEM_PROMPT,
    source_section="Character Reference Sheet + Image/Video Prompt Structure",
    source_reference="https://labs.google/fx/tools/flow",
    confidence=1.0,
    version="1.0.0",
    notes=(
        "Reference template extracted from public Google Flow prompt "
        "patterns. Reproducible, abstract production rules only — no "
        "copyrighted scripts or assets are stored."
    ),
)


SOURCE_DINO_AI = KnowledgeSource(
    source_id="src_dino_ai_v1",
    source_name="DINO AI Cinematic Dictionary",
    source_type=SourceType.REFERENCE_DOCUMENT,
    source_section="Camera Angles + Camera Movement Terms",
    source_reference="https://drive.google.com/drive/folders/1VCDA3ej6JpzpaknoD82WXx0jkFN8K5nv",
    confidence=1.0,
    version="1.0.0",
    notes=(
        "Standard cinematography vocabulary. Reproducible bounded "
        "vocabulary."
    ),
)


SOURCE_AXEN_REF = KnowledgeSource(
    source_id="src_axen_ref_learner_v1",
    source_name="Axen Reference Video Learner — composition_rules.json + voice_rules.json",
    source_type=SourceType.CHANNEL_ANALYSIS,
    source_section="PROMPT 11 — composition + voice rules",
    source_reference="workspace/reference_videos/composition_rules.json + voice_rules.json (Prompt 11)",
    confidence=0.85,
    version="1.0.0",
    notes=(
        "Heuristically extracted composition rules from two sample "
        "videos. Confidence reflects heuristic classification accuracy "
        "(~5-10% border-case error per the Prompt 11 final report)."
    ),
)


# ============================================================================
# Helper
# ============================================================================

def _e(
    *,
    id: str,
    domain: KnowledgeDomain,
    name: str,
    description: str,
    rules: list[str],
    applicability: list[str],
    examples: list[str] | None = None,
    constraints: list[str] | None = None,
    status: KnowledgeStatus = KnowledgeStatus.EXPLICIT,
    tags: list[str] | None = None,
    version: str = "1.0.0",
) -> KnowledgeEntry:
    """Compact constructor for KnowledgeEntry seeds."""
    return KnowledgeEntry(
        id=id,
        domain=domain,
        name=name,
        description=description,
        rules=rules,
        constraints=constraints or [],
        examples=examples or [],
        applicability=applicability,
        status=status,
        version=version,
        tags=tags or [],
    )


# ============================================================================
# Google Flow seeds
# ============================================================================

def google_flow_seeds() -> list[KnowledgeEntry]:
    """KnowledgeEntries extracted from Google Flow patterns."""
    return [
        # ---- Character Reference Sheet ----
        _e(
            id="gf.charref.six_panel_layout",
            domain=KnowledgeDomain.CHARACTER_CONSISTENCY,
            name="6-Panel Character Reference Sheet Layout",
            description=(
                "A character reference sheet MUST show the same character "
                "across multiple panels to lock identity."
            ),
            rules=[
                "A reference sheet MUST include a full-body front view.",
                "A reference sheet MUST include a full-body side view.",
                "A reference sheet MUST include a full-body back view.",
                "A reference sheet MUST include a head turnaround (front / three-quarter / side).",
                "A reference sheet SHOULD include expression panels covering the character's main emotional range.",
                "A reference sheet MUST include a close-up of the signature prop.",
            ],
            applicability=["character", "character_consistency"],
            examples=[
                "Panels: full-body front / side / back, head turnaround, 4 expression panels, signature-prop close-up.",
            ],
            tags=["reference_sheet", "character", "google_flow"],
        ),
        _e(
            id="gf.charref.no_redesign_between_panels",
            domain=KnowledgeDomain.CHARACTER_CONSISTENCY,
            name="Reference-Sheet No-Redesign Rule",
            description=(
                "All panels in a reference sheet MUST show the EXACT same "
                "character, not variants."
            ),
            rules=[
                "All reference-sheet panels MUST share the same head shape.",
                "All reference-sheet panels MUST share the same face.",
                "All reference-sheet panels MUST share the same outline weight.",
                "All reference-sheet panels MUST share the same color palette.",
                "All reference-sheet panels MUST share the same proportions.",
                "The character MUST NOT be redesigned between panels.",
            ],
            applicability=["character", "character_consistency"],
            examples=[
                "A farmer character with hunched posture appears identically across all 6 panels; only the expression varies.",
            ],
            tags=["reference_sheet", "consistency", "google_flow"],
        ),
        _e(
            id="gf.charref.character_family",
            domain=KnowledgeDomain.CHARACTER_CONSISTENCY,
            name="Character-Family Lineage",
            description=(
                "Characters may belong to a family (shared visual lineage). "
                "Family members share a design language while remaining "
                "distinct."
            ),
            rules=[
                "Family members MUST share the round-head / eye-style / outline family.",
                "Family members MAY differ in posture, expression, palette, props.",
                "Use the @CHARACTER reference token consistently across prompts.",
            ],
            applicability=["character", "character_consistency"],
            examples=[
                "@FARMER and @ANCESTOR share the same round-head family.",
            ],
            tags=["family", "character", "google_flow"],
        ),
        _e(
            id="gf.charref.signature_props",
            domain=KnowledgeDomain.CHARACTER_CONSISTENCY,
            name="Signature Props Distinguish Characters",
            description=(
                "Every named character SHOULD carry a signature prop to "
                "make identity instantly recognizable."
            ),
            rules=[
                "A signature prop MUST appear consistently across panels.",
                "A signature prop SHOULD be drawn in a close-up panel.",
                "A signature prop SHOULD be echoed in scene prompts to anchor identity.",
            ],
            applicability=["character", "character_consistency"],
            examples=[
                "@FARMER: wooden hoe + wheat stalk.",
            ],
            tags=["signature_prop", "character", "google_flow"],
        ),

        # ---- Image Prompt Structure ----
        _e(
            id="gf.img.style_foundation",
            domain=KnowledgeDomain.IMAGE_PROMPT,
            name="Image Prompt Style Foundation",
            description=(
                "Every image prompt MUST establish the visual style before "
                "introducing the subject."
            ),
            rules=[
                "The style foundation MUST precede the subject in the prompt.",
                "The style foundation MUST specify outline style (e.g. 'bold black outlines').",
                "The style foundation MUST specify line quality (e.g. 'slightly imperfect sketchy marker lines').",
            ],
            applicability=["image_prompt"],
            examples=[
                "'Hand-drawn 2D doodle cartoon, flat colors, bold black outlines, slightly imperfect sketchy marker lines'.",
            ],
            tags=["image_prompt", "style", "google_flow"],
        ),
        _e(
            id="gf.img.subject_then_environment",
            domain=KnowledgeDomain.IMAGE_PROMPT,
            name="Image Prompt Subject → Environment Order",
            description=(
                "The subject is described first, then the environment, then "
                "any text overlay, then the background colour, then the "
                "constraints, then the format."
            ),
            rules=[
                "Subject comes before environment.",
                "Environment comes before effects / motion lines.",
                "Text overlay (if any) comes after subject and environment.",
                "Background colour comes after environment.",
                "Negative constraints come last.",
                "Format (aspect ratio, medium) comes at the very end.",
            ],
            applicability=["image_prompt"],
            examples=[
                "@MODERNYOU buried under a blanket, layered messy bed, background color cold cobalt blue, bold black ALL-CAPS 'MONDAY' top-left, no gradients, 16:9.",
            ],
            tags=["image_prompt", "structure", "google_flow"],
        ),
        _e(
            id="gf.img.negative_constraints",
            domain=KnowledgeDomain.NEGATIVE_CONSTRAINT,
            name="Image Prompt Negative Constraints",
            description=(
                "Image prompts SHOULD always declare a negative constraint "
                "list to prevent unwanted style drift."
            ),
            rules=[
                "An image prompt SHOULD forbid 'no gradients' for flat-style rendering.",
                "An image prompt SHOULD forbid 'no shadows' for flat-style rendering.",
                "An image prompt SHOULD forbid 'no textures' for flat-style rendering.",
                "An image prompt SHOULD forbid 'no photorealism' for cartoon rendering.",
                "An image prompt SHOULD forbid 'no 3D' for 2D rendering.",
                "An image prompt SHOULD forbid 'no extra limbs or fingers'.",
            ],
            applicability=["image_prompt"],
            examples=[
                "'no gradients, no shadows, no textures, no photorealism, no 3D, no extra limbs or fingers'.",
            ],
            tags=["negative", "image_prompt", "google_flow"],
        ),
        _e(
            id="gf.img.text_overlay",
            domain=KnowledgeDomain.FORMAT,
            name="Image Prompt Text Overlay Convention",
            description=(
                "Text overlays in image prompts use a fixed style."
            ),
            rules=[
                "Text overlays SHOULD be bold black ALL-CAPS.",
                "Text overlays SHOULD declare an explicit corner (e.g. 'top-left').",
            ],
            applicability=["image_prompt"],
            examples=[
                "bold black ALL-CAPS 'MONDAY' in the top-left corner.",
            ],
            tags=["text_overlay", "image_prompt", "google_flow"],
        ),

        # ---- Video Prompt Structure ----
        _e(
            id="gf.vid.motion_type_required",
            domain=KnowledgeDomain.VIDEO_PROMPT,
            name="Video Prompt Requires Explicit Motion Type",
            description=(
                "A video prompt MUST declare its motion type — that is "
                "what distinguishes it from an image prompt."
            ),
            rules=[
                "A video prompt MUST include 'frame-by-frame doodle motion' (or equivalent) for cell-style animation.",
                "A video prompt MUST include camera work (HOLD / PUSH-IN / SHAKE / etc).",
                "A video prompt MUST include a sound description at the end.",
                "A video prompt MUST NOT use 'no morphing artifacts' to forbid blended-frame generation.",
            ],
            applicability=["video_prompt"],
            examples=[
                "'frame-by-frame doodle motion — extreme close-up of a small red alarm clock jolting and rattling violently on a nightstand, jagged motion lines flickering and snapping around it, the little bell hammer buzzing. Camera holds with a tiny nervous shake then a slow push-in.'",
            ],
            tags=["video_prompt", "motion", "google_flow"],
        ),
        _e(
            id="gf.vid.sound_description",
            domain=KnowledgeDomain.SOUND,
            name="Video Prompt Sound Description",
            description=(
                "Every video prompt MUST include a sound description that "
                "anchors the audio production."
            ),
            rules=[
                "The sound description MUST start with the literal word 'Sound:'.",
                "The sound description MUST describe the dominant sound source (object, character, environment).",
                "The sound description MAY describe secondary cues (e.g. button-tap click).",
            ],
            applicability=["video_prompt"],
            examples=[
                "Sound: a harsh repeating alarm-clock buzzer ringing.",
                "Sound: a muffled alarm buzz cut by a single tired button-tap click.",
            ],
            tags=["sound", "video_prompt", "google_flow"],
        ),

        # ---- Camera vocabulary ----
        _e(
            id="dino.camera.shot_types",
            domain=KnowledgeDomain.CAMERA,
            name="Canonical Camera Shot Types",
            description=(
                "DINO AI Cinematic Dictionary provides a bounded shot-type "
                "vocabulary."
            ),
            rules=[
                "Use 'extreme_wide_shot' (EWS) for establishing shots.",
                "Use 'wide_shot' (WS) for environment context.",
                "Use 'medium_shot' (MS) for standard dialogue framing.",
                "Use 'close_up' (CU) for emotional focus.",
                "Use 'extreme_close_up' (ECU) for single-detail drama.",
                "Use 'over_the_shoulder' (OTS) for POV dialogue.",
                "Use 'point_of_view' (POV) for character perspective.",
                "Use 'dutch_angle' for unease / tension.",
                "Use 'birds_eye' for total-control perspective.",
                "Use 'worms_eye' for power / dominance.",
            ],
            applicability=["image_prompt", "video_prompt", "composition"],
            tags=["camera", "shot_type", "dino_ai"],
        ),
        _e(
            id="dino.camera.movement_types",
            domain=KnowledgeDomain.CAMERA_MOVEMENT,
            name="Canonical Camera Movement Types",
            description=(
                "DINO AI Cinematic Dictionary provides a bounded "
                "movement-type vocabulary."
            ),
            rules=[
                "Use 'hold' for a static camera.",
                "Use 'push_in' to focus / build tension.",
                "Use 'pull_out' to reveal / release.",
                "Use 'pan' for horizontal rotation.",
                "Use 'tilt' for vertical rotation.",
                "Use 'zoom' for focal-length change.",
                "Use 'tracking' to follow a subject.",
                "Use 'shake' for nervous / tension effects.",
                "Use 'orbit' to circle a subject.",
                "Use 'parallax' for layered-depth shift.",
            ],
            applicability=["video_prompt", "composition"],
            tags=["camera", "movement", "dino_ai"],
        ),

        # ---- Motion language ----
        _e(
            id="dino.motion.frame_by_frame",
            domain=KnowledgeDomain.MOTION,
            name="Frame-by-Frame Doodle Motion",
            description=(
                "Hand-drawn 2D doodle animation SHOULD use frame-by-frame "
                "cell motion, not interpolated frames."
            ),
            rules=[
                "Frame-by-frame motion SHOULD use jagged motion lines to convey shake / impact.",
                "Frame-by-frame motion SHOULD describe a body-language change (e.g. 'eye cracking open into a dreading frown').",
                "Frame-by-frame motion MAY include a faint impact jolt on physical metaphors.",
            ],
            applicability=["video_prompt"],
            examples=[
                "jagged motion lines flickering and snapping around it, the little bell hammer buzzing.",
            ],
            tags=["motion", "frame_by_frame", "doodle", "google_flow"],
        ),

        # ---- Background ----
        _e(
            id="gf.img.background_color",
            domain=KnowledgeDomain.IMAGE_PROMPT,
            name="Image Prompt Background Color",
            description=(
                "Every image prompt MUST declare a background colour "
                "(solid or near-solid)."
            ),
            rules=[
                "Background colour is declared via 'background color [NAME]'.",
                "Background colour SHOULD match the scene's emotional register (e.g. cold cobalt blue for morning dread).",
            ],
            applicability=["image_prompt"],
            examples=[
                "background color cold cobalt blue.",
            ],
            tags=["background", "color", "image_prompt", "google_flow"],
        ),

        # ---- Format ----
        _e(
            id="gf.format.aspect_and_medium",
            domain=KnowledgeDomain.FORMAT,
            name="Image / Video Format Declaration",
            description=(
                "Image and video prompts MUST declare the aspect ratio and "
                "the medium."
            ),
            rules=[
                "Image prompt format MUST declare aspect ratio (e.g. '16:9').",
                "Image prompt format MUST declare medium (e.g. 'educational YouTube explainer doodle style').",
                "Video prompt format MUST declare aspect ratio and '16:9 animation'.",
            ],
            applicability=["image_prompt", "video_prompt", "format"],
            examples=[
                "16:9, educational YouTube explainer doodle style.",
                "16:9 animation.",
            ],
            tags=["format", "aspect_ratio", "google_flow"],
        ),

        # ---- Continuity ----
        _e(
            id="gf.continuity.identity_lock",
            domain=KnowledgeDomain.CONTINUITY,
            name="Identity Lock Across Scenes",
            description=(
                "Character identity MUST stay locked across scenes that "
                "feature the same character."
            ),
            rules=[
                "Re-use the @CHARACTER token across all prompts that reference the same character.",
                "Do NOT redesign the character between scenes.",
                "Do NOT change the character's signature prop between scenes unless the story demands it.",
            ],
            applicability=["character", "continuity", "image_prompt", "video_prompt"],
            tags=["continuity", "character", "google_flow"],
        ),

        # ---- Visual Style foundations ----
        _e(
            id="gf.style.hand_drawn_doodle",
            domain=KnowledgeDomain.VISUAL_STYLE,
            name="Hand-Drawn 2D Doodle Cartoon Style",
            description=(
                "A canonical visual style for educational explainer videos."
            ),
            rules=[
                "Style foundation: 'Hand-drawn 2D doodle cartoon'.",
                "Outline: 'bold black outlines'.",
                "Line quality: 'slightly imperfect sketchy marker lines'.",
                "Fills: 'flat single-color fills'.",
                "FORBID: gradients, shadows, textures, photorealism, 3D rendering.",
            ],
            applicability=["image_prompt", "video_prompt", "visual_style"],
            examples=[
                "Hand-drawn 2D doodle cartoon, flat colors, bold black outlines, slightly imperfect sketchy marker lines.",
            ],
            tags=["style", "doodle", "google_flow"],
        ),

        # ---- Character (general) ----
        _e(
            id="gf.character.head_outline_proportions",
            domain=KnowledgeDomain.CHARACTER,
            name="Head / Outline / Proportions",
            description=(
                "Common doodle-style character design tokens that recur "
                "in Google Flow reference sheets."
            ),
            rules=[
                "A doodle-style character often has a large round head relative to a minimal body.",
                "Doodle-style eyes are typically dots.",
                "Doodle-style eyebrows are typically thick expressive marker brows.",
                "Doodle-style bodies are minimal — single-color tunic / stick-figure proportion.",
                "Bold black outlines SHOULD be consistent across panels.",
            ],
            applicability=["character", "character_consistency"],
            examples=[
                "Large round head, dot eyes, thick expressive marker brows, minimal body.",
            ],
            tags=["character", "design", "doodle", "google_flow"],
        ),
        _e(
            id="gf.character.wardrobe_signature_color",
            domain=KnowledgeDomain.CHARACTER,
            name="Wardrobe + Signature Color",
            description=(
                "Each named character carries a wardrobe and a "
                "signature color that together create identity."
            ),
            rules=[
                "Each named character MUST declare a signature color (hex).",
                "Wardrobe description MUST be concrete enough to draw (e.g. 'plain rough tunic, bare feet').",
                "Signature color SHOULD appear in the character's primary fills.",
            ],
            applicability=["character"],
            examples=[
                "@FARMER: dull earth-brown #8B5E3C, plain rough tunic, bare feet.",
            ],
            tags=["character", "wardrobe", "google_flow"],
        ),
    ]


# ============================================================================
# DINO AI seeds — pure vocabulary additions (already covered above).
# We add one bounded vocabulary entry that ties shot + movement together.
# ============================================================================

def dino_ai_seeds() -> list[KnowledgeEntry]:
    return [
        _e(
            id="dino.shot_movement_pairing",
            domain=KnowledgeDomain.COMPOSITION,
            name="Shot + Movement Pairing",
            description=(
                "Camera movement should reinforce the shot type, not "
                "contradict it."
            ),
            rules=[
                "A close-up SHOULDN'T pair with a wide pull-out unless the contrast is intentional.",
                "A wide shot can pair with a slow push-in to introduce a subject.",
                "An ECU SHOULD often pair with HOLD or a tiny SHAKE for tension.",
                "An OTS SHOULDN'T pair with orbit (breaks dialogue framing).",
            ],
            applicability=["video_prompt", "composition"],
            status=KnowledgeStatus.INFERENCE,
            tags=["camera", "composition", "dino_ai"],
        ),
    ]


# ============================================================================
# Axen reference learner seeds — composition + voice rules.
# ============================================================================

def axen_learner_seeds() -> list[KnowledgeEntry]:
    return [
        _e(
            id="axen.composition.three_state_loop",
            domain=KnowledgeDomain.COMPOSITION,
            name="3-State Visual Loop",
            description=(
                "Reference videos alternate between three canonical "
                "visual states: animated_2d, talking_head, text_overlay."
            ),
            rules=[
                "Each EditorialScene MUST declare a visual_state.",
                "Transition between different states uses a fade of 0.3-0.5 s.",
                "Transition within the same state uses a CUT.",
                "Subtitles live in the lower-third zone (y: 75-95%), white with a dark stroke.",
                "The video MUST NOT letterbox; it MUST fill 1920x1080.",
                "A scene transition occurs every 15-60 s (2-3 state changes per minute).",
                "The colour palette MUST visually separate animated vs talking_head scenes.",
            ],
            applicability=["composition", "video_prompt"],
            status=KnowledgeStatus.EXPLICIT,
            tags=["composition", "axen", "reference_video", "visual_state"],
        ),
        _e(
            id="axen.voice.loudness_target",
            domain=KnowledgeDomain.SOUND,
            name="Voice Loudness Target",
            description=(
                "Narration voice is mastered to a defined loudness target."
            ),
            rules=[
                "Mean volume MUST be approximately -23 dBFS (±2 dB).",
                "Max volume MUST be ≤ -1 dBFS (headroom).",
                "Integrated loudness target SHOULD be -16 LUFS.",
                "Speech percentage SHOULD be ≥ 95%.",
                "There SHOULD be no silences ≥ 1 s and no silences ≥ 3 s.",
            ],
            applicability=["sound", "voice", "audio"],
            status=KnowledgeStatus.EXPLICIT,
            tags=["voice", "loudness", "axen"],
        ),
        _e(
            id="axen.voice.no_music_no_sfx",
            domain=KnowledgeDomain.SOUND,
            name="No Music / SFX in v1",
            description=(
                "v1 reference videos carry pure voice — no music, no SFX, "
                "no ambient."
            ),
            rules=[
                "v1 audio MUST be voice-only.",
                "Music / SFX / ambience are explicitly OUT OF SCOPE for v1.",
            ],
            applicability=["sound", "audio"],
            status=KnowledgeStatus.PROJECT_RULE,
            tags=["voice", "music", "sfx", "axen"],
        ),
        _e(
            id="axen.voice.tts_priority",
            domain=KnowledgeDomain.SOUND,
            name="TTS Provider Priority",
            description=(
                "Project decided on a TTS provider priority for the v1 "
                "reference style."
            ),
            rules=[
                "TTS preference order is ElevenLabs > OpenAI TTS > gTTS.",
                "Voice MUST be male, 28-45 years old, warm register.",
            ],
            applicability=["sound", "voice", "tts"],
            status=KnowledgeStatus.PROJECT_RULE,
            tags=["voice", "tts", "axen"],
        ),
    ]


# ============================================================================
# Master loader
# ============================================================================

def default_seeds() -> list[KnowledgeEntry]:
    """All default seeds from the L-U1 knowledge sources."""
    return google_flow_seeds() + dino_ai_seeds() + axen_learner_seeds()


def default_sources() -> list[KnowledgeSource]:
    """The KnowledgeSource records paired with the default seeds."""
    return [
        SOURCE_GOOGLE_FLOW,
        SOURCE_DINO_AI,
        SOURCE_AXEN_REF,
    ]
