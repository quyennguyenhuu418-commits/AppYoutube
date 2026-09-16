# 🎬 VIDEO AI PRODUCTION PLAYBOOK
## Complete Guide: Axen Channel + Reference Videos + Google Flow

**Last Updated:** Wednesday Sep 16, 2026, 10:30 AM (UTC+7)  
**Version:** 3.0 (Added YouTube Production Pipeline)

---

## 📋 Mục Lục

1. [Tổng Quan](#1-tổng-quan)
2. [Axen Channel Analysis](#2-axen-channel-analysis)
3. [Reference Videos Analysis](#3-reference-videos-analysis)
4. [Google Flow Integration](#4-google-flow-integration)
5. [Character Design System](#5-character-design-system)
6. [Scene Composition](#6-scene-composition)
7. [Voice & Audio Mastering](#7-voice--audio-mastering)
8. [Prompt Engineering Templates](#8-prompt-engineering-templates)
9. [Pipeline Architecture](#9-pipeline-architecture)
10. [Quick Reference Cards](#10-quick-reference-cards)

---

## 1. Tổng Quan

### 1.1 Nguồn Dữ Liệu

| Source | Prompt | Key Learnings |
|--------|---------|---------------|
| **Axen Channel** (18 videos) | PROMPT 0.5-10 | 3-state loop, semi-realistic style, -23 dBFS voice |
| **Reference Videos** (2 videos) | PROMPT 11 | Stick figure approach, visual state classification |
| **Google Flow** | PROMPT 12 | Character reference sheets, structured prompts, sound descriptions |
| **YouTube Production Pipeline** | PROMPT 13 | 7-stage pipeline, packaging-first, automation stack (Nông Dân Học AI + 5 industry sources) |

### 1.2 Production Pattern Tổng Hợp

```
┌─────────────────────────────────────────────────────────────┐
│  UNIVERSAL PRODUCTION PATTERN                              │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  3-STATE LOOP (Axen + Reference):                         │
│  ┌──────────┐     ┌──────────┐     ┌──────────────┐       │
│  │ ANIMATED │ ←→  │  TALKING │ ←→  │ TEXT_OVERLAY │       │
│  │    2D    │     │   HEAD   │     │              │       │
│  │   (60%)  │     │   (25%)  │     │    (15%)    │       │
│  └──────────┘     └──────────┘     └──────────────┘       │
│       ↑                ↑                ↑                  │
│       └────────────────┴────────────────┘                  │
│                    CONTINUOUS LOOP                           │
│                                                             │
│  VOICE: -23 dBFS, 140-170 WPM, male 28-45, neutral En     │
│  BACKGROUND: Dark navy gradient (#0E1525 → #1A1A2E)       │
│  FORMAT: 1920×1080 @ 30fps, 16:9                          │
│  DURATION: 5-13 phút (sweet spot)                         │
│                                                             │
└─────────────────────────────────────────────────────────────┘
```

---

## 2. Axen Channel Analysis

### 2.1 Thiết Kế Nhân Vật

**Từ file:** `axen_character_design.json`

```yaml
Character Style:
  Type: AI-generated semi-realistic 2D cartoon
  Head-to-Body Ratio: 1:3 to 1:4 (head = 20-35% frame)
  Expressions: 7 core emotions
    - Joy
    - Fear
    - Anger
    - Sadness
    - Surprise
    - Concentration
    - Determination

Color Palettes (3 themes):
  Prehistoric:
    Primary: "#8B5A3C"
    Secondary: "#A0703D"
    Tertiary: "#C18A5C"
    Accent: "#6B4423"
    
  Royal/Medieval:
    Primary: "#7B2D8E"
    Secondary: "#D4AF37"
    Accent: "#8B0000"
    
  Modern:
    Primary: "#2C3E50"
    Secondary: "#7F8C8D"

Diversity Rules:
  - Multiple ethnicities
  - Various body types
  - Theme-based color switching
```

### 2.2 Bối Cảnh & Dựng Hình

**Từ file:** `axen_scene_composition.json`

```yaml
Background: Dark navy/indigo gradient
  - #0E1525 (darkest)
  - #1A1A2E (mid)
  - #16213E (lightest)

3 Depth Zones:
  Background: 100% opacity, warm tones
  Midground: 60% opacity, neutral
  Foreground: 20% opacity, cool tones

5 Lighting Setups:
  1. Prehistoric Day
  2. Prehistoric Night + Fire
  3. Underwater Deep
  4. Cosmic
  5. Royal Indoor

7 Framing Templates:
  - Extreme Wide: 5% usage
  - Wide: 15%
  - Medium: 25%
  - Medium Close-up: 20%
  - Close-up: 20%
  - Extreme Close-up: 10%
  - Insert: 5%

Pacing:
  - Avg shot duration: 6 seconds
  - Cuts per minute: 8
  - State changes per minute: 3
```

### 2.3 Giọng Đọc

**Từ file:** `axen_voice_profile.json`

```yaml
Loudness:
  Mean: -23.0 dBFS
  Stdev: ± 0.25 dBFS (extremely consistent)
  Max: ≤ -1.5 dBFS (headroom)
  Min: ≥ -40 dBFS

Pace:
  WPM: 140-170 (medium educational)
  Pause between sentences: 0.4-1.2s
  Max pause: 1.5s

Voice Profile:
  Type: Male, 28-45 years
  Accent: Neutral English
  Persona: Calm, authoritative, curious-explorer narrator
  Providers (priority):
    1. elevenlabs
    2. openai_tts
    3. gtts

Audio Format:
  Codec: WAV
  Sample Rate: 44100 Hz
  Bit Depth: 16-bit
  Channels: 2 (stereo)
```

### 2.4 Storytelling Techniques

```yaml
Hook Patterns (first 5-10s):
  1. Question - "What if...?"
  2. Statement - Bold claim
  3. Imagery - Visual hook
  4. Contrast - Before/after

6 Storytelling Devices:
  1. Hook - Grab attention
  2. Narrative Arc - Beginning/middle/end
  3. Comparison - Like X but Y
  4. Scale Emphasis - Numbers/data
  5. Emotional Beat - Relatable moment
  6. Callback - Reference earlier point

Transitions:
  - Cut: Same state, same pacing
  - Fade through black: Chapter break
  - Cross-dissolve: 0.3-0.5s
  - Match cut: Visual continuity
  - Zoom through: Focus change
```

### 2.5 Top Performing Content

**Video topics with >1M views:**
- Ancient human survival (predators)
- How humans survived winters
- Ancient daily life

**Sweet Spot Duration:** 5-13 minutes

---

## 3. Reference Videos Analysis

### 3.1 Visual Style

```yaml
Style: Stick figure (line-art + dots)
  - Simple head (circle)
  - Body (lines)
  - Minimal features

Animation: 2D frame-by-frame
Background: Solid colors
  - Primary: #1E3A5F (deep blue)
  - Secondary: #F5F5DC (beige)
  - Accent: #8B4513 (brown)

Character Consistency: HIGH (same style throughout)
```

### 3.2 Voice Metrics

```yaml
Mean Volume: -23.4 dBFS
Max Volume: -2.3 dBFS
Speech %: 99.3%

Comparison with Axen:
  - Mean: Similar (-23.4 vs -23.0)
  - Max: Similar (-2.3 vs -1.5 target)
  - Slightly higher speech % (99.3 vs typical)
```

### 3.3 Validation Pipeline

```bash
# Audio validation commands
ffmpeg -i video.mp4 -af "volumedetect" -vn -f null -
ffmpeg -i video.mp4 -af "silencedetect=noise=-35dB:d=0.4" -f null -

# Frame extraction
ffmpeg -i video.mp4 -vf "fps=0.5" frame_%04d.jpg

# Signalstats
ffmpeg -i video.mp4 -vf "signalstats" -f null -
```

---

## 4. Google Flow Integration

### 4.1 Character Reference Sheet Pattern

**CRITICAL for consistency across scenes**

```yaml
REFERENCE SHEET STRUCTURE (6 panels):
  1. Full-body front
  2. Full-body side
  3. Full-body back
  4. Head turnaround: front / three-quarter / side
  5. 4 EXPRESSION panels:
     - tired-hunched (slumped)
     - strained (gritted, lifting)
     - anxious (worried brows)
     - blank-resigned
  6. Close-up of signature prop

CONSISTENCY RULES:
  - All panels show EXACT same character
  - Identical head shape
  - Same face, outline weight, colors, proportions
  - NO redesign between panels
  - NO photorealism, 3D, anime, extra limbs

CHARACTER NAMING: @CHARACTER_NAME
  Examples: @MODERNYOU, @FARMER, @ANCESTOR
```

### 4.2 Image Prompt Template (Google Flow)

```yaml
IMAGE_PROMPT_V2:
  template: |
    [STYLE], [SUBJECT/CHARACTER], [ENVIRONMENT], 
    [EFFECTS/ACTION], background color [COLOR],
    [TEXT OVERLAY if needed], [NEGATIVE CONSTRAINTS],
    [FORMAT], [EDUCATIONAL CONTEXT]

  example: |
    "Hand-drawn 2D doodle cartoon, flat colors, bold black outlines,
     slightly imperfect sketchy marker lines, @MODERNYOU buried under
     a blanket with one eye cracking open in a dreading frown, one hand
     groping toward the alarm, layered messy bed and nightstand,
     background color cold cobalt blue, bold black ALL-CAPS 'MONDAY'
     in the top-left corner, no gradients, no shadows, no textures,
     no photorealism, no 3D, no extra limbs or fingers, 16:9,
     educational YouTube explainer doodle style."
```

### 4.3 Video Prompt Template (Google Flow)

```yaml
VIDEO_PROMPT_V2:
  template: |
    [STYLE] animation, [OUTLINE], [MOTION TYPE],
    [SCENE DESCRIPTION], [CAMERA WORK],
    Background color [COLOR], [NEGATIVE CONSTRAINTS],
    16:9 animation. Sound: [SOUND DESCRIPTION]

  example: |
    "Hand-drawn 2D doodle cartoon animation, flat colors, bold black
     marker outlines, slightly imperfect sketchy lines, frame-by-frame
     doodle motion — @MODERNYOU buried under a blanket, one eye
     cracking open into a dreading frown as one hand slides out and
     gropes blindly toward the alarm, the bold black ALL-CAPS 'MONDAY'
     sitting in the top-left corner. Camera holds steady with a slight
     push-in. Background color cold cobalt blue, no gradients,
     no shadows, no textures, no photorealism, no 3D, no morphing
     artifacts, no extra limbs or fingers, 16:9 animation.
     Sound: a muffled alarm buzz cut by a single tired button-tap click."
```

### 4.4 Prompt Components Breakdown

```
┌────────────────────────────────────────────────────────────┐
│ IMAGE PROMPT COMPONENTS                                    │
├────────────────────────────────────────────────────────────┤
│ 1. STYLE FOUNDATION                                        │
│    "Hand-drawn 2D doodle cartoon"                         │
│    "flat colors, bold black outlines"                       │
│    "slightly imperfect sketchy marker lines"               │
│                                                            │
│ 2. SUBJECT                                                 │
│    "@CHARACTER_NAME [action]"                             │
│    OR "[extreme close-up of OBJECT]"                      │
│                                                            │
│ 3. ENVIRONMENT                                            │
│    "[environment description]"                              │
│    "background color [COLOR]"                            │
│                                                            │
│ 4. EFFECTS/ACTION                                          │
│    "[motion lines, metaphor elements]"                     │
│    "[text overlay if needed]"                             │
│                                                            │
│ 5. NEGATIVE CONSTRAINTS                                    │
│    "no gradients, no shadows, no textures"                 │
│    "no photorealism, no 3D"                                │
│    "no extra limbs or fingers"                             │
│                                                            │
│ 6. FORMAT                                                  │
│    "16:9, educational YouTube explainer doodle style"    │
└────────────────────────────────────────────────────────────┘

┌────────────────────────────────────────────────────────────┐
│ VIDEO PROMPT COMPONENTS (Extra vs Image)                   │
├────────────────────────────────────────────────────────────┤
│ 1-6. Same as image prompt                                  │
│                                                            │
│ 7. MOTION TYPE                                             │
│    "frame-by-frame doodle motion" ← CRITICAL              │
│    (distinguishes from image prompts)                      │
│                                                            │
│ 8. CAMERA WORK                                             │
│    "Camera holds"                                          │
│    "slow push-in"                                         │
│    "tiny nervous shake"                                    │
│    "faint downward jolt"                                    │
│                                                            │
│ 9. SOUND DESCRIPTION                                       │
│    "Sound: [SOUND_EFFECT]" ← CRITICAL for audio prod     │
└────────────────────────────────────────────────────────────┘
```

### 4.5 Camera Terminology (DINO AI)

```yaml
Camera Angles:
  - Extreme Wide Shot (EWS): Toàn cảnh, nhân vật như chấm nhỏ
  - Wide Shot (WS): Toàn thân, chi tiết môi trường
  - Medium Shot (MS): Từ đầu gối trở lên
  - Close-Up (CU): Khuôn mặt hoặc object
  - Extreme Close-Up (ECU): Một phần khuôn mặt/object
  - Over-the-Shoulder (OTS): Qua vai nhân vật
  - POV Shot: Góc nhìn nhân vật
  - Dutch Angle: Nghiêng camera (unease/tension)
  - Bird's Eye: Từ trên xuống (total control)
  - Worm's Eye: Từ dưới lên (power/dominance)

Camera Movements:
  - HOLD: Camera đứng yên
  - PUSH-IN: Di chuyển về phía trước (focus/tension)
  - PULL-OUT: Di chuyển ra xa (context/release)
  - PAN: Xoay ngang
  - TILT: Xoay dọc
  - ZOOM: Thay đổi focal length
  - TRACKING: Di chuyển theo subject
  - SHAKE: Run nhẹ (nervous/tension)
```

---

## 5. Character Design System

### 5.1 Hybrid Approach (Axen + Google Flow)

```yaml
HYBRID CHARACTER SYSTEM:
  # Từ Google Flow:
  - Character reference sheets (@CHARACTER)
  - 6-panel consistency system
  - Signature props per character
  - Expression variations
  
  # Từ Axen:
  - Semi-realistic style (thay vì pure doodle)
  - Theme-based color palettes
  - Multi-ethnic diversity
  - Various body types

CHARACTER TYPES:
  Stick Figure (Simple):
    Style: Line-art + dots
    Use case: Rapid prototyping, cost-effective
    Examples: @MODERNYOU, @FARMER
    
  Semi-Realistic (Complex):
    Style: AI-generated 2D cartoon
    Use case: High-quality production
    Examples: Ancestor characters in Axen
```

### 5.2 Character Reference Template

```yaml
CHARACTER_REFERENCE:
  name: "@CHARACTER_NAME"
  description: "Early Neolithic farmer, what @ANCESTOR became"
  
  style: "Hand-drawn 2D doodle cartoon" OR "Semi-realistic AI-generated"
  
  design:
    head_shape: "Large round"
    eyes: "Dot eyes"
    brows: "Thick expressive marker brows"
    body: "Minimal, gaunt/thin"
    posture: "Hunched, stooped"
    outfit: "Plain rough tunic, bare feet"
    signature_color: "#8B5E3C"
    outline_weight: "Bold"
  
  expressions:
    - tired-hunched (slumped)
    - strained (gritted, lifting)
    - anxious (worried brows)
    - blank-resigned
  
  signature_prop: "Wooden hoe + wheat stalk"
  
  consistency_rules:
    - "All panels show EXACT same character"
    - "No redesign between panels"
    - "Same proportions throughout"
  
  reference_scenes: [007, 010, 026, 042, 043, 046, 048, 049]
```

---

## 6. Scene Composition

### 6.1 Scene Composition Rules (Axen + Reference)

```yaml
BACKGROUND SYSTEM:
  Axen Style:
    Gradient: Dark navy #0E1525 → #1A1A2E → #16213E
    Depth: 3 zones (100%, 60%, 20% opacity)
    Temperature: Warm BG, neutral MG, cool FG
    
  Google Flow Style:
    Solid colors: #1E3A5F (deep blue), #F5F5DC (beige)
    Simple backgrounds for readability
    
  Recommended Hybrid:
    Gradient backgrounds for immersion
    Solid color overlays for text clarity
```

### 6.2 Scene Templates (Axen)

```yaml
6 COMMON SCENE TEMPLATES:
  1. Cold Open Hook
     - Duration: 5-10s
     - Purpose: Grab attention
     - Style: Dramatic visual + hook question
     
  2. Establishing Context
     - Duration: 10-20s
     - Purpose: Set the scene
     - Style: Wide shot + narrator intro
     
  3. Concept Breakdown
     - Duration: 30-60s
     - Purpose: Explain main idea
     - Style: Animated 2D + text overlay
     
  4. Dramatic Reveal
     - Duration: 10-20s
     - Purpose: Surprise element
     - Style: Close-up + sound effect
     
  5. Comparison
     - Duration: 20-40s
     - Purpose: Show contrast
     - Style: Split screen or sequential
     
  6. Talking Head Personal
     - Duration: 15-30s
     - Purpose: Emotional connection
     - Style: Medium shot, warm lighting
```

### 6.3 Pacing Rules

```yaml
PACING STANDARDS:
  Shot Duration: 6 seconds average
    - Short: 3-4s (action scenes)
    - Medium: 5-7s (standard)
    - Long: 8-12s (dramatic pauses)
  
  Cuts per Minute: 8
  State Changes per Minute: 3
  
  3-STATE DISTRIBUTION:
    Animated 2D: 60%
    Talking Head: 25%
    Text Overlay: 15%
  
  DURATION SWEET SPOT: 5-13 phút
```

---

## 7. Voice & Audio Mastering

### 7.1 Voice Target Specifications

```yaml
LOUDNESS TARGET:
  Mean: -23.0 dBFS ± 0.25
  Max: ≤ -1.5 dBFS (HEADROOM critical)
  Min: ≥ -40 dBFS
  Stdev: ≤ 0.25 (consistency)

PACE:
  WPM: 140-170 (educational pace)
  Pause between sentences: 0.4-1.2s
  Max pause: 1.5s

PROFILE:
  Gender: Male preferred
  Age: 28-45 years
  Accent: Neutral English
  Persona: Calm, authoritative, curious-explorer
  
PROVIDERS (priority order):
  1. elevenlabs (highest quality)
  2. openai_tts (fallback)
  3. gtts (last resort)
```

### 7.2 Audio Validation Commands

```bash
# Volume detection
ffmpeg -i input.wav -af "volumedetect" -f null -

# Silence detection
ffmpeg -i input.wav -af "silencedetect=noise=-35dB:d=0.4" -f null -

# LUFS measurement (EBU R128)
ffmpeg -i input.wav -af "loudnorm=I=-16:TP=-1.5:LRA=11" -f null -
```

### 7.3 Sound Effects Library

```yaml
COMMON SOUND DESCRIPTIONS (Google Flow):
  - "a harsh repeating alarm-clock buzzer ringing"
  - "a muffled alarm buzz cut by a single tired button-tap click"
  - "a small puff-pop as the storm cloud forms"
  - "a heavy dull thud as the grey block lands"
  - "a sharp cracking sound"
  - "distant thunder rumble"
  - "footsteps on gravel"

SOUND IN VIDEO PROMPTS:
  Format: "Sound: [DESCRIPTION]"
  Purpose: Guide audio production
  Placement: End of video prompt
```

---

## 8. Prompt Engineering Templates

### 8.1 Image Prompt Template

```yaml
IMAGE_PROMPT_TEMPLATE:
  format: |
    [STYLE_BASE], [OUTLINE_STYLE],
    [SUBJECT] with [ACTION],
    [ENVIRONMENT_DETAILS],
    background color [BG_COLOR],
    [TEXT_OVERLAY if needed],
    [EFFECTS/LINES],
    [NEGATIVE_CONSTRAINTS],
    [FORMAT_SPEC]

  variables:
    STYLE_BASE:
      - "Hand-drawn 2D doodle cartoon"
      - "Semi-realistic AI-generated 2D cartoon"
      - "AI-generated semi-realistic cartoon"
    
    OUTLINE_STYLE:
      - "flat colors, bold black outlines"
      - "slightly imperfect sketchy marker lines"
    
    SUBJECT:
      - "@CHARACTER_NAME [action]"
      - "[extreme close-up of OBJECT]"
    
    BG_COLOR:
      - "cold cobalt blue"
      - "dark navy"
      - "#0E1525"
    
    NEGATIVE_CONSTRAINTS:
      - "no gradients, no shadows, no textures"
      - "no photorealism, no 3D"
      - "no extra limbs or fingers"
    
    FORMAT_SPEC:
      - "16:9, educational YouTube explainer doodle style"
```

### 8.2 Video Prompt Template

```yaml
VIDEO_PROMPT_TEMPLATE:
  format: |
    [STYLE_BASE] animation, [OUTLINE_STYLE],
    slightly imperfect sketchy lines,
    [MOTION_TYPE] —
    [SUBJECT] with [ACTION],
    [ENVIRONMENT_DETAILS],
    Camera [CAMERA_WORK].
    Background color [BG_COLOR],
    [NEGATIVE_CONSTRAINTS],
    16:9 animation.
    Sound: [SOUND_DESCRIPTION]

  variables:
    MOTION_TYPE:
      - "frame-by-frame doodle motion"
    
    CAMERA_WORK:
      - "holds with a tiny nervous shake"
      - "holds steady with a slight push-in"
      - "slowly pushes in"
      - "holds, a faint downward jolt on impact"
    
    SOUND_DESCRIPTION:
      - "a harsh repeating alarm-clock buzzer ringing"
      - "a muffled alarm buzz cut by a single tired button-tap click"
      - "[custom description]"
```

### 8.3 Character Reference Prompt

```yaml
CHARACTER_REFERENCE_PROMPT:
  format: |
    A clean character reference sheet for ONE [STYLE] character,
    on a pure white background with a thin light-grey grid.
    NOT realistic, NOT 3D.
    
    LAYOUT:
    1. full-body front
    2. full-body side
    3. full-body back
    4. head turnaround: front / three-quarter / side
    5. 4 EXPRESSION panels: [EXPRESSIONS]
    6. close-up of the signature prop: [PROP_DESCRIPTION]
    
    DESIGN:
    [CHARACTER_DESCRIPTION]
    
    CONSISTENCY:
    All panels show the EXACT same character —
    identical head shape, face, outline weight, colors, proportions.
    Do not redesign between panels.
    
    STYLE:
    [STYLE_SPEC]
    
    NEGATIVE:
    [NEGATIVE_CONSTRAINTS]
```

---

## 9. Pipeline Architecture

### 9.1 Current Pipeline Status

```
┌─────────────────────────────────────────────────────────────┐
│ PIPELINE ARCHITECTURE                                       │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  RESEARCH ──► EDITORIAL ──► STORYBOARD ──► RENDER ──► MP4 │
│      │            │            │           │               │
│      ▼            ▼            ▼           ▼               │
│  Provider      Compiler    ScenePlan   Remotion           │
│  Selection     Transitions Animations  Captions           │
│                                                             │
│  EXISTING MODULES:                                         │
│  ✅ orchestrator/app/research/     (4 files)               │
│  ✅ orchestrator/app/editorial/   (8 files)               │
│  ✅ orchestrator/app/story/       (3 files)                │
│  ✅ orchestrator/app/voice/       (16 files)               │
│  ✅ orchestrator/app/mastering/   (7 files)                │
│  ✅ orchestrator/app/character/   (4 files)                │
│  ✅ orchestrator/app/captions/     (9 files)                │
│  ✅ renderer/src/scenes/          (6 files)                 │
│                                                             │
│  MISSING (Integration needed):                             │
│  ⚠️  Character Reference System                           │
│  ⚠️  Prompt Templates V2                                  │
│  ⚠️  Sound Description Module                             │
│  ⚠️  Camera Terminology Library                           │
│                                                             │
└─────────────────────────────────────────────────────────────┘
```

### 9.2 Integration Points

```python
# 1. Character Reference Integration
class CharacterReference:
    name: str              # @CHARACTER_NAME
    design: CharacterDesign  # From axen_character_design.json
    reference_scenes: List[int]
    
    def generate_sheet() -> Image:
        """Generate 6-panel reference sheet"""
    
    def validate_prompt(prompt: str) -> bool:
        """Ensure @CHARACTER used correctly"""

# 2. Prompt Engine V2
class PromptEngineV2:
    def image_prompt(scene, character) -> str:
        """Structured image prompt with @CHARACTER"""
    
    def video_prompt(scene, character) -> str:
        """Structured video prompt with camera work + sound"""
    
    def sound_description(scene) -> str:
        """Generate sound description for audio"""

# 3. Editorial Compiler Update
class EditorialCompiler:
    def compile_with_references(job) -> RenderPlan:
        """Compile with character references"""
    
    def validate_consistency(plan) -> ValidationResult:
        """Ensure visual consistency"""
```

---

## 10. Quick Reference Cards

### 10.0 Production Pipeline (Industry Standard 2026)

```yaml
7-STAGE PIPELINE:
  1. IDEA CAPTURE: Continuous, 10s/note, no friction
  2. PACKAGING: Title + thumbnail BEFORE filming (GATE)
  3. SCRIPTING: First 30s written, body as 8-15 bullets
  4. FILMING/RENDER: Batch (high setup, low marginal)
  5. EDITING: 1 per session, NEVER batch (judgement degrades)
  6. PUBLISHING: Title/desc/chapters/end screen/captions
  7. ANALYSIS: CTR + retention + AVD at 48h + 2w

2 STALL POINTS:
  - Stall 1: No idea system (capture continuously)
  - Stall 2: Packaging done LAST (do BEFORE filming)

AUTOMATION_STACK (Industry Best):
  VidIQ (keywords) + Claude (scripts) + 
  Remotion (rendering) + N8n (upload) + 
  Repurpose.io (distribution)

TIME_SAVINGS:
  Manual: 22 hours/video
  Automated: 4 hours/video
  Savings: 83%
```

### 10.1 Character Consistency Checklist

```yaml
✅ REFERENCE SHEET CREATED
✅ @CHARACTER used consistently in all prompts
✅ Same head shape across all panels
✅ Same outline weight throughout
✅ Same colors/proportions
✅ Signature prop included
✅ 4 expressions captured
✅ No redesign between panels

❌ PHOTOREALISM
❌ 3D RENDER
❌ ANIME STYLE
❌ EXTRA LIMBS/FINGERS
❌ TEXT/WATERMARKS
❌ BUSY BACKGROUND
```

### 10.2 Voice Mastering Checklist

```yaml
✅ Mean: -23.0 dBFS ± 0.25
✅ Max: ≤ -1.5 dBFS
✅ WPM: 140-170
✅ Pause: 0.4-1.5s
✅ Male voice, 28-45, neutral English

❌ CLIPPPING (max = 0.0 dBFS)
❌ INCONSISTENT VOLUME (stdev > 0.5)
❌ TOO FAST (>180 WPM)
❌ TOO SLOW (<120 WPM)
```

### 10.3 Scene Pacing Checklist

```yaml
✅ Shot duration: 6s average
✅ Cuts per minute: 8
✅ State changes per minute: 3
✅ Duration: 5-13 minutes
✅ Animated 2D: 60%
✅ Talking Head: 25%
✅ Text Overlay: 15%

❌ TOO SHORT (<3 phút)
❌ TOO LONG (>20 phút)
❌ MONOTONE (no state changes)
```

### 10.4 Prompt Structure Checklist

```yaml
IMAGE PROMPT:
✅ Style foundation
✅ Subject (@CHARACTER or object)
✅ Environment
✅ Effects/action
✅ Background color
✅ Negative constraints
✅ Format (16:9)

VIDEO PROMPT:
✅ All image components
✅ Motion type (frame-by-frame)
✅ Camera work
✅ Sound description
```

---

## 📚 Files Reference

### JSON Specifications

| File | Lines | Purpose |
|------|-------|---------|
| `axen_character_design.json` | ~200 | Character design specs |
| `axen_scene_composition.json` | ~180 | Scene composition rules |
| `axen_voice_profile.json` | ~100 | Voice/audio specs |
| `composition_rules.json` | 96 | Reference video composition |
| `voice_rules.json` | 70 | Reference video voice rules |
| `character_reference_template.json` | TBD | Google Flow reference template |

### Documentation

| File | Purpose |
|------|---------|
| `prompt_12_GOOGLE_FLOW_INTEGRATION.md` | Google Flow analysis |
| `reference_video_spec.md` | Reference videos spec (Vi+En) |
| `final.md` | This file - complete playbook |

---

## 🚀 Next Steps

### Immediate (This Week)
1. Implement Character Reference System
2. Wire Prompt Templates V2 into pipeline
3. Create sound description module

### Short-term (This Month)
1. Test hybrid approach (Axen + Google Flow)
2. A/B test: stick figure vs semi-realistic
3. Add camera terminology library

### Long-term (This Quarter)
1. Auto-generate character reference sheets
2. Multi-language support (Vi-En-Es-Fr)
3. Real-time quality validation

---

**CREDITS:**
- Axen Channel Analysis: PROMPTs 0.5-11
- Reference Videos Analysis: PROMPT 11
- Google Flow AI Creative Studio: labs.google/fx/tools/flow
- DINO AI Cinematic Dictionary: Tudien_dienanh_DINOAI

**VERSION:** 2.0  
**LAST UPDATE:** Wednesday Sep 16, 2026, 10:20 AM (UTC+7)
