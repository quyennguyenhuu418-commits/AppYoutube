"""
Character SVG Generation System — produces deterministic SVG character components
from CharacterDefinitions.

This module generates:
    - Canonical base character SVG (the stick figure with correct color/style)
    - Pose variant SVGs (8 renderer-supported poses)
    - Expression variant SVGs (11 canonical expressions)

Design principles:
    - SVG is the primary format (vector, scalable, editable)
    - All SVG uses a canonical coordinate system (200x200 viewBox)
    - No external references, no scripts, no animations embedded in SVGs
    - Components are separated: head, torso, limbs for future animation
    - Output is deterministic: same CharacterDefinition → same SVG

The existing renderer (renderer/src/components/Character.tsx) already has 8 pose
variants hardcoded. This SVG system provides a richer component hierarchy that
can be used by future animation engines.
"""
from __future__ import annotations

import hashlib
import re
from pathlib import Path
from typing import Any

from app.schemas.character import (
    CharacterDefinition,
    ExpressionDefinition,
    ExpressionLabel,
    PoseDefinition,
)


# ============================================================================
# SVG Coordinate Constants
# ============================================================================

SVG_WIDTH = 200
SVG_HEIGHT = 400
VIEW_BOX = f"0 0 {SVG_WIDTH} {SVG_HEIGHT}"
CENTER_X = SVG_WIDTH // 2

# Stick figure proportions (matching Character.tsx conventions)
HEAD_RADIUS = 20
HEAD_CX = CENTER_X
HEAD_CY = 40
NECK_Y = HEAD_CY + HEAD_RADIUS
TORSO_TOP_Y = NECK_Y + 5
TORSO_BOTTOM_Y = TORSO_TOP_Y + 80
TORSO_WIDTH = 30
ARM_LENGTH = 60
LEG_LENGTH = 80
LINE_WIDTH = 4


# ============================================================================
# SVG Building Blocks
# ============================================================================

def _head_svg(character: CharacterDefinition) -> str:
    """Generate the SVG head (circle + face components)."""
    color = character.color
    skin = character.color_palette.skin_tone or "#8D5524"
    outline = character.color_palette.outline

    head_elem = f'<circle cx="{HEAD_CX}" cy="{HEAD_CY}" r="{HEAD_RADIUS}" fill="{skin}" stroke="{outline}" stroke-width="2"/>'
    # Simple eyes
    eye_y = HEAD_CY - 3
    eye_left_x = HEAD_CX - 7
    eye_right_x = HEAD_CX + 7
    eye_elem = f'<circle cx="{eye_left_x}" cy="{eye_y}" r="3" fill="{outline}"/><circle cx="{eye_right_x}" cy="{eye_y}" r="3" fill="{outline}"/>'
    # Simple mouth
    mouth_y = HEAD_CY + 8
    mouth_elem = f'<line x1="{HEAD_CX - 5}" y1="{mouth_y}" x2="{HEAD_CX + 5}" y2="{mouth_y}" stroke="{outline}" stroke-width="2" stroke-linecap="round"/>'

    return f'<g id="head">{head_elem}{eye_elem}{mouth_elem}</g>'


def _torso_svg(character: CharacterDefinition) -> str:
    """Generate the SVG torso."""
    color = character.color
    clothing = character.color_palette.clothing_primary or color
    outline = character.color_palette.outline

    return (
        f'<line x1="{CENTER_X}" y1="{NECK_Y}" x2="{CENTER_X}" y2="{TORSO_BOTTOM_Y}" '
        f'stroke="{clothing}" stroke-width="{LINE_WIDTH + 2}" stroke-linecap="round"/>'
        f'<line x1="{CENTER_X}" y1="{NECK_Y}" x2="{CENTER_X}" y2="{TORSO_BOTTOM_Y}" '
        f'stroke="{outline}" stroke-width="{LINE_WIDTH}" stroke-linecap="round" opacity="0.3"/>'
    )


