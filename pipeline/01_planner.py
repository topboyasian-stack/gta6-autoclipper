"""Stage 1: use Gemini Structured Outputs to create a validated episode.json."""
from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

from config import FALLBACK_PLANNER_MODEL, GEMINI_API_KEY, PLANNER_MODEL
from pipeline.models import EpisodePackage


def _make_prompt(topic: str, scene_count: int) -> str:
    return f"""
You are the story editor and cinematographer for an original, monetization-minded
YouTube mystery/science-fiction channel. Create one self-contained episode that can
also seed a continuing series. Use original characters, no copyrighted franchises,
and no imitation of named creators. Tone: suspenseful, grounded, cinematic, intelligent.

TOPIC / ONE-LINE PREMISE:
{topic}

OUTPUT REQUIREMENTS:
- Create exactly {scene_count} scenes, each planned for an approximately 8-second Flow clip.
- The expected full cut is approximately {scene_count * 8} seconds before pacing adjustments.
- Write one continuous narrator voiceover, not character dialogue. Keep each scene's narration
  short enough to fit its visual beat; use pauses, tension and specific story progression.
- narration_script must equal the scene narrations joined in order.
- Include 1–6 recurring characters with stable, specific visual descriptions and continuity anchors.
- Every scene must contain a 16:9 cinematic starting-frame prompt and a separate concise motion prompt.
- Describe shot size, composition, lighting, camera movement, environment, weather and emotional beat.
- Maintain continuity: do not change a character's age, face, hair, clothing, distinctive props or location
  details between scenes unless the story explicitly shows a change.
- Avoid generated lettering, logos, subtitles, watermarks, and gibberish text inside images.
- Provide 3 distinct thumbnail alternatives A/B/C with readable short title_text.
- Do not promise factual accuracy for fictional elements; mark any potentially sensitive material in content_notes.
- Make the ending emotionally or intellectually satisfying while leaving one meaningful hook for the next episode.
Return only data matching the supplied structured schema.
""".strip()


def _episode_from_response(response: Any) -> EpisodePackage:
    parsed = getattr(response, "parsed", None)
    if isinstance(parsed, EpisodePackage):
        return parsed
    if parsed is not None:
        try:
            return EpisodePackage.model_validate(parsed)
        except Exception:
            pass
    text = getattr(response, "text", None)
    if not text:
        raise RuntimeError("Gemini returned no structured episode data.")
    try:
        return EpisodePackage.model_validate_json(text)
    except Exception:
        start = text.find("{")
        end = text.rfind("}")
        if start < 0 or end <= start:
            raise RuntimeError("Gemini did not return a JSON episode object.")
        return EpisodePackage.model_validate_json(text[start : end + 1])



# Gemini Developer API's raw JSON Schema route accepts a documented subset of JSON Schema.
# Keep those supported keywords on the wire; Pydantic still enforces all constraints locally.
_GEMINI_SCHEMA_KEYS = {
    "$id", "$defs", "$ref", "$anchor", "type", "format", "title", "description",
    "enum", "items", "prefixItems", "minItems", "maxItems", "minimum", "maximum",
    "anyOf", "oneOf", "properties", "additionalProperties", "required", "propertyOrdering",
}


def _gemini_response_schema() -> dict:
    """Return an API-compatible JSON Schema; strict Pydantic validation remains downstream."""
    source = EpisodePackage.model_json_schema()

    def clean(node: Any) -> Any:
        if not isinstance(node, dict):
            return node
        result = {}
        for key, value in node.items():
            if key not in _GEMINI_SCHEMA_KEYS:
                continue
            if key in {"$defs", "properties"} and isinstance(value, dict):
                # Preserve definition/property names; clean each associated schema node.
                result[key] = {name: clean(child) for name, child in value.items()}
            elif key in {"items", "additionalProperties"} and isinstance(value, dict):
                result[key] = clean(value)
            elif key in {"anyOf", "oneOf", "prefixItems"} and isinstance(value, list):
                result[key] = [clean(child) for child in value]
            else:
                result[key] = value
        return result

    return clean(source)


