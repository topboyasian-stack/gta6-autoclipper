"""Stage 1: ask Gemini for JSON and validate it locally as an EpisodePackage."""
from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

from config import (
    ADDITIONAL_FALLBACK_PLANNER_MODELS,
    FALLBACK_PLANNER_MODEL,
    GEMINI_API_KEY,
    PLANNER_MODEL,
    PLANNER_RETRY_ATTEMPTS,
    PLANNER_RETRY_INITIAL_DELAY_SECONDS,
    PLANNER_RETRY_MAX_DELAY_SECONDS,
)
from pipeline.models import EpisodePackage


def _make_prompt(topic: str, scene_count: int) -> str:
    prompt = """
You are the story editor and cinematographer for an original, monetization-minded
YouTube mystery/science-fiction channel. Create one self-contained episode that can
also seed a continuing series. Use original characters, no copyrighted franchises,
and no imitation of named creators. Tone: suspenseful, grounded, cinematic, intelligent.

TOPIC / ONE-LINE PREMISE:
<<TOPIC>>

OUTPUT REQUIREMENTS:
- Create exactly <<SCENE_COUNT>> scenes, each planned for an approximately 8-second Flow clip.
- The expected full cut is approximately <<EXPECTED_SECONDS>> seconds before pacing adjustments.
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
- narration_script must be the scene narration combined in order; it will be rebuilt from scenes before saving.
- Use simple, direct strings and arrays. Do not add commentary or Markdown fences outside the JSON object.

JSON OUTPUT SHAPE — return one JSON object with these keys:
{
  "title": "string",
  "logline": "string",
  "topic": "string",
  "target_audience": "string",
  "synopsis": "string",
  "visual_style": "string",
  "narration_script": "string",
  "characters": [
    {
      "character_id": "short stable id",
      "name": "string",
      "visual_description": "string",
      "continuity_anchors": ["string", "string"],
      "reference_image_prompt": "string"
    }
  ],
  "scenes": [
    {
      "scene_number": 1,
      "duration_seconds": 8,
      "scene_title": "string",
      "narration": "string",
      "start_frame_prompt": "string",
      "motion_prompt": "string",
      "camera_motion": "string",
      "sound_effects": ["string"],
      "character_ids": ["character id"],
      "continuity_notes": "string"
    }
  ],
  "thumbnail_prompts": [
    {"variant": "A", "concept": "string", "image_prompt": "string", "title_text": "string"},
    {"variant": "B", "concept": "string", "image_prompt": "string", "title_text": "string"},
    {"variant": "C", "concept": "string", "image_prompt": "string", "title_text": "string"}
  ],
  "content_notes": ["string"]
}
Use the exact property names above. Return valid JSON only.
""".strip()
    return (
        prompt.replace("<<TOPIC>>", topic)
        .replace("<<SCENE_COUNT>>", str(scene_count))
        .replace("<<EXPECTED_SECONDS>>", str(scene_count * 8))
    )


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

    # Gemini's SDK does not retry HTTP errors unless retry_options are configured.
    # Keep retries bounded and let the SDK handle transient 408/429/5xx responses
    # with exponential backoff before the planner moves to another model.
    retry_options = types.HttpRetryOptions(
        attempts=PLANNER_RETRY_ATTEMPTS,
        initial_delay=PLANNER_RETRY_INITIAL_DELAY_SECONDS,
        max_delay=PLANNER_RETRY_MAX_DELAY_SECONDS,
        exp_base=2.0,
        jitter=1.0,
        http_status_codes=[408, 429, 500, 502, 503, 504],
    )
    client = genai.Client(
        api_key=key,
        http_options=types.HttpOptions(
            timeout=180000,
            retry_options=retry_options,
        ),
    )
    primary = primary_model or PLANNER_MODEL
    candidates = []
    for model in (
        primary,
        FALLBACK_PLANNER_MODEL,
        *ADDITIONAL_FALLBACK_PLANNER_MODELS,
    ):
        if model and model not in candidates:
            candidates.append(model)
    last_error: Exception | None = None
    package: EpisodePackage | None = None
    used_model = None
    for model in candidates:
        try:
            print(
                f"Gemini planner: requesting {scene_count} scenes from {model} "
                (
                    f"(request timeout: 180 seconds; up to {PLANNER_RETRY_ATTEMPTS} attempts "
                    "for transient HTTP errors)…"
                ),
                flush=True,
            )
            response = client.models.generate_content(
                model=model,
                contents=_make_prompt(topic, int(scene_count)),
                # A compact in-prompt JSON shape avoids Gemini's schema-complexity limit.
                # EpisodePackage performs the full strict validation locally afterwards.
                config=types.GenerateContentConfig(
                    response_mime_type="application/json",
                    temperature=0.8,
                ),
            )
            print(f"Gemini planner: response received from {model}; validating episode…", flush=True)
            package = _episode_from_response(response)
            used_model = model
            print(f"Gemini planner: validated {len(package.scenes)} scenes.", flush=True)
            break
        except Exception as exc:
            last_error = exc
            print(f"Gemini planner: {model} failed ({type(exc).__name__}): {exc}", flush=True)
            # Invalid requests and permission errors will not be fixed by changing models.
            status_code = getattr(exc, "code", None)
            if status_code in {400, 401, 403}:
                break
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
