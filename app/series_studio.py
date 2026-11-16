"""Story-first production tools for the original THE 2:17 SIGNAL series.

This module is deliberately separate from the gaming, engineering and legacy Puffy
pipelines. It keeps the series bible, canon ledger, character references and voice
cast in a persistent Drive workspace, then creates episode-specific story and
Flow shot packages before any video clips are generated.
"""
from __future__ import annotations

import hashlib
import json
import re
import shutil
import subprocess
import time
import wave
from pathlib import Path
from typing import Any, Iterable

SERIES_ID = "the_217_signal"
SERIES_TITLE = "THE 2:17 SIGNAL"
DEFAULT_SCENE_COUNT = 24
DEFAULT_SCENE_SECONDS = 8.0
DEFAULT_WORD_RANGE = (340, 520)
SAMPLE_LINE = (
    "The receiver is active. I heard the warning at two seventeen. "
    "We verify the location before anyone acts."
)


def _read_json(path: Path, default: Any = None) -> Any:
    try:
        return json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return default


def _write_json(path: Path, payload: dict) -> Path:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".partial")
    temporary.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    temporary.replace(path)
    return path


def _fingerprint(payload: Any) -> str:
    encoded = json.dumps(payload, sort_keys=True, ensure_ascii=False, default=str).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _words(value: str) -> list[str]:
    return re.findall(r"[A-Za-z0-9]+(?:['’\-][A-Za-z0-9]+)*", value or "")


def _safe_id(value: str) -> str:
    safe = re.sub(r"[^A-Za-z0-9_-]+", "_", str(value).strip()).strip("_")[:70]
    if not safe:
        raise ValueError("A non-empty project identifier is required.")
    return safe


def _natural_key(path: Path) -> list[Any]:
    return [int(part) if part.isdigit() else part.lower()
            for part in re.split(r"(\d+)", Path(path).name)]


def initialize_series_workspace(workspace: Path) -> Path:
    """Install default series assets into Drive without overwriting user-approved files."""
    workspace = Path(workspace)
    repository_template = Path(__file__).resolve().parents[1] / "series" / SERIES_ID
    if not repository_template.is_dir():
        raise FileNotFoundError(f"The {SERIES_TITLE} source-of-truth files are missing from the repository.")
    series_dir = workspace / "series" / SERIES_ID
    series_dir.mkdir(parents=True, exist_ok=True)
    for source in repository_template.rglob("*"):
        if not source.is_file():
            continue
        relative = source.relative_to(repository_template)
        destination = series_dir / relative
        destination.parent.mkdir(parents=True, exist_ok=True)
        if not destination.exists():
            shutil.copy2(source, destination)
    for folder in (
        "character_references", "voice_auditions", "voice_models",
        "continuity", "episodes", "exports",
    ):
        (series_dir / folder).mkdir(parents=True, exist_ok=True)

    continuity_path = series_dir / "continuity" / "season_01.json"
    if not continuity_path.exists():
        _write_json(continuity_path, {
            "season": 1,
            "canonical_episodes": [],
            "last_updated": None,
            "policy": "Only manually approved and exported episodes may enter canon.",
        })
    return series_dir


def load_series_bible(series_dir: Path) -> dict:
    bible = _read_json(Path(series_dir) / "series_bible.json")
    if not isinstance(bible, dict):
        raise FileNotFoundError(f"Series bible not found in {series_dir}.")
    validate_series_bible(bible)
    return bible


def validate_series_bible(bible: dict) -> None:
    required = ("series_id", "series_title", "logline", "world_rules", "cast", "style_bible")
    missing = [key for key in required if not bible.get(key)]
    if missing:
        raise ValueError("Series bible is incomplete: " + ", ".join(missing))
    if len(bible["cast"]) < 2:
        raise ValueError("A serialized series needs at least two defined recurring characters.")
    character_ids = [str(item.get("id", "")).strip() for item in bible["cast"]]
    if any(not item for item in character_ids) or len(set(character_ids)) != len(character_ids):
        raise ValueError("Every recurring character needs a unique, non-empty id.")
    for character in bible["cast"]:
        if not character.get("name") or not character.get("appearance_lock"):
            raise ValueError(f"Character {character.get('id', '(unknown)')} needs a name and appearance lock.")
        voice = character.get("voice_profile") or {}
        if not voice.get("voice_id"):
            raise ValueError(f"Character {character['id']} has no proposed voice profile.")


def _load_season_outline(series_dir: Path, season_number: int) -> dict:
    path = Path(series_dir) / f"season_{int(season_number):02d}" / "outline.json"
    outline = _read_json(path)
    if not isinstance(outline, dict):
        raise FileNotFoundError(f"Season outline is missing: {path}")
    return outline


def _load_canonical_continuity(series_dir: Path, season_number: int) -> dict:
    path = Path(series_dir) / "continuity" / f"season_{int(season_number):02d}.json"
    state = _read_json(path, {"season": int(season_number), "canonical_episodes": []})
    if not isinstance(state.get("canonical_episodes"), list):
        raise ValueError(f"Continuity ledger is malformed: {path}")
    return state


def create_series_episode_project(
    workspace: Path,
    project_id: str,
    season_number: int = 1,
    episode_number: int = 1,
) -> Path:
    """Create a new episode workspace while leaving all prior projects untouched."""
    series_dir = initialize_series_workspace(workspace)
    outline = _load_season_outline(series_dir, season_number)
    if not any(int(item.get("episode", 0)) == int(episode_number) for item in outline.get("episodes", [])):
        raise ValueError(f"Episode {episode_number} is not defined in season {season_number}.")
    project_dir = Path(workspace) / "projects" / _safe_id(project_id)
    project_dir.mkdir(parents=True, exist_ok=True)
    _write_json(project_dir / "series_episode_state.json", {
        "series_id": SERIES_ID,
        "series_title": SERIES_TITLE,
        "season": int(season_number),
        "episode": int(episode_number),
        "status": "preproduction",
        "updated_at": time.strftime("%Y-%m-%d %H:%M:%S"),
    })
    return project_dir


