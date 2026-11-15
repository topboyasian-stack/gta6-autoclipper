"""Production helpers for original animated engineering explainers.

Google Flow creates the scene videos; this module assembles user-supplied exports.
It does not generate scenes, scrape video platforms, or publish to YouTube.
"""
from __future__ import annotations

import csv
import json
import re
import shutil
import subprocess
from pathlib import Path
from typing import Iterable

VIDEO_EXTENSIONS = {".mp4", ".mov", ".mkv", ".webm", ".m4v"}
AUDIO_EXTENSIONS = {".mp3", ".wav", ".m4a", ".aac", ".ogg", ".flac"}
MANIFEST_FIELDS = (
    "order",
    "scene_file",
    "scene_title",
    "visual_description",
    "engineering_explanation",
    "source_urls",
    "review_status",
)


def natural_key(path: Path | str) -> list[tuple[int, object]]:
    """Sort filenames naturally, so scene_2 precedes scene_10."""
    name = Path(path).name
    return [
        (0, int(part)) if part.isdigit() else (1, part.lower())
        for part in re.split(r"(\d+)", name)
    ]


def run_checked(command: list[str], label: str) -> subprocess.CompletedProcess[str]:
    result = subprocess.run(command, capture_output=True, text=True)
    if result.returncode:
        detail = (result.stderr or result.stdout or "")[-5000:]
        raise RuntimeError(f"{label} failed:\n{detail}")
    return result


def probe_media(path: Path) -> dict[str, object]:
    result = run_checked(
        [
            "ffprobe", "-v", "error", "-show_entries",
            "format=duration:stream=codec_type,width,height",
            "-of", "json", str(path),
        ],
        f"Inspecting {path.name}",
    )
    payload = json.loads(result.stdout)
    duration = float(payload.get("format", {}).get("duration") or 0)
    streams = payload.get("streams", [])
    video = next((s for s in streams if s.get("codec_type") == "video"), None)
    if duration <= 0 or video is None:
        raise ValueError(f"{path.name} is not a readable video with a positive duration.")
    return {
        "duration": duration,
        "has_audio": any(s.get("codec_type") == "audio" for s in streams),
        "width": int(video.get("width") or 0),
        "height": int(video.get("height") or 0),
    }


