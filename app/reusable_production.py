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
import os
import re
import shutil
import subprocess
import time
import urllib.request
from difflib import SequenceMatcher
from pathlib import Path
from typing import Iterable

from whisper_runtime import load_whisper_model, resolve_whisper_runtime

PIPELINE_VERSION = 6
AUDIO_EXTENSIONS = {".mp3", ".wav", ".m4a", ".aac", ".ogg", ".flac"}
VIDEO_EXTENSIONS = {".mp4", ".mov", ".mkv", ".webm", ".m4v"}

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
    "filename": "How_it_Begins_CC_BY_3.0.mp3",
    "download_url": "https://commons.wikimedia.org/wiki/Special:Redirect/file/How_it_Begins_(ISRC_USUAN1100200).mp3",
    "title": "How it Begins",
    "artist": "Kevin MacLeod",
    "source": "https://commons.wikimedia.org/wiki/File:How_it_Begins_(ISRC_USUAN1100200).mp3",
    "source_site": "incompetech.com",
    "license": "Creative Commons Attribution 3.0 Unported",
    "license_url": "https://creativecommons.org/licenses/by/3.0/",
    "attribution": (
        "How it Begins Kevin MacLeod (incompetech.com)\n"
        "Licensed under Creative Commons: By Attribution 3.0 License\n"
        "https://creativecommons.org/licenses/by/3.0/"
    ),
    "commercial_use": True,
    "changes_made": "Looped or trimmed to the episode duration and mixed quietly beneath narration.",
    "verification_source": "Wikimedia Commons file description",
}