def _validate_episode_package(package: dict, bible: dict, expected_episode: int) -> dict:
    for key in ("episode_title", "logline", "episode_summary", "continuity_in", "continuity_out", "ending_hook", "scenes"):
        if not package.get(key):
            raise ValueError(f"Episode package is missing {key}.")
    if int(package.get("episode_number", 0)) != int(expected_episode):
        raise ValueError("Generated package changed the requested episode number.")

    cast_ids = {str(item["id"]) for item in bible["cast"]}
    location_ids = {str(item["id"]) for item in bible.get("setting", {}).get("locations", [])}
    scenes = package["scenes"]
    if not isinstance(scenes, list) or len(scenes) != DEFAULT_SCENE_COUNT:
        raise ValueError(f"The pilot package must contain exactly {DEFAULT_SCENE_COUNT} ordered scenes.")
    runtime = 0.0
    total_words = 0
    all_dialogue = []
    for index, scene in enumerate(scenes, 1):
        if int(scene.get("order", 0)) != index:
            raise ValueError(f"Scene order is not sequential at scene {index}.")
        duration = float(scene.get("duration_seconds", 0))
        if not 6 <= duration <= 9:
            raise ValueError(f"Scene {index} must be between 6 and 9 seconds, not {duration}.")
        runtime += duration
        if scene.get("location_id") not in location_ids:
            raise ValueError(f"Scene {index} uses an unknown location. Update the series bible before adding locations.")
        character_ids = scene.get("characters")
        if not isinstance(character_ids, list) or not set(character_ids).issubset(cast_ids):
            raise ValueError(f"Scene {index} contains a character outside the approved cast.")
        for key in ("scene_title", "visual_action", "camera", "flow_prompt", "continuity_notes"):
            if not str(scene.get(key, "")).strip():
                raise ValueError(f"Scene {index} is missing {key}.")
        lines = scene.get("dialogue_lines")
        if not isinstance(lines, list) or not 1 <= len(lines) <= 3:
            raise ValueError(f"Scene {index} must contain one to three dialogue lines.")
        for line in lines:
            speaker = str(line.get("speaker_id", ""))
            text = str(line.get("text", "")).strip()
            count = len(_words(text))
            if speaker not in cast_ids or speaker not in character_ids:
                raise ValueError(f"Scene {index} dialogue uses a speaker not present in that scene.")
            if not 3 <= count <= 24:
                raise ValueError(f"Scene {index} has a dialogue line outside the 3–24 word limit.")
            total_words += count
            all_dialogue.append((speaker, text))
    if not 160 <= runtime <= 220:
        raise ValueError(f"Episode picture runtime must be 160–220 seconds; generated runtime is {runtime:.1f}s.")
    low, high = DEFAULT_WORD_RANGE
    if not low <= total_words <= high:
        raise ValueError(f"Episode dialogue must contain {low}–{high} spoken words; received {total_words}.")
    package["scene_runtime_seconds"] = round(runtime, 2)
    package["dialogue_word_count"] = total_words
    package["dialogue_script"] = "\n".join(
        f"{next(c['name'] for c in bible['cast'] if c['id'] == speaker)}: {line}"
        for speaker, line in all_dialogue
    )
    return package


def render_series_flow_prompt_pack(package: dict, bible: dict) -> str:
    """Build reference-driven, no-generated-dialogue scene prompts for Flow."""
    cast = {str(item["id"]): item for item in bible["cast"]}
    style = bible["style_bible"]
    global_lock = (
        f"SERIES: {bible['series_title']}. "
        f"VISUAL STYLE: {style['animation']}; lighting: {style['lighting']}; "
        f"palette: {', '.join(style['palette'])}; camera: {style['camera']}. "
        "This is one episode of the same continuing animated series. Maintain exact "
        "location geography, prop placement, lighting continuity and character identity. "
        "Use the uploaded approved character reference images as strict visual identity "
        "references. Do not reinterpret, redesign, beautify, age, recast or change any "
        "character. Do not generate dialogue, voiceover, subtitles, readable text, logos "
        "or watermarks; all dialogue and captions will be added in post-production. "
        "Use one clear action and one motivated camera movement per clip."
    )
    blocks = [
        f"# {bible['series_title']} — Season {package.get('season_number', 1)}, "
        f"Episode {package['episode_number']:02d}: {package['episode_title']}",
        "",
        "## Mandatory scene-generation rules",
        global_lock,
        "",
        "Generate the scenes separately in order. Reuse the same Flow project and the exact "
        "approved character-reference images. Export each clip as MP4 and name it "
        "scene_001.mp4 through scene_024.mp4. Do not generate audio dialogue inside Flow.",
        "",
    ]
    for scene in package["scenes"]:
        refs = []
        for character_id in scene["characters"]:
            character = cast[character_id]
            refs.append(
                f"{character['name']} — use {character['reference_asset']}. "
                f"Appearance lock: {character['appearance_lock']}"
            )
        prompt = (
            f"## Scene {int(scene['order']):02d} — {scene['scene_title']}\n\n"
            f"{global_lock}\n\n"
            f"CHARACTER REFERENCES:\n" + "\n".join(refs) + "\n\n"
            f"LOCATION: {scene['location_id']} (preserve its established design and geography).\n"
            f"ACTION: {scene['visual_action']}\n"
            f"CAMERA: {scene['camera']}\n"
            f"CONTINUITY: {scene['continuity_notes']}\n"
            f"SHOT PROMPT: {scene['flow_prompt']}\n\n"
            "No audible speech, no lip-synced dialogue, no text, no captions, no logos, no watermark."
        )
        blocks.append(prompt)
        blocks.append("")
    return "\n".join(blocks).strip() + "\n"


