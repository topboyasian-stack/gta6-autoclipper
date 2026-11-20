"""Stage 5: sync Flow clips and narration, mix/duck music, burn captions and export 1080p."""
from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path

from config import MUSIC_TRACK, OUTPUT_FPS, OUTPUT_SIZE


def _duration(path: Path) -> float:
    result = subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries", "format=duration",
         "-of", "default=noprint_wrappers=1:nokey=1", str(path)],
        check=True, capture_output=True, text=True,
    )
    try:
        return float(result.stdout.strip())
    except ValueError as exc:
        raise RuntimeError(f"Could not read duration for {path}") from exc


def _escape_filter_path(path: Path) -> str:
    # FFmpeg filter syntax requires escaping punctuation in absolute paths.
    value = str(path.resolve()).replace("\\", "/")
    value = value.replace(":", r"\:").replace("'", r"\'")
    return value


def assemble_episode(
    output_dir: Path,
    *,
    music_track: Path | None = None,
    output_file: Path | None = None,
    burn_subtitles: bool = True,
) -> dict:
    """Assemble every scene in episode.json order; fail rather than silently skip missing media."""
    if not shutil.which("ffmpeg") or not shutil.which("ffprobe"):
        raise RuntimeError("FFmpeg and ffprobe must be installed and available on PATH.")
    out = Path(output_dir)
    episode_path = out / "episode.json"
    if not episode_path.is_file():
        raise FileNotFoundError(f"Run stage 1 first: {episode_path} is missing.")
    episode = json.loads(episode_path.read_text(encoding="utf-8"))
    scenes = episode.get("scenes") or []
    if not scenes:
        raise ValueError("episode.json contains no scenes.")
    clips_dir = out / "flow_clips"
    audio_dir = out / "audio"
    missing = []
    media = []
    total_duration = 0.0
    for scene in scenes:
        number = int(scene["scene_number"])
        scene_id = f"scene_{number:03d}"
        video = clips_dir / f"{scene_id}.mp4"
        audio = audio_dir / f"{scene_id}.wav"
        if not video.is_file():
            missing.append(str(video))
        if not audio.is_file():
            missing.append(str(audio))
        if video.is_file() and audio.is_file():
            video_duration = _duration(video)
            audio_duration = _duration(audio)
            target_duration = audio_duration + 0.4
            if video_duration <= 0 or audio_duration <= 0:
                raise ValueError(f"{scene_id} has a zero-length video or audio file.")
            ratio = target_duration / video_duration
            media.append({
                "scene_id": scene_id,
                "video": video,
                "audio": audio,
                "video_duration": video_duration,
                "audio_duration": audio_duration,
                "target_duration": target_duration,
                "speed_ratio": ratio,
            })
            total_duration += target_duration
    if missing:
        preview = "\n".join(f"- {item}" for item in missing[:12])
        extra = f"\n...and {len(missing) - 12} more missing files" if len(missing) > 12 else ""
        raise FileNotFoundError(
            "Assembly stopped because required scene media is missing. Nothing was exported.\n"
            + preview + extra
        )
    if len(media) != len(scenes):
        raise RuntimeError("Not all episode scenes were validated; refusing to assemble a partial cut.")

    captions = out / "captions" / "subtitles.srt"
    use_captions = burn_subtitles and captions.is_file()
    chosen_music = Path(music_track) if music_track else MUSIC_TRACK
    use_music = chosen_music.is_file()
    final_path = Path(output_file) if output_file else out / "final_youtube_video.mp4"
    final_path.parent.mkdir(parents=True, exist_ok=True)

    cmd = ["ffmpeg", "-hide_banner", "-loglevel", "error", "-y"]
    filter_parts: list[str] = []
    for index, item in enumerate(media):
        cmd.extend(["-i", str(item["video"]), "-i", str(item["audio"])])
        ratio = float(item["speed_ratio"])
        target = float(item["target_duration"])
        video_duration = float(item["video_duration"])
        video_label = f"v{index}"
        audio_label = f"a{index}"
        width, height = OUTPUT_SIZE
        filters = []
        if 0.80 <= ratio <= 1.25:
            filters.append(f"setpts={ratio:.6f}*PTS")
        filters.extend([
            f"scale={width}:{height}:force_original_aspect_ratio=increase",
            f"crop={width}:{height}",
            f"fps={OUTPUT_FPS}",
        ])
        if ratio > 1.25 and target > video_duration:
            filters.append(f"tpad=stop_mode=clone:stop_duration={target - video_duration:.4f}")
        filters.extend([
            f"trim=duration={target:.4f}",
            "setpts=PTS-STARTPTS",
            "format=yuv420p",
        ])
        filter_parts.append(f"[{index * 2}:v]{','.join(filters)}[{video_label}]")
        filter_parts.append(
            f"[{index * 2 + 1}:a]apad=pad_dur=0.4,"
            f"atrim=duration={target:.4f},asetpts=PTS-STARTPTS[{audio_label}]"
        )

    concat_inputs = "".join(f"[v{i}][a{i}]" for i in range(len(media)))
    filter_parts.append(f"{concat_inputs}concat=n={len(media)}:v=1:a=1[basev][basea]")
    audio_label = "basea"
    video_label = "basev"
    next_input = len(media) * 2
    if use_music:
        cmd.extend(["-stream_loop", "-1", "-i", str(chosen_music)])
        fade_start = max(0.0, total_duration - 3.0)
        filter_parts.append(
            f"[{next_input}:a]volume=0.26,"
            f"afade=t=out:st={fade_start:.3f}:d={min(3.0, total_duration):.3f}[bg]"
        )
        filter_parts.append(
            "[bg][basea]sidechaincompress=threshold=0.025:ratio=7:attack=40:release=450[ducked]"
        )
        filter_parts.append(
            "[basea][ducked]amix=inputs=2:duration=first:dropout_transition=2[finala]"
        )
        audio_label = "finala"
    if use_captions:
        style = (
            "FontName=Arial,FontSize=22,PrimaryColour=&H00FFFFFF,"
            "OutlineColour=&H00101010,BackColour=&H60000000,"
            "BorderStyle=1,Outline=2,Shadow=1,MarginV=48"
        )
        filter_parts.append(
            f"[{video_label}]subtitles='{_escape_filter_path(captions)}':"
            f"force_style='{style}'[finalv]"
        )
        video_label = "finalv"

    filter_graph = ";".join(filter_parts)
    cmd.extend([
        "-filter_complex", filter_graph,
        "-map", f"[{video_label}]",
        "-map", f"[{audio_label}]",
        "-t", f"{total_duration:.3f}",
        "-c:v", "libx264",
        "-preset", "medium",
        "-crf", "18",
        "-pix_fmt", "yuv420p",
        "-r", str(OUTPUT_FPS),
        "-c:a", "aac",
        "-b:a", "256k",
        "-movflags", "+faststart",
        str(final_path),
    ])
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        raise RuntimeError(
            "FFmpeg assembly failed; no quality approval was recorded. "
            + (result.stderr[-4000:] if result.stderr else "No FFmpeg error output was returned.")
        )
    actual_duration = _duration(final_path)
    report = {
        "status": "rendered_needs_human_review",
        "episode_title": episode.get("title"),
        "scene_count": len(media),
        "output": str(final_path),
        "output_duration_seconds": round(actual_duration, 3),
        "resolution": f"{OUTPUT_SIZE[0]}x{OUTPUT_SIZE[1]}",
        "fps": OUTPUT_FPS,
        "music_mixed_and_ducked": use_music,
        "subtitles_burned": use_captions,
        "scenes": [
            {
                "scene_id": item["scene_id"],
                "source_video_duration": round(item["video_duration"], 3),
                "narration_duration": round(item["audio_duration"], 3),
                "target_duration": round(item["target_duration"], 3),
                "video_speed_ratio": round(item["speed_ratio"], 4),
                "note": (
                    "Moderate time adjustment"
                    if 0.80 <= item["speed_ratio"] <= 1.25
                    else "Trim/freeze padding used to avoid extreme speed changes; review this shot."
                ),
            }
            for item in media
        ],
        "human_review_required": True,
    }
    report_path = out / "assembly_quality_report.json"
    report_path.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    return report