DEFAULT_MUSIC_TRACKS = [
    DEFAULT_MUSIC,
    {
        "filename": "At_Launch_CC_BY_3.0.mp3",
        "download_url": "https://commons.wikimedia.org/wiki/Special:Redirect/file/At_Launch_(ISRC_USUAN1100539).mp3",
        "title": "At Launch",
        "artist": "Kevin MacLeod",
        "source": "https://commons.wikimedia.org/wiki/File:At_Launch_(ISRC_USUAN1100539).mp3",
        "license": "Creative Commons Attribution 3.0 Unported",
        "license_url": "https://creativecommons.org/licenses/by/3.0/",
        "attribution": "At Launch Kevin MacLeod (incompetech.com)\nLicensed under Creative Commons: By Attribution 3.0 License\nhttps://creativecommons.org/licenses/by/3.0/",
        "commercial_use": True,
        "changes_made": "Looped or trimmed to the episode duration and mixed quietly beneath narration.",
        "verification_source": "Wikimedia Commons file description",
    },
    {
        "filename": "Cipher_CC_BY_3.0.mp3",
        "download_url": "https://commons.wikimedia.org/wiki/Special:Redirect/file/Cipher_(ISRC_USUAN1100844).mp3",
        "title": "Cipher",
        "artist": "Kevin MacLeod",
        "source": "https://commons.wikimedia.org/wiki/File:Cipher_(ISRC_USUAN1100844).mp3",
        "license": "Creative Commons Attribution 3.0 Unported",
        "license_url": "https://creativecommons.org/licenses/by/3.0/",
        "attribution": "Cipher Kevin MacLeod (incompetech.com)\nLicensed under Creative Commons: By Attribution 3.0 License\nhttps://creativecommons.org/licenses/by/3.0/",
        "commercial_use": True,
        "changes_made": "Looped or trimmed to the episode duration and mixed quietly beneath narration.",
        "verification_source": "Wikimedia Commons file description",
    },
    {
        "filename": "On_the_Passing_of_Time_CC_BY_3.0.mp3",
        "download_url": "https://commons.wikimedia.org/wiki/Special:Redirect/file/On_the_Passing_of_Time_(ISRC_USUAN1100520).mp3",
        "title": "On the Passing of Time",
        "artist": "Kevin MacLeod",
        "source": "https://commons.wikimedia.org/wiki/File:On_the_Passing_of_Time_(ISRC_USUAN1100520).mp3",
        "license": "Creative Commons Attribution 3.0 Unported",
        "license_url": "https://creativecommons.org/licenses/by/3.0/",
        "attribution": "On the Passing of Time Kevin MacLeod (incompetech.com)\nLicensed under Creative Commons: By Attribution 3.0 License\nhttps://creativecommons.org/licenses/by/3.0/",
        "commercial_use": True,
        "changes_made": "Looped or trimmed to the episode duration and mixed quietly beneath narration.",
        "verification_source": "Wikimedia Commons file description",
    },
]



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
    """Create a persistent Drive music library and seed several verified CC-BY tracks once."""
    library = Path(workspace) / "assets" / "music_library"
    library.mkdir(parents=True, exist_ok=True)
    available = []
    failures = []

    # If the user has already registered their own cleared tracks, honour that library
    # without downloading the default pack on their behalf.
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

    default_tracks_to_seed = [] if has_registered_track else DEFAULT_MUSIC_TRACKS
    for track in default_tracks_to_seed:
        audio_path = library / track["filename"]
        license_path = library / (audio_path.stem + ".license.json")
        try:
            if not audio_path.exists() or audio_path.stat().st_size < 250_000:
                _download(track["download_url"], audio_path, min_bytes=250_000)
            if not license_path.exists():
                _write_json(license_path, track)
            metadata = json.loads(license_path.read_text(encoding="utf-8"))
            if (
                audio_path.exists()
                and metadata.get("commercial_use")
                and metadata.get("license_url")
                and metadata.get("attribution")
            ):
                available.append((audio_path, license_path, metadata))
        except Exception as exc:
            failures.append({
                "title": track["title"],
                "error": f"{type(exc).__name__}: {exc}",
            })
            (library / f"{audio_path.stem}.download_error.txt").write_text(
                f"Could not download this default music track: {type(exc).__name__}: {exc}\n"
                "The studio will skip it and use another track with a complete licence record.\n",
                encoding="utf-8",
            )

    # User-registered tracks remain available alongside the default library.
    seeded_names = {audio.name for audio, _, _ in available}
    for sidecar in sorted(library.glob("*.license.json")):
        try:
            metadata = json.loads(sidecar.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        stem = sidecar.name.removesuffix(".license.json")
        matches = [
            path for path in library.glob(stem + ".*")
            if path.is_file() and path.suffix.lower() in AUDIO_EXTENSIONS
        ]
        for audio in matches:
            if audio.name in seeded_names:
                continue
            if metadata.get("commercial_use") and metadata.get("license_url") and metadata.get("attribution"):
                available.append((audio, sidecar, metadata))
                seeded_names.add(audio.name)

    if not available:
        raise FileNotFoundError(
            "No commercial-use music track with a complete licence record is available. "
            "Check the internet connection or add an audio file with a complete licence sidecar."
        )

    return {
        "directory": library,
        "audio": available[0][0],
        "license": available[0][1],
        "available_count": len(available),
        "download_failures": failures,
    }

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


def _extract_storyboard_frame(
    scene_file: Path,
    sample_at: float,
    output_path: Path,
) -> tuple[Path, bool]:
    """Extract one storyboard frame, retrying different seek modes before failing clearly."""
    from PIL import Image

    scene_file = Path(scene_file)
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    # Scale to a fixed width only. Pillow fits the extracted frame into the contact-sheet tile;
    # avoiding FFmpeg pad prevents portrait Flow exports from producing invalid pad dimensions.
    scale_filter = "scale=240:-2"
    attempts = [
        (
            "accurate timestamp seek",
            ["-i", str(scene_file), "-ss", f"{sample_at:.3f}"],
            scale_filter,
            False,
        ),
        (
            "fast timestamp seek",
            ["-ss", f"{sample_at:.3f}", "-i", str(scene_file)],
            scale_filter,
            False,
        ),
        (
            "first decodable frame fallback",
            [
                "-fflags", "+discardcorrupt",
                "-err_detect", "ignore_err",
                "-i", str(scene_file),
            ],
            "select=eq(n\\,0)," + scale_filter,
            True,
        ),
    ]
    errors = []
    for label, input_args, video_filter, is_fallback in attempts:
        output_path.unlink(missing_ok=True)
        command = [
            "ffmpeg", "-hide_banner", "-loglevel", "error", "-nostdin", "-y",
            *input_args,
            "-an", "-sn", "-dn", "-frames:v", "1",
            "-vf", video_filter, "-q:v", "3", str(output_path),
        ]
        try:
            result = subprocess.run(command, capture_output=True, text=True, timeout=60)
            if result.returncode == 0 and output_path.is_file() and output_path.stat().st_size > 0:
                try:
                    with Image.open(output_path) as frame:
                        frame.verify()
                    return output_path, is_fallback
                except Exception as exc:
                    errors.append(f"{label}: output image could not be opened ({type(exc).__name__})")
            else:
                detail = (result.stderr or result.stdout or "").strip()[-1200:]
                errors.append(
                    f"{label}: FFmpeg exit {result.returncode}"
                    + (f" ({detail})" if detail else "")
                )
        except subprocess.TimeoutExpired:
            errors.append(f"{label}: FFmpeg timed out after 60 seconds")
        except Exception as exc:
            errors.append(f"{label}: {type(exc).__name__}: {exc}")
        output_path.unlink(missing_ok=True)

    detail = " | ".join(errors)
    raise RuntimeError(
        f"Could not extract a storyboard frame from {scene_file.name} at {sample_at:.2f}s. "
        f"Tried accurate seek, fast seek and first-decodable-frame fallback. {detail}. "
        "The Flow MP4 may be incomplete or use a damaged video stream; re-export only this clip from Flow."
    )


def _extract_scene_contact_sheet(scene_files: Iterable[Path], output_path: Path) -> Path:
    """Create a storyboard contact sheet with start/middle/end frames from every Flow clip."""
    from PIL import Image, ImageDraw, ImageFont

    scenes = sorted([Path(p) for p in scene_files], key=lambda p: _natural_key(p.name))
    if not scenes:
        raise ValueError("No Google Flow scene files were supplied.")
    work = Path(output_path).parent / "storyboard_frames"
    work.mkdir(parents=True, exist_ok=True)
    font = ImageFont.load_default()
    thumb_w, thumb_h = 240, 135
    frame_label_h, scene_label_h = 22, 24
    frame_count = 3
    sheet_width = frame_count * thumb_w
    row_height = scene_label_h + thumb_h + frame_label_h
    sheet = Image.new("RGB", (sheet_width, len(scenes) * row_height), "white")
    draw = ImageDraw.Draw(sheet)

    for index, scene in enumerate(scenes):
        result = subprocess.run(
            [
                "ffprobe", "-v", "error", "-show_entries", "format=duration",
                "-of", "default=noprint_wrappers=1:nokey=1", str(scene),
            ],
            capture_output=True, text=True,
        )
        if result.returncode:
            raise RuntimeError(f"Cannot inspect scene {scene.name}: {result.stderr[-1200:]}")
        duration = max(0.1, float(result.stdout.strip()))
        sample_points = [
            min(max(0.1, duration * fraction), max(0.1, duration - 0.05))
            for fraction in (0.20, 0.50, 0.80)
        ]
        row_y = index * row_height
        draw.text((6, row_y + 4), f"SCENE {index + 1:02d}: {scene.name[:78]}", fill="black", font=font)

        for frame_index, sample_at in enumerate(sample_points):
            frame_path = work / f"{index + 1:02d}_{scene.stem}_{frame_index + 1}.jpg"
            frame_path, used_fallback = _extract_storyboard_frame(
                scene_file=scene,
                sample_at=sample_at,
                output_path=frame_path,
            )
            with Image.open(frame_path) as frame:
                thumbnail = frame.convert("RGB")
            thumbnail.thumbnail((thumb_w, thumb_h), Image.Resampling.LANCZOS)
            tile = Image.new("RGB", (thumb_w, thumb_h), "black")
            tile.paste(
                thumbnail,
                ((thumb_w - thumbnail.width) // 2, (thumb_h - thumbnail.height) // 2),
            )
            x = frame_index * thumb_w
            y = row_y + scene_label_h
            sheet.paste(tile, (x, y))
            frame_label = ("START", "MIDDLE", "END")[frame_index]
            if used_fallback:
                frame_label += " (fallback)"
            draw.text((x + 5, y + thumb_h + 4), frame_label, fill="black", font=font)

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
    if host.endswith((".gov", ".edu", ".int", ".state.mn.us")):
        return True
    trusted = {
        "asce.org", "www.asce.org",
        "concrete.org", "www.concrete.org",
        "usgbc.org", "www.usgbc.org",
        "iea.org", "www.iea.org",
        "aia.org", "www.aia.org",
        "cmha.org", "www.cmha.org",
        "masonryandhardscapes.org", "www.masonryandhardscapes.org",
    }
    return host in trusted


def _curated_technical_source_urls(topic: str, engineering_question: str) -> list[str]:
    """Known official sources for the parking-lot/permeable-pavement pilot when discovery URLs fail."""
    subject = f"{topic} {engineering_question}".lower()
    pavement_terms = (
        "permeable pavement", "permeable pavements", "parking lot", "parking-lot",
        "stormwater", "runoff", "rainwater", "green streets",
    )
    if not any(term in subject for term in pavement_terms):
        return []
    return [
        "https://www.epa.gov/green-infrastructure/types-green-infrastructure",
        "https://www.epa.gov/green-infrastructure/green-infrastructure-design-strategies",
        "https://stormwater.pca.state.mn.us/types_of_permeable_pavement",
        "https://stormwater.pca.state.mn.us/green_infrastructure_benefits_of_permeable_pavement",
        "https://www.epa.gov/system/files/documents/2021-11/bmp-permeable-pavements.pdf",
        "https://www.epa.gov/sites/default/files/2021-04/documents/green_streets_design_manual_feb_2021_web_res_small_508.pdf",
        "https://ask.ifas.ufl.edu/publication/AE530",
        "https://www.cmha.org/resource/pav-man-001-26/",
    ]


def _extract_technical_pdf_text(raw: bytes) -> str:
    """Extract readable text from an official technical PDF using pypdf."""
    from io import BytesIO
    try:
        from pypdf import PdfReader
    except ImportError as exc:
        raise RuntimeError(
            "A source is a PDF but pypdf is missing. Re-run the Colab processing setup to install it."
        ) from exc

    reader = PdfReader(BytesIO(raw), strict=False)
    pages = []
    for page in reader.pages[:80]:
        try:
            text = page.extract_text() or ""
        except Exception:
            text = ""
        if text.strip():
            pages.append(text)
    return re.sub(r"\s+", " ", " ".join(pages)).strip()


def fetch_verified_technical_sources(candidate_urls, max_pages: int = 5) -> list[dict]:
    """Fetch HTML or PDF sources from trusted technical domains, retaining useful error diagnostics."""
    from urllib.request import Request, urlopen
    from urllib.parse import urlparse
    from urllib.error import HTTPError, URLError

    verified = []
    seen = set()
    diagnostics = []
    for raw_url in candidate_urls:
        url = str(raw_url).strip()
        if url in seen or not _trusted_technical_url(url):
            continue
        seen.add(url)
        request = Request(
            url,
            headers={
                "User-Agent": (
                    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
                    "(KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36"
                ),
                "Accept": "text/html,application/xhtml+xml,application/pdf;q=0.9,*/*;q=0.7",
                "Accept-Language": "en-US,en;q=0.9",
            },
        )
        try:
            with urlopen(request, timeout=35) as response:
                final_url = response.geturl()
                content_type = response.headers.get("Content-Type", "").lower()
                if not _trusted_technical_url(final_url):
                    diagnostics.append(f"{urlparse(url).hostname}: redirected outside the trusted-domain list")
                    continue
                raw = response.read(8_000_000)

            parsed_path = urlparse(final_url).path.lower()
            is_pdf = (
                "application/pdf" in content_type
                or parsed_path.endswith(".pdf")
                or raw.lstrip().startswith(b"%PDF-")
            )
            if is_pdf:
                page_text = _extract_technical_pdf_text(raw)
                title = Path(parsed_path).name or "Technical PDF"
            else:
                is_html = (
                    "text/html" in content_type
                    or "application/xhtml+xml" in content_type
                    or b"<html" in raw[:2000].lower()
                    or b"<!doctype html" in raw[:2000].lower()
                )
                if not is_html:
                    diagnostics.append(
                        f"{urlparse(url).hostname}: unsupported content type {content_type or 'unknown'}"
                    )
                    continue
                parser = _EpisodeResearchHTMLParser.Parser()
                parser.feed(raw.decode("utf-8", errors="replace"))
                page_text = re.sub(r"\s+", " ", " ".join(parser.parts)).strip()
                title = " ".join(parser.title_parts).strip()[:240] or final_url

            if len(page_text) < 500:
                diagnostics.append(f"{urlparse(url).hostname}: only {len(page_text)} readable characters")
                continue
            verified.append({
                "title": title[:240],
                "url": final_url,
                "domain": urlparse(final_url).hostname or "",
                "content_excerpt": page_text[:9000],
                "content_type": "application/pdf" if is_pdf else "text/html",
                "verified_at": time.strftime("%Y-%m-%d %H:%M:%S"),
            })
        except HTTPError as exc:
            diagnostics.append(f"{urlparse(url).hostname}: HTTP {exc.code}")
        except URLError as exc:
            diagnostics.append(f"{urlparse(url).hostname}: network error ({type(exc.reason).__name__})")
        except Exception as exc:
            diagnostics.append(f"{urlparse(url).hostname}: {type(exc).__name__}")

        if len(verified) >= max_pages:
            break

    if len(verified) < 2:
        detail = "; ".join(diagnostics[:6]) or "No candidate URL passed the trusted-domain check."
        raise RuntimeError(
            "The studio could not retrieve at least two readable technical sources from trusted domains. "
            f"Attempted {len(seen)} trusted URL(s). Retrieval details: {detail}. "
            "No narration was generated. The next retry will use the pilot's built-in official EPA and "
            "state engineering references as fallbacks."
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
        "and Wikipedia. Direct HTML pages and technical PDFs are both acceptable. Do not invent a URL; if uncertain, omit it. Return JSON only with key candidate_source_urls "
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

    if not isinstance(candidates, list):
        raise RuntimeError("The research step returned candidate_source_urls in an unexpected format.")
    curated_sources = _curated_technical_source_urls(topic, engineering_question)
    # Put the known official pilot references first; model-suggested URLs remain additional candidates.
    verified = fetch_verified_technical_sources(curated_sources + candidates)
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




FLOW_SCENE_COUNT = 6
FLOW_SCENE_DURATION_SECONDS = 8


def validate_flow_prompt_pack(
    payload: object,
    episode_title: str,
    engineering_question: str,
) -> dict:
    """Validate a six-scene, subscription-credit-conscious Google Flow prompt plan."""
    if not isinstance(payload, dict):
        raise ValueError("The Flow prompt planner returned a non-object response.")
    continuity = str(payload.get("visual_continuity_bible", "")).strip()
    raw_scenes = payload.get("scenes")
    if len(continuity) < 80:
        raise ValueError("The Flow prompt plan needs a usable visual-continuity guide.")
    if not isinstance(raw_scenes, list) or len(raw_scenes) != FLOW_SCENE_COUNT:
        raise ValueError(f"The Flow prompt plan must contain exactly {FLOW_SCENE_COUNT} scenes.")

    normalized_scenes = []
    for expected_order, raw_scene in enumerate(raw_scenes, start=1):
        if not isinstance(raw_scene, dict):
            raise ValueError(f"Scene {expected_order} is not a valid object.")
        try:
            order = int(raw_scene.get("order", expected_order))
        except (TypeError, ValueError) as exc:
            raise ValueError(f"Scene {expected_order} has an invalid order.") from exc
        if order != expected_order:
            raise ValueError("Flow scene orders must be sequential from 1 to 6.")
        title = str(raw_scene.get("scene_title", "")).strip()
        purpose = str(raw_scene.get("purpose", "")).strip()
        shot_description = str(raw_scene.get("shot_description", "")).strip()
        if len(title) < 3 or len(purpose) < 12 or len(shot_description) < 40:
            raise ValueError(f"Scene {expected_order} is missing its title, purpose, or visual description.")
        complete_prompt = (
            "Create one 8-second vertical 9:16 clip for an educational engineering explainer. "
            "Style and continuity for every scene: " + continuity + " "
            "Specific shot for this scene: " + shot_description + " "
            "Use one clear continuous shot and one restrained camera movement. "
            "No visible words, captions, labels, numbers, logos, watermarks, or spoken dialogue. "
            "Do not invent measurements, performance claims, or unsupported technical details. "
            "Show a plausible visual explanation only; verified narration and labels will be added later."
        )
        normalized_scenes.append({
            "order": expected_order,
            "scene_title": title,
            "purpose": purpose,
            "shot_description": shot_description,
            "prompt": complete_prompt,
            "filename": f"{expected_order:02d}_{re.sub(r'[^A-Za-z0-9]+', '_', title).strip('_').lower()[:42] or 'scene'}.mp4",
        })

    return {
        "episode_title": str(episode_title).strip(),
        "engineering_question": str(engineering_question).strip(),
        "visual_continuity_bible": continuity,
        "flow_model_recommendation": "Veo 3.1 Lite",
        "scene_duration_seconds": FLOW_SCENE_DURATION_SECONDS,
        "scene_count": FLOW_SCENE_COUNT,
        "scenes": normalized_scenes,
    }


def render_flow_prompt_pack_markdown(pack: dict) -> str:
    """Render a beginner-friendly Flow prompt sheet and credit plan."""
    scenes = pack.get("scenes", [])
    lines = [
        "# Google Flow Scene Prompt Pack",
        "",
        f"**Episode:** {pack['episode_title']}",
        f"**Viewer question:** {pack['engineering_question']}",
        "",
        "## Google Flow settings — check the live credit label before each batch",
        "",
        "- Model: **Veo 3.1 Lite**",
        "- Duration: **8 seconds per scene**",
        "- Aspect ratio: **vertical 9:16**",
        "- Generate at **720p**; if Flow offers 1080p upscaling for the generated clip at no extra credits, use that option.",
        "- For non-Ultra plans, Google's current help page lists 10 credits per Veo 3.1 Lite generation (4, 6, or 8 seconds). Costs and available models can change.",
        "",
        "## Monthly planning baseline",
        "",
        "- Six scenes per Short: about **60 credits** before retries.",
        "- Twenty Shorts: **1,200 credits** before retries; reserve 25% for replacements, for a working budget of about **1,500 credits**.",
        "- Google AI Pro currently includes 1,000 monthly Flow credits plus 50 daily credits. Daily credits do not roll over; the practical total depends on using them on the days they refresh.",
        "- A 30-day month could provide up to 2,500 credits if all 30 daily allotments are used. Daily credits do not accumulate when skipped.",
        "- Check current costs and refresh rules in Google Flow Help: https://support.google.com/flow/answer/16526234.",
        "- This is a planning estimate, not an unlimited allowance. Check the current Flow credit balance and model cost in the prompt box.",
        "",
        "## Visual continuity guide",
        "",
        pack["visual_continuity_bible"],
        "",
        "## Generate the six clips",
        "",
        "Create one clip for each prompt below. Keep the same Flow project, recurring subject, setting, style, and aspect ratio. Download the six approved MP4s into the episode-specific incoming folder shown by Colab. The Colab studio then checks the actual clips, can sequence them for clarity, and produces the researched narration, captions, licensed music and final render.",
        "",
        "These are visual prompts, not the engineering script. The notebook separately retrieves technical sources and writes the final sourced narration. Do not add unverified text or numerical claims inside the generated footage.",
        "",
    ]
    for scene in scenes:
        lines.extend([
            f"### Scene {scene['order']:02d} — {scene['scene_title']}",
            "",
            f"**Purpose:** {scene['purpose']}",
            "",
            "**Copy this complete prompt into Google Flow:**",
            "",
            "~~~text",
            scene["prompt"].strip(),
            "~~~",
            "",
            f"**Suggested export filename:** {scene['filename']}",
            "",
        ])
    lines.extend([
        "## After all six scenes are approved",
        "",
        "1. Export/download the scenes as MP4 files.",
        "2. Put only these six clips in the episode-specific Drive incoming folder displayed by the Colab controls.",
        "3. Return to Colab and continue with source preparation, processing/preview, and final export.",
        "4. Watch the finished preview before uploading it manually to YouTube.",
        "",
    ])
    return "\n".join(lines)


def generate_flow_prompt_pack(
    episode_title: str,
    engineering_question: str,
    gemini_api_key: str,
    user_guidance: str = "",
    model: str = "gemini-3.8-flash",
) -> dict:
    """Generate six scene-specific visual prompts for subscription-based Google Flow production."""
    if not gemini_api_key or len(gemini_api_key.strip()) < 10:
        raise ValueError("A GEMINI_API_KEY saved in Colab Secrets is required to generate a Flow prompt pack.")
    if not episode_title.strip() or not engineering_question.strip():
        raise ValueError("Enter both an episode title and the viewer question before generating prompts.")
    try:
        from google import genai
        from google.genai import types
    except ImportError as exc:
        raise RuntimeError("google-genai is not installed. Run the prompt-pack setup step again.") from exc

    client = genai.Client(api_key=gemini_api_key.strip())
    prompt = (
        "Create an original, visually coherent six-shot scene plan for a vertical engineering explainer to be "
        "generated manually in Google Flow. Return JSON only with exactly these keys: visual_continuity_bible, "
        "scenes. visual_continuity_bible must be a detailed guide that fixes the recurring subject/location, "
        "materials, colour palette, time of day, camera geography and visual style across all six clips. "
        "scenes must be an array of exactly six objects; each object has order (1 through 6), scene_title, purpose, "
        "shot_description. Make a logical progression from hook/problem, through the mechanism/components, to an "
        "outcome and a relevant limitation. Each scene should be a single simple 8-second shot that can be generated "
        "separately. Use stylised 3D engineering animation, not photorealistic fake news footage, unless the topic "
        "makes a different clearly educational visual style more appropriate. No on-screen text, labels, captions, "
        "numbers, logos, watermarks, dialogue, invented dimensions, unsupported performance claims, or impossible "
        "physics. Keep each shot visually clear and specific; narration, factual labels and captions will be added "
        "later after the studio retrieves and checks technical sources. Avoid directing the video to display any "
        "factual claims as text. The prompts must each be understandable as standalone prompts and maintain the same "
        "continuity guide. Do not return actual video, image, audio or script; return only scene-planning JSON.\n\n"
        f"Episode title: {episode_title.strip()}\n"
        f"Viewer question: {engineering_question.strip()}\n"
        f"Topic focus: {user_guidance.strip() or 'None'}"
    )
    response = client.models.generate_content(
        model=model,
        contents=prompt,
        config=types.GenerateContentConfig(
            response_mime_type="application/json",
            temperature=0.35,
        ),
    )
    try:
        raw_payload = json.loads(response.text)
    except (TypeError, json.JSONDecodeError) as exc:
        raise RuntimeError("Gemini did not return a valid Flow prompt pack. No prompt file was saved.") from exc
    pack = validate_flow_prompt_pack(raw_payload, episode_title, engineering_question)
    pack["model"] = model
    pack["generated_at"] = time.strftime("%Y-%m-%d %H:%M:%S")
    pack["topic_focus"] = user_guidance.strip()
    return pack


def save_flow_prompt_pack(pack: dict, workspace: Path) -> dict[str, Path]:
    """Save prompt JSON and copy-ready Markdown in the persistent Google Drive workspace."""
    title_slug = re.sub(r"[^A-Za-z0-9_-]+", "_", pack["episode_title"]).strip("_").lower()[:48] or "engineering_episode"
    fingerprint = _json_fingerprint({
        "episode_title": pack["episode_title"],
        "engineering_question": pack["engineering_question"],
        "topic_focus": pack.get("topic_focus", ""),
        "scene_count": pack.get("scene_count", FLOW_SCENE_COUNT),
    })[:12]
    output_dir = Path(workspace) / "flow_prompt_packs" / f"{title_slug}_{fingerprint}"
    output_dir.mkdir(parents=True, exist_ok=True)
    json_path = output_dir / "flow_scene_prompt_pack.json"
    markdown_path = output_dir / "flow_scene_prompt_pack.md"
    _write_json(json_path, pack)
    markdown_path.write_text(render_flow_prompt_pack_markdown(pack), encoding="utf-8")
    return {"directory": output_dir, "json": json_path, "markdown": markdown_path}


def _is_retryable_gemini_error(error: Exception) -> bool:
    """Recognise temporary Gemini capacity and rate-limit errors without hiding bad requests."""
    status = getattr(error, "code", None)
    try:
        status_code = int(status)
    except (TypeError, ValueError):
        status_code = None
    if status_code in {429, 500, 502, 503, 504}:
        return True
    message = str(error).lower()
    return any(
        marker in message
        for marker in (
            "503 unavailable",
            "service unavailable",
            "temporarily unavailable",
            "currently experiencing high demand",
            "resource exhausted",
            "rate limit",
            "429",
            "502",
            "504",
        )
    )


def _generate_content_with_fallback(
    client,
    model: str,
    contents,
    config,
) -> tuple[object, str]:
    """Retry temporary Gemini errors, then switch to a lighter stable model automatically."""
    model_candidates = [model]
    fallback_model = "gemini-3.5-flash-lite"
    if fallback_model != model:
        model_candidates.append(fallback_model)

    failures = []
    last_error = None
    for candidate in model_candidates:
        for attempt in range(2):
            try:
                response = client.models.generate_content(
                    model=candidate,
                    contents=contents,
                    config=config,
                )
                return response, candidate
            except Exception as exc:
                if not _is_retryable_gemini_error(exc):
                    raise
                last_error = exc
                failures.append(f"{candidate} attempt {attempt + 1}: {type(exc).__name__}: {exc}")
                if attempt == 0:
                    time.sleep(3)

    detail = " | ".join(failures)
    raise RuntimeError(
        "Gemini script generation is temporarily unavailable on the primary and fallback models. "
        "Your saved clips and research remain intact; rerun processing to retry. "
        + detail
    ) from last_error


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
        "pipeline_version": PIPELINE_VERSION,
    })
    existing_brief_path = project_dir / "episode_brief.json"
    existing_manifest_path = project_dir / "scene_manifest.csv"
    if existing_brief_path.exists() and existing_manifest_path.exists():
        existing_brief = json.loads(existing_brief_path.read_text(encoding="utf-8"))
        if existing_brief.get("storyboard_fingerprint") == storyboard_fingerprint:
            existing_brief["storyboard_reused"] = True
            return existing_brief
    work = project_dir / "work" / "engineering"
    contact_sheet = None
    storyboard_warning = ""
    try:
        contact_sheet = _extract_scene_contact_sheet(
            scene_files, work / "flow_storyboard_contact_sheet.jpg"
        )
    except (RuntimeError, OSError, ValueError) as exc:
        # A visual storyboard improves scene matching, but it must never block the episode.
        # The text-only path below preserves the supplied clip order and clearly records that
        # no machine visual inspection was performed.
        storyboard_warning = f"{type(exc).__name__}: {exc}"
    references = [str(url).strip() for url in source_references if str(url).strip().startswith(("https://", "http://"))]
    if not references:
        raise ValueError("Add at least one credible technical source URL.")

    if contact_sheet is not None:
        visual_review_instructions = """
VISUAL REVIEW AVAILABLE:
You have a contact sheet made from the actual Google Flow clips.
Use only details that are genuinely visible when describing a scene.
You may reorder the supplied clips if that makes the engineering explanation clearer.
"""
        visual_analysis_rules = (
            "- Use actual visible content to choose the clearest engineering story sequence.\n"
            "- You may reorder supplied scenes into the clearest engineering story using their visible content. "
            "Set order to consecutive integers from 1 to N.\n"
        )
    else:
        visual_review_instructions = """
VISUAL REVIEW UNAVAILABLE:
The contact sheet could not be created. You have not seen the clip frames.
Treat the numbered Flow clips as illustrative assets already supplied in their intended order.
Keep the exact natural filename order from scene 1 through scene N. Do not reorder them.
Do not claim to see, identify or describe specific objects, camera shots or actions in the footage.
For every visual_description, write exactly:
"Visual content not machine-reviewed; retained in supplied order."
"""
        visual_analysis_rules = (
            "- Do not claim to have seen the clips or infer specific visible objects/actions.\n"
            "- Keep the exact supplied natural filename order, with consecutive order numbers from 1 through N.\n"
        )

    prompt = f"""
You are the original scriptwriter for an educational animated engineering channel.
Create one factual, engaging YouTube Short grounded only in the technical research below.
{visual_review_instructions}

Episode title: {episode_title}
Viewer's engineering question: {engineering_question}
Target narration length: about {target_seconds} seconds (aim for roughly {max(45, int(target_seconds * 1.85))}-{max(65, int(target_seconds * 2.15))} spoken words).
Technical research notes (the only facts you may assert):
{research_notes}

Verified technical source URLs retrieved for this episode:
{chr(10).join(references)}

Optional script draft to improve, if present:
{draft_script or "[No draft supplied. Write an original script grounded only in the notes above.]"}

Rules:
{visual_analysis_rules}
- Do not invent dimensions, capacities, prices, dates, statistics, performance guarantees, or engineering properties.
- Make clear any conditional components, design limitations or trade-offs in the notes.
- Write original narration, not a rewrite of another YouTube channel.
- Use a strong opening question, clear cause-and-effect explanation and a concise ending.
- Do not include Markdown, stage directions, sound-effect cues, citations inside the spoken narration, or section headings.
- Provide concise, factually bounded lower-third scene titles and short scene descriptions. There must be exactly one scene_manifest entry for each supplied file, using every exact filename once.
- The script should be readable aloud and not exceed the target time by more than 10 percent.
- Output valid JSON only with keys:
  "episode_title", "engineering_question", "hook", "original_script",
  "engineering_takeaway", "scene_manifest".
- scene_manifest must be an array of objects with keys:
  "order", "scene_file", "scene_title", "visual_description", "engineering_explanation".
- Keep each scene_file exactly as listed below:
{json.dumps([p.name for p in scene_files], ensure_ascii=False)}
"""
    client = genai.Client(api_key=gemini_api_key.strip())
    contents = [prompt]
    if contact_sheet is not None:
        with Image.open(contact_sheet) as image:
            contents.append(image.copy())
    response, used_model = _generate_content_with_fallback(
        client=client,
        model=model,
        contents=contents,
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
    if contact_sheet is None:
        # Enforce source order and explicit non-observation in code, not merely in the prompt.
        source_order = {path.name: index for index, path in enumerate(scene_files, 1)}
        for row in generated_rows:
            row["order"] = source_order[row["scene_file"]]
            row["visual_description"] = (
                "Visual content not machine-reviewed; retained in supplied order."
            )
    generated_rows.sort(key=lambda row: int(row["order"]))

    result["source_references"] = references
    result["research_notes"] = research_notes
    result["storyboard_model"] = used_model
    result["storyboard_requested_model"] = model
    result["storyboard_fingerprint"] = storyboard_fingerprint
    result["storyboard_reused"] = False
    result["storyboard_visual_review"] = (
        "completed" if contact_sheet is not None else "skipped_after_frame_extraction_error"
    )
    result["storyboard_visual_review_warning"] = storyboard_warning
    result["storyboard_generated_at"] = time.strftime("%Y-%m-%d %H:%M:%S")
    result["script_generation_mode"] = (
        "Gemini storyboard-assisted"
        if contact_sheet is not None
        else "Gemini text-only, source-grounded (visual review skipped)"
    )
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
                "review_status": (
                    "auto_generated_needs_content_QC"
                    if contact_sheet is not None
                    else "auto_generated_needs_content_QC_no_visual_review"
                ),
            })
    return result


