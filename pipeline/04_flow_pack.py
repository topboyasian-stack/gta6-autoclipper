"""Stage 4: prepare an auditable manifest for the automated Google Flow browser worker."""
from __future__ import annotations

import json
from pathlib import Path

from config import DEFAULT_SCENE_SECONDS, MAX_SCENES_PER_FLOW_RUN
from pipeline.models import EpisodePackage


def _load_episode(output_dir: Path) -> EpisodePackage:
    episode_file = Path(output_dir) / "episode.json"
    if not episode_file.is_file():
        raise FileNotFoundError(f"Run stage 1 first: {episode_file} is missing.")
    return EpisodePackage.model_validate_json(episode_file.read_text(encoding="utf-8"))


def build_flow_pack(output_dir: Path, max_scenes_per_run: int | None = None) -> dict:
    """Write prompts, image paths, and ordered batches for the automated Flow worker."""
    out = Path(output_dir)
    frames_dir = out / "frames"
    clips_dir = out / "flow_clips"
    frames_dir.mkdir(parents=True, exist_ok=True)
    clips_dir.mkdir(parents=True, exist_ok=True)
    package = _load_episode(out)
    batch_cap = max_scenes_per_run or MAX_SCENES_PER_FLOW_RUN
    batch_cap = max(1, min(12, int(batch_cap)))
    manifest_scenes = []
    for scene in package.scenes:
        number = int(scene.scene_number)
        scene_id = f"scene_{number:03d}"
        frame_path = frames_dir / f"{scene_id}.png"
        clip_path = clips_dir / f"{scene_id}.mp4"
        manifest_scenes.append({
            "scene_number": number,
            "scene_id": scene_id,
            "duration_seconds": int(scene.duration_seconds or DEFAULT_SCENE_SECONDS),
            "starting_frame": str(frame_path),
            "starting_frame_exists": frame_path.is_file(),
            "motion_prompt": scene.motion_prompt,
            "camera_motion": scene.camera_motion,
            "narration_audio": str(out / "audio" / f"{scene_id}.wav"),
            "output_clip": str(clip_path),
            "clip_exists": clip_path.is_file(),
            "character_ids": scene.character_ids,
            "continuity_notes": scene.continuity_notes,
        })
    manifest = {
        "episode_title": package.title,
        "topic": package.topic,
        "visual_style": package.visual_style,
        "flow_usage_note": (
            "Generate only the scenes in the current batch. Confirm the current model and credit cost "
            "in Flow before every batch. Do not queue the full season or rerun completed scenes."
        ),
        "batch_limit": batch_cap,
        "scenes": manifest_scenes,
        "batches": [],
    }
    for start in range(0, len(manifest_scenes), batch_cap):
        subset = manifest_scenes[start:start + batch_cap]
        manifest["batches"].append({
            "batch_number": len(manifest["batches"]) + 1,
            "first_scene": subset[0]["scene_id"],
            "last_scene": subset[-1]["scene_id"],
            "scene_ids": [item["scene_id"] for item in subset],
            "scenes": subset,
        })
    manifest_path = out / "flow_upload_manifest.json"
    manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    master_path = out / "flow_master_prompt.md"
    master_path.write_text(
        "# Google Flow master instructions\n\n"
        + "**Episode:** " + package.title + "\n\n"
        + "**Overall premise:** " + package.logline + "\n\n"
        + "**Visual rules:** " + package.visual_style + "\n\n"
        + "Maintain the same character identity, face, hair, wardrobe, body proportions and signature props "
          "across all shots. Animate only the action described for each shot. Preserve framing and avoid "
          "unrequested scene changes. Do not generate narration, dialogue, captions, UI text, titles or logos; "
          "voiceover and subtitles are added by the local assembly stage.\n\n"
        + "## Scene prompts\n\n"
        + "\n\n".join(
            f"### {item['scene_id']} — {next(s.scene_title for s in package.scenes if s.scene_number == item['scene_number'])}\n"
            f"Starting frame: {item['starting_frame']}\n\n"
            f"Motion prompt: {item['motion_prompt']}\n\n"
            f"Camera: {item['camera_motion']}\n\n"
            f"Continuity: {item['continuity_notes']}"
            for item in manifest_scenes
        ) + "\n",
        encoding="utf-8",
    )
    text_path = out / "flow_upload_manifest.txt"
    text_lines = [
        f"EPISODE: {package.title}",
        f"BATCH CAP: {batch_cap} scenes per automated Flow run",
        "Review the chosen Flow model's credits before pressing Generate.",
        "Do not regenerate an existing output clip unless its shot is intentionally being replaced.",
        "",
    ]
    for batch in manifest["batches"]:
        text_lines.append(
            f"BATCH {batch['batch_number']:02d}: {batch['first_scene']} through {batch['last_scene']}"
        )
        for item in batch["scenes"]:
            text_lines.extend([
                f"  {item['scene_id']}",
                f"    Start frame: {item['starting_frame']} "
                f"({'READY' if item['starting_frame_exists'] else 'MISSING — generate or import this frame first'})",
                f"    Motion: {item['motion_prompt']}",
                f"    Save export as: {item['output_clip']}",
            ])
        text_lines.append("")
    text_path.write_text("\n".join(text_lines) + "\n", encoding="utf-8")
    return {
        "manifest": str(manifest_path),
        "master_prompt": str(master_path),
        "text_manifest": str(text_path),
        "scene_count": len(manifest_scenes),
        "batch_count": len(manifest["batches"]),
        "batch_limit": batch_cap,
        "missing_frames": sum(not item["starting_frame_exists"] for item in manifest_scenes),
        "missing_clips": sum(not item["clip_exists"] for item in manifest_scenes),
    }