def _arm_segment_svg(x1: float, y1: float, x2: float, y2: float,
                     color: str, outline: str) -> str:
    """Generate a single arm/leg line."""
    return (
        f'<line x1="{x1}" y1="{y1}" x2="{x2}" y2="{y2}" '
        f'stroke="{color}" stroke-width="{LINE_WIDTH}" stroke-linecap="round"/>'
        f'<line x1="{x1}" y1="{y1}" x2="{x2}" y2="{y2}" '
        f'stroke="{outline}" stroke-width="{LINE_WIDTH - 1}" stroke-linecap="round" opacity="0.3"/>'
    )


def _base_figure_svg(character: CharacterDefinition) -> str:
    """Generate the base character SVG (standing pose) with all components."""
    color = character.color
    clothing = character.color_palette.clothing_primary or color
    outline = character.color_palette.outline

    # Head
    head = _head_svg(character)
    # Torso
    torso = _torso_svg(character)

    # Arms (hanging down)
    shoulder_y = TORSO_TOP_Y
    elbow_y = shoulder_y + ARM_LENGTH * 0.4
    hand_y = shoulder_y + ARM_LENGTH
    arm_left = _arm_segment_svg(CENTER_X - TORSO_WIDTH // 2, shoulder_y,
                                 CENTER_X - TORSO_WIDTH // 2 - 15, elbow_y, clothing, outline)
    arm_left2 = _arm_segment_svg(CENTER_X - TORSO_WIDTH // 2 - 15, elbow_y,
                                  CENTER_X - TORSO_WIDTH // 2 - 20, hand_y, clothing, outline)
    arm_right = _arm_segment_svg(CENTER_X + TORSO_WIDTH // 2, shoulder_y,
                                   CENTER_X + TORSO_WIDTH // 2 + 15, elbow_y, clothing, outline)
    arm_right2 = _arm_segment_svg(CENTER_X + TORSO_WIDTH // 2 + 15, elbow_y,
                                   CENTER_X + TORSO_WIDTH // 2 + 20, hand_y, clothing, outline)

    # Legs (standing)
    hip_y = TORSO_BOTTOM_Y
    knee_y = hip_y + LEG_LENGTH * 0.55
    foot_y = hip_y + LEG_LENGTH
    leg_left = _arm_segment_svg(CENTER_X - 8, hip_y, CENTER_X - 12, knee_y, clothing, outline)
    leg_left2 = _arm_segment_svg(CENTER_X - 12, knee_y, CENTER_X - 15, foot_y, clothing, outline)
    leg_right = _arm_segment_svg(CENTER_X + 8, hip_y, CENTER_X + 12, knee_y, clothing, outline)
    leg_right2 = _arm_segment_svg(CENTER_X + 12, knee_y, CENTER_X + 15, foot_y, clothing, outline)

    return f'<g id="character_base">{head}{torso}{arm_left}{arm_left2}{arm_right}{arm_right2}{leg_left}{leg_left2}{leg_right}{leg_right2}</g>'


# ============================================================================
# Pose Variant SVG Generators
# ============================================================================

def _walk_arms(character: CharacterDefinition) -> str:
    """Arms for walk pose."""
    clothing = character.color_palette.clothing_primary or character.color
    outline = character.color_palette.outline

    # Left arm forward, right arm back
    left = (_arm_segment_svg(CENTER_X - TORSO_WIDTH // 2, TORSO_TOP_Y,
                               CENTER_X - 30, TORSO_TOP_Y + 30, clothing, outline) +
            _arm_segment_svg(CENTER_X - 30, TORSO_TOP_Y + 30,
                              CENTER_X - 25, TORSO_TOP_Y + 55, clothing, outline))
    right = (_arm_segment_svg(CENTER_X + TORSO_WIDTH // 2, TORSO_TOP_Y,
                                CENTER_X + 30, TORSO_TOP_Y + 30, clothing, outline) +
             _arm_segment_svg(CENTER_X + 30, TORSO_TOP_Y + 30,
                               CENTER_X + 25, TORSO_TOP_Y + 55, clothing, outline))
    return left + right


def _run_arms(character: CharacterDefinition) -> str:
    """Arms for run pose (more exaggerated)."""
    clothing = character.color_palette.clothing_primary or character.color
    outline = character.color_palette.outline

    left = (_arm_segment_svg(CENTER_X - TORSO_WIDTH // 2, TORSO_TOP_Y,
                               CENTER_X - 40, TORSO_TOP_Y + 10, clothing, outline) +
            _arm_segment_svg(CENTER_X - 40, TORSO_TOP_Y + 10,
                              CENTER_X - 35, TORSO_TOP_Y + 40, clothing, outline))
    right = (_arm_segment_svg(CENTER_X + TORSO_WIDTH // 2, TORSO_TOP_Y,
                                CENTER_X + 40, TORSO_TOP_Y + 10, clothing, outline) +
             _arm_segment_svg(CENTER_X + 40, TORSO_TOP_Y + 10,
                               CENTER_X + 35, TORSO_TOP_Y + 40, clothing, outline))
    return left + right


def _point_arms(character: CharacterDefinition) -> str:
    """Arms for point pose (right arm pointing)."""
    clothing = character.color_palette.clothing_primary or character.color
    outline = character.color_palette.outline

    # Left arm down, right arm pointing right
    left = (_arm_segment_svg(CENTER_X - TORSO_WIDTH // 2, TORSO_TOP_Y,
                               CENTER_X - TORSO_WIDTH // 2 - 15, TORSO_TOP_Y + 40, clothing, outline) +
            _arm_segment_svg(CENTER_X - TORSO_WIDTH // 2 - 15, TORSO_TOP_Y + 40,
                              CENTER_X - TORSO_WIDTH // 2 - 20, TORSO_TOP_Y + 60, clothing, outline))
    right = (_arm_segment_svg(CENTER_X + TORSO_WIDTH // 2, TORSO_TOP_Y,
                                CENTER_X + 50, TORSO_TOP_Y - 10, clothing, outline) +
             _arm_segment_svg(CENTER_X + 50, TORSO_TOP_Y - 10,
                               CENTER_X + 70, TORSO_TOP_Y - 15, clothing, outline))
    return left + right


def _think_arms(character: CharacterDefinition) -> str:
    """Arms for think pose (hand on chin)."""
    clothing = character.color_palette.clothing_primary or character.color
    outline = character.color_palette.outline

    # Left arm raised to chin, right arm down
    left = (_arm_segment_svg(CENTER_X - TORSO_WIDTH // 2, TORSO_TOP_Y,
                               CENTER_X - 5, TORSO_TOP_Y + 20, clothing, outline) +
            _arm_segment_svg(CENTER_X - 5, TORSO_TOP_Y + 20,
                              CENTER_X, HEAD_CY + HEAD_RADIUS - 5, clothing, outline))
    right = (_arm_segment_svg(CENTER_X + TORSO_WIDTH // 2, TORSO_TOP_Y,
                                CENTER_X + TORSO_WIDTH // 2 + 10, TORSO_TOP_Y + 40, clothing, outline) +
             _arm_segment_svg(CENTER_X + TORSO_WIDTH // 2 + 10, TORSO_TOP_Y + 40,
                               CENTER_X + TORSO_WIDTH // 2 + 15, TORSO_TOP_Y + 60, clothing, outline))
    return left + right


def _celebrate_arms(character: CharacterDefinition) -> str:
    """Arms for celebrate pose (both raised)."""
    clothing = character.color_palette.clothing_primary or character.color
    outline = character.color_palette.outline

    left = (_arm_segment_svg(CENTER_X - TORSO_WIDTH // 2, TORSO_TOP_Y,
                               CENTER_X - 40, TORSO_TOP_Y - 20, clothing, outline) +
            _arm_segment_svg(CENTER_X - 40, TORSO_TOP_Y - 20,
                              CENTER_X - 35, TORSO_TOP_Y + 10, clothing, outline))
    right = (_arm_segment_svg(CENTER_X + TORSO_WIDTH // 2, TORSO_TOP_Y,
                                CENTER_X + 40, TORSO_TOP_Y - 20, clothing, outline) +
             _arm_segment_svg(CENTER_X + 40, TORSO_TOP_Y - 20,
                               CENTER_X + 35, TORSO_TOP_Y + 10, clothing, outline))
    return left + right


def _hide_arms(character: CharacterDefinition) -> str:
    """Arms for hide/crouch pose (arms wrapped around self)."""
    clothing = character.color_palette.clothing_primary or character.color
    outline = character.color_palette.outline

    # Arms wrapped close to body
    left = (_arm_segment_svg(CENTER_X - TORSO_WIDTH // 2, TORSO_TOP_Y,
                               CENTER_X - 5, TORSO_TOP_Y + 30, clothing, outline) +
            _arm_segment_svg(CENTER_X - 5, TORSO_TOP_Y + 30,
                              CENTER_X + 5, TORSO_TOP_Y + 25, clothing, outline))
    right = (_arm_segment_svg(CENTER_X + TORSO_WIDTH // 2, TORSO_TOP_Y,
                                CENTER_X + 5, TORSO_TOP_Y + 30, clothing, outline) +
             _arm_segment_svg(CENTER_X + 5, TORSO_TOP_Y + 30,
                               CENTER_X - 5, TORSO_TOP_Y + 35, clothing, outline))
    return left + right


def _walk_legs(character: CharacterDefinition) -> str:
    """Legs for walk pose."""
    clothing = character.color_palette.clothing_primary or character.color
    outline = character.color_palette.outline

    left = (_arm_segment_svg(CENTER_X - 8, TORSO_BOTTOM_Y,
                               CENTER_X - 20, TORSO_BOTTOM_Y + LEG_LENGTH * 0.5, clothing, outline) +
            _arm_segment_svg(CENTER_X - 20, TORSO_BOTTOM_Y + LEG_LENGTH * 0.5,
                              CENTER_X - 25, TORSO_BOTTOM_Y + LEG_LENGTH, clothing, outline))
    right = (_arm_segment_svg(CENTER_X + 8, TORSO_BOTTOM_Y,
                                 CENTER_X + 20, TORSO_BOTTOM_Y + LEG_LENGTH * 0.5, clothing, outline) +
             _arm_segment_svg(CENTER_X + 20, TORSO_BOTTOM_Y + LEG_LENGTH * 0.5,
                               CENTER_X + 25, TORSO_BOTTOM_Y + LEG_LENGTH, clothing, outline))
    return left + right


def _run_legs(character: CharacterDefinition) -> str:
    """Legs for run pose (more exaggerated stride)."""
    clothing = character.color_palette.clothing_primary or character.color
    outline = character.color_palette.outline

    left = (_arm_segment_svg(CENTER_X - 8, TORSO_BOTTOM_Y,
                               CENTER_X - 35, TORSO_BOTTOM_Y + LEG_LENGTH * 0.4, clothing, outline) +
            _arm_segment_svg(CENTER_X - 35, TORSO_BOTTOM_Y + LEG_LENGTH * 0.4,
                              CENTER_X - 30, TORSO_BOTTOM_Y + LEG_LENGTH * 0.9, clothing, outline))
    right = (_arm_segment_svg(CENTER_X + 8, TORSO_BOTTOM_Y,
                                 CENTER_X + 35, TORSO_BOTTOM_Y + LEG_LENGTH * 0.4, clothing, outline) +
             _arm_segment_svg(CENTER_X + 35, TORSO_BOTTOM_Y + LEG_LENGTH * 0.4,
                               CENTER_X + 30, TORSO_BOTTOM_Y + LEG_LENGTH * 0.9, clothing, outline))
    return left + right


def _sit_legs(character: CharacterDefinition) -> str:
    """Legs for sit pose."""
    clothing = character.color_palette.clothing_primary or character.color
    outline = character.color_palette.outline

    # Knees bent forward, feet on ground
    left = (_arm_segment_svg(CENTER_X - 8, TORSO_BOTTOM_Y,
                               CENTER_X - 30, TORSO_BOTTOM_Y + 30, clothing, outline) +
            _arm_segment_svg(CENTER_X - 30, TORSO_BOTTOM_Y + 30,
                              CENTER_X - 35, TORSO_BOTTOM_Y + 50, clothing, outline))
    right = (_arm_segment_svg(CENTER_X + 8, TORSO_BOTTOM_Y,
                                 CENTER_X + 30, TORSO_BOTTOM_Y + 30, clothing, outline) +
             _arm_segment_svg(CENTER_X + 30, TORSO_BOTTOM_Y + 30,
                               CENTER_X + 35, TORSO_BOTTOM_Y + 50, clothing, outline))
    return left + right


def _base_legs(character: CharacterDefinition) -> str:
    """Standard standing legs."""
    clothing = character.color_palette.clothing_primary or character.color
    outline = character.color_palette.outline

    left = (_arm_segment_svg(CENTER_X - 8, TORSO_BOTTOM_Y,
                               CENTER_X - 12, TORSO_BOTTOM_Y + LEG_LENGTH * 0.55, clothing, outline) +
            _arm_segment_svg(CENTER_X - 12, TORSO_BOTTOM_Y + LEG_LENGTH * 0.55,
                              CENTER_X - 15, TORSO_BOTTOM_Y + LEG_LENGTH, clothing, outline))
    right = (_arm_segment_svg(CENTER_X + 8, TORSO_BOTTOM_Y,
                                 CENTER_X + 12, TORSO_BOTTOM_Y + LEG_LENGTH * 0.55, clothing, outline) +
             _arm_segment_svg(CENTER_X + 12, TORSO_BOTTOM_Y + LEG_LENGTH * 0.55,
                               CENTER_X + 15, TORSO_BOTTOM_Y + LEG_LENGTH, clothing, outline))
    return left + right


# ============================================================================
# Expression Face Modifiers
# ============================================================================

def _apply_expression(base_svg: str, expression: ExpressionDefinition) -> str:
    """Apply expression modifiers to the base head SVG.

    Only modifies approved face components: eyes, eyebrows, mouth.
    Does not regenerate the entire character.
    """
    # Extract current head group
    head_match = re.search(r'<g id="head">.*?</g>', base_svg, re.DOTALL)
    if not head_match:
        return base_svg

    head_content = head_match.group(0)

    # Modify eyes based on expression
    eye_y = HEAD_CY - 3
    eye_left_x = HEAD_CX - 7
    eye_right_x = HEAD_CX + 7

    eye_shape = expression.eyes.shape
    eyebrow_raise = expression.eyes.eyebrow_raise
    eyebrow_inner_raise = expression.eyes.eyebrow_inner_raise
    mouth_shape = expression.mouth.shape
    corner_raise = expression.mouth.corner_raise
    open_amount = expression.mouth.open_amount

    # Build new eyes
    if eye_shape == "closed":
        new_eyes = (
            f'<line x1="{eye_left_x - 4}" y1="{eye_y}" x2="{eye_left_x + 4}" y2="{eye_y}" '
            f'stroke="#222222" stroke-width="2" stroke-linecap="round"/>'
            f'<line x1="{eye_right_x - 4}" y1="{eye_y}" x2="{eye_right_x + 4}" y2="{eye_y}" '
            f'stroke="#222222" stroke-width="2" stroke-linecap="round"/>'
        )
    elif eye_shape == "wide":
        new_eyes = (
            f'<circle cx="{eye_left_x}" cy="{eye_y}" r="5" fill="#222222"/>'
            f'<circle cx="{eye_right_x}" cy="{eye_y}" r="5" fill="#222222"/>'
        )
    elif eye_shape == "squint":
        new_eyes = (
            f'<circle cx="{eye_left_x}" cy="{eye_y}" r="2" fill="#222222"/>'
            f'<circle cx="{eye_right_x}" cy="{eye_y}" r="2" fill="#222222"/>'
        )
    else:  # open / default
        new_eyes = (
            f'<circle cx="{eye_left_x}" cy="{eye_y}" r="3" fill="#222222"/>'
            f'<circle cx="{eye_right_x}" cy="{eye_y}" r="3" fill="#222222"/>'
        )

    # Build new mouth
    mouth_y = HEAD_CY + 8
    if mouth_shape == "smile":
        new_mouth = (
            f'<path d="M {HEAD_CX - 6} {mouth_y + 2} Q {HEAD_CX} {mouth_y + 8} {HEAD_CX + 6} {mouth_y + 2}" '
            f'stroke="#222222" stroke-width="2" fill="none" stroke-linecap="round"/>'
        )
    elif mouth_shape == "frown":
        new_mouth = (
            f'<path d="M {HEAD_CX - 6} {mouth_y + 5} Q {HEAD_CX} {mouth_y - 2} {HEAD_CX + 6} {mouth_y + 5}" '
            f'stroke="#222222" stroke-width="2" fill="none" stroke-linecap="round"/>'
        )
    elif mouth_shape == "o_shape":
        new_mouth = (
            f'<ellipse cx="{HEAD_CX}" cy="{mouth_y + 2}" rx="4" ry="{5 + open_amount * 5}" '
            f'fill="#222222"/>'
        )
    else:  # neutral / default
        new_mouth = (
            f'<line x1="{HEAD_CX - 5}" y1="{mouth_y}" x2="{HEAD_CX + 5}" y2="{mouth_y}" '
            f'stroke="#222222" stroke-width="2" stroke-linecap="round"/>'
        )

    # Build new head group
    new_head = f'<g id="head"><circle cx="{HEAD_CX}" cy="{HEAD_CY}" r="{HEAD_RADIUS}" fill="#8D5524" stroke="#222222" stroke-width="2"/>'
    new_head += new_eyes + new_mouth + '</g>'

    return base_svg.replace(head_match.group(0), new_head)


# ============================================================================
# Full Pose SVG Generator
# ============================================================================

def generate_pose_svg(
    character: CharacterDefinition,
    pose_id: str,
) -> str:
    """Generate the complete SVG for a specific pose.

    Returns a complete, self-contained SVG string.
    """
    # Determine which pose variant
    pose_type = pose_id.rsplit("_", 1)[-1] if "_" in pose_id else pose_id

    # Build base figure
    base = _base_figure_svg(character)

    # Get pose-specific arms and legs
    if pose_type == "walk":
        arms = _walk_arms(character)
        legs = _walk_legs(character)
    elif pose_type == "run":
        arms = _run_arms(character)
        legs = _run_legs(character)
    elif pose_type == "point":
        arms = _point_arms(character)
        legs = _base_legs(character)
    elif pose_type == "think":
        arms = _think_arms(character)
        legs = _base_legs(character)
    elif pose_type == "celebrate":
        arms = _celebrate_arms(character)
        legs = _base_legs(character)
    elif pose_type == "hide":
        arms = _hide_arms(character)
        legs = _sit_legs(character)  # Hide uses sitting legs
    elif pose_type == "sit":
        arms = _arm_segment_svg(CENTER_X - TORSO_WIDTH // 2, TORSO_TOP_Y,
                                 CENTER_X - TORSO_WIDTH // 2 - 15, TORSO_TOP_Y + 50, character.color, "#222222") + \
               _arm_segment_svg(CENTER_X - TORSO_WIDTH // 2 - 15, TORSO_TOP_Y + 50,
                                 CENTER_X - TORSO_WIDTH // 2 - 20, TORSO_TOP_Y + 65, character.color, "#222222") + \
               _arm_segment_svg(CENTER_X + TORSO_WIDTH // 2, TORSO_TOP_Y,
                                 CENTER_X + TORSO_WIDTH // 2 + 15, TORSO_TOP_Y + 50, character.color, "#222222") + \
               _arm_segment_svg(CENTER_X + TORSO_WIDTH // 2 + 15, TORSO_TOP_Y + 50,
                                 CENTER_X + TORSO_WIDTH // 2 + 20, TORSO_TOP_Y + 65, character.color, "#222222")
        legs = _sit_legs(character)
    else:  # stand (default)
        arms = _arm_segment_svg(CENTER_X - TORSO_WIDTH // 2, TORSO_TOP_Y,
                                  CENTER_X - TORSO_WIDTH // 2 - 15, TORSO_TOP_Y + ARM_LENGTH, character.color, "#222222") + \
               _arm_segment_svg(CENTER_X + TORSO_WIDTH // 2, TORSO_TOP_Y,
                                 CENTER_X + TORSO_WIDTH // 2 + 15, TORSO_TOP_Y + ARM_LENGTH, character.color, "#222000") + \
               _arm_segment_svg(CENTER_X - TORSO_WIDTH // 2 - 15, TORSO_TOP_Y + ARM_LENGTH,
                                  CENTER_X - TORSO_WIDTH // 2 - 20, TORSO_TOP_Y + ARM_LENGTH + 20, character.color, "#222222") + \
               _arm_segment_svg(CENTER_X + TORSO_WIDTH // 2 + 15, TORSO_TOP_Y + ARM_LENGTH,
                                  CENTER_X + TORSO_WIDTH // 2 + 20, TORSO_TOP_Y + ARM_LENGTH + 20, character.color, "#222222")
        legs = _base_legs(character)

    # Assemble full SVG
    svg = f'''<svg xmlns="http://www.w3.org/2000/svg" viewBox="{VIEW_BOX}" width="{SVG_WIDTH}" height="{SVG_HEIGHT}">
  <g id="character_{pose_id}" data-character="{character.character_id}" data-pose="{pose_type}">
    {base}
    <g id="arms">{arms}</g>
    <g id="legs">{legs}</g>
  </g>
</svg>'''
    return svg


def generate_expression_svg(
    character: CharacterDefinition,
    pose_svg: str,
    expression: ExpressionDefinition,
) -> str:
    """Generate an SVG with a specific expression applied to the pose SVG."""
    return _apply_expression(pose_svg, expression)


def generate_character_preview_svg(character: CharacterDefinition) -> str:
    """Generate a simple preview SVG for the character (default standing pose)."""
    return generate_pose_svg(character, "stand")


# ============================================================================
# SVG Validation
# ============================================================================

def validate_svg(svg_content: str) -> tuple[bool, list[str]]:
    """Validate an SVG string.

    Returns (is_valid, list_of_issues).
    """
    issues: list[str] = []

    # 1. Must be well-formed XML
    try:
        import xml.etree.ElementTree as ET
        ET.fromstring(svg_content)
    except ET.ParseError as e:
        issues.append(f"Malformed XML: {e}")
        return False, issues

    # 2. Must have viewBox
    if 'viewBox="' not in svg_content and "viewBox='" not in svg_content:
        issues.append("Missing viewBox attribute")

    # 3. Must have width/height or viewBox
    if 'width="' not in svg_content and 'height="' not in svg_content:
        if 'viewBox="' not in svg_content:
            issues.append("Missing width/height and viewBox")

    # 4. No dangerous scripts
    if "<script" in svg_content.lower():
        issues.append("SVG contains <script> element — SECURITY RISK")

    # 5. No event handlers (onclick, onmouseover, etc.)
    if re.search(r'\bon\w+\s*=', svg_content, re.IGNORECASE):
        issues.append("SVG contains event handlers — SECURITY RISK")

    # 6. No external references
    if re.search(r'xlink:href=["\']https?://', svg_content):
        issues.append("SVG contains external URL reference")

    # 7. No path traversal
    if ".." in svg_content and ("file://" in svg_content or "path=" in svg_content.lower()):
        issues.append("SVG contains potential path traversal")

    # 8. Reasonable bounding box
    vb_match = re.search(r'viewBox=["\']([^"\']+)["\']', svg_content)
    if vb_match:
        parts = vb_match.group(1).split()
        if len(parts) == 4:
            try:
                _, _, w, h = [float(x) for x in parts]
                if w > 10000 or h > 10000:
                    issues.append(f"Unreasonably large viewBox: {w}x{h}")
                if w < 10 or h < 10:
                    issues.append(f"Unreasonably small viewBox: {w}x{h}")
            except ValueError:
                issues.append("Invalid viewBox values")

    return len(issues) == 0, issues


def compute_svg_hash(svg_content: str) -> str:
    """Compute a deterministic hash of SVG content for caching."""
    # Normalize whitespace before hashing
    normalized = re.sub(r'\s+', ' ', svg_content).strip()
    return hashlib.sha256(normalized.encode()).hexdigest()[:16]
