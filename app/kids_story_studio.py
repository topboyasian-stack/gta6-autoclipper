"""Narrated kids-story script generation for the Universal Colab Production Studio.

This module is intentionally separate from the tested engineering narration pipeline.
It reuses only the studio's shared, licence-verified Piper voice implementation.
"""
from __future__ import annotations

import json
import re
import time
from pathlib import Path
from typing import Iterable


def _story_word_targets(total_duration: float) -> tuple[int, int]:
    """Return target/minimum spoken words for the supplied scene runtime.

    The target guides the model; the lower bound allows a complete, coherent
    story to proceed when the model comes back shorter than requested. Narration
    is subsequently tempo-fitted to the actual scene duration.
    """
    target_words = max(50, min(145, int(float(total_duration) * 2.25)))
    minimum_story_words = max(45, int(target_words * 0.70))
    return target_words, minimum_story_words


def generate_kids_story_script(
    project_dir: Path,
    scene_files: Iterable[Path],
    story_title: str,
    gemini_api_key: str,
    model: str = "gemini-3.8-flash",
) -> dict:
    """Write a short, scene-grounded children's story for numbered Flow clips."""
    from PIL import Image
    from google import genai
    from google.genai import types

    from app.reusable_production import (
        _extract_scene_contact_sheet,
        _file_fingerprint,
        _generate_content_with_fallback,
        _json_fingerprint,
        _natural_key,
        _write_json,
    )

    project_dir = Path(project_dir)
    scenes = sorted([Path(p) for p in scene_files], key=lambda p: _natural_key(p.name))
    if len(scenes) < 2:
        raise ValueError("A narrated kids story needs at least two supplied Flow scenes.")
    if not gemini_api_key or len(gemini_api_key.strip()) < 10:
        raise ValueError(
            "GEMINI_API_KEY is required to write a story that matches the supplied scenes. "
            "Add it in Colab Secrets; do not paste it into the notebook."
        )
    if not story_title.strip():
        raise ValueError("Enter a title for this kids story.")

    durations = []
    import subprocess
    for scene in scenes:
        probe = subprocess.run(
            ["ffprobe", "-v", "error", "-show_entries", "format=duration",
             "-of", "default=noprint_wrappers=1:nokey=1", str(scene)],
            capture_output=True, text=True, timeout=30, check=True,
        )
        duration = float(probe.stdout.strip())
        if not (0 < duration <= 1800):
            raise ValueError(f"Unexpected scene duration for {scene.name}: {duration}")
        durations.append(duration)
    total_duration = sum(durations)
    # Aim for a complete spoken story across the scene runtime, not a brief intro
    # followed by twenty seconds of silent visuals. Treat the word target as guidance,
    # not a brittle pass/fail threshold; the voice is later tempo-fitted to the footage.
    target_words, minimum_story_words = _story_word_targets(total_duration)
    scene_rows = [{"scene_file": p.name, "duration_seconds": round(d, 2)} for p, d in zip(scenes, durations)]
    fingerprint = _json_fingerprint({
        "pipeline_version": 1,
        "story_title": story_title.strip(),
        "scene_files": [_file_fingerprint(p) for p in scenes],
        "target_words": target_words,
        "model": model,
    })

    brief_path = project_dir / "episode_brief.json"
    script_path = project_dir / "original_script.md"
    cache_path = project_dir / "kids_story_package.json"
    if brief_path.exists() and script_path.exists() and cache_path.exists():
        try:
            cached = json.loads(cache_path.read_text(encoding="utf-8"))
            script = str(cached.get("original_script", "")).strip()
            words = re.findall(r"[A-Za-z0-9]+(?:['’-][A-Za-z0-9]+)*", script)
            if cached.get("storyboard_fingerprint") == fingerprint and minimum_story_words <= len(words) <= target_words + 25:
                return cached
        except (OSError, json.JSONDecodeError):
            pass

    work_dir = project_dir / "work" / "kids_story"
    contact_sheet = _extract_scene_contact_sheet(scenes, work_dir / "scene_contact_sheet.jpg")
    prompt = f"""
You are an experienced children's picture-book writer. Create a warm, original,
coherent narrated story for young children (ages 3–7) using the actual supplied
Google Flow scene frames in the attached contact sheet. The contact sheet has one
row per source clip, in numbered scene order, with START, MIDDLE and END samples.

Title: {story_title.strip()}
Total footage duration: {total_duration:.1f} seconds.
Narration target: approximately {target_words} spoken words; aim for at least {minimum_story_words}, never exceed {target_words + 25}. Prioritize a coherent complete story over padding.
Source clips, in the exact order to be used:
{json.dumps(scene_rows, ensure_ascii=False)}

STORY RULES:
- Make a real story with a beginning, a small safe problem, an attempt to solve it,
  a kind/helpful choice, a satisfying ending, and one simple memorable lesson.
- Make the events cause and lead into one another; do not merely describe six unrelated shots.
- Let the observed characters and actions in the contact sheet guide the story.
  Do not identify species, relationships, objects or actions that are not reasonably visible.
- Respect the six scenes' exact supplied order. Do not reorder, remove or invent extra scenes.
- Write spoken narration for a single narrator. A few short quoted words of dialogue are
  okay for the narrator to read, but do not assume character lip-sync or separate voices.
- Use simple natural sentences, child-friendly vocabulary, gentle humour and a warm tone.
- No frightening peril, cruelty, dangerous imitation instructions, preachiness, headings,
  stage directions, camera directions, sound-effect cues or production notes in the spoken script.
- The final narration must sound like one complete little story and fit the available footage.
- Use the character name Puffy if it fits the supplied story title, but do not invent details
  about Puffy's appearance that are not visible.
- Return valid JSON only with exactly these keys:
  "episode_title", "story_lesson", "original_script", "scene_manifest".
- "scene_manifest" must contain one object for every supplied source file, in source order,
  with keys "order", "scene_file", "scene_title", and "story_beat".
- Preserve each scene_file exactly as provided; order must be 1 through {len(scenes)}.
"""
    # Bound network waits so a stalled API request cannot leave Colab executing forever.
    # HttpOptions.timeout is expressed in milliseconds by the Google Gen AI Python SDK.
    client = genai.Client(
        api_key=gemini_api_key.strip(),
        http_options=types.HttpOptions(timeout=90_000),
    )
    with Image.open(contact_sheet) as image:
        response, used_model = _generate_content_with_fallback(
            client=client,
            model=model,
            contents=[prompt, image.copy()],
            config=types.GenerateContentConfig(
                response_mime_type="application/json",
                temperature=0.55,
            ),
        )
    try:
        result = json.loads(response.text)
    except (TypeError, json.JSONDecodeError) as exc:
        raise RuntimeError("The story writer did not return valid JSON. No narrated export was made.") from exc

    title = str(result.get("episode_title", "")).strip()
    lesson = str(result.get("story_lesson", "")).strip()
    script = str(result.get("original_script", "")).strip()
    word_count = len(re.findall(r"[A-Za-z0-9]+(?:['’-][A-Za-z0-9]+)*", script))
    if len(title) < 3 or len(lesson) < 8 or not (minimum_story_words <= word_count <= target_words + 25):
        raise ValueError(
            f"The generated story package failed its length/content checks (word count {word_count}; "
            f"target {minimum_story_words}-{target_words + 25}). Nothing was exported. Re-run processing to retry."
        )
    rows = result.get("scene_manifest")
    expected = [p.name for p in scenes]
    if not isinstance(rows, list) or len(rows) != len(expected):
        raise ValueError("The story package must account for every supplied scene exactly once.")
    if [str(row.get("scene_file", "")) for row in rows] != expected:
        raise ValueError("The story writer changed the supplied scene order or filenames. Nothing was exported.")
    for index, row in enumerate(rows, 1):
        if int(row.get("order", 0)) != index or len(str(row.get("story_beat", "")).strip()) < 4:
            raise ValueError("The story's scene-by-scene sequence is incomplete. Nothing was exported.")

    package = {
        "episode_title": title,
        "story_lesson": lesson,
        "original_script": script,
        "scene_manifest": rows,
        "source_files": expected,
        "scene_duration_seconds": round(total_duration, 2),
        "target_word_count": target_words,
        "actual_word_count": word_count,
        "storyboard_fingerprint": fingerprint,
        "storyboard_model": used_model,
        "storyboard_visual_review": "completed",
        "script_generation_mode": "Gemini scene-grounded original children's story",
        "storyboard_generated_at": time.strftime("%Y-%m-%d %H:%M:%S"),
    }
    _write_json(cache_path, package)
    _write_json(brief_path, {
        "episode_title": title,
        "story_lesson": lesson,
        "original_script": script,
        "scene_manifest": rows,
        "storyboard_fingerprint": fingerprint,
        "script_generation_mode": package["script_generation_mode"],
        "storyboard_model": used_model,
        "source_files": expected,
    })
    script_path.write_text(f"# {title}\n\n{script}\n\n**Story lesson:** {lesson}\n", encoding="utf-8")
    return package



