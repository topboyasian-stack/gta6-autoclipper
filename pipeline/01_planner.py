"""Stage 1: ask Gemini for JSON and validate it locally as an EpisodePackage."""
from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

from config import (
    ADDITIONAL_FALLBACK_PLANNER_MODELS, DEFAULT_SCENE_COUNT, FALLBACK_PLANNER_MODEL,
    GEMINI_API_KEY, PLANNER_MODEL, PLANNER_RETRY_ATTEMPTS,
    PLANNER_RETRY_INITIAL_DELAY_SECONDS, PLANNER_RETRY_MAX_DELAY_SECONDS,
)
from pipeline.models import EpisodePackage


def _make_prompt(topic: str, scene_count: int) -> str:
    profile = os.getenv("MYSTERY_PLANNER_PROFILE", "mystery_scifi").strip().lower()
    if profile in {"pip_pattern_explainer", "educational_explainer", "pip_pattern"}:
        channel_brief = """
You are the educational explainer writer and visual director for Pip & The Pattern, an original YouTube
channel about the hidden patterns behind money, habits, and human behaviour. Make an accurate, useful,
original visual explanation for a general audience; use concrete everyday examples and simple analogies.
This is educational nonfiction, not a mystery/science-fiction story. Do not invent research, statistics,
expert quotations, or guaranteed financial outcomes. Keep Pip visually consistent as a friendly recurring
host in a hand-drawn ink and soft-watercolor world on warm cream paper. Never imitate a named creator or
copy another video's script or structure.
""".strip()
        beat_duration = 5
        runtime_rule = "Target runtime is approximately <<EXPECTED_SECONDS>> seconds and must stay at or under 60 seconds."
        arc_rules = """
- Build one clear explanation arc: relatable hook, familiar problem, concrete visual analogy, why the
  pattern happens, and a useful takeaway.
- Choose story, contrast, cause-and-effect, myth correction, or a short sequence according to the topic.
  Do not force numbered steps, suspense, a plot twist, or a sequel hook.
- If the topic does not call for a sequence of steps, keep titles and narration free of step numbers.
- Keep narration short enough for about 5 seconds per scene (roughly 7–11 spoken words); the full voiceover
  must fit the 60-second target.
- Use financial examples as illustrations, not personalized financial advice. State uncertainty where needed.
""".strip()
    else:
        channel_brief = """
You are the story editor and cinematographer for an original, monetization-minded
YouTube mystery/science-fiction Shorts channel. Create one self-contained, emotionally satisfying
micro-story using original characters, no copyrighted franchises, and no imitation of named creators.
Tone: suspenseful, grounded, cinematic, intelligent.
""".strip()
        beat_duration = 8
        runtime_rule = "Target runtime is approximately <<EXPECTED_SECONDS>> seconds; keep it suitable for a vertical YouTube Short."
        arc_rules = "Build one clear story arc: hook, escalation, discovery or reversal, and satisfying ending/payoff."
    prompt = f"""
{channel_brief}

TOPIC / ONE-LINE PREMISE:
<<TOPIC>>

OUTPUT REQUIREMENTS:
- Create exactly <<SCENE_COUNT>> scenes, each planned for an approximately {beat_duration}-second Google Flow clip.
- {runtime_rule}
- The opening scene must establish a clear visual hook and an unanswered question or useful promise in the first 1–2 seconds.
{arc_rules}
- Build a coherent arc appropriate to the channel profile, with a clear ending and payoff.
- Write one continuous narrator voiceover, not character dialogue. Keep each scene's narration concise,
  natural to speak, and aligned with the action shown; avoid filler and generic exposition.
- narration_script must equal the scene narrations joined in order.
- Include 1–4 recurring characters with stable, specific visual descriptions and continuity anchors.
- Every scene must contain a vertical 9:16 starting-frame prompt and a separate concise motion prompt.
- Compose for 9:16 mobile viewing: clear focal subject, readable silhouettes, safe headroom, no critical
  story information at the extreme top/bottom, and enough foreground/background depth for motion.
- Describe shot size, composition, lighting, camera movement, environment, weather and emotional beat.
- Vary shot sizes and motivated camera movement while maintaining character identity, geography and screen direction.
- Maintain continuity: do not change a character's age, face, hair, clothing, distinctive props or location
  details between scenes unless the story explicitly shows a change.
- Avoid generated lettering, logos, subtitles, watermarks, split panels, and gibberish text inside images.
- Provide 3 distinct 16:9 YouTube thumbnail alternatives A/B/C with readable short title_text.
- Do not promise factual accuracy for fictional elements; mark potentially sensitive material in content_notes.
- End with an earned payoff; for educational explainers, the payoff should be a clear insight or practical takeaway rather than a forced plot twist.
- narration_script must be the scene narration combined in order; it will be rebuilt from scenes before saving.
- Use simple, direct strings and arrays. Do not add commentary or Markdown fences outside the JSON object.

JSON OUTPUT SHAPE — return one JSON object with these keys:
{
  "title": "string",
  "logline": "string",
  "topic": "string",
  "target_audience": "teen and adult general audience",
  "synopsis": "string",
  "visual_style": "string",
  "narration_script": "string",
  "characters": [
    {"character_id": "short stable id", "name": "string", "visual_description": "string",
     "continuity_anchors": ["string", "string"], "reference_image_prompt": "string"}
  ],
  "scenes": [
    {"scene_number": 1, "duration_seconds": 8, "scene_title": "string", "narration": "string",
     "start_frame_prompt": "string", "motion_prompt": "string", "camera_motion": "string",
     "sound_effects": ["string"], "character_ids": ["character id"], "continuity_notes": "string"}
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
    expected_seconds = min(60, int(scene_count) * 5) if profile in {"pip_pattern_explainer", "educational_explainer", "pip_pattern"} else int(scene_count) * 8
    return (prompt.replace("<<TOPIC>>", topic)
            .replace("<<SCENE_COUNT>>", str(scene_count))
            .replace("<<EXPECTED_SECONDS>>", str(expected_seconds)))


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
        start, end = text.find("{"), text.rfind("}")
        if start < 0 or end <= start:
            raise RuntimeError("Gemini did not return a JSON episode object.")
        return EpisodePackage.model_validate_json(text[start:end + 1])


def generate_episode(
    topic: str, output_dir: Path, scene_count: int = DEFAULT_SCENE_COUNT,
    api_key: str | None = None, primary_model: str | None = None,
) -> dict:
    """Generate and save a validated Shorts-first episode package."""
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

    retry_options = types.HttpRetryOptions(
        attempts=PLANNER_RETRY_ATTEMPTS, initial_delay=PLANNER_RETRY_INITIAL_DELAY_SECONDS,
        max_delay=PLANNER_RETRY_MAX_DELAY_SECONDS, exp_base=2.0, jitter=1.0,
        http_status_codes=[408, 429, 500, 502, 503, 504],
    )
    client = genai.Client(api_key=key, http_options=types.HttpOptions(timeout=180000, retry_options=retry_options))
    candidates = []
    for model in (primary_model or PLANNER_MODEL, FALLBACK_PLANNER_MODEL, *ADDITIONAL_FALLBACK_PLANNER_MODELS):
        if model and model not in candidates:
            candidates.append(model)
    last_error: Exception | None = None
    package: EpisodePackage | None = None
    used_model = None
    for model in candidates:
        try:
            print(f"Gemini planner: requesting {scene_count} vertical Shorts scenes from {model} "
                  f"(up to {PLANNER_RETRY_ATTEMPTS} transient retries)…", flush=True)
            response = client.models.generate_content(
                model=model, contents=_make_prompt(topic, int(scene_count)),
                config=types.GenerateContentConfig(response_mime_type="application/json", temperature=0.8),
            )
            print(f"Gemini planner: response received from {model}; validating episode…", flush=True)
            package = _episode_from_response(response)
            used_model = model
            print(f"Gemini planner: validated {len(package.scenes)} scenes.", flush=True)
            break
        except Exception as exc:
            last_error = exc
            print(f"Gemini planner: {model} failed ({type(exc).__name__}): {exc}", flush=True)
            if getattr(exc, "code", None) in {400, 401, 403}:
                break
    if package is None:
        raise RuntimeError(
            "Gemini planning failed on the configured model and fallback. Check API-key model access/quota; "
            f"no episode.json was written. Last error: {type(last_error).__name__}: {last_error}"
        ) from last_error
    if len(package.scenes) != int(scene_count):
        raise ValueError(f"Gemini produced {len(package.scenes)} scenes; {scene_count} were requested. No episode.json was written.")
    package.narration_script = "\n\n".join(scene.narration.strip() for scene in package.scenes)
    out = Path(output_dir)
    out.mkdir(parents=True, exist_ok=True)
    episode_path = out / "episode.json"
    temp_path = out / "episode.json.partial"
    temp_path.write_text(json.dumps(package.model_dump(mode="json"), ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    temp_path.replace(episode_path)
    (out / "episode_brief.md").write_text(
        "# " + package.title + "\n\n" + "**Logline:** " + package.logline + "\n\n"
        + "**Topic:** " + package.topic + "\n\n" + "**Target audience:** " + package.target_audience + "\n\n"
        + "**Synopsis:** " + package.synopsis + "\n\n" + "**Scene count:** " + str(len(package.scenes)) + "\n\n"
        + "**Planner model:** " + str(used_model) + "\n\n## Narration\n\n" + package.narration_script + "\n",
        encoding="utf-8",
    )
    return {"episode_json": str(episode_path), "title": package.title, "scene_count": len(package.scenes),
            "narration_word_count": len(package.narration_script.split()), "planner_model": used_model}


def load_episode(path: Path) -> EpisodePackage:
    episode_path = Path(path)
    if episode_path.is_dir():
        episode_path = episode_path / "episode.json"
    if not episode_path.is_file():
        raise FileNotFoundError(f"Episode package not found: {episode_path}")
    return EpisodePackage.model_validate_json(episode_path.read_text(encoding="utf-8"))