def synthesize_episode_narration(
    project_dir: Path,
    workspace: Path,
    voice_id: str = "en_US-joe-medium",
) -> dict:
    """Create episode-specific speech using a Piper voice with verified model-card licensing provenance."""
    device_preference = (
        device_preference or os.getenv("WHISPER_DEVICE", "auto") or "auto"
    ).strip().lower()
    desired_device, _ = resolve_whisper_runtime(device_preference)

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
    voice_fingerprint = _file_fingerprint(Path(voice["model"]))
    shutil.copy2(voice["model_card"], audio_dir / "voice_MODEL_CARD.txt")
    engine_license_path = Path(voice["directory"]) / "PIPER_ENGINE_LICENSE.txt"
    if engine_license_path.exists():
        shutil.copy2(engine_license_path, audio_dir / "PIPER_ENGINE_LICENSE.txt")
    existing = json.loads(metadata_path.read_text(encoding="utf-8")) if metadata_path.exists() else {}
    if (
        existing.get("script_sha256") == script_hash
        and existing.get("voice_id") == actual_voice_id
        and existing.get("voice_model_fingerprint") == voice_fingerprint
        and existing.get("pipeline_version") == PIPELINE_VERSION
        and narration_path.exists()
    ):
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
        "voice_model_card": "audio/voice_MODEL_CARD.txt",
        "voice_model_fingerprint": voice_fingerprint,
        "pipeline_version": PIPELINE_VERSION,
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