def prepare_puffy_story_voice(
    narration_path: Path,
    pitch_ratio: float = 1.12,
    target_duration: float | None = None,
) -> tuple[Path, dict]:
    """Create a consistent, brighter Puffy storybook voice from the verified LJSpeech narration.

    The original narration WAV is never modified. Pitch and formants are lifted together;
    tempo is adjusted only as much as needed to fit the scene duration. A deterministic
    resampling fallback supports standard Colab FFmpeg builds without librubberband.
    """
    import hashlib
    import subprocess

    from app.reusable_production import _write_json

    narration_path = Path(narration_path)
    if not narration_path.is_file():
        raise FileNotFoundError(f"Base Puffy narrator audio is missing: {narration_path}")
    if not 1.04 <= float(pitch_ratio) <= 1.20:
        raise ValueError("Puffy storybook pitch ratio must be between 1.04 and 1.20.")

    output_path = narration_path.parent / "puffy_storybook_narration.wav"
    metadata_path = narration_path.parent / "puffy_storybook_voice.json"
    profile_version = 2
    digest = hashlib.sha256(narration_path.read_bytes()).hexdigest()

    try:
        existing = json.loads(metadata_path.read_text(encoding="utf-8")) if metadata_path.exists() else {}
    except (OSError, json.JSONDecodeError):
        existing = {}

    def probe_duration(path: Path) -> float:
        result = subprocess.run(
            ["ffprobe", "-v", "error", "-show_entries", "format=duration",
             "-of", "default=noprint_wrappers=1:nokey=1", str(path)],
            capture_output=True, text=True, timeout=30, check=True,
        )
        return float(result.stdout.strip())

    source_duration = probe_duration(narration_path)
    if not (0 < source_duration <= 180):
        raise ValueError(f"Unexpected Puffy narration duration: {source_duration:.2f}s")

    if target_duration is not None:
        target_duration = float(target_duration)
        if not (15 <= target_duration <= 180):
            raise ValueError(f"Unexpected target duration for Puffy narration: {target_duration:.2f}s")
        tempo_scale = source_duration / target_duration
        if not 0.62 <= tempo_scale <= 1.15:
            raise ValueError(
                f"The story narration is {source_duration:.1f}s for {target_duration:.1f}s of scenes. "
                "The narration length needs adjusting; the studio will not distort the voice to force a fit."
            )
    else:
        tempo_scale = 0.94
    expected_duration = source_duration / tempo_scale

    if (
        output_path.is_file()
        and existing.get("source_sha256") == digest
        and existing.get("profile_version") == profile_version
        and abs(float(existing.get("tempo_scale", 0)) - tempo_scale) < 0.005
        and abs(probe_duration(output_path) - expected_duration) <= 0.8
    ):
        return output_path, existing

    probe = subprocess.run(
        ["ffprobe", "-v", "error", "-select_streams", "a:0",
         "-show_entries", "stream=sample_rate", "-of", "csv=p=0", str(narration_path)],
        capture_output=True, text=True, timeout=30, check=True,
    )
    source_rate = int(probe.stdout.strip().splitlines()[0])
    filter_list = subprocess.run(
        ["ffmpeg", "-hide_banner", "-filters"],
        capture_output=True, text=True, timeout=30, check=True,
    ).stdout
    has_rubberband = "rubberband" in filter_list

    polish = (
        "highpass=f=85,lowpass=f=13500,"
        "acompressor=threshold=0.125:ratio=2.0:attack=18:release=140,"
        "alimiter=limit=0.95"
    )
    if has_rubberband:
        voice_filter = (
            f"rubberband=pitch={pitch_ratio:.3f}:tempo={tempo_scale:.4f}:formant=shifted,"
            + polish
        )
        method = "rubberband pitch/formant lift with scene-length pacing"
    else:
        raised_rate = int(round(source_rate * pitch_ratio))
        voice_filter = (
            f"asetrate={raised_rate},aresample=48000,"
            f"atempo={tempo_scale / pitch_ratio:.8f}," + polish
        )
        method = "sample-rate pitch lift with scene-length tempo compensation"

    temporary_path = output_path.with_name(output_path.stem + ".partial.wav")
    temporary_path.unlink(missing_ok=True)
    result = subprocess.run(
        [
            "ffmpeg", "-y", "-i", str(narration_path),
            "-af", voice_filter, "-ar", "48000", "-ac", "2",
            "-c:a", "pcm_s16le", str(temporary_path),
        ],
        capture_output=True, text=True, timeout=120,
    )
    if result.returncode:
        temporary_path.unlink(missing_ok=True)
        raise RuntimeError(
            "Puffy storybook voice styling failed. The original narrator WAV is unchanged. "
            + (result.stderr or result.stdout or "")[-2500:]
        )

    styled_duration = probe_duration(temporary_path)
    if abs(styled_duration - expected_duration) > 0.8:
        temporary_path.unlink(missing_ok=True)
        raise RuntimeError(
            f"Puffy voice styling produced an unexpected duration "
            f"({styled_duration:.2f}s; expected {expected_duration:.2f}s)."
        )
    temporary_path.replace(output_path)

    details = {
        "profile_name": "Puffy Storybook",
        "profile_version": profile_version,
        "base_voice_model": "en_US-ljspeech-medium",
        "base_voice_model_license": "Public Domain; model card verified by studio voice loader",
        "pitch_ratio": float(pitch_ratio),
        "pitch_lift_semitones_approx": round(12 * __import__("math").log2(pitch_ratio), 2),
        "tempo_scale": round(tempo_scale, 4),
        "target_duration_seconds": round(expected_duration, 3),
        "processing_method": method,
        "source_sha256": digest,
        "source_duration_seconds": round(source_duration, 3),
        "styled_duration_seconds": round(styled_duration, 3),
        "created_at": time.strftime("%Y-%m-%d %H:%M:%S"),
    }
    _write_json(metadata_path, details)
    return output_path, details