def _write_json(path: Path, payload: dict[str, object]) -> None:
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def create_engineering_workspace(
    project_dir: Path,
    scene_files: Iterable[Path],
    brief: dict[str, object],
) -> dict[str, Path]:
    """Create editable episode and scene templates without overwriting user edits."""
    project_dir = Path(project_dir)
    audio_dir = project_dir / "audio"
    captions_dir = project_dir / "captions"
    research_dir = project_dir / "research"
    work_dir = project_dir / "work" / "engineering"
    exports_dir = project_dir / "exports"
    for folder in (audio_dir, captions_dir, research_dir, work_dir, exports_dir):
        folder.mkdir(parents=True, exist_ok=True)

    ordered_scenes = sorted(
        [Path(item) for item in scene_files if Path(item).suffix.lower() in VIDEO_EXTENSIONS],
        key=natural_key,
    )
    if len(ordered_scenes) < 2:
        raise ValueError("An engineering explainer needs at least two Google Flow scene videos.")

    brief_path = project_dir / "episode_brief.json"
    if not brief_path.exists():
        payload = dict(brief)
        payload.setdefault("channel_name", "")
        payload["production_mode"] = "Animated engineering explainer"
        payload["output_format"] = "YouTube Shorts 9:16"
        payload["status"] = "draft"
        _write_json(brief_path, payload)

    manifest_path = project_dir / "scene_manifest.csv"
    if not manifest_path.exists():
        with manifest_path.open("w", newline="", encoding="utf-8") as handle:
            writer = csv.DictWriter(handle, fieldnames=MANIFEST_FIELDS)
            writer.writeheader()
            for index, scene in enumerate(ordered_scenes, 1):
                writer.writerow(
                    {
                        "order": index,
                        "scene_file": scene.name,
                        "scene_title": f"Scene {index:02d}",
                        "visual_description": "",
                        "engineering_explanation": "",
                        "source_urls": "",
                        "review_status": "needs_review",
                    }
                )

    script_path = project_dir / "original_script.md"
    if not script_path.exists():
        script_path.write_text(
            "# Original episode script\n\n"
            "Use this file to maintain the final approved narration. "
            "Keep it consistent with episode_brief.json.\n\n"
            + str(brief.get("original_script", "")).strip()
            + "\n",
            encoding="utf-8",
        )

    sources_path = research_dir / "source_notes.txt"
    if not sources_path.exists():
        refs = brief.get("source_references", [])
        sources_path.write_text(
            "Engineering research references. Verify that each source supports the claims used.\n\n"
            + "\n".join(str(item) for item in refs)
            + "\n",
            encoding="utf-8",
        )

    instructions_path = project_dir / "ENGINEERING_PRODUCTION_README.txt"
    if not instructions_path.exists():
        instructions_path.write_text(
            "ANIMATED ENGINEERING EPISODE FILES\n\n"
            "1. episode_brief.json: episode title, question, original script and takeaway.\n"
            "2. scene_manifest.csv: scene order and optional lower-third scene titles.\n"
            "3. audio/narration.mp3 (optional): your original recorded/licensed narration.\n"
            "4. audio/music.mp3 (optional): music you own or are licensed to use.\n"
            "5. captions/episode.srt (optional): reviewed subtitle file to burn into the video.\n\n"
            "The Google Flow scene videos remain in sources/. The final export is vertical 1080x1920.\n"
            "Do not place unrelated media files in sources/ or the scene assembly will include them.\n",
            encoding="utf-8",
        )

    return {
        "brief": brief_path,
        "manifest": manifest_path,
        "script": script_path,
        "sources": project_dir / "sources",
        "audio": audio_dir,
        "captions": captions_dir,
        "research": research_dir,
        "work": work_dir,
        "exports": exports_dir,
    }


def validate_episode_brief(brief_path: Path) -> dict[str, object]:
    payload = json.loads(Path(brief_path).read_text(encoding="utf-8"))
    required = {
        "episode_title": 5,
        "engineering_question": 12,
        "hook": 15,
        "original_script": 100,
        "engineering_takeaway": 30,
    }
    missing = [
        key for key, minimum in required.items()
        if len(str(payload.get(key, "")).strip()) < minimum
    ]
    if missing:
        raise ValueError(
            "Complete these episode brief fields before exporting: "
            + ", ".join(missing)
            + ". A genuinely original explanation is required; do not publish a blank template."
        )
    refs = payload.get("source_references", [])
    if isinstance(refs, str):
        refs = [line.strip() for line in refs.splitlines() if line.strip()]
    valid_refs = [item for item in refs if str(item).startswith(("https://", "http://"))]
    if not valid_refs:
        raise ValueError("Add at least one credible technical source URL to source_references.")
    payload["source_references"] = valid_refs
    return payload


