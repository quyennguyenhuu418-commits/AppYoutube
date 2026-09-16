# PROMPT 12: Google Flow Integration — Learning from AI Video Prompts
**Created:** Wednesday Sep 16, 2026, 10:15 AM (UTC+7)  
**Source:** Google Flow AI Creative Studio (labs.google/fx/tools/flow) + DINO AI Cinematic Dictionary

---

## Executive Summary

Tài liệu Google Flow cung cấp **prompt engineering patterns cực kỳ chi tiết** cho:
1. **Character Reference Sheet** — Tạo nhân vật consistent cho multi-scene production
2. **Image Prompts** — Mô tả scene với nhân vật reference (@MODERNYOU, @FARMER)
3. **Video Prompts** — Animation với motion description chi tiết

**Điểm nổi bật:** Style "Hand-drawn 2D doodle cartoon" phù hợp với approach stick-figure từ reference videos, có thể kết hợp với Axen semi-realistic style.

---

## 1. Character Reference Sheet Pattern (@FARMER Example)

### 1.1 Cấu trúc bắt buộc (6 panels)

```
┌─────────────────────────────────────────────────────────┐
│  CHARACTER REFERENCE SHEET — @FARMER                     │
│  [khuyến nghị: cảnh 007,010,026,042,043,046,048,049]    │
├─────────────────────────────────────────────────────────┤
│  1. Full-body front                                     │
│  2. Full-body side                                      │
│  3. Full-body back                                      │
│  4. Head turnaround: front / three-quarter / side       │
│  5. 4 EXPRESSION panels:                                │
│     - tired-hunched (slumped)                           │
│     - strained (gritted, lifting)                       │
│     - anxious (worried brows)                            │
│     - blank-resigned                                    │
│  6. Close-up signature prop: wooden hoe + wheat stalk   │
└─────────────────────────────────────────────────────────┘
```

### 1.2 Design Rules cho Character

```yaml
Style: "Hand-drawn 2D doodle cartoon"
  - Large round head
  - Dot eyes
  - Thick expressive marker brows
  - Minimal body
  - Bold black outlines
  - Flat single-color fills

Character: "Early Neolithic farmer"
  - Hunched posture (stooped, worn)
  - Gaunt/thin body
  - Plain rough tunic
  - Bare feet
  - Same round head family as @ANCESTOR

Signature Color: "#8B5E3C" (dull earth-brown)

Consistency Rule: "All panels show EXACT same character"
  - Identical head shape
  - Same face
  - Same outline weight
  - Same colors/proportions
  - NO redesign between panels
```

### 1.3 Negative Prompts (Anti-patterns)

```yaml
NO:
  - Photorealism
  - 3D render
  - Realistic face
  - Anime style
  - Extra limbs/fingers
  - Text/labels/numbers/watermark
  - Busy background
  - Redesign between panels
```

---

## 2. Image Prompt Structure

### 2.1 Template Pattern (4 Examples)

**Pattern 001: Extreme Close-up Object**
```yaml
TEMPLATE:
  "Hand-drawn 2D doodle cartoon, flat colors, bold black outlines,
   slightly imperfect sketchy marker lines, [extreme close-up of OBJECT],
   [action description], background color [COLOR], no gradients,
   no shadows, no textures, no photorealism, no 3D, no extra limbs,
   16:9, educational YouTube explainer doodle style."

EXAMPLE:
  "Hand-drawn 2D doodle cartoon, flat colors, bold black outlines,
   slightly imperfect sketchy marker lines, extreme close-up of a small
   red alarm clock blaring on a nightstand with sharp jagged motion
   lines around it, a blurred dark bedroom behind, background color
   cold cobalt blue, no gradients, no shadows, no textures,
   no photorealism, no 3D, no extra limbs or fingers, 16:9,
   educational YouTube explainer doodle style."
```

**Pattern 002: Character + Environment + Text Overlay**
```yaml
TEMPLATE:
  "Hand-drawn 2D doodle cartoon, flat colors, bold black outlines,
   slightly imperfect sketchy marker lines, @CHARACTER [action],
   [environment description], background color [COLOR],
   bold black ALL-CAPS [TEXT] in the [corner],
   [style constraints], 16:9, educational YouTube explainer doodle style."

EXAMPLE:
  "Hand-drawn 2D doodle cartoon, flat colors, bold black outlines,
   slightly imperfect sketchy marker lines, @MODERNYOU buried under
   a blanket with one eye cracking open in a dreading frown, one hand
   groping toward the alarm, layered messy bed and nightstand,
   background color cold cobalt blue, bold black ALL-CAPS 'MONDAY'
   in the top-left corner, no gradients, no shadows, no textures,
   no photorealism, no 3D, no extra limbs or fingers, 16:9,
   educational YouTube explainer doodle style."
```

**Pattern 003: Character Emotion + Metaphor**
```yaml
EXAMPLE:
  "Hand-drawn 2D doodle cartoon, flat colors, bold black outlines,
   slightly imperfect sketchy marker lines, close-up of @MODERNYOU lying
   with eyes still shut and a flat tense mouth as a small grey storm
   cloud forms above his head, dim bedroom, background color cobalt blue,
   no gradients, no shadows, no textures, no photorealism, no 3D,
   no extra limbs or fingers, 16:9, educational YouTube explainer doodle style."
```