def generate_series_episode_package(
    project_dir: Path,
    series_dir: Path,
    season_number: int,
    episode_number: int,
    gemini_api_key: str,
    model: str = "gemini-3.8-flash",
    force_regenerate: bool = False,
) -> dict:
    """Generate an episode screenplay and Flow prompt pack before video generation."""
    if not gemini_api_key or len(gemini_api_key.strip()) < 10:
        raise ValueError("Add GEMINI_API_KEY in Colab Secrets. Do not paste API keys into the notebook.")
    bible = load_series_bible(series_dir)
    outline = _load_season_outline(series_dir, season_number)
    episode_outline = next(
        (item for item in outline.get("episodes", []) if int(item.get("episode", 0)) == int(episode_number)),
        None,
    )
    if episode_outline is None:
        raise ValueError(f"Episode {episode_number} is not defined in season {season_number}.")
    continuity = _load_canonical_continuity(series_dir, season_number)
    canonical = continuity["canonical_episodes"]
    completed_numbers = {int(item.get("episode", 0)) for item in canonical}
    missing_prior = [number for number in range(1, int(episode_number)) if number not in completed_numbers]
    if missing_prior:
        raise ValueError(
            "Future episodes can only be drafted after all earlier episodes are marked canonical. "
            f"Missing approved episode(s): {', '.join(map(str, missing_prior))}."
        )

    project_dir = Path(project_dir)
    project_dir.mkdir(parents=True, exist_ok=True)
    package_path = project_dir / "series_episode_package.json"
    fingerprint_payload = {
        "bible": bible,
        "outline": episode_outline,
        "continuity": canonical,
        "season": int(season_number),
        "episode": int(episode_number),
        "model": model,
        "scene_count": DEFAULT_SCENE_COUNT,
        "word_range": DEFAULT_WORD_RANGE,
    }
    fingerprint = _fingerprint(fingerprint_payload)
    cached = _read_json(package_path, {})
    if not force_regenerate and cached.get("request_fingerprint") == fingerprint:
        return cached

    prompt = f"""
You are the showrunner and screenplay editor for an original premium animated serialized drama.
Write one complete, producible episode. Treat the provided series bible and season outline as
the only canon. Do not add new permanent characters, locations, organisations or world rules.

SERIES BIBLE:
{json.dumps(bible, ensure_ascii=False, indent=2)}

SEASON OUTLINE:
{json.dumps(outline, ensure_ascii=False, indent=2)}

THIS EPISODE'S REQUIRED STORY:
{json.dumps(episode_outline, ensure_ascii=False, indent=2)}

PREVIOUS CANONICAL EPISODE STATE:
{json.dumps(canonical, ensure_ascii=False, indent=2)}

OUTPUT REQUIREMENTS:
- Return valid JSON only, with keys: season_number, episode_number, episode_title, logline,
  episode_summary, continuity_in, continuity_out, ending_hook, scenes.
- Create exactly {DEFAULT_SCENE_COUNT} scenes in order. Each scene is {DEFAULT_SCENE_SECONDS:.0f}
  seconds and the full picture runtime must be 160–220 seconds.
- The spoken dialogue must total {DEFAULT_WORD_RANGE[0]}–{DEFAULT_WORD_RANGE[1]} words.
- Every scene must have 1–3 dialogue_lines. Each line must contain 3–24 words.
- Each dialogue line must use a speaker_id from the approved cast and that character must appear
  in the same scene's characters list. Never invent a voice or give one character another's lines.
- Every scene object must have: order, duration_seconds, scene_title, location_id, characters,
  visual_action, camera, continuity_notes, flow_prompt, dialogue_lines.
- Each dialogue_lines object has exactly speaker_id and text.
- Use only the known location IDs in the bible. If a scene needs a new recurring location, do not
  invent it; stage the scene at an existing location or clearly flag a non-recurring exterior.
- The dialogue should sound performed, not like a summary. Use distinct motivations and natural
  interruptions, restrained pauses and specific character language. Avoid exposition dumps.
- No jokes, memes, comic relief, forced humour, slapstick, cheap jump scares or filler.
- The episode must have a satisfying immediate dramatic resolution, advance the season mystery,
  change at least one character relationship or belief, and end on the specified meaningful hook.
- Respect every world rule and all established character facts. No contradictions, unexplained
  powers, arbitrary rescues or convenient coincidences.
- Keep the West African setting grounded and specific without stereotypes or generic tourist imagery.
- Flow prompts describe silent visuals only: no speech, voiceover, subtitles, signs, logos or readable text.
  Every prompt must direct Flow to reuse the exact supplied character-reference images.
- Do not make unsupported scientific or real-world factual claims; all technology shown is fictional
  where not explicitly established as real.
"""
    from google import genai
    from google.genai import types
    from app.reusable_production import _generate_content_with_fallback

    client = genai.Client(
        api_key=gemini_api_key.strip(),
        http_options=types.HttpOptions(timeout=120_000),
    )
    response, used_model = _generate_content_with_fallback(
        client=client,
        model=model,
        contents=[prompt],
        config=types.GenerateContentConfig(
            response_mime_type="application/json",
            temperature=0.45,
        ),
    )
    try:
        package = json.loads(response.text)
    except (TypeError, json.JSONDecodeError) as exc:
        raise RuntimeError("The series writer returned invalid JSON. No episode package was saved.") from exc
    package["season_number"] = int(season_number)
    package["episode_number"] = int(episode_number)
    package = _validate_episode_package(package, bible, episode_number)
    package["series_id"] = bible["series_id"]
    package["series_title"] = bible["series_title"]
    package["request_fingerprint"] = fingerprint
    package["writer_model"] = used_model
    package["generated_at"] = time.strftime("%Y-%m-%d %H:%M:%S")
    package["status"] = "draft_not_canonical"
    package["flow_prompt_pack"] = "flow_prompt_pack.md"
    _write_json(package_path, package)
    (project_dir / "original_script.md").write_text(
        f"# {package['episode_title']}\n\n"
        f"**Logline:** {package['logline']}\n\n"
        f"{package['dialogue_script']}\n\n"
        f"**Ending hook:** {package['ending_hook']}\n",
        encoding="utf-8",
    )
    (project_dir / "flow_prompt_pack.md").write_text(
        render_series_flow_prompt_pack(package, bible), encoding="utf-8"
    )
    (project_dir / "series_episode_summary.md").write_text(
        f"# {package['episode_title']}\n\n{package['episode_summary']}\n\n"
        f"**Continuity entering:** {package['continuity_in']}\n\n"
        f"**Continuity leaving:** {package['continuity_out']}\n\n"
        f"**Next-episode hook:** {package['ending_hook']}\n",
        encoding="utf-8",
    )
    state_path = project_dir / "series_episode_state.json"
    state = _read_json(state_path, {})
    state.update({
        "series_id": bible["series_id"],
        "season": int(season_number),
        "episode": int(episode_number),
        "episode_title": package["episode_title"],
        "status": "script_and_prompt_pack_ready",
        "updated_at": time.strftime("%Y-%m-%d %H:%M:%S"),
    })
    _write_json(state_path, state)
    return package


