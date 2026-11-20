"""CLI orchestrator for the modular mystery/sci-fi video workflow.

Typical use:
  python main.py --topic "The signal that arrives one day too early"
  python main.py --stage assets --output output --allow-paid-images --max-images 10
  python main.py --stage assemble --output output

The first command plans the episode, prepares image prompts (but does not bill for image
generation by default), creates narration and word-timed captions, then writes Flow batches.
Video generation remains in Google Flow unless a separately tested local browser adapter is used.
"""
from __future__ import annotations

import argparse
import importlib.util
import json
import shutil
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


def _load_numbered_stage(filename: str, module_name: str):
    path = ROOT / "pipeline" / filename
    spec = importlib.util.spec_from_file_location(module_name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Cannot load pipeline stage: {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _print(payload: Any) -> None:
    print(json.dumps(payload, ensure_ascii=False, indent=2, default=str))


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Modular mystery/sci-fi episode production")
    parser.add_argument("--topic", help="One-line premise or episode topic")
    parser.add_argument("--output", type=Path, default=ROOT / "output", help="Episode working folder")
    parser.add_argument("--scene-count", type=int, default=24, help="Requested number of 4–10 second scenes")
    parser.add_argument(
        "--stage",
        choices=["prepare", "plan", "assets", "audio", "flow-pack", "assemble"],
        default=None,
        help="Run one stage or the full prepare workflow",
    )
    parser.add_argument(
        "--allow-paid-images", action="store_true",
        help="Explicitly authorize a bounded Gemini Developer API image-generation batch; may incur separate charges",
    )
    parser.add_argument("--max-images", type=int, default=10, help="Images generated in this one API run (hard cap 10)")
    parser.add_argument("--max-scenes-per-flow-run", type=int, default=10, help="Scenes listed per Flow batch (hard cap 12)")
    parser.add_argument("--voice", help="Edge TTS narrator voice ID")
    parser.add_argument("--whisper-model", default=None, help="Faster-Whisper model name (default: base.en)")
    parser.add_argument("--whisper-device", choices=["cpu", "cuda"], default="cpu")
    parser.add_argument("--music", type=Path, help="Optional licensed background music file")
    parser.add_argument("--no-subtitles", action="store_true", help="Create audio only; skip Whisper")
    parser.add_argument("--no-audio", action="store_true", help="Plan and prepare Flow manifests only")
    parser.add_argument("--force-plan", action="store_true", help="Back up and replace an existing episode.json")
    return parser


def _plan(topic: str, output_dir: Path, scene_count: int, force: bool) -> dict:
    from pipeline.models import EpisodePackage

    output_dir.mkdir(parents=True, exist_ok=True)
    episode_path = output_dir / "episode.json"
    if episode_path.is_file() and not force:
        saved = EpisodePackage.model_validate_json(episode_path.read_text(encoding="utf-8"))
        return {
            "status": "reused_existing_plan",
            "episode_json": str(episode_path),
            "title": saved.title,
            "scene_count": len(saved.scenes),
            "message": "Existing episode.json was preserved. Use --force-plan only when you intend to replace it.",
        }
    if episode_path.is_file() and force:
        from datetime import datetime, timezone
        backup = output_dir / f"episode.backup.{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')}.json"
        shutil.copy2(episode_path, backup)
    planner = _load_numbered_stage("01_planner.py", "mystery_planner_stage")
    return planner.generate_episode(topic, output_dir, scene_count=scene_count)


def _prepare(args) -> dict:
    output_dir = args.output.resolve()
    output_dir.mkdir(parents=True, exist_ok=True)
    results: dict[str, Any] = {}
    if args.topic:
        results["planning"] = _plan(args.topic, output_dir, args.scene_count, args.force_plan)
    elif not (output_dir / "episode.json").is_file():
        raise ValueError("Supply --topic for a new episode, or point --output to a folder with episode.json.")
    else:
        results["planning"] = {"status": "reusing_existing_plan", "episode_json": str(output_dir / "episode.json")}

    assets = _load_numbered_stage("02_assets.py", "mystery_assets_stage")
    results["assets"] = assets.generate_image_assets(
        output_dir, allow_paid=args.allow_paid_images, max_images=args.max_images
    )
    if not args.no_audio:
        audio = _load_numbered_stage("03_audio.py", "mystery_audio_stage")
        from config import WHISPER_MODEL
        results["audio"] = audio.generate_audio_and_subtitles(
            output_dir,
            voice=args.voice,
            whisper_model_name=args.whisper_model or WHISPER_MODEL,
            make_subtitles=not args.no_subtitles,
            whisper_device=args.whisper_device,
        )
    flow_pack = _load_numbered_stage("04_flow_pack.py", "mystery_flow_pack_stage")
    results["flow_pack"] = flow_pack.build_flow_pack(
        output_dir, max_scenes_per_run=args.max_scenes_per_flow_run
    )
    results["next_step"] = (
        "Review the episode and assets. Generate/import missing starting frames into frames/, "
        "then use the ordered Flow batch manifest. Export every clip as scene_NNN.mp4 into flow_clips/."
    )
    return results


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    stage = args.stage or ("assemble" if not args.topic else "prepare")
    if stage == "prepare":
        result = _prepare(args)
    elif stage == "plan":
        if not args.topic:
            raise ValueError("--topic is required for --stage plan.")
        result = _plan(args.topic, args.output.resolve(), args.scene_count, args.force_plan)
    elif stage == "assets":
        assets = _load_numbered_stage("02_assets.py", "mystery_assets_stage")
        result = assets.generate_image_assets(
            args.output.resolve(), allow_paid=args.allow_paid_images, max_images=args.max_images
        )
    elif stage == "audio":
        audio = _load_numbered_stage("03_audio.py", "mystery_audio_stage")
        from config import WHISPER_MODEL
        result = audio.generate_audio_and_subtitles(
            args.output.resolve(),
            voice=args.voice,
            whisper_model_name=args.whisper_model or WHISPER_MODEL,
            make_subtitles=not args.no_subtitles,
            whisper_device=args.whisper_device,
        )
    elif stage == "flow-pack":
        flow_pack = _load_numbered_stage("04_flow_pack.py", "mystery_flow_pack_stage")
        result = flow_pack.build_flow_pack(
            args.output.resolve(), max_scenes_per_run=args.max_scenes_per_flow_run
        )
    elif stage == "assemble":
        assembly = _load_numbered_stage("05_assemble.py", "mystery_assemble_stage")
        result = assembly.assemble_episode(
            args.output.resolve(),
            music_track=args.music,
        )
    else:
        raise ValueError(f"Unsupported stage: {stage}")
    _print(result)
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:
        print(f"ERROR: {type(exc).__name__}: {exc}", file=sys.stderr)
        raise SystemExit(1)