def _load_drive_safe_whisper_model(
    model_size: str,
    model_cache: Path,
    model_class,
    device_preference: str | None = None,
):
    """Load Whisper from real files in Drive, avoiding Hugging Face symlink caches.

    Hugging Face's default cache creates snapshot symlinks to blob files. Google Drive
    mounts may represent those symlinks as small text files (for example, a relative
    path beginning with '../'), which CTranslate2 then mistakes for model.bin bytes.
    snapshot_download(local_dir=...) stores the model bundle as regular files; where
    supported, local_dir_use_symlinks=False is passed explicitly for older Hub releases.
    """
    import inspect
    from faster_whisper.utils import _MODELS
    from huggingface_hub import snapshot_download

    model_cache = Path(model_cache)
    model_cache.mkdir(parents=True, exist_ok=True)
    if Path(str(model_size)).is_dir():
        model_dir = Path(str(model_size))
    else:
        safe_model_name = re.sub(r"[^A-Za-z0-9_.-]+", "_", str(model_size)).strip("._") or "whisper"
        model_dir = model_cache / "direct_files" / safe_model_name

    def valid_model_binary(directory: Path) -> tuple[bool, int | None]:
        binary_path = directory / "model.bin"
        if not binary_path.is_file() or binary_path.is_symlink():
            return False, None
        try:
            if binary_path.stat().st_size < 1_000_000:
                return False, None
            with binary_path.open("rb") as handle:
                header = handle.read(4)
            if len(header) != 4:
                return False, None
            binary_version = int.from_bytes(header, byteorder="little", signed=False)
            # CTranslate2 model bundles use a small integer format version. Large
            # values here usually indicate a symlink target string or an HTML/error file.
            return 1 <= binary_version <= 100, binary_version
        except OSError:
            return False, None

    valid, observed_version = valid_model_binary(model_dir)
    if not valid:
        if model_dir.is_symlink() or (model_dir.exists() and not model_dir.is_dir()):
            model_dir.unlink(missing_ok=True)
        elif model_dir.exists():
            shutil.rmtree(model_dir)
        model_dir.parent.mkdir(parents=True, exist_ok=True)

        model_name = str(model_size)
        repo_id = model_name if "/" in model_name else _MODELS.get(model_name)
        if not repo_id:
            raise ValueError(f"Unsupported faster-whisper model name: {model_name!r}")

        download_args = {
            "repo_id": repo_id,
            "local_dir": str(model_dir),
            "allow_patterns": [
                "config.json",
                "preprocessor_config.json",
                "model.bin",
                "tokenizer.json",
                "vocabulary.*",
            ],
        }
        # Recent huggingface_hub releases removed this option because local_dir
        # downloads now use ordinary files. Older releases still need False explicitly.
        if "local_dir_use_symlinks" in inspect.signature(snapshot_download).parameters:
            download_args["local_dir_use_symlinks"] = False
        snapshot_download(**download_args)

        valid, observed_version = valid_model_binary(model_dir)
        if not valid:
            shutil.rmtree(model_dir, ignore_errors=True)
            raise RuntimeError(
                "The Whisper model download did not produce a valid CTranslate2 model.bin "
                f"(observed binary header: {observed_version!r}). The incomplete model folder "
                "was removed; check the Hugging Face download connection and rerun captions."
            )

    model, device, compute_type = load_whisper_model(
        model_class, str(model_dir), device_preference=device_preference
    )
    # Preserve the actual selected runtime so the caption QA record can explain
    # whether this render used CUDA or the CPU fallback.
    try:
        model._production_whisper_device = device
        model._production_whisper_compute_type = compute_type
    except Exception:
        pass
    print(
        f"Whisper ready: {model_size} on {device} ({compute_type}).",
        flush=True,
    )
    return model