def set_series_voice_candidates(series_dir: Path, selections: dict[str, str]) -> dict:
    """Persist a distinct, licence-checked Piper audition choice for every recurring role."""
    from app.reusable_production import VOICE_MODELS

    bible = load_series_bible(series_dir)
    expected = {character["id"] for character in bible["cast"]}
    if set(selections) != expected:
        raise ValueError("Select a proposed voice for every recurring character.")
    selected_ids = [str(selections[item]) for item in sorted(expected)]
    if any(item not in VOICE_MODELS for item in selected_ids):
        raise ValueError("One or more selected voices are not in the studio's verified model catalogue.")
    if len(set(selected_ids)) != len(selected_ids):
        raise ValueError("Each recurring character needs a distinct proposed voice.")
    for character in bible["cast"]:
        voice_id = str(selections[character["id"]])
        character["voice_profile"] = {
            "voice_id": voice_id,
            "status": "provisional",
            "casting_note": "Selected for audition only. Listen and approve before locking this role.",
        }
    bible["voice_cast"] = {
        "status": "provisional_not_locked",
        "unique_voice_per_character_required": True,
        "narrator": "none; the story is carried by character dialogue and scene sound",
        "approval_required": True,
        "notes": "Proposed selections are not final until auditioned and approved.",
    }
    _write_json(Path(series_dir) / "series_bible.json", bible)
    (Path(series_dir) / "voice_cast.json").unlink(missing_ok=True)
    (Path(series_dir) / "voice_auditions" / "auditions.json").unlink(missing_ok=True)
    return bible["voice_cast"]


def generate_series_voice_auditions(workspace: Path, series_dir: Path) -> dict:
    """Generate one reusable audition phrase per proposed character voice."""
    from piper import PiperVoice
    from app.reusable_production import ensure_voice_model

    bible = load_series_bible(series_dir)
    audition_dir = Path(series_dir) / "voice_auditions"
    audition_dir.mkdir(parents=True, exist_ok=True)
    results = {}
    for character in bible["cast"]:
        speaker_id = character["id"]
        proposed_voice = character["voice_profile"]["voice_id"]
        voice = ensure_voice_model(Path(workspace), proposed_voice)
        actual_voice_id = str(voice["voice_id"])
        output = audition_dir / f"{speaker_id}_{actual_voice_id}_audition.wav"
        if not output.is_file():
            instance = PiperVoice.load(str(voice["model"]))
            with wave.open(str(output), "wb") as wav_file:
                instance.synthesize_wav(SAMPLE_LINE, wav_file)
        results[speaker_id] = {
            "character_name": character["name"],
            "proposed_voice_id": proposed_voice,
            "actual_voice_id": actual_voice_id,
            "fallback_used": bool(voice["fallback_used"]),
            "audio_path": str(output),
            "model_card_path": str(voice["model_card"]),
            "voice_license": str(voice["license"]),
            "training_base": str(voice["training_base"]),
        }
    _write_json(audition_dir / "auditions.json", {
        "series_id": bible["series_id"],
        "generated_at": time.strftime("%Y-%m-%d %H:%M:%S"),
        "sample_text": SAMPLE_LINE,
        "characters": results,
    })
    return results


