"""Stage 3: create per-scene narration audio and word-timed captions."""
from __future__ import annotations

import asyncio
import json
import os
import re
import shutil
import subprocess
from pathlib import Path
from typing import Any, Iterable

from config import NARRATOR_VOICE, WHISPER_MODEL


def _run(cmd: list[str]) -> None:
    subprocess.run(cmd, check=True, capture_output=True, text=True)


def _duration(path: Path) -> float:
    if not shutil.which("ffprobe"):
        raise RuntimeError("ffprobe is required. Install FFmpeg and ensure ffprobe is on PATH.")
    result = subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries", "format=duration",
         "-of", "default=noprint_wrappers=1:nokey=1", str(path)],
        check=True, capture_output=True, text=True,
    )
    try:
        return float(result.stdout.strip())
    except ValueError as exc:
        raise RuntimeError(f"Could not read audio duration for {path}") from exc


def _srt_time(seconds: float) -> str:
    milliseconds = max(0, int(round(seconds * 1000)))
    hours, milliseconds = divmod(milliseconds, 3_600_000)
    minutes, milliseconds = divmod(milliseconds, 60_000)
    secs, milliseconds = divmod(milliseconds, 1000)
    return f"{hours:02d}:{minutes:02d}:{secs:02d},{milliseconds:03d}"


async def _synthesize(text: str, target_mp3: Path, voice: str) -> None:
    import edge_tts

    communicate = edge_tts.Communicate(text=text, voice=voice, rate="-5%", pitch="-4Hz")
    await communicate.save(str(target_mp3))


def _word_cues(model, audio_path: Path, offset: float) -> tuple[list[dict], float]:
    segments, info = model.transcribe(
        str(audio_path),
        word_timestamps=True,
        vad_filter=True,
        condition_on_previous_text=False,
    )
    cues: list[dict] = []
    for segment in segments:
        words = getattr(segment, "words", None) or []
        for word in words:
            token = (getattr(word, "word", "") or "").strip()
            start = getattr(word, "start", None)
            end = getattr(word, "end", None)
            if token and start is not None and end is not None and float(end) > float(start):
                cues.append({"start": offset + float(start), "end": offset + float(end), "text": token})
    return cues, _duration(audio_path)


def _group_cues(cues: list[dict], max_words: int = 5) -> list[dict]:
    """Group Whisper word timestamps into readable captions without losing timing."""
    grouped: list[dict] = []
    current: list[dict] = []
    for cue in cues:
        current.append(cue)
        text = cue["text"]
        punctuated = bool(re.search(r"[.!?,;:]$", text))
        if len(current) >= max_words or punctuated:
            grouped.append({
                "start": current[0]["start"],
                "end": current[-1]["end"],
                "text": " ".join(item["text"] for item in current).strip(),
            })
            current = []
    if current:
        grouped.append({
            "start": current[0]["start"],
            "end": current[-1]["end"],
            "text": " ".join(item["text"] for item in current).strip(),
        })
    return grouped


def _write_srt(cues: list[dict], target: Path) -> None:
    lines: list[str] = []
    for index, cue in enumerate(cues, start=1):
        start = _srt_time(cue["start"])
        end = _srt_time(max(cue["start"] + 0.05, cue["end"]))
        lines.extend([str(index), f"{start} --> {end}", cue["text"], ""])
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text("\n".join(lines).rstrip() + "\n", encoding="utf-8")


def generate_audio_and_subtitles(
    output_dir: Path,
    voice: str | None = None,
    whisper_model_name: str = WHISPER_MODEL,
    make_subtitles: bool = True,
) -> dict:
    """Synthesize each scene; use Faster-Whisper timestamps for the combined SRT."""
    import json

    out = Path(output_dir)
    episode_path = out / "episode.json"
    if not episode_path.is_file():
        raise FileNotFoundError(f"Run stage 1 first: {episode_path} is missing.")
    episode = json.loads(episode_path.read_text(encoding="utf-8"))
    audio_dir = out / "audio"
    captions_dir = out / "captions"
    audio_dir.mkdir(parents=True, exist_ok=True)
    captions_dir.mkdir(parents=True, exist_ok=True)
    selected_voice = voice or NARRATOR_VOICE
    if not shutil.which("ffmpeg") or not shutil.which("ffprobe"):
        raise RuntimeError("FFmpeg and ffprobe are required to export WAV audio and validate durations.")

    for scene in episode["scenes"]:
        text = (scene.get("narration") or "").strip()
        if not text:
            raise ValueError(f"Scene {scene.get('scene_number')} has no narration.")
        scene_id = f"scene_{int(scene['scene_number']):03d}"
        mp3_path = audio_dir / f"{scene_id}.mp3"
        wav_path = audio_dir / f"{scene_id}.wav"
        if not mp3_path.is_file():
            asyncio.run(_synthesize(text, mp3_path, selected_voice))
        if not wav_path.is_file() or wav_path.stat().st_mtime < mp3_path.stat().st_mtime:
            _run([
                "ffmpeg", "-hide_banner", "-loglevel", "error", "-y",
                "-i", str(mp3_path), "-ac", "1", "-ar", "44100", "-c:a", "pcm_s16le",
                str(wav_path),
            ])

    manifest = []
    for scene in episode["scenes"]:
        scene_id = f"scene_{int(scene['scene_number']):03d}"
        audio_path = audio_dir / f"{scene_id}.wav"
        manifest.append({
            "scene_number": int(scene["scene_number"]),
            "audio_mp3": str(audio_dir / f"{scene_id}.mp3"),
            "audio_wav": str(audio_path),
            "duration_seconds": round(_duration(audio_path), 3),
            "voice": selected_voice,
        })
    manifest_path = audio_dir / "narration_manifest.json"
    manifest_path.write_text(json.dumps({
        "voice": selected_voice,
        "voice_provider": "Edge TTS",
        "scenes": manifest,
    }, indent=2) + "\n", encoding="utf-8")

    result = {
        "audio_dir": str(audio_dir),
        "scene_count": len(manifest),
        "voice": selected_voice,
        "manifest": str(manifest_path),
        "subtitles": None,
    }
    if not make_subtitles:
        return result
    try:
        from faster_whisper import WhisperModel
    except ImportError as exc:
        raise RuntimeError("faster-whisper is required for word-timed captions. Install project requirements.") from exc

    device = os.getenv("MYSTERY_WHISPER_DEVICE", "cpu").strip().lower()
    if device not in {"cpu", "cuda"}:
        device = "cpu"
    compute_type = "float16" if device == "cuda" else "int8"
    model = WhisperModel(whisper_model_name, device=device, compute_type=compute_type)
    all_words: list[dict] = []
    offset = 0.0
    for item in manifest:
        words, actual_duration = _word_cues(model, Path(item["audio_wav"]), offset)
        all_words.extend(words)
        offset += actual_duration + 0.4  # match the assembly pause inserted after each scene
    if not all_words:
        raise RuntimeError("Whisper returned no word timestamps; subtitles were not written.")
    grouped = _group_cues(all_words)
    srt_path = captions_dir / "subtitles.srt"
    _write_srt(grouped, srt_path)
    result["subtitles"] = str(srt_path)
    result["caption_count"] = len(grouped)
    result["subtitle_model"] = whisper_model_name
    result["subtitle_device"] = device
    return result