def generate_episode(
    topic: str,
    output_dir: Path,
    scene_count: int = 24,
    api_key: str | None = None,
    primary_model: str | None = None,
) -> dict:
    """Generate and save a validated episode.json and a readable episode brief."""
    topic = (topic or "").strip()
    if len(topic) < 8:
        raise ValueError("Enter a usable topic or one-line premise (at least 8 characters).")
    if not 6 <= int(scene_count) <= 48:
        raise ValueError("scene_count must be between 6 and 48.")
    key = (api_key or os.getenv("GEMINI_API_KEY") or GEMINI_API_KEY).strip()
    if len(key) < 10:
        raise ValueError("GEMINI_API_KEY is missing. Save it in Colab Secrets or the local .env file.")
    try:
        from google import genai
        from google.genai import types
    except ImportError as exc:
        raise RuntimeError("Install google-genai before running the planner stage.") from exc

    client = genai.Client(api_key=key)
    primary = primary_model or PLANNER_MODEL
    candidates = [primary]
    if FALLBACK_PLANNER_MODEL and FALLBACK_PLANNER_MODEL not in candidates:
        candidates.append(FALLBACK_PLANNER_MODEL)
    last_error: Exception | None = None
    package: EpisodePackage | None = None
    used_model = None
    for model in candidates:
        try:
            response = client.models.generate_content(
                model=model,
                contents=_make_prompt(topic, int(scene_count)),
                config=types.GenerateContentConfig(
                    response_mime_type="application/json",
                    # Use raw JSON Schema to avoid a google-genai SDK bug: response_schema
                    # converts Pydantic's additionalProperties flag into a proto field rejected
                    # by Gemini Developer API. Gemini supports JSON Schema via response_json_schema.
                    response_json_schema=_gemini_response_schema(),
                    temperature=0.8,
                ),
            )
            package = _episode_from_response(response)
            used_model = model
            break
        except Exception as exc:
            last_error = exc
    if package is None:
        raise RuntimeError(
            "Gemini planning failed on the configured model and fallback. "
            "Check API-key model access/quota; no episode.json was written. "
            f"Last error: {type(last_error).__name__}: {last_error}"
        ) from last_error

    if len(package.scenes) != int(scene_count):
        raise ValueError(
            f"Gemini produced {len(package.scenes)} scenes; {scene_count} were requested. "
            "No episode.json was written."
        )
    # Rebuild script from the individually timed scene narration to avoid text/audio drift.
    package.narration_script = "\n\n".join(scene.narration.strip() for scene in package.scenes)
    out = Path(output_dir)
    out.mkdir(parents=True, exist_ok=True)
    episode_path = out / "episode.json"
    temp_path = out / "episode.json.partial"
    temp_path.write_text(
        json.dumps(package.model_dump(mode="json"), ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    temp_path.replace(episode_path)
    (out / "episode_brief.md").write_text(
        "# " + package.title + "\n\n"
        + "**Logline:** " + package.logline + "\n\n"
        + "**Topic:** " + package.topic + "\n\n"
        + "**Target audience:** " + package.target_audience + "\n\n"
        + "**Synopsis:** " + package.synopsis + "\n\n"
        + "**Scene count:** " + str(len(package.scenes)) + "\n\n"
        + "**Planner model:** " + str(used_model) + "\n\n"
        + "## Narration\n\n" + package.narration_script + "\n",
        encoding="utf-8",
    )
    return {
        "episode_json": str(episode_path),
        "title": package.title,
        "scene_count": len(package.scenes),
        "narration_word_count": len(package.narration_script.split()),
        "planner_model": used_model,
    }


def load_episode(path: Path) -> EpisodePackage:
    episode_path = Path(path)
    if episode_path.is_dir():
        episode_path = episode_path / "episode.json"
    if not episode_path.is_file():
        raise FileNotFoundError(f"Episode package not found: {episode_path}")
    return EpisodePackage.model_validate_json(episode_path.read_text(encoding="utf-8"))