def approve_series_voice_cast(series_dir: Path, approvals: dict[str, bool]) -> dict:
    """Lock only auditioned, distinct and explicitly approved character voices."""
    bible = load_series_bible(series_dir)
    audition_path = Path(series_dir) / "voice_auditions" / "auditions.json"
    auditions = _read_json(audition_path)
    if not isinstance(auditions, dict):
        raise FileNotFoundError("Generate and listen to all voice auditions before approving the cast.")
    expected = {character["id"] for character in bible["cast"]}
    if set(approvals) != expected or not all(bool(approvals.get(item)) for item in expected):
        raise ValueError("Approve every recurring character's voice after listening to the audition.")
    actual_ids = [
        str(auditions.get("characters", {}).get(item, {}).get("actual_voice_id", ""))
        for item in sorted(expected)
    ]
    if any(not item for item in actual_ids):
        raise ValueError("At least one character is missing an auditioned voice model.")
    if len(set(actual_ids)) != len(actual_ids):
        raise ValueError(
            "The voice downloads resolved to duplicate models. The cast cannot be locked until every "
            "recurring character has a distinct, approved voice."
        )
    for item in expected:
        audition = auditions["characters"][item]
        audio = Path(audition["audio_path"])
        if not audio.is_file() or audio.stat().st_size < 1000:
            raise FileNotFoundError(f"The {item} audition file is missing or incomplete.")
    candidate_fingerprint = _fingerprint({
        item["id"]: item["voice_profile"]["voice_id"] for item in bible["cast"]
    })
    locked = {
        "series_id": bible["series_id"],
        "status": "locked",
        "locked_at": time.strftime("%Y-%m-%d %H:%M:%S"),
        "approval_basis": "Human audition and explicit approval of every cast voice.",
        "candidate_fingerprint": candidate_fingerprint,
        "characters": auditions["characters"],
    }
    return _write_json(Path(series_dir) / "voice_cast.json", locked) and locked


def approve_series_character_references(series_dir: Path, approvals: dict[str, bool]) -> dict:
    """Lock character reference images only after all three assets exist and are approved."""
    bible = load_series_bible(series_dir)
    expected = {character["id"] for character in bible["cast"]}
    if set(approvals) != expected or not all(bool(approvals.get(item)) for item in expected):
        raise ValueError("Approve every character reference after reviewing the generated turnaround sheets.")
    assets = {}
    for character in bible["cast"]:
        asset = Path(series_dir) / character["reference_asset"]
        if not asset.is_file() or asset.stat().st_size < 10_000:
            raise FileNotFoundError(
                f"Missing or incomplete reference image for {character['name']}: {asset}"
            )
        image_bytes = asset.read_bytes()
        if not image_bytes.startswith(b"\\x89PNG\\r\\n\\x1a\\n") or len(image_bytes) < 24:
            raise ValueError(f"Reference image for {character['name']} is not a valid PNG file.")
        import struct
        image_width, image_height = struct.unpack(">II", image_bytes[16:24])
        if image_width < 512 or image_height < 512:
            raise ValueError(f"Reference image for {character['name']} must be at least 512x512 pixels.")
        assets[character["id"]] = {
            "path": character["reference_asset"],
            "sha256": hashlib.sha256(image_bytes).hexdigest(),
            "size_bytes": asset.stat().st_size,
            "dimensions": [image_width, image_height],
        }
    locked = {
        "series_id": bible["series_id"],
        "status": "locked",
        "approved_at": time.strftime("%Y-%m-%d %H:%M:%S"),
        "assets": assets,
    }
    _write_json(Path(series_dir) / "character_references_approval.json", locked)
    return locked


def validate_series_scene_files(project_dir: Path, scene_files: Iterable[Path]) -> list[Path]:
    package = _read_json(Path(project_dir) / "series_episode_package.json")
    if not isinstance(package, dict) or not package.get("scenes"):
        raise FileNotFoundError("Generate the screenplay and Flow prompt pack before adding scene videos.")
    ordered = sorted([Path(path) for path in scene_files], key=_natural_key)
    expected = len(package["scenes"])
    if len(ordered) != expected:
        raise ValueError(
            f"This episode requires exactly {expected} scene videos in order; found {len(ordered)}. "
            "Do not reuse clips from another episode or omit a scene."
        )
    for path in ordered:
        if not path.is_file() or path.stat().st_size < 1024:
            raise ValueError(f"Scene video is missing or incomplete: {path}")
    return ordered


def _probe_duration(path: Path) -> float:
    result = subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries", "format=duration",
         "-of", "default=noprint_wrappers=1:nokey=1", str(path)],
        capture_output=True, text=True, timeout=30, check=True,
    )
    duration = float(result.stdout.strip())
    if not 5 <= duration <= 12:
        raise ValueError(f"Unexpected Flow clip duration for {path.name}: {duration:.2f}s.")
    return duration


def _srt_timestamp(seconds: float) -> str:
    milliseconds = max(0, int(round(seconds * 1000)))
    hours, milliseconds = divmod(milliseconds, 3_600_000)
    minutes, milliseconds = divmod(milliseconds, 60_000)
    whole_seconds, milliseconds = divmod(milliseconds, 1000)
    return f"{hours:02d}:{minutes:02d}:{whole_seconds:02d},{milliseconds:03d}"