def load_scene_manifest(project_dir: Path, scene_files: Iterable[Path]) -> list[dict[str, str]]:
    project_dir = Path(project_dir)
    supplied = {
        Path(path).name: Path(path)
        for path in scene_files
        if Path(path).suffix.lower() in VIDEO_EXTENSIONS
    }
    manifest_path = project_dir / "scene_manifest.csv"
    if not manifest_path.exists():
        raise FileNotFoundError(f"Scene manifest is missing: {manifest_path}")

    rows: list[dict[str, str]] = []
    with manifest_path.open("r", newline="", encoding="utf-8-sig") as handle:
        reader = csv.DictReader(handle)
        missing_headers = {"order", "scene_file"} - set(reader.fieldnames or [])
        if missing_headers:
            raise ValueError(f"Scene manifest is missing columns: {sorted(missing_headers)}")
        for row in reader:
            filename = (row.get("scene_file") or "").strip()
            if not filename:
                continue
            if filename not in supplied:
                raise ValueError(f"Manifest scene is not present in this project: {filename}")
            item = {key: (value or "").strip() for key, value in row.items() if key}
            item["scene_file"] = filename
            item["scene_title"] = item.get("scene_title") or f"Scene {len(rows) + 1:02d}"
            try:
                item["_order"] = str(int(item.get("order") or len(rows) + 1))
            except ValueError as exc:
                raise ValueError(f"Invalid scene order for {filename}: {item.get('order')}") from exc
            rows.append(item)

    names = [row["scene_file"] for row in rows]
    if len(names) != len(set(names)):
        raise ValueError("The scene manifest contains duplicate scene_file entries.")
    if set(names) != set(supplied):
        missing = sorted(set(supplied) - set(names), key=natural_key)
        extra = sorted(set(names) - set(supplied), key=natural_key)
        raise ValueError(f"Manifest must list every source scene exactly once. Missing: {missing}; extra: {extra}")
    rows.sort(key=lambda row: (int(row["_order"]), natural_key(row["scene_file"])))
    if len(rows) < 2:
        raise ValueError("At least two scenes are required for an engineering episode.")
    for row in rows:
        row["_path"] = str(supplied[row["scene_file"]])
    return rows


def _escape_filter_path(path: Path) -> str:
    return (
        Path(path).resolve().as_posix()
        .replace("\\", "\\\\")
        .replace(":", "\\:")
        .replace("'", "\\'")
    )


def _find_optional_audio(audio_dir: Path, stem: str) -> Path | None:
    matches = sorted(
        [p for p in audio_dir.glob(f"{stem}.*") if p.is_file() and p.suffix.lower() in AUDIO_EXTENSIONS],
        key=natural_key,
    )
    if len(matches) > 1:
        raise ValueError(f"Keep only one {stem} audio file in {audio_dir}; found {[p.name for p in matches]}.")
    return matches[0] if matches else None