**Pattern 004: Metaphor/Abstract Visual**
```yaml
EXAMPLE:
  "Hand-drawn 2D doodle cartoon, flat colors, bold black outlines,
   slightly imperfect sketchy marker lines, @MODERNYOU lying flat on
   his back with a literal heavy grey block sitting on his chest
   pressing him down, rumpled blanket, background color cobalt blue,
   no gradients, no shadows, no textures, no photorealism, no 3D,
   no extra limbs or fingers, 16:9, educational YouTube explainer doodle style."
```

### 2.2 Prompt Components Breakdown

```
┌────────────────────────────────────────────────────────────┐
│ IMAGE PROMPT COMPONENTS (Google Flow Pattern)              │
├────────────────────────────────────────────────────────────┤
│ 1. STYLE FOUNDATION                                        │
│    "Hand-drawn 2D doodle cartoon"                         │
│    "flat colors, bold black outlines"                       │
│    "slightly imperfect sketchy marker lines"               │
│                                                            │
│ 2. SUBJECT                                                 │
│    "@CHARACTER_NAME [action]"                              │
│    OR "[extreme close-up of OBJECT]"                       │
│                                                            │
│ 3. ENVIRONMENT                                             │
│    "[environment description]"                              │
│    "background color [COLOR]"                              │
│                                                            │
│ 4. EFFECTS/ACTION                                          │
│    "[motion lines, metaphor elements]"                      │
│    "[text overlay if needed]"                              │
│                                                            │
│ 5. NEGATIVE CONSTRAINTS                                    │
│    "no gradients, no shadows, no textures"                 │
│    "no photorealism, no 3D"                               │
│    "no extra limbs or fingers"                             │
│                                                            │
│ 6. FORMAT                                                  │
│    "16:9, educational YouTube explainer doodle style"      │
└────────────────────────────────────────────────────────────┘
```

---

## 3. Video Prompt Structure

### 3.1 Template Pattern

```yaml
TEMPLATE:
  "Hand-drawn 2D doodle cartoon animation, flat colors, bold black
   marker outlines, slightly imperfect sketchy lines, frame-by-frame
   doodle motion — [SCENE DESCRIPTION]. Camera [CAMERA_MOVEMENT].
   Background color [COLOR], [negative constraints], 16:9 animation.
   Sound: [SOUND_DESCRIPTION]."
```

### 3.2 Video Prompt Examples

**Video 001: Object Animation**
```yaml
"Hand-drawn 2D doodle cartoon animation, flat colors, bold black
 marker outlines, slightly imperfect sketchy lines, frame-by-frame
 doodle motion — extreme close-up of a small red alarm clock
 jolting and rattling violently on a nightstand, jagged motion
 lines flickering and snapping around it, the little bell hammer
 buzzing. Camera holds with a tiny nervous shake then a slow
 push-in. Background color cold cobalt blue, no gradients,
 no shadows, no textures, no photorealism, no 3D, no morphing
 artifacts, no extra limbs or fingers, 16:9 animation.
 Sound: a harsh repeating alarm-clock buzzer ringing."
```

**Video 002: Character + Action**
```yaml
"Hand-drawn 2D doodle cartoon animation, flat colors, bold black
 marker outlines, slightly imperfect sketchy lines, frame-by-frame
 doodle motion — @MODERNYOU buried under a blanket, one eye
 cracking open into a dreading frown as one hand slides out and
 gropes blindly toward the alarm, the bold black ALL-CAPS
 'MONDAY' sitting in the top-left corner. Camera holds steady
 with a slight push-in. Background color cold cobalt blue,
 no gradients, no shadows, no textures, no photorealism, no 3D,
 no morphing artifacts, no extra limbs or fingers, 16:9 animation.
 Sound: a muffled alarm buzz cut by a single tired button-tap click."
```

**Video 003: Metaphor Animation**
```yaml
"Hand-drawn 2D doodle cartoon animation, flat colors, bold black
 marker outlines, slightly imperfect sketchy lines, frame-by-frame
 doodle motion — close-up of @MODERNYOU lying with eyes shut
 and a flat tense mouth as a small grey storm cloud puffs into
 being above his head and drifts. Camera slowly pushes in.
 Background color cobalt blue, no gradients, no shadows, no textures,
 no photorealism, no 3D, no morphing artifacts, no extra limbs
 or fingers, 16:9 animation.
 Sound: a small puff-pop as the storm cloud forms."
```

**Video 004: Impact/Physical Metaphor**
```yaml
"Hand-drawn 2D doodle cartoon animation, flat colors, bold black
 marker outlines, slightly imperfect sketchy lines, frame-by-frame
 doodle motion — @MODERNYOU lying flat on his back as a heavy
 grey block drops onto his chest and presses him down into the
 rumpled blanket, his body squashing slightly. Camera holds,
 a faint downward jolt on impact. Background color cobalt blue,
 no gradients, no shadows, no textures, no photorealism, no 3D,
 no morphing artifacts, no extra limbs or fingers, 16:9 animation.
 Sound: a heavy dull thud as the grey block lands."
```