def synthesize_series_dialogue(
    project_dir: Path,
    workspace: Path,
    series_dir: Path,
    scene_files: Iterable[Path],
) -> dict:
    """Create scene-aligned character dialogue with the locked, licensed voice cast."""
    from piper import PiperVoice
    from app.reusable_production import ensure_voice_model

    bible = load_series_bible(series_dir)
    voice_cast = _read_json(Path(series_dir) / "voice_cast.json")
    references = _read_json(Path(series_dir) / "character_references_approval.json")
    if not isinstance(voice_cast, dict) or voice_cast.get("status") != "locked":
        raise PermissionError("Character voices are not locked. Listen to and approve the distinct voice auditions first.")
    if not isinstance(references, dict) or references.get("status") != "locked":
        raise PermissionError("Character reference images are not approved. Lock all canonical character references first.")
    current_reference_ids = {character["id"]: character["reference_asset"] for character in bible["cast"]}
    for character_id, relative_path in current_reference_ids.items():
        approved_asset = references.get("assets", {}).get(character_id, {})
        reference_path = Path(series_dir) / relative_path
        if not reference_path.is_file() or hashlib.sha256(reference_path.read_bytes()).hexdigest() != approved_asset.get("sha256"):
            raise PermissionError(
                f"The approved reference for {character_id} has changed or is missing. Review and approve it again."
            )
    candidate_fingerprint = _fingerprint({
        item["id"]: item["voice_profile"]["voice_id"] for item in bible["cast"]
    })
    if voice_cast.get("candidate_fingerprint") != candidate_fingerprint:
        raise PermissionError("The proposed voice mapping changed after approval. Re-audition and lock the cast again.")
    sources = validate_series_scene_files(project_dir, scene_files)
    package = _read_json(Path(project_dir) / "series_episode_package.json")
    actual_durations = [_probe_duration(path) for path in sources]
    if len(package["scenes"]) != len(actual_durations):
        raise ValueError("The generated Flow scene count does not match the episode script.")

    character_by_id = {character["id"]: character for character in bible["cast"]}
    voice_instances = {}
    actual_models = {}
    for character_id, cast_entry in voice_cast["characters"].items():
        model_id = cast_entry["actual_voice_id"]
        if character_id not in character_by_id:
            raise ValueError(f"Voice cast contains an unknown character: {character_id}")
        if character_id in voice_instances:
            continue
        voice = ensure_voice_model(Path(workspace), model_id)
        if str(voice["voice_id"]) != model_id:
            raise RuntimeError(
                f"The approved voice model for {character_id} resolved to {voice['voice_id']}, "
                f"not {model_id}. Re-audition and approve the voice cast."
            )
        voice_instances[character_id] = PiperVoice.load(str(voice["model"]))
        actual_models[character_id] = model_id
    if len(set(actual_models.values())) != len(character_by_id):
        raise ValueError("Every speaking character must have a distinct voice model.")

    audio_dir = Path(project_dir) / "audio"
    part_dir = audio_dir / "series_dialogue_parts"
    part_dir.mkdir(parents=True, exist_ok=True)
    audio_dir.mkdir(parents=True, exist_ok=True)
    sample_rate = 48_000
    bytes_per_frame = 4  # 16-bit stereo PCM
    full_frames = bytearray()
    srt_blocks = []
    caption_number = 1
    timeline = 0.0
    voice_manifest = []

    for scene_index, (scene, clip_duration) in enumerate(zip(package["scenes"], actual_durations), 1):
        scene_frames = bytearray()
        scene_elapsed = 0.0
        for line_index, line in enumerate(scene["dialogue_lines"], 1):
            speaker_id = line["speaker_id"]
            text = str(line["text"]).strip()
            raw_path = part_dir / f"scene_{scene_index:03d}_line_{line_index:02d}_raw.wav"
            pcm_path = part_dir / f"scene_{scene_index:03d}_line_{line_index:02d}_pcm.wav"
            with wave.open(str(raw_path), "wb") as wav_file:
                voice_instances[speaker_id].synthesize_wav(text, wav_file)
            conversion = subprocess.run(
                [
                    "ffmpeg", "-y", "-i", str(raw_path),
                    "-af", "highpass=f=85,lowpass=f=14000,acompressor=threshold=0.14:ratio=2:attack=18:release=140,alimiter=limit=0.92",
                    "-ar", str(sample_rate), "-ac", "2", "-c:a", "pcm_s16le", str(pcm_path),
                ],
                capture_output=True, text=True, timeout=60,
            )
            if conversion.returncode != 0 or not pcm_path.is_file():
                raise RuntimeError(f"Audio preparation failed for {speaker_id} line {line_index}: {(conversion.stderr or '')[-1200:]}")
            with wave.open(str(pcm_path), "rb") as wav_file:
                frames = wav_file.readframes(wav_file.getnframes())
                duration = len(frames) / (sample_rate * bytes_per_frame)
            if not frames or duration <= 0:
                raise RuntimeError(f"Voice synthesis returned empty audio for {speaker_id}.")
            if scene_elapsed + duration > clip_duration - 0.15:
                raise ValueError(
                    f"Dialogue in scene {scene_index} takes {scene_elapsed + duration:.2f}s, "
                    f"but the Flow clip is only {clip_duration:.2f}s. Shorten or re-record the lines; "
                    "the studio will not crush speech to force it to fit."
                )
            line_start = timeline + scene_elapsed
            line_end = line_start + duration
            display_name = character_by_id[speaker_id]["name"].upper()
            srt_blocks.extend([
                str(caption_number),
                f"{_srt_timestamp(line_start)} --> {_srt_timestamp(line_end)}",
                f"{display_name}: {text}",
                "",
            ])
            caption_number += 1
            scene_frames.extend(frames)
            scene_elapsed += duration
            voice_manifest.append({
                "scene": scene_index,
                "speaker_id": speaker_id,
                "voice_model": actual_models[speaker_id],
                "text": text,
                "start_seconds": round(line_start, 3),
                "end_seconds": round(line_end, 3),
            })
            pause_frames = int(sample_rate * 0.22)
            scene_frames.extend(b"\x00" * pause_frames * bytes_per_frame)
            scene_elapsed += 0.22
        remaining = max(0.0, clip_duration - scene_elapsed)
        scene_frames.extend(b"\x00" * int(round(remaining * sample_rate)) * bytes_per_frame)
        expected_frames = int(round(clip_duration * sample_rate))
        if len(scene_frames) < expected_frames * bytes_per_frame:
            scene_frames.extend(b"\x00" * (expected_frames * bytes_per_frame - len(scene_frames)))
        elif len(scene_frames) > expected_frames * bytes_per_frame:
            scene_frames = scene_frames[:expected_frames * bytes_per_frame]
        full_frames.extend(scene_frames)
        timeline += clip_duration

    dialogue_path = audio_dir / "series_dialogue.wav"
    with wave.open(str(dialogue_path), "wb") as wav_file:
        wav_file.setnchannels(2)
        wav_file.setsampwidth(2)
        wav_file.setframerate(sample_rate)
        wav_file.writeframes(bytes(full_frames))
    captions_dir = Path(project_dir) / "captions"
    captions_dir.mkdir(parents=True, exist_ok=True)
    srt_path = captions_dir / "episode.srt"
    srt_path.write_text("\n".join(srt_blocks).rstrip() + "\n", encoding="utf-8")
    manifest_path = audio_dir / "series_dialogue_manifest.json"
    _write_json(manifest_path, {
        "series_id": bible["series_id"],
        "voice_cast_file": str(Path(series_dir) / "voice_cast.json"),
        "total_duration_seconds": round(timeline, 3),
        "sample_rate": sample_rate,
        "speaker_models": actual_models,
        "voice_lines": voice_manifest,
        "created_at": time.strftime("%Y-%m-%d %H:%M:%S"),
    })
    return {
        "audio": dialogue_path,
        "captions": srt_path,
        "manifest": manifest_path,
        "duration_seconds": round(timeline, 3),
        "speaker_models": actual_models,
    }