def render_engineering_episode(
    project_dir: Path,
    scene_files: Iterable[Path],
    output_format: str = "shorts",
    keep_scene_audio: bool = True,
    output_size: tuple[int, int] = (1080, 1920),
) -> Path:
    """Normalize, label, concatenate and mix a reviewed engineering episode."""
    if output_format != "shorts":
        raise ValueError("Animated engineering explainer currently exports vertical YouTube Shorts only.")
    width, height = output_size
    if width <= 0 or height <= 0 or height <= width:
        raise ValueError("Shorts output must use a portrait width/height pair.")

    project_dir = Path(project_dir)
    scene_rows = load_scene_manifest(project_dir, scene_files)
    brief = validate_episode_brief(project_dir / "episode_brief.json")
    work_dir = project_dir / "work" / "engineering"
    work_dir.mkdir(parents=True, exist_ok=True)
    normalized_dir = work_dir / f"normalized_{width}x{height}_{'source_audio' if keep_scene_audio else 'muted'}"
    normalized_dir.mkdir(parents=True, exist_ok=True)

    normalized_files: list[Path] = []
    report_scenes: list[dict[str, object]] = []
    font_path = Path("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf")
    for index, row in enumerate(scene_rows, 1):
        source = Path(row["_path"])
        source_info = probe_media(source)
        stat = source.stat()
        normalized = normalized_dir / (
            f"{index:03d}_{source.stem}_{stat.st_size}_{stat.st_mtime_ns}_{width}x{height}.mp4"
        )
        title_path = work_dir / f"scene_{index:03d}_title.txt"
        title_path.write_text(row["scene_title"], encoding="utf-8")
        if not normalized.exists():
            vf = (
                f"[0:v]split=2[bg][fg];"
                f"[bg]scale={width}:{height}:force_original_aspect_ratio=increase,"
                f"crop={width}:{height},boxblur=24:10[background];"
                f"[fg]scale={width}:{height}:force_original_aspect_ratio=decrease[foreground];"
                f"[background][foreground]overlay=(W-w)/2:(H-h)/2,"
                "setsar=1,fps=30,format=yuv420p"
            )
            safe_title_path = _escape_filter_path(title_path)
            safe_font = _escape_filter_path(font_path)
            vf += (
                f",drawtext=fontfile='{safe_font}':textfile='{safe_title_path}':"
                "fontcolor=white:fontsize=40:borderw=3:bordercolor=black:"
                "box=1:boxcolor=black@0.48:boxborderw=18:"
                "x=(w-text_w)/2:y=h-230[v]"
            )
            command = ["ffmpeg", "-hide_banner", "-loglevel", "error", "-y", "-i", str(source)]
            if source_info["has_audio"] and keep_scene_audio:
                audio_filter = (
                    "[0:a:0]aresample=48000,"
                    "aformat=sample_fmts=fltp:channel_layouts=stereo,apad[a]"
                )
            else:
                command += [
                    "-f", "lavfi", "-i",
                    "anullsrc=channel_layout=stereo:sample_rate=48000",
                ]
                audio_filter = (
                    f"[1:a]atrim=duration={float(source_info['duration']):.3f},"
                    "asetpts=PTS-STARTPTS[a]"
                )
            command += [
                "-filter_complex", f"{vf};{audio_filter}",
                "-map", "[v]", "-map", "[a]",
                "-c:v", "libx264", "-preset", "veryfast", "-crf", "22",
                "-pix_fmt", "yuv420p", "-r", "30",
                "-c:a", "aac", "-ar", "48000", "-ac", "2", "-b:a", "160k",
                "-shortest", "-movflags", "+faststart", str(normalized),
            ]
            run_checked(command, f"Preparing engineering scene {source.name}")
        normalized_files.append(normalized)
        report_scenes.append(
            {
                "order": index,
                "file": source.name,
                "title": row["scene_title"],
                "duration_seconds": round(float(source_info["duration"]), 3),
                "visual_description": row.get("visual_description", ""),
                "engineering_explanation": row.get("engineering_explanation", ""),
                "source_urls": row.get("source_urls", ""),
            }
        )

    concat_list = work_dir / "engineering_concat.txt"
    concat_list.write_text(
        "".join(
            "file '" + str(path.resolve()).replace("\\", "/").replace("'", "'\\''") + "'\n"
            for path in normalized_files
        ),
        encoding="utf-8",
    )
    assembled = work_dir / "episode_picture_and_scene_audio.mp4"
    run_checked(
        [
            "ffmpeg", "-hide_banner", "-loglevel", "error", "-y",
            "-f", "concat", "-safe", "0", "-i", str(concat_list),
            "-c", "copy", "-movflags", "+faststart", str(assembled),
        ],
        "Joining engineering scenes",
    )

    audio_dir = project_dir / "audio"
    narration = _find_optional_audio(audio_dir, "narration")
    music = _find_optional_audio(audio_dir, "music")
    captions = project_dir / "captions" / "episode.srt"
    caption_qc_path = project_dir / "captions" / "caption_qc.json"
    music_license_path = project_dir / "audio" / "music_license.json"
    narration_meta_path = project_dir / "audio" / "narration.json"

    if narration is None or not narration.is_file():
        raise FileNotFoundError("Episode narration is missing. Run the automatic narration stage before rendering.")
    if music is None or not music.is_file():
        raise FileNotFoundError("Licensed background music is missing. Run the shared music-library stage before rendering.")
    if not captions.is_file() or captions.stat().st_size == 0:
        raise FileNotFoundError("Automatic SRT captions are missing. Run the caption generation stage before rendering.")
    if not caption_qc_path.is_file():
        raise FileNotFoundError("Caption quality report is missing. Automatic caption verification must run before rendering.")
    caption_qc = json.loads(caption_qc_path.read_text(encoding="utf-8"))
    if caption_qc.get("status") != "AUTO_VERIFIED":
        raise ValueError(
            "Caption quality checks did not pass. Inspect captions/episode.srt and "
            "captions/caption_qc_report.txt, then rerun caption generation before exporting."
        )
    if not music_license_path.is_file():
        raise FileNotFoundError("The selected background track has no saved license record.")
    music_license = json.loads(music_license_path.read_text(encoding="utf-8"))
    if not music_license.get("commercial_use") or not music_license.get("license_url") or not music_license.get("attribution"):
        raise PermissionError("The selected background track is missing commercial-use or attribution details.")
    narration_meta = json.loads(narration_meta_path.read_text(encoding="utf-8")) if narration_meta_path.exists() else {}

    final_draft = work_dir / f"{Path(project_dir).name}_engineering_short_{width}x{height}_draft.mp4"
    command = ["ffmpeg", "-hide_banner", "-loglevel", "error", "-y", "-i", str(assembled)]
    narration_index = None
    music_index = None
    next_index = 1
    if narration:
        narration_index = next_index
        command += ["-i", str(narration)]
        next_index += 1
    if music:
        music_index = next_index
        command += ["-stream_loop", "-1", "-i", str(music)]
        next_index += 1

    filters: list[str] = []
    mix_inputs: list[str] = []
    if narration or music:
        scene_gain = "0.14"
        filters.append(f"[0:a]volume={scene_gain}[scene]")
        mix_inputs.append("[scene]")
        if narration_index is not None:
            filters.append(f"[{narration_index}:a]aresample=48000,volume=1.0[narration]")
            mix_inputs.append("[narration]")
        if music_index is not None:
            target_duration = sum(float(item["duration_seconds"]) for item in report_scenes)
            fade_start = max(0.0, target_duration - 1.5)
            filters.append(
                f"[{music_index}:a]aresample=48000,volume=0.055,"
                f"atrim=duration={target_duration:.3f},"
                f"afade=t=out:st={fade_start:.3f}:d=1.5[music]"
            )
            mix_inputs.append("[music]")
        labels = "".join(mix_inputs)
        filters.append(
            f"{labels}amix=inputs={len(mix_inputs)}:duration=first:"
            "dropout_transition=2:normalize=0,alimiter=limit=0.95[aout]"
        )
        command += ["-filter_complex", ";".join(filters), "-map", "0:v:0", "-map", "[aout]"]
    else:
        command += ["-map", "0:v:0", "-map", "0:a:0"]

    if captions.exists():
        caption_path = _escape_filter_path(captions)
        subtitle_filter = (
            f"subtitles=filename='{caption_path}':"
            "force_style='FontName=DejaVu Sans,FontSize=30,Outline=2,Shadow=1,"
            "Alignment=2,MarginV=150'"
        )
        command += ["-vf", subtitle_filter, "-c:v", "libx264", "-preset", "veryfast", "-crf", "21"]
    else:
        command += ["-c:v", "copy"]
    if narration or music:
        command += ["-c:a", "aac", "-ar", "48000", "-ac", "2", "-b:a", "192k"]
    else:
        command += ["-c:a", "copy"]
    command += ["-t", f"{sum(float(item['duration_seconds']) for item in report_scenes):.3f}",
                "-movflags", "+faststart", str(final_draft)]
    run_checked(command, "Finalizing engineering episode audio and captions")

    output_info = probe_media(final_draft)
    if output_info["width"] != width or output_info["height"] != height:
        raise RuntimeError(
            f"Unexpected export dimensions: {output_info['width']}x{output_info['height']}; "
            f"expected {width}x{height}."
        )
    if output_info["duration"] > 180:
        raise ValueError(
            f"This Short is {output_info['duration'] / 60:.1f} minutes. "
            "Shorten the scene selection to no more than three minutes."
        )

    report = {
        "episode_title": brief["episode_title"],
        "production_mode": "Animated engineering explainer",
        "output_format": "YouTube Shorts 9:16",
        "resolution": f"{width}x{height}",
        "duration_seconds": round(float(output_info["duration"]), 3),
        "narration_included": True,
        "narration_voice_id": narration_meta.get("voice_id"),
        "narration_voice_license": narration_meta.get("voice_model_license"),
        "music_included": True,
        "music_title": music_license.get("title"),
        "music_artist": music_license.get("artist"),
        "music_license": music_license.get("license"),
        "music_attribution": music_license.get("attribution"),
        "captions_burned_in": True,
        "caption_status": caption_qc.get("status"),
        "caption_script_match_ratio": caption_qc.get("script_match_ratio"),
        "scenes": report_scenes,
        "technical_sources": brief["source_references"],
        "review_required": False,
    }
    _write_json(work_dir / "render_report.json", report)
    return final_draft


