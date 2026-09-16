"""
Stage 8: scene_json — LLM emits the SceneDefinition JSON.

This is the highest-risk stage: the LLM must conform to a tight schema.
We use OpenAI's `response_format={"type":"json_object"}` to force valid
JSON, and stage 9 (validate) re-checks everything with Pydantic.

If validation fails, stage 9 will re-invoke this stage once with the
error message appended to the prompt. After one retry we surface the
error to the user.
"""
from __future__ import annotations

import json
from pathlib import Path

from app.core.logging import get_logger
from app.core.paths import read_json, stage_path, write_json
from app.pipeline.cache import should_skip
from app.pipeline.stages.base import Stage, StageContext
from app.providers.base import LLMMessage, LLMRequest
from app.providers.llm import get_llm_provider
from app.providers.openai_llm import SYSTEM_JSON_AGENT

log = get_logger(__name__)


_PROMPT = """[SCENE_DEFINITION_TASK] Topic: {topic}
Title: {title}
Script sections:
{script}

Storyboard beats:
{storyboard}

Word timestamps for narration (ms resolution):
{words}

Emit a complete SceneDefinition JSON for a 2-minute documentary. Follow
this schema strictly (any deviation will be rejected):

{{
  "meta": {{"title": "...", "fps": 30, "width": 1920, "height": 1080,
            "target_duration_sec": 120}},
  "style": {{"primary_color":"#RRGGBB","accent_color":"#RRGGBB",
             "background_color":"#RRGGBB","text_color":"#RRGGBB"}},
  "characters": [
    {{"id":"narrator","name":"Narrator","color":"#RRGGBB",
      "default_pose":"stand","description":"..."}}
  ],
  "environments": [
    {{"id":"ice_age_plains","name":"Ice Age Plains",
      "background_asset":"backgrounds/ice_age_plains.png","mood":"tense"}}
  ],
  "scenes": [
    {{
      "id":"scene_1","kind":"narration","start_sec":0.0,"end_sec":8.0,
      "environment_id":"ice_age_plains",
      "narration_text":"...",
      "narration_words": [{{"word":"...","start_sec":0.0,"end_sec":0.3}}, ...],
      "camera": {{"pan_x":0.5,"pan_y":0.5,"zoom":1.0,"easing":"ease_in_out"}},
      "actors":[{{"character_id":"narrator","x":0.5,"y":0.7,"scale":1.0,
                   "rotation_deg":0,"pose":"stand","enter_anim":"fade_in",
                   "exit_anim":"none"}}],
      "props":[], "overlay_text":[], "sfx":[], "music":null
    }}
  ]
}}

Hard constraints:
  - Scene `kind` is one of: narration, diagram, title, transition.
  - `pose` is one of: stand, walk, point, think, celebrate, hide, run, sit.
  - `enter_anim` / `exit_anim` one of: none, fade_in, slide_left,
    slide_right, pop, zoom_in.
  - `easing` one of: none, ease_in, ease_out, ease_in_out.
  - Scenes are sorted by start_sec, non-overlapping, contiguous.
  - narration_words must be inside the scene's start/end.
  - x/y/zoom are normalized 0..1.
  - Total duration ≈ 120 seconds (±20%).
  - Use exactly these environment_ids when relevant:
    ice_age_plains, cave_interior, diagram_white, mammoth_camp, title_card.
  - Use these prop kinds only (no arbitrary SVG):
    human_silhouette, cave, fire, tree_pine, snowflake, arrow, timeline,
    chart_axes, animal_mammoth, sun, mountain, question_mark.

Return ONLY the JSON object, no commentary.
"""


