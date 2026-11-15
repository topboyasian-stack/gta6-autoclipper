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

PIPELINE_VERSION = 3

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
    "download_url": "https://commons.wikimedia.org/wiki/Special:Redirect/file/New_Direction_(ISRC_USUAN1100677).mp3",
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


def _extract_scene_contact_sheet(scene_files: Iterable[Path], output_path: Path) -> Path:
    """Create a contact sheet with start/middle/end frames from every Flow clip."""
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
            subprocess.run(
                [
                    "ffmpeg", "-hide_banner", "-loglevel", "error", "-y",
                    "-ss", f"{sample_at:.3f}", "-i", str(scene),
                    "-frames:v", "1",
                    "-vf", "scale=240:135:force_original_aspect_ratio=decrease,pad=240:135:(ow-iw)/2:(oh-ih)/2",
                    str(frame_path),
                ],
                check=True, capture_output=True, text=True,
            )
            with Image.open(frame_path) as frame:
                thumbnail = frame.convert("RGB")
            x = frame_index * thumb_w
            y = row_y + scene_label_h
            sheet.paste(thumbnail, (x, y))
            frame_label = ("START", "MIDDLE", "END")[frame_index]
            draw.text((x + 5, y + thumb_h + 4), frame_label, fill="black", font=font)

    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    sheet.save(output_path, format="JPEG", quality=90)
    return output_path

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
