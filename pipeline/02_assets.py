"""Stage 2: build image prompts and optionally generate images through Gemini.

Image API calls are disabled by default because Google AI Pro subscription credits do
not cover Gemini Developer API billing. Use --allow-paid-images only after reviewing
the current API pricing for the key being used.
"""
from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

from PIL import Image, ImageOps

from config import ALLOW_PAID_IMAGE_API, IMAGE_MODEL, MAX_IMAGES_PER_API_RUN
from pipeline.models import EpisodePackage


def _load_episode(output_dir: Path) -> EpisodePackage:
    path = Path(output_dir) / "episode.json"
    if not path.is_file():
        raise FileNotFoundError(f"Run stage 1 first: {path} is missing.")
    return EpisodePackage.model_validate_json(path.read_text(encoding="utf-8"))


def _prompt_plan(package: EpisodePackage, output_dir: Path) -> list[dict]:
    out = Path(output_dir)
    plan = []
    for scene in package.scenes:
        name = f"scene_{int(scene.scene_number):03d}.png"
        plan.append({
            "kind": "starting_frame",
            "key": name,
            "output": str(out / "frames" / name),
            "prompt": (
                "Create one cinematic horizontal 16:9 starting frame for an original mystery/sci-fi film. "
                + package.visual_style + " "
                + scene.start_frame_prompt
                + " No written text, subtitles, logos, watermarks or panels."
            ),
        })
    for character in package.characters:
        name = f"character_{character.character_id}.png"
        plan.append({
            "kind": "character_reference",
            "key": name,
            "output": str(out / "character_references" / name),
            "prompt": (
                "Create a clean, production-ready character reference sheet for consistent future animation. "
                "Show a single original character with consistent face, hair, body proportions, wardrobe and "
                "distinctive props in clear front, three-quarter and profile views on a neutral uncluttered "
                "background. " + character.reference_image_prompt + " No labels or written text."
            ),
        })
    for thumb in package.thumbnail_prompts:
        name = f"thumbnail_{thumb.variant}.png"
        plan.append({
            "kind": "thumbnail",
            "key": name,
            "output": str(out / "thumbnails" / name),
            "prompt": (
                "Create a high-contrast 16:9 YouTube thumbnail for an original mystery/sci-fi episode. "
                "Make one readable focal point, strong silhouette, emotional tension and clear negative space "
                "for a title overlay. Do not render words or logos into the image. "
                + thumb.image_prompt
            ),
        })
    return plan


def _normalize_16_9(path: Path, kind: str) -> None:
    if kind == "character_reference":
        return
    with Image.open(path) as im:
        im = im.convert("RGB")
        result = ImageOps.fit(im, (1920, 1080), method=Image.Resampling.LANCZOS, centering=(0.5, 0.5))
        result.save(path, format="PNG", optimize=True)


def _save_image_response(response: Any, destination: Path) -> bool:
    destination.parent.mkdir(parents=True, exist_ok=True)
    for candidate in getattr(response, "candidates", []) or []:
        content = getattr(candidate, "content", None)
        for part in (getattr(content, "parts", []) or []):
            image_obj = None
            try:
                image_obj = part.as_image()
            except Exception:
                image_obj = None
            if image_obj is not None:
                image_obj.save(destination)
                return True
            inline = getattr(part, "inline_data", None)
            data = getattr(inline, "data", None) if inline is not None else None
            if data:
                import base64
                raw = base64.b64decode(data) if isinstance(data, str) else data
                destination.write_bytes(raw)
                return True
    return False


def generate_image_assets(
    output_dir: Path,
    *,
    allow_paid: bool = False,
    max_images: int | None = None,
) -> dict:
    """Generate at most one bounded image batch; repeated runs resume existing assets."""
    out = Path(output_dir)
    package = _load_episode(out)
    plan = _prompt_plan(package, out)
    plan_path = out / "assets_generation_plan.json"
    plan_path.write_text(json.dumps(plan, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    missing = [item for item in plan if not Path(item["output"]).is_file()]
    if not (allow_paid or ALLOW_PAID_IMAGE_API):
        return {
            "status": "prompt-only",
            "generated": 0,
            "pending": len(missing),
            "plan": str(plan_path),
            "message": (
                "Image API generation was skipped. Gemini API image calls may be billed separately from "
                "Google AI Pro. Use this plan for an authorized image workflow, or explicitly opt in after "
                "checking the current API pricing."
            ),
        }
    key = os.getenv("GEMINI_API_KEY", "").strip()
    if len(key) < 10:
        raise ValueError("GEMINI_API_KEY is missing.")
    limit = min(MAX_IMAGES_PER_API_RUN, max(1, int(max_images or MAX_IMAGES_PER_API_RUN)))
    batch = missing[:limit]
    if not batch:
        return {"status": "complete", "generated": 0, "pending": 0, "plan": str(plan_path)}
    try:
        from google import genai
        from google.genai import types
    except ImportError as exc:
        raise RuntimeError("Install google-genai to generate image assets.") from exc

    client = genai.Client(api_key=key)
    generated = []
    failures = []
    for item in batch:
        target = Path(item["output"])
        try:
            target.parent.mkdir(parents=True, exist_ok=True)
            response = client.models.generate_content(
                model=IMAGE_MODEL,
                contents=item["prompt"],
                config=types.GenerateContentConfig(response_modalities=["TEXT", "IMAGE"]),
            )
            if not _save_image_response(response, target):
                raise RuntimeError("Gemini returned no image data.")
            _normalize_16_9(target, item["kind"])
            generated.append(str(target))
        except Exception as exc:
            failures.append({"key": item["key"], "error": f"{type(exc).__name__}: {exc}"})
            if target.exists() and target.stat().st_size == 0:
                target.unlink()
    remaining = sum(not Path(item["output"]).is_file() for item in plan)
    result = {
        "status": "partial" if remaining else "complete",
        "generated": len(generated),
        "files": generated,
        "pending": remaining,
        "batch_limit": limit,
        "plan": str(plan_path),
        "failures": failures,
        "model": IMAGE_MODEL,
        "warning": "Check API billing and inspect assets before using them in production.",
    }
    (out / "assets_generation_report.json").write_text(
        json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    return result
