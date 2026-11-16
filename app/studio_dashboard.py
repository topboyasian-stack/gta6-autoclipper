from __future__ import annotations

import json
import re
import time
from pathlib import Path
from typing import Any


PROJECT_ID_RE = re.compile(r"^[A-Za-z0-9_-]{1,100}$")
VIDEO_EXTENSIONS = {".mp4", ".mov", ".mkv", ".webm", ".m4v"}


def _read_json(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
        return value if isinstance(value, dict) else {}
    except (OSError, json.JSONDecodeError):
        return {}


def _safe_project_dir(workspace: Path, project_id: str) -> Path:
    if not PROJECT_ID_RE.fullmatch(project_id):
        raise ValueError("Invalid project ID.")
    root = (Path(workspace) / "projects").resolve()
    project = (root / project_id).resolve()
    if project.parent != root or not project.is_dir():
        raise FileNotFoundError("Production project was not found.")
    return project


def _relative_media(project_dir: Path, candidate: Path | None) -> str | None:
    if candidate is None:
        return None
    try:
        resolved = candidate.resolve()
        resolved.relative_to(project_dir.resolve())
        if resolved.is_file():
            return resolved.relative_to(project_dir.resolve()).as_posix()
    except (OSError, ValueError):
        return None
    return None


def _latest_draft(project_dir: Path) -> Path | None:
    work = project_dir / "work"
    if not work.is_dir():
        return None
    candidates = [
        path for path in work.rglob("*.mp4")
        if path.is_file() and "normalized" not in str(path.parent).lower()
    ]
    if not candidates:
        return None
    # A named draft takes precedence over source/normalised intermediates.
    candidates.sort(
        key=lambda path: (
            1 if "draft" in path.stem.lower() or "narrated" in path.stem.lower() else 0,
            path.stat().st_mtime,
        ),
        reverse=True,
    )
    return candidates[0]


def _project_status(project_dir: Path, progress: dict[str, Any], draft: Path | None, exports: list[Path]) -> dict[str, str]:
    status = str(progress.get("status") or "").lower()
    stage = str(progress.get("stage") or "").lower()
    message = str(progress.get("message") or "")
    updated_at = str(progress.get("updated_at") or "")

    if status == "running":
        try:
            age = time.time() - float(progress.get("updated_epoch", 0))
        except (TypeError, ValueError):
            age = 0
        if age > 45 * 60:
            status = "stalled"
            message = "No recent progress update. Reopen the production notebook to check the last stage."
    elif any(path.suffix.lower() == ".zip" for path in exports):
        status = status or "exported"
        stage = stage or "export"
        message = message or "Export package is saved in this project."
    elif draft:
        status = status or "preview_ready"
        stage = stage or "preview"
        message = message or "A draft video is ready for review."
    elif (project_dir / "sources").is_dir() and any((project_dir / "sources").glob("*")):
        status = status or "sources_ready"
        stage = stage or "sources"
        message = message or "Source scenes are saved and ready for production."
    else:
        status = status or "created"
        stage = stage or "setup"
        message = message or "Project created. Add source videos to begin."

    return {
        "status": status,
        "stage": stage,
        "message": message[:300],
        "updated_at": updated_at,
    }


def build_project_summary(project_dir: Path) -> dict[str, Any]:
    project_dir = Path(project_dir).resolve()
    project_id = project_dir.name
    state = _read_json(project_dir / "project_state.json")
    brief = _read_json(project_dir / "episode_brief.json")
    progress = _read_json(project_dir / "studio_progress.json")

    source_dir = project_dir / "sources"
    sources = sorted(
        [
            {"name": item.name, "size_bytes": item.stat().st_size}
            for item in source_dir.iterdir()
            if item.is_file() and item.suffix.lower() in VIDEO_EXTENSIONS
        ],
        key=lambda item: item["name"].lower(),
    ) if source_dir.is_dir() else []

    exports_dir = project_dir / "exports"
    export_files = sorted(
        [
            path for path in exports_dir.iterdir()
            if path.is_file() and path.suffix.lower() in {".mp4", ".zip"}
        ],
        key=lambda path: path.stat().st_mtime,
        reverse=True,
    ) if exports_dir.is_dir() else []

    draft = _latest_draft(project_dir)
    latest_video = next((path for path in export_files if path.suffix.lower() == ".mp4"), None)
    latest_zip = next((path for path in export_files if path.suffix.lower() == ".zip"), None)
    script_path = project_dir / "original_script.md"
    narration_meta = _read_json(project_dir / "audio" / "narration.json")
    puffy_meta = _read_json(project_dir / "audio" / "puffy_storybook_voice.json")

    return {
        "id": project_id,
        "name": str(state.get("project_name") or project_id),
        "mode": str(state.get("mode") or "Production project"),
        "format": str(state.get("output_format") or ""),
        "created_at": str(state.get("created_at") or ""),
        "updated_at": str(progress.get("updated_at") or state.get("updated_at") or ""),
        "source_count": len(sources),
        "sources": sources[:12],
        "status": _project_status(project_dir, progress, draft, export_files),
        "story": {
            "title": str(brief.get("episode_title") or state.get("kids_story_title") or ""),
            "lesson": str(brief.get("story_lesson") or ""),
            "word_count": int(brief.get("actual_word_count") or 0),
            "script_available": script_path.is_file(),
        },
        "narration": {
            "available": (project_dir / "audio" / "narration.wav").is_file(),
            "base_voice": str(narration_meta.get("voice_id") or ""),
            "profile": str(puffy_meta.get("profile_name") or ("Engineering narrator" if narration_meta else "")),
            "duration_seconds": float(puffy_meta.get("styled_duration_seconds") or 0),
        },
        "media": {
            "draft": _relative_media(project_dir, draft),
            "final_video": _relative_media(project_dir, latest_video),
            "export_zip": _relative_media(project_dir, latest_zip),
        },
        "export_count": len(export_files),
        "exports": [
            {"name": path.name, "kind": "video" if path.suffix.lower() == ".mp4" else "package",
             "size_bytes": path.stat().st_size}
            for path in export_files[:6]
        ],
    }


def list_projects(workspace: Path) -> list[dict[str, Any]]:
    root = Path(workspace) / "projects"
    if not root.is_dir():
        return []
    projects = []
    for folder in root.iterdir():
        if folder.is_dir() and PROJECT_ID_RE.fullmatch(folder.name):
            try:
                projects.append(build_project_summary(folder))
            except OSError:
                continue
    projects.sort(key=lambda item: (item.get("updated_at") or item.get("created_at") or item["id"]), reverse=True)
    return projects[:100]


def get_project_file(workspace: Path, project_id: str, kind: str) -> Path:
    project_dir = _safe_project_dir(Path(workspace), project_id)
    summary = build_project_summary(project_dir)
    relative = summary["media"].get(kind)
    if not relative or kind not in {"draft", "final_video", "export_zip"}:
        raise FileNotFoundError("That project file is not available.")
    candidate = (project_dir / relative).resolve()
    candidate.relative_to(project_dir.resolve())
    if not candidate.is_file():
        raise FileNotFoundError("That project file is no longer available.")
    return candidate


def get_project_script(workspace: Path, project_id: str) -> Path:
    project_dir = _safe_project_dir(Path(workspace), project_id)
    script = (project_dir / "original_script.md").resolve()
    script.relative_to(project_dir.resolve())
    if not script.is_file():
        raise FileNotFoundError("This project does not have a saved script.")
    return script


def workspace_summary(workspace: Path) -> dict[str, Any]:
    workspace = Path(workspace)
    projects = list_projects(workspace)
    assets = workspace / "assets"
    voice_root = assets / "voice_models"
    music_root = assets / "music_library"
    voice_profiles = []
    if voice_root.is_dir():
        voice_profiles = sorted(
            [path.name for path in voice_root.iterdir() if path.is_dir()]
        )
    exports = sum(item["export_count"] for item in projects)
    running = sum(item["status"]["status"] == "running" for item in projects)
    return {
        "workspace_ready": workspace.is_dir(),
        "project_count": len(projects),
        "active_count": running,
        "export_count": exports,
        "source_count": sum(item["source_count"] for item in projects),
        "shared_assets": {
            "voice_profiles": voice_profiles,
            "music_library_ready": music_root.is_dir() and any(music_root.iterdir()),
            "puffy_voice_ready": (voice_root / "en_US-ljspeech-medium" / "en_US-ljspeech-medium.onnx").is_file(),
        },
    }