def render_series_episode(
    project_dir: Path,
    workspace: Path,
    series_dir: Path,
    scene_files: Iterable[Path],
    keep_scene_audio: bool = False,
    output_size: tuple[int, int] = (1920, 1080),
) -> dict:
    """Render a landscape pilot from approved scenes, locked voices and timed dialogue."""
    project_dir = Path(project_dir)
    sources = validate_series_scene_files(project_dir, scene_files)
    package = _read_json(project_dir / "series_episode_package.json")
    width, height = map(int, output_size)
    if (width, height) != (1920, 1080):
        raise ValueError("The serialized series master is locked to 1920x1080 landscape.")
    dialogue = synthesize_series_dialogue(project_dir, workspace, series_dir, sources)
    work_dir = project_dir / "work" / "series_render"
    normalized_dir = work_dir / "scenes"
    normalized_dir.mkdir(parents=True, exist_ok=True)
    normalized = []
    durations = []
    for index, source in enumerate(sources, 1):
        duration = _probe_duration(source)
        durations.append(duration)
        target = normalized_dir / f"{index:03d}_normalized.mp4"
        if target.exists() and abs(_probe_duration(target) - duration) < 0.1:
            normalized.append(target)
            continue
        temporary = target.with_name(target.stem + ".partial.mp4")
        temporary.unlink(missing_ok=True)
        has_audio = subprocess.run(
            ["ffprobe", "-v", "error", "-select_streams", "a:0",
             "-show_entries", "stream=index", "-of", "csv=p=0", str(source)],
            capture_output=True, text=True, timeout=30,
        ).returncode == 0
        command = ["ffmpeg", "-y", "-i", str(source)]
        if not has_audio or not keep_scene_audio:
            command += ["-f", "lavfi", "-t", f"{duration:.3f}", "-i",
                        "anullsrc=channel_layout=stereo:sample_rate=48000"]
        command += [
            "-vf", f"scale={width}:{height}:force_original_aspect_ratio=decrease:flags=lanczos,"
                   f"pad={width}:{height}:(ow-iw)/2:(oh-ih)/2,setsar=1,fps=30,format=yuv420p",
            "-map", "0:v:0",
        ]
        if keep_scene_audio and has_audio:
            command += ["-map", "0:a:0"]
        else:
            command += ["-map", "1:a:0"]
        command += [
            "-c:v", "libx264", "-preset", "fast", "-crf", "19", "-threads", "2",
            "-c:a", "aac", "-ar", "48000", "-ac", "2", "-b:a", "160k",
            "-t", f"{duration:.3f}", "-movflags", "+faststart", str(temporary),
        ]
        result = subprocess.run(command, capture_output=True, text=True, timeout=300)
        if result.returncode or not temporary.is_file() or temporary.stat().st_size < 1024:
            temporary.unlink(missing_ok=True)
            raise RuntimeError(f"Scene normalization failed for {source.name}: {(result.stderr or '')[-1800:]}")
        temporary.replace(target)
        normalized.append(target)

    concat_file = work_dir / "concat_list.txt"
    concat_file.write_text(
        "".join(f"file '{str(path.resolve()).replace(chr(92), '/')}'\n" for path in normalized),
        encoding="utf-8",
    )
    silent_master = work_dir / "silent_picture_master.mp4"
    silent_master.unlink(missing_ok=True)
    concat_result = subprocess.run(
        ["ffmpeg", "-y", "-f", "concat", "-safe", "0", "-i", str(concat_file),
         "-c:v", "libx264", "-preset", "fast", "-crf", "19", "-threads", "2",
         "-c:a", "aac", "-ar", "48000", "-ac", "2", "-b:a", "160k",
         "-movflags", "+faststart", str(silent_master)],
        capture_output=True, text=True, timeout=600,
    )
    if concat_result.returncode or not silent_master.is_file():
        raise RuntimeError(f"Scene assembly failed: {(concat_result.stderr or '')[-2000:]}")

    music = None
    try:
        from app.reusable_production import select_shared_music
        music = select_shared_music(Path(workspace), project_dir)
    except Exception as exc:
        # The episode can still be reviewed without music; this warning is recorded.
        music = {"warning": f"No licensed score was mixed: {type(exc).__name__}: {exc}"}

    output_dir = project_dir / "work"
    output_dir.mkdir(parents=True, exist_ok=True)
    output_path = output_dir / "series_episode_draft_1920x1080.mp4"
    subtitles_path = str(dialogue["captions"].resolve()).replace("\\", "/").replace(":", r"\:")
    vf = (
        f"subtitles='{subtitles_path}':force_style="
        "'FontName=DejaVu Sans,FontSize=22,Outline=2,Shadow=0,MarginV=38,Alignment=2'"
    )
    command = ["ffmpeg", "-y", "-i", str(silent_master), "-i", str(dialogue["audio"])]
    music_audio = music.get("audio") if isinstance(music, dict) else None
    if keep_scene_audio:
        ambient_filter = "[0:a:0]volume=0.12[ambient];"
    else:
        ambient_filter = "[0:a:0]volume=0[ambient];"
    if music_audio:
        command += ["-stream_loop", "-1", "-i", str(music_audio)]
        graph = (
            ambient_filter
            + "[1:a:0]volume=1.0[dialogue];"
            + "[2:a:0]volume=0.075[score];"
            + "[ambient][dialogue][score]amix=inputs=3:duration=first:dropout_transition=2,"
              "alimiter=limit=0.94[a]"
        )
        audio_map = "[a]"
    else:
        graph = (
            ambient_filter + "[1:a:0]volume=1.0[dialogue];"
            "[ambient][dialogue]amix=inputs=2:duration=first:dropout_transition=1,"
            "alimiter=limit=0.94[a]"
        )
        audio_map = "[a]"
    command += [
        "-filter_complex", graph, "-map", "0:v:0", "-map", audio_map,
        "-vf", vf, "-c:v", "libx264", "-preset", "fast", "-crf", "19", "-threads", "2",
        "-c:a", "aac", "-ar", "48000", "-ac", "2", "-b:a", "192k",
        "-movflags", "+faststart", str(output_path),
    ]
    result = subprocess.run(command, capture_output=True, text=True, timeout=900)
    if result.returncode or not output_path.is_file() or output_path.stat().st_size < 10_000:
        raise RuntimeError(f"Series episode render failed: {(result.stderr or '')[-2500:]}")

    probe = subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries", "stream=codec_type,width,height,codec_name:"
         "format=duration,size", "-of", "json", str(output_path)],
        capture_output=True, text=True, timeout=30, check=True,
    )
    metadata = json.loads(probe.stdout)
    streams = metadata.get("streams", [])
    video = next((item for item in streams if item.get("codec_type") == "video"), {})
    audio = next((item for item in streams if item.get("codec_type") == "audio"), {})
    rendered_duration = float(metadata.get("format", {}).get("duration", 0) or 0)
    expected_duration = sum(durations)
    if not video or not audio or video.get("width") != width or video.get("height") != height:
        raise RuntimeError("Rendered episode failed the video/audio/resolution quality checks.")
    if abs(rendered_duration - expected_duration) > max(1.0, expected_duration * 0.01):
        raise RuntimeError("Rendered episode duration does not match its approved source scenes.")

    report_path = project_dir / "work" / "series_quality_report.json"
    report = {
        "status": "rendered_pending_human_review",
        "series_id": SERIES_ID,
        "episode_title": package["episode_title"],
        "video": str(output_path),
        "duration_seconds": round(rendered_duration, 2),
        "resolution": f"{width}x{height}",
        "video_codec": video.get("codec_name"),
        "audio_codec": audio.get("codec_name"),
        "scene_count": len(sources),
        "dialogue_lines": len(_read_json(dialogue["manifest"], {}).get("voice_lines", [])),
        "speaker_models": dialogue["speaker_models"],
        "captions": str(dialogue["captions"]),
        "licensed_music": music.get("metadata", {}) if isinstance(music, dict) else {},
        "music_warning": music.get("warning") if isinstance(music, dict) else None,
        "human_review_required": True,
        "created_at": time.strftime("%Y-%m-%d %H:%M:%S"),
    }
    _write_json(report_path, report)
    return {
        "video": output_path,
        "dialogue": dialogue,
        "quality_report": report_path,
        "report": report,
    }