### 3.3 Video Prompt Components

```
┌────────────────────────────────────────────────────────────┐
│ VIDEO PROMPT COMPONENTS (Google Flow Pattern)              │
├────────────────────────────────────────────────────────────┤
│ 1. STYLE FOUNDATION (same as image)                        │
│    "Hand-drawn 2D doodle cartoon animation"               │
│    "flat colors, bold black marker outlines"                │
│                                                            │
│ 2. MOTION TYPE                                             │
│    "frame-by-frame doodle motion"                          │
│    (CRITICAL: distinguishes from image prompts)            │
│                                                            │
│ 3. SCENE DESCRIPTION                                       │
│    "[CHARACTER/OBJECT] [ACTION] [DETAILS]"                │
│    "jagged motion lines"                                   │
│    "specific body language"                                │
│                                                            │
│ 4. CAMERA WORK                                             │
│    "Camera holds"                                          │
│    "slow push-in"                                          │
│    "tiny nervous shake"                                    │
│    "faint downward jolt"                                   │
│                                                            │
│ 5. BACKGROUND                                             │
│    "background color [COLOR]"                              │
│    (usually consistent with image prompts)                  │
│                                                            │
│ 6. NEGATIVE CONSTRAINTS                                    │
│    "no morphing artifacts" (VIDEO-SPECIFIC)                │
│    (others same as image)                                  │
│                                                            │
│ 7. SOUND DESCRIPTION                                       │
│    "Sound: [SOUND_EFFECT]"                                 │
│    (CRITICAL: guides audio production)                     │
└────────────────────────────────────────────────────────────┘
```

---

## 4. Character Reference System (@MODERNYOU, @FARMER)

### 4.1 Character Naming Convention

```yaml
@MODERNYOU:
  - Modern person (Monday alarm clock scenario)
  - Character family: "modern person"

@FARMER:
  - Early Neolithic farmer
  - Same round head family as @ANCESTOR
  - Stooped, worn posture

@ANCESTOR:
  - Referenced by @FARMER description
  - "Same round head family"
```

### 4.2 Character Consistency Rules

```yaml
RULE 1: "All panels show EXACT same character"
  - Identical head shape
  - Same face
  - Same outline weight
  - Same colors/proportions
  - NO redesign between panels

RULE 2: "Character family relationship"
  - @FARMER is "what @ANCESTOR became"
  - Shared design language (round head family)
  - Different pose/expression to show evolution

RULE 3: "Signature props distinguish characters"
  - @FARMER: wooden hoe + wheat stalk
  - Other characters would have their own props
```

---

## 5. Cinematic Dictionary (DINO AI) — Camera Angles

### 5.1 Các thuật ngữ camera quan trọng

Từ DINO_CameraAngle.html:

| Thuật ngữ | Mô tả | Ứng dụng |
|-----------|-------|----------|
| Extreme Wide Shot (EWS) | Toàn cảnh, nhân vật như một chấm nhỏ | Establishing shots |
| Wide Shot (WS) | Toàn thân, chi tiết môi trường | Context setting |
| Medium Shot (MS) | Từ đầu gối trở lên | Standard dialogue |
| Close-Up (CU) | Khuôn mặt hoặc object | Emotional focus |
| Extreme Close-Up (ECU) | Một phần khuôn mặt/object | Tension/drama |
| Over-the-Shoulder (OTS) | Qua vai nhân vật | POV dialogue |
| POV Shot | Góc nhìn nhân vật | Immersion |
| Dutch Angle | Nghiêng camera | Unease/tension |
| Bird's Eye | Từ trên xuống | Total control |
| Worm's Eye | Từ dưới lên | Power/dominance |

### 5.2 Camera Movement Terms

```yaml
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

## 6. So sánh Google Flow vs Axen Channel

### 6.1 Style Comparison

| Aspect | Google Flow | Axen Channel |
|--------|-------------|--------------|
| **Style** | Hand-drawn doodle cartoon | Semi-realistic AI-generated 2D |
| **Complexity** | Simple, readable | More detailed, immersive |
| **Production Speed** | Faster (simpler) | Slower (detailed) |
| **Consistency Method** | Character reference sheets | Visual style guide + templates |
| **Voice** | Not specified in prompts | -23 dBFS, 140-170 WPM |
| **Background** | Solid colors | Dark navy gradient |
| **Motion** | Frame-by-frame doodle | AI-generated animation |

### 6.2 Key Insights từ Google Flow

1. **Character Reference System là CRITICAL**
   - Axen không có formal reference sheet → có thể dẫn đến inconsistency
   - Google Flow approach: tạo @CHARACTER reference, dùng trong mọi prompt

2. **Prompt Structure hoàn chỉnh hơn**
   - Google Flow: style → subject → environment → effects → constraints → format
   - Axen: style → subject → lighting → effects (less structured)

3. **Video prompts có SOUND DESCRIPTION**
   - Axen không có sound trong prompts → tạo ra silent videos
   - Google Flow: "Sound: [description]" giúp audio production

4. **Frame-by-frame motion description**
   - "jagged motion lines", "bell hammer buzzing", "squashing slightly"
   - Axen: generic "animated" → less specific guidance

### 6.3 Hybrid Approach (Best of Both)

```yaml
MERGED STYLE:
  # Từ Google Flow:
  - Character reference system (@CHARACTER)
  - Structured prompt template
  - Sound descriptions
  - Frame-by-frame motion details
  - Consistent negative prompts
  
  # Từ Axen:
  - Dark navy gradient backgrounds
  - Multi-point lighting
  - Educational narrative arc
  - Voice mastering standards
  - 3-state loop (animated/talking/text)