def write_engineering_export_notes(project_dir: Path, final_video: Path, manifest: dict[str, object]) -> Path:
    """Write an evidence-aware YouTube metadata sidecar for the reviewed export."""
    project_dir = Path(project_dir)
    brief = validate_episode_brief(project_dir / "episode_brief.json")
    music_license_path = project_dir / "audio" / "music_license.json"
    narration_meta_path = project_dir / "audio" / "narration.json"
    caption_qc_path = project_dir / "captions" / "caption_qc.json"
    music_license = json.loads(music_license_path.read_text(encoding="utf-8")) if music_license_path.exists() else {}
    narration_meta = json.loads(narration_meta_path.read_text(encoding="utf-8")) if narration_meta_path.exists() else {}
    caption_qc = json.loads(caption_qc_path.read_text(encoding="utf-8")) if caption_qc_path.exists() else {}
    music_credit = str(music_license.get("attribution", "")).strip()
    music_license_url = str(music_license.get("license_url", "")).strip()
    music_changes = str(music_license.get("changes_made", "Trimmed or looped to fit and mixed under narration.")).strip()
    notes = [
        f"Suggested title: {brief['episode_title']} #Shorts",
        "",
        "Suggested description:",
        str(brief["hook"]),
        "",
        str(brief["engineering_takeaway"]),
        "",
        "Music credit (required by the track licence):",
        music_credit,
        music_license_url,
        f"Changes made to the track: {music_changes}",
        "",
        "Technical references used during research:",
        *[f"- {url}" for url in brief["source_references"]],
        "",
        "Production and caption checks:",
        f"Voice engine: {narration_meta.get('tts_engine', 'Not recorded')}",
        f"Voice model: {narration_meta.get('voice_id', 'Not recorded')} ({narration_meta.get('voice_model_license', 'See project evidence')})",
        f"Piper engine licence: {narration_meta.get('tts_engine_license', 'See project evidence')}",
        "Voice model dataset licence and Piper engine software licence are separate; see the included MODEL_CARD and engine licence note.",
        f"Caption status: {caption_qc.get('status', 'Not recorded')}",
        f"Caption script match: {caption_qc.get('script_match_ratio', 'Not recorded')}",
        "Narration was generated from the saved episode script. Captions were generated from the rendered narration and checked against that script.",
        "The export is blocked automatically when caption verification does not pass.",
        "",
        "Production notes:",
        "Original animated engineering explainer assembled from supplied Google Flow scene exports.",
        "Verify engineering claims against the listed references and confirm Flow output rights before publishing.",
        "AI-generated visuals may require altered-content disclosure when they realistically depict events or places that never existed.",
        "This production workflow does not guarantee YouTube Partner Program acceptance or monetisation.",
        "",
        f"Export file: {Path(final_video).name}",
        f"Resolution: {manifest.get('resolution', '1080x1920')}",
        f"Duration seconds: {manifest.get('duration_seconds', 'unknown')}",
    ]
    output = project_dir / "exports" / "youtube_metadata_engineering.txt"
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text("\n".join(notes) + "\n", encoding="utf-8")
    return output