def mark_series_episode_canonical(
    series_dir: Path,
    project_dir: Path,
    human_review_passed: bool,
) -> dict:
    """Update season continuity only after explicit human approval of the final episode."""
    if not human_review_passed:
        raise PermissionError("A failed or unreviewed episode cannot become canonical.")
    package = _read_json(Path(project_dir) / "series_episode_package.json")
    quality = _read_json(Path(project_dir) / "work" / "series_quality_report.json")
    if not isinstance(package, dict) or not isinstance(quality, dict):
        raise FileNotFoundError("The episode package and quality report are required before canon approval.")
    if quality.get("status") != "rendered_pending_human_review":
        raise ValueError("The rendered episode is not awaiting its required final review.")
    if not Path(quality["video"]).is_file():
        raise FileNotFoundError("The rendered episode file is missing.")
    season = int(package["season_number"])
    episode = int(package["episode_number"])
    ledger_path = Path(series_dir) / "continuity" / f"season_{season:02d}.json"
    ledger = _load_canonical_continuity(series_dir, season)
    existing = [item for item in ledger["canonical_episodes"] if int(item.get("episode", 0)) == episode]
    record = {
        "episode": episode,
        "episode_title": package["episode_title"],
        "summary": package["episode_summary"],
        "continuity_out": package["continuity_out"],
        "ending_hook": package["ending_hook"],
        "quality_report": str(Path(project_dir) / "work" / "series_quality_report.json"),
        "approved_at": time.strftime("%Y-%m-%d %H:%M:%S"),
    }
    ledger["canonical_episodes"] = [item for item in ledger["canonical_episodes"] if int(item.get("episode", 0)) != episode]
    ledger["canonical_episodes"].append(record)
    ledger["canonical_episodes"].sort(key=lambda item: int(item["episode"]))
    ledger["last_updated"] = record["approved_at"]
    _write_json(ledger_path, ledger)
    quality["status"] = "human_review_passed_canonical"
    quality["human_review_passed_at"] = record["approved_at"]
    _write_json(Path(project_dir) / "work" / "series_quality_report.json", quality)
    return record