def create_automatic_episode_captions(
    project_dir: Path,
    workspace: Path,
    model_size: str = "base.en",
    minimum_similarity: float = 0.90,
    device_preference: str | None = None,
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
        and old_qc.get("device_preference") == device_preference
        and old_qc.get("whisper_device") == desired_device
        and old_qc.get("pipeline_version") == PIPELINE_VERSION
        and srt_path.exists()
    ):
        return {"srt": srt_path, "qc": qc_path, "details": old_qc, "reused": True}

    model_cache = Path(workspace) / "assets" / "whisper_models"
    model_cache.mkdir(parents=True, exist_ok=True)
    whisper = _load_drive_safe_whisper_model(
        model_size, model_cache, WhisperModel, device_preference=device_preference
    )
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
        "device_preference": device_preference,
        "whisper_device": getattr(whisper, "_production_whisper_device", desired_device),
        "whisper_compute_type": getattr(whisper, "_production_whisper_compute_type", None),
        "pipeline_version": PIPELINE_VERSION,
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
    fitted_target = max(15, min(178, int(scene_duration * 0.70)))

    narration = synthesize_episode_narration(project_dir, workspace, voice_id=voice_id)
    studio_config_path = Path(workspace) / "assets" / "studio_config.json"
    studio_config = json.loads(studio_config_path.read_text(encoding="utf-8")) if studio_config_path.exists() else {}
    studio_config["default_voice_id"] = narration["details"]["voice_id"]
    studio_config["updated_at"] = time.strftime("%Y-%m-%d %H:%M:%S")
    _write_json(studio_config_path, studio_config)
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