class SceneJsonStage(Stage):
    name = "scene_json"
    label = "Scene JSON"

    def run(self, ctx: StageContext) -> dict:
        out = stage_path(ctx.job_id, "scene_definition")
        if should_skip(out):
            return read_json(out)

        script = ctx.state.get("script") or read_json(stage_path(ctx.job_id, "script"))
        storyboard = ctx.state.get("storyboard") or read_json(stage_path(ctx.job_id, "storyboard"))
        titles = ctx.state.get("titles") or read_json(stage_path(ctx.job_id, "titles"))
        title = titles["candidates"][titles["chosen_index"]]["title"]
        words = ctx.state.get("narration", {}).get("words") or read_json(
            stage_path(ctx.job_id, "narration.words"))

        script_text = "\n".join(
            f"[{s['name']}] " + " ".join(b["text"] for b in s["beats"])
            for s in script["sections"]
        )
        storyboard_text = "\n".join(
            f"- ({b['environment_id']}, {b['duration_sec']:.0f}s) {b['summary']}"
            for b in storyboard["beats"]
        )
        words_text = json.dumps(words[:200])  # truncate if huge

        # PROMPT 6 INTEGRATION:
        # If an AssetSystemPackage exists from a prior run, surface its
        # canonical environment/prop IDs to the LLM so it does NOT invent
        # new IDs. This prevents the LLM from creating untracked assets.
        asset_pkg_path = stage_path(ctx.job_id, "asset_system_package")
        if Path(asset_pkg_path).exists():
            try:
                asset_pkg = read_json(asset_pkg_path)
                env_ids = [e["asset_id"] for e in asset_pkg.get("environments", [])]
                prop_ids = [p["asset_id"] for p in asset_pkg.get("props", [])]
                if env_ids:
                    storyboard_text = (
                        f"# Canonical assets available in registry:\n"
                        f"# environments: {', '.join(env_ids)}\n"
                        f"# props: {', '.join(prop_ids)}\n"
                        f"# Use ONLY these identifiers.\n\n"
                        f"{storyboard_text}"
                    )
                    log.info(
                        "[%s] %d canonical envs available to LLM",
                        self.name, len(env_ids),
                    )
            except Exception as exc:
                log.warning("[%s] asset_system_package read failed: %s", self.name, exc)

        # S8 SceneJson cần input lớn (script + storyboard + words).
        # Groq gpt-oss-120b có TPM limit 8000, cần input <6000 tokens.
        # Truncate aggressively để fit.
        provider = get_llm_provider()  # Groq default

        # Truncate storyboard mạnh hơn (thường là phần lớn nhất)
        # 1 token ≈ 3-4 chars cho English text. Mục tiêu: input <5000 tokens
        if len(storyboard_text) > 2500:
            log.info("[%s] truncating storyboard_text %d -> 2500 chars", self.name, len(storyboard_text))
            storyboard_text = storyboard_text[:2500] + "\n[... truncated]"
        if len(script_text) > 2000:
            log.info("[%s] truncating script_text %d -> 2000 chars", self.name, len(script_text))
            script_text = script_text[:2000] + "\n[... truncated]"
        # Chỉ giữ 100 word timestamps
        words_data = ctx.state.get("narration", {}).get("words") or read_json(
            stage_path(ctx.job_id, "narration.words"))
        if isinstance(words_data, list) and len(words_data) > 100:
            log.info("[%s] using first 100 of %d word timestamps", self.name, len(words_data))
            words_data = words_data[:100]
        words_text = json.dumps(words_data)

        req = LLMRequest(
            messages=[
                LLMMessage(role="system", content=SYSTEM_JSON_AGENT),
                LLMMessage(role="user", content=_PROMPT.format(
                    topic=ctx.topic, title=title, script=script_text,
                    storyboard=storyboard_text, words=words_text)),
            ],
            json_mode=True,
            model_hint="large",
            max_tokens=3000,
        )
        resp = provider.complete(req)
        assert resp.parsed_json is not None
        data = resp.parsed_json

        # Normalize mood enum: LLM thường trả về mood không match enum
        # Map common synonyms → valid values
        MOOD_MAP = {
            "intimate": "warm",
            "cozy": "warm",
            "calm": "calm",
            "peaceful": "calm",
            "serene": "calm",
            "tense": "tense",
            "anxious": "tense",
            "dramatic": "tense",
            "triumphant": "triumphant",
            "victorious": "triumphant",
            "heroic": "triumphant",
            "mysterious": "mysterious",
            "dark": "mysterious",
            "ominous": "mysterious",
            "warm": "warm",
            "happy": "warm",
            "friendly": "warm",
            "informative": "calm",
            "educational": "calm",
            "intro": "calm",
            "neutral": "calm",
            "title": "calm",
            "outro": "warm",
        }
        for env in data.get("environments", []):
            mood = env.get("mood", "calm")
            env["mood"] = MOOD_MAP.get(mood.lower(), "calm")

        # Normalize music: LLM có thể trả string thay vì MusicCue dict
        for scene in data.get("scenes", []):
            music = scene.get("music")
            if music is not None and isinstance(music, str):
                # Convert "path/to/file.mp3" → MusicCue dict
                # Extract name từ path
                name = music.split("/")[-1].replace(".mp3", "").replace(".wav", "").replace("-", "_") or "ambient_calm"
                scene["music"] = {"name": name, "gain_db": -18.0, "fade_in_sec": 0.5, "fade_out_sec": 1.0}
            elif music is None:
                pass  # music is optional

        # Normalize word timestamps: LLM có thể đặt từ cuối vượt quá scene end_sec
        # Clamp words vào trong [start_sec, end_sec]
        for scene in data.get("scenes", []):
            s_sec = scene.get("start_sec", 0)
            e_sec = scene.get("end_sec", 0)
            for w in scene.get("narration_words", []):
                # Nếu có end_sec > e_sec → clamp vào e_sec
                if "end_sec" in w and w["end_sec"] > e_sec:
                    w["end_sec"] = e_sec
                if "start_sec" in w and w["start_sec"] > e_sec:
                    w["start_sec"] = max(s_sec, e_sec - 0.1)
                if "start_sec" in w and "end_sec" in w and w["start_sec"] > w["end_sec"]:
                    w["start_sec"] = max(s_sec, w["end_sec"] - 0.1)

        # Normalize target_duration_sec: khớp với tổng scene duration (cho phép ±20%)
        # Nếu LLM tạo scene quá ngắn, điều chỉnh target_duration cho phù hợp
        if data.get("scenes"):
            last_scene = data["scenes"][-1]
            actual_duration = last_scene.get("end_sec", 0)
            target = data.get("meta", {}).get("target_duration_sec", 120)
            if abs(actual_duration - target) > target * 0.20:
                log.warning(
                    "[%s] total duration %.1fs differs from target %.1fs; adjusting target",
                    self.name, actual_duration, target,
                )
                data["meta"]["target_duration_sec"] = actual_duration

        write_json(out, data)
        log.info("[%s] emitted %d scenes", self.name, len(data.get("scenes", [])))
        return data
