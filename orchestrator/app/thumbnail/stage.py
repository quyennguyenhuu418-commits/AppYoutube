"""Stage: Thumbnail — generate thumbnail images from video.

Consumes:
  - final.mp4 (from s10_render)
  - story_package.json (from s2_thesis)
  - scene_definition.json (from s8_scene_json)

Produces:
  - thumbnails/thumb_*.webp (thumbnail images)
  - thumbnail_plan.json (ThumbnailPlan)
"""

from __future__ import annotations

import json
from pathlib import Path

from app.core.logging import get_logger
from app.core.paths import job_dir, thumbnails_dir, stage_path
from app.pipeline.stages.base import Stage, StageContext
from app.thumbnail.compiler import ThumbnailCompiler, ThumbnailGenerator, thumbnail_plan_fingerprint
from app.thumbnail.schemas import ThumbnailPlan, ThumbnailQAReport

log = get_logger(__name__)


class ThumbnailStage(Stage):
    """Thumbnail generation stage."""

    name = "thumbnail"
    label = "Thumbnails"

    def run(self, ctx: StageContext) -> dict:
        job_id = ctx.job_id

        # Load data
        story_pkg = self._load_story_package(job_id)
        scene_def = self._load_scene_definition(job_id)
        title = self._load_title(job_id)

        source_video = job_dir(job_id) / "final.mp4"
        source_path = str(source_video) if source_video.exists() else None

        # Compile plan
        compiler = ThumbnailCompiler()
        plan = compiler.compile(
            job_id=job_id,
            source_video_path=source_path,
            story_package=story_pkg,
            scene_definition=scene_def,
            title=title,
            topic=story_pkg.get("topic", ""),
        )

        # Save plan
        plan_path = stage_path(job_id, "thumbnail_plan")
        plan_path.write_text(plan.model_dump_json(indent=2), encoding="utf-8")

        # Generate thumbnails
        generator = ThumbnailGenerator()
        outputs: list[dict] = []
        out_dir = thumbnails_dir(job_id)
        out_dir.mkdir(parents=True, exist_ok=True)

        for tn in plan.thumbnails:
            output = self._generate_thumbnail(tn, source_path, out_dir, generator)
            outputs.append(output)

        log.info(
            "[%s] produced %d thumbnails for job %s",
            self.name, len(outputs), job_id
        )
        return {
            "plan_path": str(plan_path),
            "thumbnail_count": len(outputs),
            "thumbnails": outputs,
            "fingerprint": thumbnail_plan_fingerprint(plan),
        }

    def _generate_thumbnail(
        self,
        tn_spec,  # ThumbnailCompilationResult
        source_path: str | None,
        out_dir: Path,
        generator: ThumbnailGenerator,
    ) -> dict:
        output_path = out_dir / tn_spec.output_filename

        if source_path and Path(source_path).exists():
            try:
                result = generator.generate(
                    source_video=source_path,
                    output_path=str(output_path),
                    capture_time_sec=tn_spec.source.capture_time_sec,
                    width=tn_spec.render_settings.width,
                    height=tn_spec.render_settings.height,
                    format=tn_spec.render_settings.format.value,
                    quality=tn_spec.render_settings.quality,
                )
            except Exception as exc:
                log.warning("[%s] thumbnail generation failed: %s", self.name, exc)
                result = {"output_path": str(output_path), "error": str(exc)}
        else:
            result = {"output_path": str(output_path), "error": "source video not found"}

        # QA check
        qa = self._qa_thumbnail(output_path, tn_spec)

        return {
            "thumbnail_id": tn_spec.thumbnail_id,
            "path": str(output_path),
            "output_filename": tn_spec.output_filename,
            "dimensions": f"{tn_spec.render_settings.width}x{tn_spec.render_settings.height}",
            "format": tn_spec.render_settings.format.value,
            "caption": tn_spec.caption,
            "qa": qa.model_dump(),
        }

    def _qa_thumbnail(self, path: Path, tn_spec) -> ThumbnailQAReport:
        notes: list[str] = []
        exists = path.exists()
        file_size = path.stat().st_size if exists else 0
        format_valid = path.suffix in (".webp", ".jpeg", ".jpg", ".png")

        return ThumbnailQAReport(
            thumbnail_id=tn_spec.thumbnail_id,
            job_id=tn_spec.job_id,
            output_path=str(path),
            file_exists=exists,
            format_valid=format_valid,
            dimensions_correct=False,  # Would need actual dimensions
            file_size_bytes=file_size,
            has_content=exists and file_size > 1024,
            has_text=False,  # Would need OCR to check
            file_size_kb=file_size / 1024,
            passed=exists and format_valid and file_size > 1024,
            notes=tuple(notes),
        )

    @staticmethod
    def _load_story_package(job_id: str) -> dict:
        path = job_dir(job_id) / "story_package.json"
        if path.exists():
            return json.loads(path.read_text(encoding="utf-8"))
        return {"topic": "", "title": ""}

    @staticmethod
    def _load_scene_definition(job_id: str) -> dict:
        path = stage_path(job_id, "scene_definition")
        if path.exists():
            return json.loads(path.read_text(encoding="utf-8"))
        return {"scenes": []}

    @staticmethod
    def _load_title(job_id: str) -> str:
        pkg = ThumbnailStage._load_story_package(job_id)
        return pkg.get("title", "")


__all__ = ["ThumbnailStage"]
