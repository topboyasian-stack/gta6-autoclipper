"""Reusable, repeatable production assets for the Universal Colab Studio.

The same episode pipeline is used for every project:
Flow scenes -> optional Gemini storyboard/script -> Piper narration ->
Faster-Whisper word timing -> reviewed SRT -> licensed shared music ->
vertical render and an evidence pack.
"""
from __future__ import annotations

import csv
import hashlib
import json
import re
import subprocess
import time
import urllib.request
from difflib import SequenceMatcher
from pathlib import Path
from typing import Iterable

VOICE_MODELS = {
    "en_US-joe-medium": {
        "language": "English (US)",
        "license": "CC0",
        "base": "rdh",
        "relative_dir": "en/en_US/joe/medium",
    },
    "en_US-mike-medium": {
        "language": "English (US)",
        "license": "CC0",
        "base": "rdh",
        "relative_dir": "en/en_US/mike/medium",
    },
    "en_US-ljspeech-medium": {
        "language": "English (US)",
        "license": "Public Domain",
        "base": "scratch",
        "relative_dir": "en/en_US/ljspeech/medium",
    },
}

DEFAULT_MUSIC = {
    "filename": "New_Direction_CC_BY_3.0.mp3",
    "download_url": (
        "https://upload.wikimedia.org/wikipedia/commons/1/1b/"
        "New_Direction_%28ISRC_USUAN1100677%29.mp3"
    ),
    "title": "New Direction",
    "artist": "Kevin MacLeod",
    "source": "https://commons.wikimedia.org/wiki/File:New_Direction_(ISRC_USUAN1100677).mp3",
    "source_site": "incompetech.com",
    "license": "Creative Commons Attribution 3.0 Unported",
    "license_url": "https://creativecommons.org/licenses/by/3.0/",
    "attribution": (
        "New Direction Kevin MacLeod (incompetech.com)\n"
        "Licensed under Creative Commons: By Attribution 3.0 License\n"
        "https://creativecommons.org/licenses/by/3.0/"
    ),
    "commercial_use": True,
    "changes_made": "Trimmed, looped if required, and mixed at low volume under narration.",
    "verification_source": "Wikimedia Commons file description and Incompetech track listing",
}



def _file_fingerprint(path: Path) -> str:
    path = Path(path)
    stat = path.stat()
    return f"{path.name}:{stat.st_size}:{stat.st_mtime_ns}"


def _json_fingerprint(payload: object) -> str:
    encoded = json.dumps(payload, sort_keys=True, ensure_ascii=False, default=str).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def _download(url: str, destination: Path, min_bytes: int = 1000, force: bool = False) -> Path:
    destination = Path(destination)
    destination.parent.mkdir(parents=True, exist_ok=True)
    if not force and destination.exists() and destination.stat().st_size >= min_bytes:
        return destination
    temporary = destination.with_suffix(destination.suffix + ".part")
    request = urllib.request.Request(
        url,
        headers={"User-Agent": "UniversalColabProductionStudio/1.0 (asset download)"},
    )
    try:
        with urllib.request.urlopen(request, timeout=90) as response, temporary.open("wb") as output:
            while True:
                chunk = response.read(1024 * 1024)
                if not chunk:
                    break
                output.write(chunk)
        if not temporary.exists() or temporary.stat().st_size < min_bytes:
            raise RuntimeError(f"Downloaded asset is unexpectedly small: {destination.name}")
        temporary.replace(destination)
    except Exception:
        temporary.unlink(missing_ok=True)
        raise
    return destination


def _safe_words(text: str) -> list[str]:
    return re.findall(r"[A-Za-z0-9]+(?:['’\-][A-Za-z0-9]+)*", text or "")


def _normal_words(text: str) -> list[str]:
    return [re.sub(r"[^a-z0-9]", "", word.lower()) for word in _safe_words(text)]


