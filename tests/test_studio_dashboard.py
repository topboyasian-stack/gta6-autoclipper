import json
import tempfile
import unittest
from pathlib import Path

from app.studio_dashboard import (
    build_project_summary,
    get_project_file,
    get_project_script,
    list_projects,
    workspace_summary,
)


class StudioDashboardTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.workspace = Path(self.temp.name)
        self.project = self.workspace / "projects" / "20261116_Puffy_Lesson"
        (self.project / "sources").mkdir(parents=True)
        (self.project / "work" / "render").mkdir(parents=True)
        (self.project / "exports").mkdir(parents=True)
        (self.project / "audio").mkdir(parents=True)
        (self.workspace / "assets" / "voice_models" / "en_US-ljspeech-medium").mkdir(parents=True)
        (self.workspace / "assets" / "music_library").mkdir(parents=True)

        (self.project / "project_state.json").write_text(json.dumps({
            "project_name": "Puffy's Little Lesson",
            "mode": "Kids story production",
            "output_format": "shorts",
            "created_at": "2026-11-16 08:00:00",
        }), encoding="utf-8")
        (self.project / "episode_brief.json").write_text(json.dumps({
            "episode_title": "Puffy's Little Lesson",
            "story_lesson": "Kindness makes a difference.",
            "actual_word_count": 81,
        }), encoding="utf-8")
        (self.project / "studio_progress.json").write_text(json.dumps({
            "status": "preview_ready",
            "stage": "preview",
            "message": "Draft ready for review.",
            "updated_at": "2026-11-16 08:20:00",
            "updated_epoch": 1794817200,
        }), encoding="utf-8")
        (self.project / "sources" / "01.mp4").write_bytes(b"video")
        (self.project / "work" / "render" / "puffy_draft.mp4").write_bytes(b"draft")
        (self.project / "original_script.md").write_text("# Puffy\nA kind story.", encoding="utf-8")
        (self.project / "audio" / "narration.wav").write_bytes(b"audio")
        (self.project / "audio" / "narration.json").write_text(json.dumps({
            "voice_id": "en_US-ljspeech-medium"
        }), encoding="utf-8")
        (self.project / "audio" / "puffy_storybook_voice.json").write_text(json.dumps({
            "profile_name": "Puffy Storybook",
            "styled_duration_seconds": 48.9,
        }), encoding="utf-8")
        (self.project / "exports" / "puffy_story.zip").write_bytes(b"zip")

        (self.workspace / "assets" / "voice_models" / "en_US-ljspeech-medium" /
         "en_US-ljspeech-medium.onnx").write_bytes(b"model")
        (self.workspace / "assets" / "music_library" / "track.json").write_text("{}", encoding="utf-8")

    def tearDown(self):
        self.temp.cleanup()

    def test_project_summary_uses_drive_project_assets(self):
        result = build_project_summary(self.project)
        self.assertEqual(result["id"], "20261116_Puffy_Lesson")
        self.assertEqual(result["mode"], "Kids story production")
        self.assertEqual(result["source_count"], 1)
        self.assertEqual(result["status"]["status"], "preview_ready")
        self.assertEqual(result["story"]["word_count"], 81)
        self.assertEqual(result["narration"]["profile"], "Puffy Storybook")
        self.assertEqual(result["media"]["draft"], "work/render/puffy_draft.mp4")
        self.assertEqual(result["media"]["export_zip"], "exports/puffy_story.zip")
        self.assertNotIn(str(self.workspace), json.dumps(result))

    def test_project_list_and_workspace_summary(self):
        projects = list_projects(self.workspace)
        self.assertEqual(len(projects), 1)
        summary = workspace_summary(self.workspace)
        self.assertEqual(summary["project_count"], 1)
        self.assertEqual(summary["source_count"], 1)
        self.assertEqual(summary["export_count"], 1)
        self.assertTrue(summary["shared_assets"]["puffy_voice_ready"])
        self.assertTrue(summary["shared_assets"]["music_library_ready"])

    def test_safe_media_and_script_access(self):
        self.assertEqual(
            get_project_file(self.workspace, self.project.name, "draft").name,
            "puffy_draft.mp4",
        )
        self.assertEqual(
            get_project_file(self.workspace, self.project.name, "export_zip").name,
            "puffy_story.zip",
        )
        self.assertEqual(
            get_project_script(self.workspace, self.project.name).name,
            "original_script.md",
        )
        with self.assertRaises(ValueError):
            get_project_file(self.workspace, "../outside", "draft")
        with self.assertRaises(FileNotFoundError):
            get_project_file(self.workspace, self.project.name, "not-allowed")


if __name__ == "__main__":
    unittest.main()