```

---

## 7. Updated Prompt Engineering Standards

### 7.1 Character Reference Sheet Template

```yaml
CHARACTER_REFERENCE_TEMPLATE:
  name: "@CHARACTER_NAME"
  description: "[1-2 sentences about character]"
  style: "Hand-drawn 2D doodle cartoon OR Semi-realistic AI-generated 2D"
  
  panels_required:
    - "Full-body front"
    - "Full-body side" 
    - "Full-body back"
    - "Head turnaround: front / three-quarter / side"
    - "4 EXPRESSION panels: [list expressions]"
    - "Close-up of signature prop"
  
  design_rules:
    head: "[shape description]"
    eyes: "[eye style]"
    body: "[body type]"
    outfit: "[clothing]"
    signature_color: "[hex color]"
    outline_weight: "[thin/medium/thick]"
  
  consistency_rules:
    - "All panels show EXACT same character"
    - "No redesign between panels"
    - "Same proportions throughout"
  
  reference_scenes: "[list scene numbers]"
```

### 7.2 Image Prompt Template (Updated)

```yaml
IMAGE_PROMPT_V2:
  template: |
    [STYLE], [SUBJECT/CHARACTER], [ENVIRONMENT], 
    [EFFECTS/ACTION], background color [COLOR],
    [TEXT OVERLAY if needed], [NEGATIVE CONSTRAINTS],
    [FORMAT], [EDUCATIONAL CONTEXT]

  components:
    style: "[Style foundation + outline style]"
    subject: "[@CHARACTER reference] [action]" OR "[close-up of object]"
    environment: "[environment description]"
    effects: "[motion lines, metaphor elements]"
    background: "background color [COLOR]"
    text: "bold black ALL-CAPS [TEXT] in [corner]"
    negative: |
      no gradients, no shadows, no textures, 
      no photorealism, no 3D, no morphing artifacts,
      no extra limbs or fingers
    format: "16:9, educational YouTube explainer doodle style"
```

### 7.3 Video Prompt Template (Updated)

```yaml
VIDEO_PROMPT_V2:
  template: |
    [STYLE] animation, [OUTLINE], [MOTION TYPE],
    [SCENE DESCRIPTION], [CAMERA WORK],
    Background color [COLOR], [NEGATIVE CONSTRAINTS],
    16:9 animation. Sound: [SOUND DESCRIPTION]

  components:
    style: "Hand-drawn 2D doodle cartoon animation" OR "[Axen style]"
    outline: "bold black marker outlines"
    motion: "frame-by-frame doodle motion"
    scene: "[CHARACTER/OBJECT] [ACTION] [DETAILS]"
    camera: "Camera [HOLD/PUSH-IN/PULL-OUT/SHAKE]"
    background: "Background color [COLOR]"
    negative: |
      no gradients, no shadows, no textures,
      no photorealism, no 3D, no morphing artifacts,
      no extra limbs or fingers
    format: "16:9 animation"
    sound: "Sound: [DESCRIPTION]"
```

---

## 8. Integration với Pipeline hiện tại

### 8.1 Files cần tạo mới

| File | Purpose |
|------|---------|
| `character_reference_template.json` | Template cho character reference sheets |
| `prompt_templates_v2.json` | Updated image/video prompt templates |
| `camera_terminology.json` | Camera angles + movements reference |
| `sound_library.json` | Common sound descriptions |
| `negative_prompts.json` | Consolidated anti-patterns |

### 8.2 Files cần update

| File | Change |
|------|--------|
| `axen_character_design.json` | Thêm Google Flow reference system |
| `axen_scene_composition.json` | Thêm camera work từ DINO AI |
| `orchestrator/app/character/engine.py` | Hỗ trợ reference-based generation |
| `orchestrator/app/story/engine.py` | Thêm sound description support |

### 8.3 Integration Points

```
┌─────────────────────────────────────────────────────────────┐
│ INTEGRATION ARCHITECTURE                                     │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  Character Reference Sheet                                  │
│         │                                                   │
│         ▼                                                   │
│  ┌─────────────────┐                                       │
│  │ @CHARACTER_NAME │ ──► Used in ALL prompts               │
│  └─────────────────┘                                       │
│         │                                                   │
│         ▼                                                   │
│  ┌─────────────────────────────────────────────────┐       │
│  │ Prompt Engineering Engine                       │       │
│  │  ├─► Image Prompt V2 Template                   │       │
│  │  ├─► Video Prompt V2 Template                   │       │
│  │  └─► Sound Description Module                   │       │
│  └─────────────────────────────────────────────────┘       │
│         │                                                   │
│         ▼                                                   │
│  ┌─────────────────────────────────────────────────┐       │
│  │ Generation Services                               │       │
│  │  ├─► Image Gen (Stable Diffusion / Midjourney)  │       │
│  │  ├─► Video Gen (Runway / Pika / Sora)           │       │
│  │  └─► Character Consistency Validator            │       │
│  └─────────────────────────────────────────────────┘       │
│         │                                                   │
│         ▼                                                   │
│  ┌─────────────────────────────────────────────────┐       │
│  │ Remotion Renderer                                │       │
│  │  ├─► Animated2DScene                             │       │
│  │  ├─► TalkingHeadScene                           │       │
│  │  └─► TextOverlayScene                           │       │
│  └─────────────────────────────────────────────────┘       │
│                                                             │
└─────────────────────────────────────────────────────────────┘
```

---

## 9. Immediate Actions

### 9.1 Week 1: Character Reference System

```python
# orchestrator/app/character/reference.py (NEW)
class CharacterReference:
    name: str                    # @CHARACTER_NAME
    style: str                   # doodle/semi-realistic
    design: CharacterDesign      # From axen_character_design.json
    reference_scenes: List[int] # Valid scene numbers
    consistency_rules: List[str]
    
    def generate_reference_sheet(self) -> Image:
        """Generate 6-panel reference sheet"""
        
    def validate_prompt(self, prompt: str) -> bool:
        """Check if prompt uses @CHARACTER correctly"""