def ensure_voice_model(workspace: Path, voice_id: str = "en_US-joe-medium") -> dict[str, Path | str]:
    """Download and verify a Piper voice against its actual model-card training chain.

    Joe/Mike are accepted only when the downloaded card says CC0 and rdh.
    LJSpeech is the public-domain, trained-from-scratch fallback.
    """
    if voice_id not in VOICE_MODELS:
        raise ValueError(
            f"Unsupported voice {voice_id!r}. Choose one of: {', '.join(VOICE_MODELS)}."
        )

    preference = [voice_id]
    if voice_id != "en_US-ljspeech-medium":
        preference.append("en_US-ljspeech-medium")
    errors = []
    for candidate in preference:
        metadata = VOICE_MODELS[candidate]
        voice_dir = Path(workspace) / "assets" / "voice_models" / candidate
        voice_dir.mkdir(parents=True, exist_ok=True)
        relative = str(metadata["relative_dir"])
        base_url = f"https://huggingface.co/rhasspy/piper-voices/resolve/main/{relative}"
        filenames = [f"{candidate}.onnx", f"{candidate}.onnx.json", "MODEL_CARD"]
        try:
            for filename in filenames:
                _download(
                    f"{base_url}/{filename}?download=true",
                    voice_dir / filename,
                    min_bytes=100 if filename == "MODEL_CARD" else 1000,
                )
            model_card = (voice_dir / "MODEL_CARD").read_text(
                encoding="utf-8", errors="replace"
            )
            if metadata["base"] == "rdh":
                verified = (
                    "CC0" in model_card.upper()
                    and "rdh" in model_card.lower()
                    and "lessac" not in model_card.lower()
                    and "ryan voice" not in model_card.lower()
                )
            else:
                card_lower = model_card.lower()
                verified = (
                    "public domain" in card_lower
                    and "trained from scratch" in card_lower
                )
            if not verified:
                # The voice name may be unchanged after a retrain. Refresh all cached files once
                # so an old Lessac/Ryan checkpoint is never accepted by filename alone.
                for filename in filenames:
                    (voice_dir / filename).unlink(missing_ok=True)
                for filename in filenames:
                    _download(
                        f"{base_url}/{filename}?download=true",
                        voice_dir / filename,
                        min_bytes=100 if filename == "MODEL_CARD" else 1000,
                        force=True,
                    )
                model_card = (voice_dir / "MODEL_CARD").read_text(
                    encoding="utf-8", errors="replace"
                )
                if metadata["base"] == "rdh":
                    verified = (
                        "CC0" in model_card.upper()
                        and "rdh" in model_card.lower()
                        and "lessac" not in model_card.lower()
                        and "ryan voice" not in model_card.lower()
                    )
                else:
                    card_lower = model_card.lower()
                    verified = (
                        "public domain" in card_lower
                        and "trained from scratch" in card_lower
                    )
            if not verified:
                errors.append(f"{candidate}: refreshed MODEL_CARD does not confirm {metadata['license']} / {metadata['base']} provenance")
                continue
            model_path = voice_dir / f"{candidate}.onnx"
            config_path = voice_dir / f"{candidate}.onnx.json"
            if not model_path.is_file() or not config_path.is_file():
                errors.append(f"{candidate}: ONNX model or config file is missing")
                continue

            engine_note = voice_dir / "PIPER_ENGINE_LICENSE.txt"
            if not engine_note.exists():
                engine_note.write_text(
                    "Piper TTS engine: GPL-3.0-or-later. The voice model is separately licensed; "
                    "see the adjacent MODEL_CARD. The production studio uses this voice only after "
                    f"the downloaded MODEL_CARD confirms {metadata['license']} and training provenance.\n"
                    "Piper licensing guidance: https://github.com/OHF-Voice/piper1-gpl/blob/main/docs/LICENSING.md\n",
                    encoding="utf-8",
                )
            return {
                "directory": voice_dir,
                "model": model_path,
                "config": config_path,
                "model_card": voice_dir / "MODEL_CARD",
                "voice_id": candidate,
                "license": str(metadata["license"]),
                "fallback_used": candidate != voice_id,
                "training_base": str(metadata["base"]),
            }
        except Exception as exc:
            errors.append(f"{candidate}: {type(exc).__name__}: {exc}")

    raise PermissionError(
        "No Piper voice with a verified commercial-use training chain was available. "
        "The studio refused to synthesize narration using an unverified model. "
        + " | ".join(errors)
    )