```

### 9.2 Week 2: Prompt Templates V2

```python
# orchestrator/app/story/prompt_engine.py (UPDATE)
class PromptEngineV2:
    def image_prompt_v2(self, scene: EditorialScene, 
                       character: CharacterReference) -> str:
        """Generate structured image prompt with reference"""
        
    def video_prompt_v2(self, scene: EditorialScene,
                       character: CharacterReference) -> str:
        """Generate structured video prompt with reference"""
        
    def sound_description(self, scene: EditorialScene) -> str:
        """Generate sound description for audio production"""
```

### 9.3 Week 3: Integration + Testing

```python
# orchestrator/app/editorial/compiler.py (UPDATE)
class EditorialCompiler:
    def compile_with_references(self, job: EditorialJob) -> RenderPlan:
        """Compile with character references + structured prompts"""
        
    def validate_character_consistency(self, plan: RenderPlan) -> ValidationResult:
        """Ensure all @CHARACTER usages are consistent"""
```

---

## 10. Summary

### What I Learned from Google Flow:

1. **Character Reference Sheet Pattern** — 6-panel system đảm bảo consistency
2. **Structured Prompt Templates** — Style → Subject → Environment → Effects → Constraints → Format
3. **@CHARACTER Reference System** — Dùng character name trong mọi prompt để maintain consistency
4. **Video Prompt Structure** — Thêm motion type ("frame-by-frame doodle motion") và camera work
5. **Sound Descriptions** — Critical cho audio production, bị thiếu trong Axen approach
6. **Negative Prompts Consolidation** — Danh sách rõ ràng các anti-patterns

### What's New vs Axen:

| Aspect | Axen (Existing) | Google Flow (New) |
|--------|-----------------|-------------------|
| Character Consistency | Visual style guide | Formal reference sheets |
| Prompt Structure | Semi-structured | Fully structured template |
| Sound in Prompts | None | Explicit sound description |
| Motion Details | Generic "animated" | Frame-by-frame specifics |
| Camera Work | Basic | 10+ specific movements |
| Negative Prompts | Implicit | Explicit consolidated list |

### Next Steps:

1. **PROMPT 13**: Implement Character Reference System
2. **PROMPT 14**: Wire Prompt Templates V2 vào pipeline
3. **PROMPT 15**: Test hybrid approach (Google Flow style + Axen quality)

---

**CREDITS:**
- Google Flow AI Creative Studio: labs.google/fx/tools/flow
- DINO AI Cinematic Dictionary: Tudien_dienanh_DINOAI
- Axen Channel Analysis: PROMPTs 0.5-11
- Nông Dân Học AI: [Claude Code + YouTube](https://www.youtube.com/watch?v=ZY4VYW_d1pY)
- Storyflow: [7-Stage Pipeline](https://storyflow.so/blog/youtube-content-pipeline-seven-stages-2026)
- Overseeros: [YouTube Operating System](https://www.overseeros.com/blog/youtube-content-operating-system)
- Sebastian Voppmann: [YouTube Automation Stack](https://sebastianvoppmann.com/youtube-automation/)

**VERSION:** 2.0 (Added Production Pipeline section)  
**LAST UPDATE:** Wednesday Sep 16, 2026, 10:30 AM (UTC+7)

---

## 11. 📊 BÁO CÁO TỔNG HỢP — PRODUCTION PIPELINE INTEGRATION

### 11.1 Executive Summary

Kết hợp kiến thức từ **Google Flow AI Creative Studio** + **Nông Dân Học AI** video + **5 nguồn industry standard** (Storyflow, Overseeros, Kliptory, Sebastian, SUMERA), tôi đã xây dựng được quy trình production hoàn chỉnh cho AppYoutube.

**Mục tiêu:** Giảm effort từ **9h30 → 4 giờ/video** (giảm 58%), scale output từ **1-2 → 4-8 videos/tháng**.

---

### 11.2 Quy Trình 7-Stage Pipeline (Industry Standard 2026)

```
┌─────────────────────────────────────────────────────────────────┐
│           7-STAGE YOUTUBE PRODUCTION PIPELINE                  │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  ┌─────────────────┐                                            │
│  │ 1. IDEA CAPTURE │  Continuous, 10s/note, no friction        │
│  └────────┬────────┘                                            │
│           ↓                                                     │
│  ┌─────────────────┐                                            │
│  │ 2. PACKAGING    │  Title + thumbnail TRƯỚC khi render        │
│  └────────┬────────┘                                            │
│           ↓                                                     │
│  ┌─────────────────┐                                            │
│  │ 3. SCRIPTING    │  First 30s written, body as 8-15 bullets  │
│  └────────┬────────┘                                            │
│           ↓                                                     │
│  ┌─────────────────┐                                            │
│  │ 4. PRODUCTION   │  Prompt Engineering + Character Ref       │
│  └────────┬────────┘                                            │
│           ↓                                                     │
│  ┌─────────────────┐                                            │
│  │ 5. VOICE/EDIT   │  Voice generation + Mastering              │
│  └────────┬────────┘                                            │
│           ↓                                                     │
│  ┌─────────────────┐                                            │
│  │ 6. PUBLISHING   │  Auto-upload (N8n + YouTube Data API)     │
│  └────────┬────────┘                                            │
│           ↓                                                     │
│  ┌─────────────────┐                                            │
│  │ 7. ANALYSIS     │  CTR + Retention + AVD (48h + 2 weeks)     │
│  └─────────────────┘                                            │
│                                                                 │
│  ⚠️ 2 STALL POINTS:                                            │
│     • No idea system (capture continuously, don't generate)     │
│     • Packaging done LAST (do BEFORE production)               │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

---

### 11.3 Hybrid Workflow — AppYoutube + Industry Best Practices

#### Stage 1: Idea Capture (Continuous)
```yaml
SOURCE: Storyflow (7-Stage Pipeline)

PRINCIPLE: "Capture, don't generate under deadline"

TOOLS:
  - Phone notes (< 10s to add)
  - Capture questions people ask you
  - Capture things you explained twice
  - Capture moments you were surprised
  - Capture titles alone (no video needed)

MONTHLY_REVIEW: 10 minutes
  - Choose from list of 50+ captured ideas
  - NOT generate new ideas under deadline

INTEGRATION_NEEDED:
  - orchestrator/app/ideation/capture.py (NEW)
  - ideas.json storage
  - frictionless CLI/API
```

#### Stage 2: Packaging (GATE — Before Production)
```yaml
SOURCE: Storyflow + Sebastian Voppmann + Google Flow

PRINCIPLE: "Package before you shoot, treat as GATE"

COMPONENTS:
  - Title generation (Claude API, 3 variants, 60 chars max)
  - Thumbnail prompt generation (Google Flow style)
  - Gate check: "Would you click this in a feed next to 4 others?"

BENEFITS:
  - Kill weak ideas cheaply (50 min, not 1 day)
  - Focus the video (title = promise)
  - Remove worst moment (tired at end of edit)

CURRENT_PIPELINE: NOT INTEGRATED ❌
INTEGRATION_NEEDED:
  - orchestrator/app/packaging/generator.py (NEW)
  - TitleGenerator with Claude API
  - ThumbnailPromptGenerator
  - GateValidator
```

#### Stage 3: Scripting (Editorial Compiler)
```yaml
SOURCE: AppYoutube existing + SUMERA

EXISTING_APPYOUTUBE:
  - orchestrator/app/editorial/ (8 files) ✅
  - EditorialCompiler với Axen rules
  - Voice profile integration
  - Scene composition rules

ADDITIONS:
  - Claude API integration cho first draft (4 minutes)
  - Manual refinement (35-40 minutes)
  - Total: 45 min/video (vs 4h manual)

TIME_SAVINGS: 4h → 45min = -82%
```

#### Stage 4: Production (Character Reference + Scene Prompts)
```yaml
SOURCE: Google Flow + Axen Hybrid

CHARACTER_REFERENCE_SYSTEM:
  - 6-panel reference sheets (@CHARACTER)
  - Style: Hand-drawn doodle OR Semi-realistic
  - Expressions: 4 standard panels
  - Signature props per character

SCENE_PROMPTS:
  - Google Flow template v2
  - Style → Subject → Environment → Effects → Constraints → Format
  - Camera work từ DINO AI dictionary
  - Sound descriptions integrated

EXISTING_APPYOUTUBE:
  - orchestrator/app/character/ (4 files) ✅
  - orchestrator/app/story/ (3 files) ✅

ADDITIONS:
  - CharacterReferenceEngine (reference sheets)
  - PromptEngineV2 (structured templates)
  - CameraTerminologyLibrary
  - SoundDescriptionLibrary
```

#### Stage 5: Voice/Mastering
```yaml
SOURCE: AppYoutube existing (robust!) ✅

EXISTING_MODULES:
  - orchestrator/app/voice/ (16 files)
  - orchestrator/app/mastering/ (7 files)
  - ElevenLabs integration
  - Auto-mastering pipeline
  - -23 dBFS target

METRICS:
  - Mean: -23.0 dBFS ± 0.25
  - Max: ≤ -1.5 dBFS (headroom)
  - WPM: 140-170
  - Speech %: 99.3+

STATUS: PRODUCTION-READY ✅
```

#### Stage 6: Rendering (Remotion)
```yaml
SOURCE: AppYoutube existing ✅

EXISTING_MODULES:
  - renderer/src/scenes/ (6 files)
  - Animated2DScene ✅
  - TalkingHeadScene ✅
  - TextOverlayScene ✅
  - 783+ tests passing, 169 validated

TIME: ~20 minutes per video (automated)
```

#### Stage 7: Captions + Shorts + Publishing
```yaml
SOURCE: AppYoutube partial + Nông Dân Học AI + Sebastian

EXISTING_APPYOUTUBE:
  - orchestrator/app/captions/ (9 files) ✅
  - Caption generation

NEW_MODULES (GAP):
  - Shorts Extractor (3 clips @ 15-60s each)
  - YouTube Uploader (Data API v3)
  - Distributor (Repurpose.io integration)
  - N8n workflow for automation

INTEGRATION_PRIORITY: HIGH ❌
```

#### Stage 8: Analysis + Strategy Loop
```yaml
SOURCE: Storyflow + Overseeros

METRICS_TO_TRACK:
  - CTR vs channel median (48h)
  - Retention curve shape (48h)
  - Average View Duration / Length (2 weeks)
  - 1 question per video: "What would I change?"

STRATEGY_LOOP:
  - Post-mortem → Update content plan
  - Monthly review (10 min)
  - Adjust next month's topics based on learnings

INTEGRATION_NEEDED:
  - orchestrator/app/analytics/ (NEW)
  - YouTubeAnalytics fetcher
  - PostMortemGenerator
  - StrategyLoop updater
```

---

### 11.4 Automation Stack — Industry Best

```yaml
PRODUCTION_STACK_RECOMMENDATIONS:

TOOLS:
  VidIQ:
    Purpose: Keyword research, trend analysis
    Cost: €15/month
    Time saved: 3h → 20min/week
    
  Claude Pro:
    Purpose: Script first draft
    Cost: €20/month
    Time saved: 4h → 4min
    Integration: API for batch processing
    
  Notion (hoặc equivalent):
    Purpose: Pipeline tracking, idea log, briefings
    Cost: Free
    Time saved: Organization, search
    
  Remotion (existing):
    Purpose: Video rendering
    Cost: Included in AppYoutube
    Time: ~20 min/video automated
    
  ElevenLabs (existing):
    Purpose: Voice generation
    Cost: API
    Time saved: 4h → 10min
    
  Canva Template:
    Purpose: Thumbnail generation
    Cost: Free/Pro
    Time saved: 1h → 8min
    
  N8n:
    Purpose: Auto-upload, notification
    Cost: Free/Pro
    Time saved: Manual → 0
    
  Repurpose.io:
    Purpose: Multi-platform distribution
    Cost: Paid
    Distribution: 1 video → 4 platforms (YouTube + TikTok + Reels + LinkedIn)

TOTAL_TIME_PER_VIDEO:
  Manual 2016: 22 hours
  Automated 2026: 4 hours
  Savings: 83%
  
APPTYOUTUBE_CURRENT:
  - Without new modules: ~9h30/video
  - With packaging + publishing + analysis: ~5h/video
  - Fully automated: ~4h/video
```

---

### 11.5 Priority Gaps & Roadmap

```yaml
HIGH_PRIORITY (Quick Wins — 1-2 weeks):
  □ Packaging System (Title + Thumbnail generator)
    Files: orchestrator/app/packaging/{title.py, thumbnail.py, gate.py}
    
  □ YouTube Upload Script (Data API v3)
    Files: orchestrator/app/publishing/youtube_uploader.py
    
  □ Shorts Extractor (3 clips per video)
    Files: orchestrator/app/distribution/shorts_extractor.py
    
  □ Packaging Gate Documentation
    Files: docs/PACKAGING_GATE.md

MEDIUM_PRIORITY (This Month):
  □ N8n Integration cho publishing automation
  □ Repurpose.io cho distribution
  □ VidIQ-style keyword module
  □ Analysis Dashboard (CTR + retention)

LOW_PRIORITY (This Quarter):
  □ Multi-language support (Vi/En/Es/Fr)
  □ A/B testing for titles/thumbnails
  □ Predictive CTR scoring
  □ Auto-translation pipeline
```

---

### 11.6 Kết Hợp 3 Nguồn Kiến Thức

```
┌─────────────────────────────────────────────────────────────────┐
│  HỢP NHẤT 3 NGUỒN: AXEN + GOOGLE FLOW + INDUSTRY PIPELINE    │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  TỪ AXEN (Production Quality):                                 │
│    - Voice mastering -23 dBFS                                   │
│    - 3-state loop (Animated/Talking/Text)                       │
│    - Dark navy gradient backgrounds                             │
│    - Educational narrative structure                            │
│                                                                 │
│  TỪ GOOGLE FLOW (Prompt Engineering):                          │
│    - Character reference sheets (@CHARACTER)                    │
│    - Structured prompt templates                                │
│    - Sound descriptions trong prompts                           │
│    - Frame-by-frame motion details                              │
│    - Camera work terminology                                    │
│                                                                 │
│  TỪ INDUSTRY (Scale & Automation):                              │
│    - 7-stage pipeline                                            │
│    - Packaging-first principle                                  │
│    - 83% time savings via automation                            │
│    - N8n + Repurpose.io workflow                                │
│    - Analysis feedback loop                                     │
│                                                                 │
│  KẾT QUẢ:                                                       │
│    - Production 4h/video                                        │
│    - 4-8 videos/month                                           │
│    - 1200%+ view growth                                         │
│    - 95% automation                                             │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

---

### 11.7 Success Metrics — Cần Track

```yaml
PRODUCTION_METRICS:
  - Videos published per month (target: 4-8)
  - Average production time per video (target: 4h)
  - Cost per video (target: < $20)
  
YOUTUBE_METRICS:
  - CTR (target: 6-10%)
  - Retention at 30s (target: > 70%)
  - Average View Duration (target: > 50% of length)
  - Views per video (track trend)
  - Subscriber growth (track monthly)

AUTOMATION_METRICS:
  - % automated stages (target: > 95%)
  - Time per stage (track each)
  - Error rate per stage (target: < 5%)
  - Cost per automation (track ROI)

CONTENT_QUALITY:
  - Character consistency score
  - Voice mastering pass rate (target: 100%)
  - Visual quality (manual review)
  - Audience retention curve shape
```

---

### 11.8 Immediate Actions

#### Week 1: Quick Wins
```python
# Day 1-2: Packaging Module
orchestrator/app/packaging/
  ├── __init__.py
  ├── title_generator.py      # Claude API, 3 variants
  ├── thumbnail_prompt.py     # Google Flow style
  ├── gate_validator.py       # "Would you click?" gate
  └── README.md

# Day 3: Shorts Extractor
orchestrator/app/distribution/
  ├── __init__.py
  ├── shorts_extractor.py     # 3 clips @ 15-60s
  └── README.md

# Day 4-5: YouTube Upload
orchestrator/app/publishing/
  ├── __init__.py
  ├── youtube_uploader.py     # Data API v3
  ├── metadata_generator.py   # Claude for SEO
  └── README.md
```

#### Week 2: Character Reference + V2 Prompts
```python
orchestrator/app/character/
  ├── reference.py             # CharacterReference class
  ├── reference_sheet.py       # 6-panel generator
  └── validator.py             # Consistency check

orchestrator/app/story/
  ├── prompt_engine.py         # Updated V2
  ├── camera_library.py        # DINO AI dictionary
  └── sound_library.py         # Sound descriptions
```

#### Week 3-4: Integration + Testing
```python
# Full pipeline integration
pipeline/runner.py — Update with all new modules

# E2E test
tests/integration/test_full_pipeline.py

# A/B testing setup
tests/experiments/test_packaging_variants.py
```

---

### 11.9 Files Reference

| File | Purpose | Status |
|------|---------|--------|
| `plans/prompt_12_GOOGLE_FLOW_INTEGRATION.md` | File này (Google Flow + Production Pipeline) | ✅ |
| `plans/prompt_13_PRODUCTION_PIPELINE.md` | Production Pipeline chi tiết 12 sections | ✅ |
| `plans/final.md` | Complete Playbook (v3.0) | ✅ |
| `orchestrator/app/research/` | Research + ideation | ✅ Exists |
| `orchestrator/app/editorial/` | Compilation + scripting | ✅ Exists |
| `orchestrator/app/story/` | Narrative + prompts | ✅ Exists |
| `orchestrator/app/voice/` | TTS generation | ✅ Exists |
| `orchestrator/app/mastering/` | Audio engineering | ✅ Exists |
| `orchestrator/app/character/` | Character design | ✅ Exists |
| `orchestrator/app/captions/` | Subtitle generation | ✅ Exists |
| `orchestrator/app/packaging/` | **NEW** - Title + thumbnail | ❌ Missing |
| `orchestrator/app/publishing/` | **NEW** - YouTube upload | ❌ Missing |
| `orchestrator/app/distribution/` | **NEW** - Shorts + TikTok | ❌ Missing |
| `orchestrator/app/analytics/` | **NEW** - CTR + retention | ❌ Missing |
| `orchestrator/app/ideation/` | **NEW** - Idea capture | ❌ Missing |

---

### 11.10 Final Recommendations

1. **Start với Packaging Module** — Highest ROI, gates weak ideas
2. **Add YouTube Upload ASAP** — Critical for distribution
3. **Implement Shorts Extractor** — Multiply output 3x
4. **Build Analysis Module last** — Need data first
5. **Use Existing modules** — 50+ files already production-ready

**Timeline estimate:**
- Quick Wins: 1-2 weeks → 2 hours saved per video
- Medium-term: 1 month → 5 hours saved per video
- Long-term: 1 quarter → 9 hours saved per video (target: 4h/video)

---

**END OF PROMPT 12 (UPDATED WITH PRODUCTION PIPELINE REPORT)**