def ensure_shared_music_library(workspace: Path) -> dict[str, Path]:
    """Create a reusable Drive music library and seed it with a verified CC-BY track."""
    library = Path(workspace) / "assets" / "music_library"
    library.mkdir(parents=True, exist_ok=True)
    audio_path = library / DEFAULT_MUSIC["filename"]
    license_path = library / (audio_path.stem + ".license.json")

    has_registered_track = False
    for sidecar in library.glob("*.license.json"):
        try:
            metadata = json.loads(sidecar.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        stem = sidecar.name.removesuffix(".license.json")
        has_audio = any(
            path.is_file() and path.suffix.lower() in AUDIO_EXTENSIONS
            for path in library.glob(stem + ".*")
        )
        if has_audio and metadata.get("commercial_use") and metadata.get("license_url") and metadata.get("attribution"):
            has_registered_track = True
            break

    if not has_registered_track:
        if not audio_path.exists() or audio_path.stat().st_size < 1_000_000:
            _download(DEFAULT_MUSIC["download_url"], audio_path, min_bytes=1_000_000)
        if not license_path.exists():
            _write_json(license_path, DEFAULT_MUSIC)

    return {"directory": library, "audio": audio_path, "license": license_path}


def select_shared_music(workspace: Path, project_dir: Path) -> dict[str, Path | dict]:
    """Rotate through music-library tracks that have an explicit rights sidecar."""
    library = ensure_shared_music_library(workspace)
    audio_dir = Path(project_dir) / "audio"
    audio_dir.mkdir(parents=True, exist_ok=True)

    # A rerun of the same episode keeps its selected track; rotation is only for new projects.
    existing_license = audio_dir / "music_license.json"
    existing_audio = [
        path for path in audio_dir.glob("music.*")
        if path.is_file() and path.suffix.lower() in {".mp3", ".wav", ".m4a", ".ogg", ".flac"}
    ]
    if existing_license.exists() and len(existing_audio) == 1:
        try:
            metadata = json.loads(existing_license.read_text(encoding="utf-8"))
            if metadata.get("commercial_use") and metadata.get("license_url") and metadata.get("attribution"):
                return {"audio": existing_audio[0], "license": existing_license, "metadata": metadata}
        except (OSError, json.JSONDecodeError):
            pass

    candidates = []
    for metadata_path in sorted(Path(library["directory"]).glob("*.license.json")):
        try:
            metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        filename = metadata_path.name.removesuffix(".license.json")
        audio_matches = [
            path for path in Path(library["directory"]).glob(filename + ".*")
            if path.is_file() and path.suffix.lower() in {".mp3", ".wav", ".m4a", ".ogg", ".flac"}
        ]
        if not audio_matches:
            continue
        if not metadata.get("commercial_use") or not metadata.get("license_url") or not metadata.get("attribution"):
            continue
        candidates.append((audio_matches[0], metadata_path, metadata))

    if not candidates:
        raise FileNotFoundError(
            "The shared music library contains no audio tracks with complete commercial-use "
            "and attribution records. Add a properly licensed track and its .license.json sidecar."
        )

    history_path = Path(library["directory"]) / ".rotation_history.json"
    history = json.loads(history_path.read_text(encoding="utf-8")) if history_path.exists() else {}
    previous = history.get("last_track")
    selected = next((item for item in candidates if item[0].name != previous), candidates[0])
    source_audio, source_license, metadata = selected

    target_audio = audio_dir / ("music" + source_audio.suffix)
    target_license = audio_dir / "music_license.json"
    import shutil
    shutil.copy2(source_audio, target_audio)
    _write_json(target_license, metadata)
    history["last_track"] = source_audio.name
    history["last_project"] = Path(project_dir).name
    history["updated_at"] = time.strftime("%Y-%m-%d %H:%M:%S")
    _write_json(history_path, history)
    return {"audio": target_audio, "license": target_license, "metadata": metadata}


def _extract_scene_contact_sheet(scene_files: Iterable[Path], output_path: Path) -> Path:
    """Create a labeled storyboard sheet from stills sampled from each Flow scene."""
    from PIL import Image, ImageDraw, ImageFont

    scenes = sorted([Path(p) for p in scene_files], key=lambda p: _natural_key(p.name))
    if not scenes:
        raise ValueError("No Google Flow scene files were supplied.")
    work = Path(output_path).parent / "storyboard_frames"
    work.mkdir(parents=True, exist_ok=True)
    font = ImageFont.load_default()
    thumb_w, thumb_h, label_h = 360, 203, 34
    cols = 2
    rows = (len(scenes) + cols - 1) // cols
    sheet = Image.new("RGB", (cols * thumb_w, rows * (thumb_h + label_h)), "white")
    draw = ImageDraw.Draw(sheet)

    for index, scene in enumerate(scenes):
        result = subprocess.run(
            ["ffprobe", "-v", "error", "-show_entries", "format=duration",
             "-of", "default=noprint_wrappers=1:nokey=1", str(scene)],
            capture_output=True, text=True,
        )
        if result.returncode:
            raise RuntimeError(f"Cannot inspect scene {scene.name}: {result.stderr[-1200:]}")
        duration = max(0.1, float(result.stdout.strip()))
        sample_at = min(max(0.1, duration * 0.55), max(0.1, duration - 0.05))
        frame_path = work / f"{index + 1:02d}_{scene.stem}.jpg"
        subprocess.run(
            ["ffmpeg", "-hide_banner", "-loglevel", "error", "-y",
             "-ss", f"{sample_at:.3f}", "-i", str(scene), "-frames:v", "1",
             "-vf", "scale=360:203:force_original_aspect_ratio=decrease,pad=360:203:(ow-iw)/2:(oh-ih)/2",
             str(frame_path)],
            check=True, capture_output=True, text=True,
        )
        with Image.open(frame_path) as frame:
            thumbnail = frame.convert("RGB")
        col, row = index % cols, index // cols
        x, y = col * thumb_w, row * (thumb_h + label_h)
        sheet.paste(thumbnail, (x, y))
        draw.text((x + 8, y + thumb_h + 7), f"Scene {index + 1:02d}: {scene.name[:42]}", fill="black", font=font)

    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    sheet.save(output_path, format="JPEG", quality=90)
    return output_path



class _EpisodeResearchHTMLParser:
    """Extract visible HTML text without installing a separate article-scraping package."""
    from html.parser import HTMLParser as _HTMLParser

    class Parser(_HTMLParser):
        def __init__(self):
            super().__init__(convert_charrefs=True)
            self.parts = []
            self.title_parts = []
            self.in_title = False
            self.skip_depth = 0

        def handle_starttag(self, tag, attrs):
            tag = tag.lower()
            if tag in {"script", "style", "noscript", "svg", "nav", "footer", "header"}:
                self.skip_depth += 1
            if tag == "title":
                self.in_title = True

        def handle_endtag(self, tag):
            tag = tag.lower()
            if tag == "title":
                self.in_title = False
            if tag in {"script", "style", "noscript", "svg", "nav", "footer", "header"}:
                self.skip_depth = max(0, self.skip_depth - 1)

        def handle_data(self, data):
            clean = re.sub(r"\s+", " ", data).strip()
            if not clean:
                return
            if self.in_title:
                self.title_parts.append(clean)
            if self.skip_depth == 0:
                self.parts.append(clean)


def _trusted_technical_url(url: str) -> bool:
    from urllib.parse import urlparse

    parsed = urlparse(str(url))
    if parsed.scheme != "https" or not parsed.hostname:
        return False
    host = parsed.hostname.lower()
    if host.endswith((".gov", ".edu", ".int")):
        return True
    trusted = {
        "asce.org", "www.asce.org", "concrete.org", "www.concrete.org",
        "usgbc.org", "www.usgbc.org", "iea.org", "www.iea.org",
        "aia.org", "www.aia.org",
    }
    return host in trusted


def fetch_verified_technical_sources(candidate_urls, max_pages: int = 5) -> list[dict]:
    """Fetch and retain only accessible, text-bearing pages from trusted technical domains."""
    from urllib.request import Request, urlopen
    from urllib.parse import urlparse

    verified = []
    seen = set()
    for raw_url in candidate_urls:
        url = str(raw_url).strip()
        if url in seen or not _trusted_technical_url(url):
            continue
        seen.add(url)
        request = Request(
            url,
            headers={"User-Agent": "UniversalColabProductionStudio/1.0 (technical research)"},
        )
        try:
            with urlopen(request, timeout=25) as response:
                final_url = response.geturl()
                content_type = response.headers.get("Content-Type", "").lower()
                if not content_type.startswith("text/html") or not _trusted_technical_url(final_url):
                    continue
                raw = response.read(1_500_000)
            parser = _EpisodeResearchHTMLParser.Parser()
            parser.feed(raw.decode("utf-8", errors="replace"))
            page_text = re.sub(r"\s+", " ", " ".join(parser.parts)).strip()
            if len(page_text) < 500:
                continue
            verified.append({
                "title": " ".join(parser.title_parts).strip()[:240] or final_url,
                "url": final_url,
                "domain": urlparse(final_url).hostname or "",
                "content_excerpt": page_text[:9000],
                "verified_at": time.strftime("%Y-%m-%d %H:%M:%S"),
            })
        except Exception as exc:
            continue
        if len(verified) >= max_pages:
            break

    if len(verified) < 2:
        raise RuntimeError(
            "The studio could not fetch at least two credible technical pages for this topic. "
            "No narration was generated. Narrow the topic or provide official .gov, .edu or engineering-body links."
        )
    return verified


def research_episode_topic(
    topic: str,
    engineering_question: str,
    gemini_api_key: str,
    user_guidance: str = "",
    model: str = "gemini-3.8-flash",
) -> dict:
    """Suggest source URLs, fetch them, then summarize only the verified page content."""
    if not gemini_api_key or len(gemini_api_key.strip()) < 10:
        raise ValueError("A Gemini API key saved in Colab Secrets is required for automatic episode research.")
    try:
        from google import genai
        from google.genai import types
    except ImportError as exc:
        raise RuntimeError("google-genai is not installed. Run the production setup cell.") from exc

    client = genai.Client(api_key=gemini_api_key.strip())
    discover_prompt = (
        "List 5 to 8 direct HTTPS URLs to authoritative technical sources for an educational engineering episode. "
        "Prefer government science/engineering agencies, universities, established standards bodies, and recognized "
        "professional engineering institutions. Avoid blogs, forums, social media, search-result pages, product pages "
        "and Wikipedia. Do not invent a URL; if uncertain, omit it. Return JSON only with key candidate_source_urls "
        "containing an array of URLs.\n"
        f"Topic: {topic}\nViewer question: {engineering_question}\nAdditional focus: {user_guidance or 'None'}"
    )
    response = client.models.generate_content(
        model=model,
        contents=discover_prompt,
        config=types.GenerateContentConfig(
            response_mime_type="application/json",
            temperature=0.1,
        ),
    )
    try:
        candidates = json.loads(response.text).get("candidate_source_urls", [])
    except (TypeError, json.JSONDecodeError) as exc:
        raise RuntimeError("The research step did not return a valid list of technical source URLs.") from exc

    verified = fetch_verified_technical_sources(candidates)
    retrieved_pages = "\n\n".join(
        f"SOURCE {index}: {item['title']}\nURL: {item['url']}\n"
        f"RETRIEVED PAGE TEXT:\n{item['content_excerpt']}"
        for index, item in enumerate(verified, 1)
    )
    summary_prompt = (
        "Prepare a technical fact pack for an original animated engineering explainer. "
        "Use only the retrieved page text below for factual claims, not model memory. "
        "Identify supported facts, important limits/conditions, common misconceptions, and which URLs support each fact. "
        "Do not invent measurements, statistics, capacities, prices or performance guarantees. "
        "Return JSON only with keys research_notes, important_caveats and unsupported_claims.\n"
        f"Topic: {topic}\nViewer question: {engineering_question}\n"
        f"Additional focus: {user_guidance or 'None'}\n\n"
        f"Retrieved source pages:\n{retrieved_pages}"
    )
    summary_response = client.models.generate_content(
        model=model,
        contents=summary_prompt,
        config=types.GenerateContentConfig(
            response_mime_type="application/json",
            temperature=0.15,
        ),
    )
    try:
        summary = json.loads(summary_response.text)
    except (TypeError, json.JSONDecodeError) as exc:
        raise RuntimeError("The research model did not return a valid technical fact pack.") from exc

    research_notes = str(summary.get("research_notes", "")).strip()
    if len(research_notes) < 100:
        raise ValueError("The fetched technical pages did not produce a sufficiently detailed fact pack.")

    return {
        "topic": topic,
        "engineering_question": engineering_question,
        "model": model,
        "research_notes": research_notes,
        "important_caveats": summary.get("important_caveats", []),
        "unsupported_claims": summary.get("unsupported_claims", []),
        "sources": [
            {"title": item["title"], "url": item["url"], "domain": item["domain"]}
            for item in verified
        ],
        "source_retrieval": verified,
        "created_at": time.strftime("%Y-%m-%d %H:%M:%S"),
    }


def generate_episode_from_flow_scenes(
    project_dir: Path,
    scene_files: Iterable[Path],
    episode_title: str,
    engineering_question: str,
    research_notes: str,
    source_references: Iterable[str],
    gemini_api_key: str,
    draft_script: str = "",
    target_seconds: int = 65,
    model: str = "gemini-3.8-flash",
) -> dict:
    """Analyse a storyboard contact sheet and generate a source-constrained script/scene manifest."""
    if not gemini_api_key or len(gemini_api_key.strip()) < 10:
        raise ValueError("A valid GEMINI_API_KEY is required for automatic script/storyboard generation.")
    if len(research_notes.strip()) < 30:
        raise ValueError(
            "Add a useful technical research summary before asking the model to write an engineering explainer."
        )

    try:
        from google import genai
        from google.genai import types
        from PIL import Image
    except ImportError as exc:
        raise RuntimeError(
            "Google GenAI and Pillow are required for automatic script generation. "
            "Run the engineering setup cell again."
        ) from exc

    scene_files = sorted([Path(p) for p in scene_files], key=lambda p: _natural_key(p.name))
    project_dir = Path(project_dir)
    storyboard_fingerprint = _json_fingerprint({
        "scene_files": [_file_fingerprint(path) for path in scene_files],
        "episode_title": episode_title,
        "engineering_question": engineering_question,
        "research_notes": research_notes,
        "source_references": list(source_references),
        "draft_script": draft_script,
        "target_seconds": target_seconds,
        "model": model,
    })
    existing_brief_path = project_dir / "episode_brief.json"
    existing_manifest_path = project_dir / "scene_manifest.csv"
    if existing_brief_path.exists() and existing_manifest_path.exists():
        existing_brief = json.loads(existing_brief_path.read_text(encoding="utf-8"))
        if existing_brief.get("storyboard_fingerprint") == storyboard_fingerprint:
            existing_brief["storyboard_reused"] = True
            return existing_brief
    work = project_dir / "work" / "engineering"
    contact_sheet = _extract_scene_contact_sheet(scene_files, work / "flow_storyboard_contact_sheet.jpg")
    references = [str(url).strip() for url in source_references if str(url).strip().startswith(("https://", "http://"))]
    if not references:
        raise ValueError("Add at least one credible technical source URL.")

    prompt = f"""
You are the original scriptwriter and visual storyboard editor for an educational animated engineering channel.
Create one factual, engaging YouTube Short using the supplied contact sheet of the actual Google Flow scenes.

Episode title: {episode_title}
Viewer's engineering question: {engineering_question}
Target narration length: about {target_seconds} seconds (aim for roughly {max(45, int(target_seconds * 1.85))}-{max(65, int(target_seconds * 2.15))} spoken words).
Technical research notes (the only facts you may assert):
{research_notes}

Reference URLs (record these; do not claim to have opened or verified them):
{chr(10).join(references)}

Optional script draft to improve, if present:
{draft_script or "[No draft supplied. Write an original script grounded only in the notes above.]"}

Rules:
- Build the narration around the actual visible scene order shown in the contact sheet.
- Do not invent dimensions, capacities, prices, dates, statistics, performance guarantees, or engineering properties.
- If the scenes show a technical detail not supported by the notes, describe only what is visibly shown and do not present it as verified fact.
- Make clear any conditional components, design limitations or trade-offs in the notes.
- Write original narration, not a rewrite of another YouTube channel.
- Use a strong opening question, clear cause-and-effect explanation and a concise ending.
- Do not include Markdown, stage directions, sound-effect cues, citations inside the spoken narration, or section headings.
- Provide concise, factually bounded lower-third scene titles and short scene descriptions. There must be exactly one scene_manifest entry for each supplied file, using every exact filename once.
- You may reorder supplied scenes into the clearest engineering story using their visible content. Set order to consecutive integers from 1 to N.
- The script should be readable aloud and not exceed the target time by more than 10 percent.
- Output valid JSON only with keys:
  "episode_title", "engineering_question", "hook", "original_script",
  "engineering_takeaway", "scene_manifest".
- scene_manifest must be an array of objects with keys:
  "order", "scene_file", "scene_title", "visual_description", "engineering_explanation".
- Keep each scene_file exactly as listed below, but you may order scenes into the most understandable real-world engineering sequence:
{json.dumps([p.name for p in scene_files], ensure_ascii=False)}
"""
    client = genai.Client(api_key=gemini_api_key.strip())
    with Image.open(contact_sheet) as image:
        response = client.models.generate_content(
            model=model,
            contents=[prompt, image.copy()],
            config=types.GenerateContentConfig(
                response_mime_type="application/json",
                temperature=0.35,
            ),
        )
    try:
        result = json.loads(response.text)
    except (TypeError, json.JSONDecodeError) as exc:
        raise RuntimeError("Gemini did not return a valid JSON episode package. Nothing was exported.") from exc

    required = ["episode_title", "engineering_question", "hook", "original_script", "engineering_takeaway"]
    missing = [key for key in required if len(str(result.get(key, "")).strip()) < 8]
    if missing:
        raise ValueError(f"Generated episode package is incomplete: {missing}")
    generated_rows = result.get("scene_manifest")
    if not isinstance(generated_rows, list) or len(generated_rows) != len(scene_files):
        raise ValueError("Generated scene manifest does not contain exactly one row per Flow scene.")
    actual_files = [str(row.get("scene_file", "")) for row in generated_rows]
    expected_files = [path.name for path in scene_files]
    if len(actual_files) != len(set(actual_files)) or set(actual_files) != set(expected_files):
        raise ValueError("Generated scene manifest must include every source filename exactly once.")
    try:
        order_values = [int(row.get("order")) for row in generated_rows]
    except (TypeError, ValueError) as exc:
        raise ValueError("Generated scene order contains a non-integer value.") from exc
    if sorted(order_values) != list(range(1, len(scene_files) + 1)):
        raise ValueError("Generated scene order must contain each number from 1 through N exactly once.")
    generated_rows.sort(key=lambda row: int(row["order"]))

    result["source_references"] = references
    result["research_notes"] = research_notes
    result["storyboard_model"] = model
    result["storyboard_fingerprint"] = storyboard_fingerprint
    result["storyboard_reused"] = False
    result["storyboard_generated_at"] = time.strftime("%Y-%m-%d %H:%M:%S")
    result["script_generation_mode"] = "Gemini storyboard-assisted"
    _write_json(Path(project_dir) / "episode_brief.json", result)
    (Path(project_dir) / "original_script.md").write_text(
        "# Approved episode narration draft\n\n" + result["original_script"].strip() + "\n",
        encoding="utf-8",
    )

    manifest_path = Path(project_dir) / "scene_manifest.csv"
    fieldnames = [
        "order", "scene_file", "scene_title", "visual_description",
        "engineering_explanation", "source_urls", "review_status",
    ]
    with manifest_path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        for row in generated_rows:
            writer.writerow({
                "order": row["order"],
                "scene_file": row["scene_file"],
                "scene_title": row.get("scene_title", ""),
                "visual_description": row.get("visual_description", ""),
                "engineering_explanation": row.get("engineering_explanation", ""),
                "source_urls": "; ".join(references),
                "review_status": "auto_generated_needs_content_QC",
            })
    return result


def synthesize_episode_narration(
    project_dir: Path,
    workspace: Path,
    voice_id: str = "en_US-joe-medium",
) -> dict:
    """Create episode-specific speech from the saved script using a verified CC0 Piper voice."""
    project_dir = Path(project_dir)
    brief = json.loads((project_dir / "episode_brief.json").read_text(encoding="utf-8"))
    script = str(brief.get("original_script", "")).strip()
    words = _safe_words(script)
    if len(words) < 35:
        raise ValueError("The original episode script is too short for narration. Add a complete spoken script.")
    voice = ensure_voice_model(workspace, voice_id)
    actual_voice_id = str(voice["voice_id"])

    audio_dir = project_dir / "audio"
    audio_dir.mkdir(parents=True, exist_ok=True)
    narration_path = audio_dir / "narration.wav"
    metadata_path = audio_dir / "narration.json"
    script_hash = hashlib.sha256(script.encode("utf-8")).hexdigest()
    existing = json.loads(metadata_path.read_text(encoding="utf-8")) if metadata_path.exists() else {}
    if existing.get("script_sha256") == script_hash and existing.get("voice_id") == actual_voice_id and narration_path.exists():
        return {"audio": narration_path, "metadata": metadata_path, "reused": True, "details": existing}

    try:
        from piper import PiperVoice
    except ImportError as exc:
        raise RuntimeError("Piper TTS is not installed. Run the engineering setup cell again.") from exc

    voice_instance = PiperVoice.load(str(voice["model"]))
    import wave
    with wave.open(str(narration_path), "wb") as wav_file:
        voice_instance.synthesize_wav(script, wav_file)

    details = {
        "voice_id": actual_voice_id,
        "voice_language": VOICE_MODELS[actual_voice_id]["language"],
        "voice_model_license": voice["license"],
        "voice_training_base": voice["training_base"],
        "voice_fallback_used": voice["fallback_used"],
        "voice_model_card": str(voice["model_card"]),
        "tts_engine": "Piper TTS",
        "tts_engine_license": "GPL-3.0-or-later",
        "script_sha256": script_hash,
        "word_count": len(words),
        "created_at": time.strftime("%Y-%m-%d %H:%M:%S"),
    }
    _write_json(metadata_path, details)
    (audio_dir / "narration_script.txt").write_text(script + "\n", encoding="utf-8")
    return {"audio": narration_path, "metadata": metadata_path, "reused": False, "details": details}


def _srt_timestamp(seconds: float) -> str:
    total_ms = max(0, int(round(float(seconds) * 1000)))
    hours, total_ms = divmod(total_ms, 3_600_000)
    minutes, total_ms = divmod(total_ms, 60_000)
    whole_seconds, milliseconds = divmod(total_ms, 1000)
    return f"{hours:02d}:{minutes:02d}:{whole_seconds:02d},{milliseconds:03d}"


def _build_srt_from_words(words: list[dict], max_words: int = 5, max_chars: int = 34) -> str:
    groups = []
    current = []
    current_chars = 0
    for item in words:
        text = str(item["text"]).strip()
        if not text:
            continue
        extra = len(text) + (1 if current else 0)
        sentence_break = bool(current and re.search(r"[.!?]$", str(current[-1]["text"])))
        if current and (
            len(current) >= max_words
            or current_chars + extra > max_chars
            or sentence_break
            or float(item["start"]) - float(current[-1]["end"]) > 0.65
        ):
            groups.append(current)
            current = []
            current_chars = 0
            extra = len(text)
        current.append(item)
        current_chars += extra
    if current:
        groups.append(current)

    blocks = []
    index = 1
    previous_end = 0.0
    for group in groups:
        start = max(previous_end, float(group[0]["start"]))
        end = max(start + 0.12, float(group[-1]["end"]))
        text = " ".join(str(item["text"]).strip() for item in group)
        blocks.extend([str(index), f"{_srt_timestamp(start)} --> {_srt_timestamp(end)}", text, ""])
        previous_end = end
        index += 1
    return "\n".join(blocks).rstrip() + "\n"


def create_automatic_episode_captions(
    project_dir: Path,
    workspace: Path,
    model_size: str = "base.en",
    minimum_similarity: float = 0.90,
) -> dict:
    """Create word-timed SRT captions from the generated voice and automatically QA them."""
    try:
        from faster_whisper import WhisperModel
    except ImportError as exc:
        raise RuntimeError("faster-whisper is not installed. Run the engineering setup cell again.") from exc

    project_dir = Path(project_dir)
    brief = json.loads((project_dir / "episode_brief.json").read_text(encoding="utf-8"))
    script = str(brief.get("original_script", "")).strip()
    audio_path = project_dir / "audio" / "narration.wav"
    if not audio_path.exists():
        raise FileNotFoundError("Narration audio has not been generated. Run the narration stage first.")

    captions_dir = project_dir / "captions"
    captions_dir.mkdir(parents=True, exist_ok=True)
    srt_path = captions_dir / "episode.srt"
    qc_path = captions_dir / "caption_qc.json"
    script_hash = hashlib.sha256(script.encode("utf-8")).hexdigest()
    audio_hash = hashlib.sha256(audio_path.read_bytes()).hexdigest()
    old_qc = json.loads(qc_path.read_text(encoding="utf-8")) if qc_path.exists() else {}
    if (
        old_qc.get("script_sha256") == script_hash
        and old_qc.get("audio_sha256") == audio_hash
        and old_qc.get("model_size") == model_size
        and srt_path.exists()
    ):
        return {"srt": srt_path, "qc": qc_path, "details": old_qc, "reused": True}

    model_cache = Path(workspace) / "assets" / "whisper_models"
    model_cache.mkdir(parents=True, exist_ok=True)
    whisper = WhisperModel(model_size, device="cpu", compute_type="int8", download_root=str(model_cache))
    segments, info = whisper.transcribe(
        str(audio_path),
        language="en",
        beam_size=1,
        word_timestamps=True,
        vad_filter=False,
        condition_on_previous_text=False,
    )
    word_rows = []
    for segment in segments:
        for word in (getattr(segment, "words", None) or []):
            text = str(getattr(word, "word", "")).strip()
            start = float(getattr(word, "start", 0))
            end = float(getattr(word, "end", 0))
            if text and end > start >= 0:
                word_rows.append({
                    "text": text,
                    "start": start,
                    "end": end,
                    "probability": float(getattr(word, "probability", 0.0) or 0.0),
                })
    if not word_rows:
        raise RuntimeError("Speech recognizer returned no word timestamps; captions were not created.")

    expected = _normal_words(script)
    recognized = _normal_words(" ".join(item["text"] for item in word_rows))
    similarity = SequenceMatcher(None, expected, recognized).ratio()
    coverage = min(len(expected), len(recognized)) / max(1, len(expected))
    probabilities = [row["probability"] for row in word_rows if row["probability"] > 0]
    mean_probability = sum(probabilities) / len(probabilities) if probabilities else None

    # When recognition is close to the exact generated script, use the canonical script spelling
    # while preserving Whisper's word timings. If word counts diverge, retain ASR text and flag it.
    aligned_words = list(word_rows)
    if similarity >= minimum_similarity and len(expected) == len(word_rows):
        canonical_tokens = _safe_words(script)
        if len(canonical_tokens) == len(word_rows):
            aligned_words = [
                {**row, "text": canonical_tokens[index]}
                for index, row in enumerate(word_rows)
            ]

    srt_text = _build_srt_from_words(aligned_words)
    srt_path.write_text(srt_text, encoding="utf-8")
    srt_blocks = [block for block in srt_text.strip().split("\n\n") if block.strip()]
    timestamp_valid = all("-->" in block for block in srt_blocks)
    text_valid = all(len(block.splitlines()) >= 3 for block in srt_blocks)
    confidence_valid = mean_probability is not None and mean_probability >= 0.45
    auto_verified = (
        similarity >= minimum_similarity
        and coverage >= 0.90
        and confidence_valid
        and timestamp_valid
        and text_valid
    )
    details = {
        "status": "AUTO_VERIFIED" if auto_verified else "REVIEW_REQUIRED",
        "model_size": model_size,
        "language": getattr(info, "language", "en"),
        "word_count_expected": len(expected),
        "word_count_recognized": len(recognized),
        "script_match_ratio": round(similarity, 4),
        "word_coverage": round(coverage, 4),
        "mean_word_probability": round(mean_probability, 4) if mean_probability is not None else None,
        "srt_caption_count": len(srt_blocks),
        "srt_timestamps_valid": timestamp_valid,
        "srt_text_valid": text_valid,
        "minimum_script_match_ratio": minimum_similarity,
        "script_sha256": script_hash,
        "audio_sha256": audio_hash,
        "confidence_valid": confidence_valid,
        "created_at": time.strftime("%Y-%m-%d %H:%M:%S"),
        "review_note": (
            "Automated transcript-to-script and SRT-structure checks passed."
            if auto_verified else
            "Automated checks found a mismatch. Inspect captions/episode.srt and narration before export."
        ),
    }
    _write_json(qc_path, details)
    (captions_dir / "caption_qc_report.txt").write_text(
        "\n".join([
            f"Caption status: {details['status']}",
            f"Transcript/script match: {details['script_match_ratio']:.1%}",
            f"Recognized word coverage: {details['word_coverage']:.1%}",
            f"Mean word probability: {details['mean_word_probability']}",
            f"Caption blocks: {details['srt_caption_count']}",
            details["review_note"],
            "",
            "The captions were generated from the actual narration recording. A review flag is raised only when automated checks fall below threshold.",
        ]),
        encoding="utf-8",
    )
    return {"srt": srt_path, "qc": qc_path, "details": details, "reused": False}


def prepare_reusable_episode_assets(
    project_dir: Path,
    workspace: Path,
    scene_files: Iterable[Path],
    voice_id: str = "en_US-joe-medium",
    gemini_api_key: str | None = None,
    auto_storyboard: bool = True,
    auto_research: bool = True,
    episode_title: str = "",
    engineering_question: str = "",
    research_notes: str = "",
    source_references: Iterable[str] = (),
    draft_script: str = "",
    target_seconds: int = 65,
    whisper_model: str = "base.en",
    use_music: bool = True,
    user_guidance: str = "",
) -> dict:
    """Run the same research, storyboard, narration, caption-QA and licensed-music stages on every episode."""
    project_dir = Path(project_dir)
    scene_files = sorted([Path(p) for p in scene_files], key=lambda p: _natural_key(p.name))
    brief_path = project_dir / "episode_brief.json"
    brief = json.loads(brief_path.read_text(encoding="utf-8")) if brief_path.exists() else {}

    research = None
    if auto_research:
        research_dir = project_dir / "research"
        research_dir.mkdir(parents=True, exist_ok=True)
        research_path = research_dir / "research_report.json"
        requested_research = {
            "topic": episode_title or brief.get("episode_title", ""),
            "engineering_question": engineering_question or brief.get("engineering_question", ""),
            "user_guidance": user_guidance,
        }
        request_hash = _json_fingerprint(requested_research)
        cached_research = json.loads(research_path.read_text(encoding="utf-8")) if research_path.exists() else {}
        if cached_research.get("request_fingerprint") == request_hash and len(cached_research.get("sources", [])) >= 2:
            research = cached_research
            research["reused"] = True
        else:
            research = research_episode_topic(
                topic=requested_research["topic"],
                engineering_question=requested_research["engineering_question"],
                gemini_api_key=gemini_api_key or "",
                user_guidance=user_guidance,
            )
            research["user_guidance"] = user_guidance
            research["request_fingerprint"] = request_hash
            research["reused"] = False
            _write_json(research_path, research)
        research_notes = research["research_notes"]
        source_references = [item["url"] for item in research["sources"]]
        (research_dir / "source_notes.txt").write_text(
            research_notes + "\n\nIMPORTANT CAVEATS\n"
            + "\n".join(str(item) for item in research["important_caveats"])
            + "\n\nUNSUPPORTED CLAIMS\n"
            + "\n".join(str(item) for item in research["unsupported_claims"])
            + "\n",
            encoding="utf-8",
        )

    if auto_storyboard:
        if not research_notes.strip() or len(list(source_references)) < 2:
            raise ValueError(
                "Automatic script generation requires a verified technical fact pack and at least two fetched sources."
            )
        if not gemini_api_key:
            raise ValueError("Add GEMINI_API_KEY to Google Colab Secrets to enable automatic research and scripting.")
        generated = generate_episode_from_flow_scenes(
            project_dir=project_dir,
            scene_files=scene_files,
            episode_title=episode_title or brief.get("episode_title", ""),
            engineering_question=engineering_question or brief.get("engineering_question", ""),
            research_notes=research_notes,
            source_references=source_references,
            gemini_api_key=gemini_api_key,
            draft_script=draft_script,
            target_seconds=target_seconds,
        )
        if research:
            generated["research_report_path"] = str(project_dir / "research" / "research_report.json")
            _write_json(brief_path, generated)
    elif draft_script.strip():
        brief["original_script"] = draft_script.strip()
        brief["script_generation_mode"] = "User-supplied original script"
        if research:
            brief["source_references"] = [item["url"] for item in research["sources"]]
            brief["research_notes"] = research["research_notes"]
        _write_json(brief_path, brief)
        (project_dir / "original_script.md").write_text(
            "# Original episode narration\n\n" + draft_script.strip() + "\n",
            encoding="utf-8",
        )

    brief = json.loads(brief_path.read_text(encoding="utf-8"))
    script = str(brief.get("original_script", "")).strip()
    if len(_safe_words(script)) < 35:
        raise ValueError(
            "No complete narration script is available. Add a Gemini API key to Colab Secrets "
            "for automatic research and scripting."
        )
    from app.engineering_studio import validate_episode_brief, probe_media
    validate_episode_brief(brief_path)

    # Calculate the available picture duration before narration so a generated script can fit the actual scene set.
    scene_duration = sum(float(probe_media(path)["duration"]) for path in scene_files)
    if scene_duration < 15:
        raise ValueError("The Flow scene set is too short for an engineering explainer. Add more scene footage.")
    fitted_target = max(15, min(178, int(scene_duration * 0.90)))

    narration = synthesize_episode_narration(project_dir, workspace, voice_id=voice_id)
    import wave
    with wave.open(str(narration["audio"]), "rb") as wav_file:
        narration_duration = wav_file.getnframes() / max(1, wav_file.getframerate())

    # One automatic correction pass prevents a narration cut-off without requiring user script editing.
    if narration_duration > scene_duration + 0.75 and auto_storyboard:
        generated = generate_episode_from_flow_scenes(
            project_dir=project_dir,
            scene_files=scene_files,
            episode_title=episode_title or brief.get("episode_title", ""),
            engineering_question=engineering_question or brief.get("engineering_question", ""),
            research_notes=research_notes,
            source_references=source_references,
            gemini_api_key=gemini_api_key or "",
            draft_script=brief.get("original_script", ""),
            target_seconds=fitted_target,
        )
        if research:
            generated["research_report_path"] = str(project_dir / "research" / "research_report.json")
            _write_json(brief_path, generated)
        narration = synthesize_episode_narration(project_dir, workspace, voice_id=voice_id)
        with wave.open(str(narration["audio"]), "rb") as wav_file:
            narration_duration = wav_file.getnframes() / max(1, wav_file.getframerate())

    if narration_duration > scene_duration + 0.75:
        raise ValueError(
            f"The narration is {narration_duration:.1f}s but the Flow scenes total only "
            f"{scene_duration:.1f}s. The studio shortened the script once automatically, but it still does not fit. "
            "Add more scene footage or select longer Flow clips; the render will not cut off narration."
        )

    captions = create_automatic_episode_captions(
        project_dir, workspace, model_size=whisper_model
    )
    music = select_shared_music(workspace, project_dir) if use_music else None

    summary = {
        "narration": narration,
        "captions": captions,
        "music": music,
        "research": research,
        "scene_duration_seconds": round(scene_duration, 2),
        "narration_duration_seconds": round(narration_duration, 2),
        "narration_fits_scene_duration": narration_duration <= scene_duration + 0.75,
        "story_mode": brief.get("script_generation_mode", "User-supplied original script"),
        "episode_title": brief.get("episode_title"),
        "auto_caption_status": captions["details"]["status"],
        "manual_review_required": captions["details"]["status"] != "AUTO_VERIFIED",
    }
    _write_json(project_dir / "work" / "engineering" / "automatic_assets_report.json", {
        "episode_title": summary["episode_title"],
        "story_mode": summary["story_mode"],
        "research": research,
        "narration": narration["details"],
        "captions": captions["details"],
        "music": music["metadata"] if music else None,
        "scene_duration_seconds": summary["scene_duration_seconds"],
        "narration_duration_seconds": summary["narration_duration_seconds"],
        "narration_fits_scene_duration": summary["narration_fits_scene_duration"],
        "assets_reused": {
            "narration": narration["reused"],
            "captions": captions["reused"],
        },
    })
    return summary

def _natural_key(name: str) -> list[tuple[int, object]]:
    return [(0, int(part)) if part.isdigit() else (1, part.lower()) for part in re.split(r"(\d+)", str(name))]


def register_music_track(
    library_dir: Path,
    audio_file: Path,
    title: str,
    artist: str,
    license_name: str,
    license_url: str,
    source_url: str,
    attribution: str,
    commercial_use: bool,
) -> Path:
    """Register one user-supplied track once; its license sidecar makes it reusable across episodes."""
    if not commercial_use:
        raise PermissionError("The selected track is not cleared for commercial use and cannot enter the auto-pick library.")
    if not all([title.strip(), artist.strip(), license_name.strip(), license_url.startswith("https://"), source_url.startswith("https://"), attribution.strip()]):
        raise ValueError("Complete the track title, artist, license, source URL and attribution.")
    library_dir = Path(library_dir)
    library_dir.mkdir(parents=True, exist_ok=True)
    audio_file = Path(audio_file)
    if not audio_file.is_file() or audio_file.stat().st_size < 10_000:
        raise FileNotFoundError("The music file is missing or unexpectedly small.")
    import shutil
    target = library_dir / audio_file.name
    if audio_file.resolve() != target.resolve():
        shutil.copy2(audio_file, target)
    metadata = {
        "filename": target.name,
        "title": title.strip(),
        "artist": artist.strip(),
        "license": license_name.strip(),
        "license_url": license_url.strip(),
        "source": source_url.strip(),
        "attribution": attribution.strip(),
        "commercial_use": True,
        "verified_by_user": True,
        "registered_at": time.strftime("%Y-%m-%d %H:%M:%S"),
    }
    sidecar = target.with_suffix(".license.json")
    _write_json(sidecar, metadata)
    return sidecar
