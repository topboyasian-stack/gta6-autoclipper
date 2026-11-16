import ast
import json
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
COLAB_URL = (
    "https://colab.research.google.com/github/topboyasian-stack/"
    "gta6-autoclipper/blob/main/notebooks/GTA6_AutoClipper_Browser_Only.ipynb"
)


class BrowserOnlyNotebookTests(unittest.TestCase):
    def test_notebook_json_is_valid_and_code_cells_parse(self):
        path = ROOT / "notebooks" / "GTA6_AutoClipper_Browser_Only.ipynb"
        notebook = json.loads(path.read_text(encoding="utf-8"))
        self.assertEqual(notebook["nbformat"], 4)
        code_cells = [cell for cell in notebook["cells"] if cell["cell_type"] == "code"]
        self.assertGreaterEqual(len(code_cells), 3)
        full_source = "\n".join("".join(c["source"]) if isinstance(c["source"], list) else c["source"] for c in notebook["cells"])
        self.assertIn("Animated engineering explainer", full_source)
        self.assertIn("render_engineering_episode", full_source)
        self.assertIn("episode_brief.json", full_source)
        self.assertIn("scene_manifest.csv", full_source)
        self.assertIn("GEMINI_API_KEY", full_source)
        self.assertIn("prepare_reusable_episode_assets", full_source)
        self.assertIn("episode.srt", full_source)
        self.assertIn("music_library", full_source)
        self.assertIn("narration.wav", full_source)
        pipeline_source = (ROOT / "app" / "reusable_production.py").read_text(encoding="utf-8")
        self.assertIn("AUTO_VERIFIED", pipeline_source)
        self.assertIn("create_automatic_episode_captions", pipeline_source)
        self.assertIn("select_shared_music", pipeline_source)
        self.assertIn("PiperVoice", pipeline_source)
        self.assertIn("GEMINI_API_KEY", full_source)
        self.assertIn("prepare_reusable_episode_assets", full_source)
        self.assertIn("episode.srt", full_source)
        self.assertIn("music_library", full_source)
        for index, cell in enumerate(code_cells):
            source = cell["source"]
            if isinstance(source, list):
                source = "".join(source)
            with self.subTest(code_cell=index):
                ast.parse(source)


    def test_video_previews_use_supported_api_and_cannot_fail_production(self):
        path = ROOT / "notebooks" / "GTA6_AutoClipper_Browser_Only.ipynb"
        notebook = json.loads(path.read_text(encoding="utf-8"))
        source = "\\n".join(
            "".join(cell["source"]) if isinstance(cell["source"], list) else cell["source"]
            for cell in notebook["cells"]
        )
        self.assertNotIn("Video(filename=", source)
        self.assertIn("def show_video_preview(path, width):", source)
        self.assertIn("Video(str(preview_path), embed=True, width=width)", source)
        self.assertIn("show_video_preview(row[\"path\"], 320)", source)
        self.assertIn("show_video_preview(draft_video_path, 360)", source)
        self.assertIn("show_video_preview(draft_video_path, 480)", source)
        self.assertIn("except Exception as exc:", source)
        self.assertIn("The rendered video is still saved at:", source)

    def test_engineering_setup_pins_pyav_for_faster_whisper_compatibility(self):
        path = ROOT / "notebooks" / "GTA6_AutoClipper_Browser_Only.ipynb"
        notebook = json.loads(path.read_text(encoding="utf-8"))
        source = "\\n".join(
            "".join(cell["source"]) if isinstance(cell["source"], list) else cell["source"]
            for cell in notebook["cells"]
        )
        self.assertIn('"av==17.1.0"', source)
        self.assertIn('"faster-whisper>=1.1,<2"', source)
        self.assertLess(source.index('"av==17.1.0"'), source.index('"faster-whisper>=1.1,<2"'))
        self.assertIn('av_major >= 18', source)
        self.assertIn('Audio decoder ready: PyAV', source)

    def test_only_one_active_colab_entry_point_is_documented(self):
        self.assertFalse((ROOT / "GTA6_AutoClipper_GrowthReady.ipynb").exists())
        self.assertTrue((ROOT / "archive" / "GTA6_AutoClipper_GrowthReady_DEPRECATED.ipynb").exists())
        self.assertIn(COLAB_URL, (ROOT / "README.md").read_text(encoding="utf-8"))
        self.assertIn(COLAB_URL, (ROOT / "docs" / "COLAB_PRODUCTION_STUDIO.md").read_text(encoding="utf-8"))
        notebook = json.loads(
            (ROOT / "archive" / "GTA6_AutoClipper_GrowthReady_DEPRECATED.ipynb").read_text(encoding="utf-8")
        )
        first_cell = notebook["cells"][0]["source"]
        if isinstance(first_cell, list):
            first_cell = "".join(first_cell)
        self.assertIn("Do not use this notebook for new production", first_cell)
        self.assertIn(COLAB_URL, first_cell)


    def test_kids_story_has_scene_grounded_narration_and_shared_voice(self):
        path = ROOT / "notebooks" / "GTA6_AutoClipper_Browser_Only.ipynb"
        notebook = json.loads(path.read_text(encoding="utf-8"))
        source = "\\n".join(
            "".join(cell["source"]) if isinstance(cell["source"], list) else cell["source"]
            for cell in notebook["cells"]
        )
        self.assertIn("Kids story production", source)
        self.assertNotIn("Multi-clip compilation", source)
        self.assertIn("generate_kids_story_script", source)
        self.assertIn("synthesize_episode_narration", source)
        self.assertIn('KIDS_VOICE_ID = "en_US-ljspeech-medium"', source)
        self.assertIn("prepare_puffy_story_voice", source)
        self.assertIn("importlib.reload(_kids_story_module)", source)
        self.assertIn("Refreshing the Kids Story code from GitHub main", source)
        self.assertIn("Stage 1/4", source)
        self.assertIn("Stage 2/4", source)
        self.assertIn("Stage 3/4", source)
        self.assertIn("Stage 4/4", source)
        self.assertIn("timeout=300", source)
        self.assertIn("timeout=60", source)
        self.assertIn('"git", "-C", str(ROOT), "pull", "--ff-only", "origin", "main"', source)
        self.assertIn("Narrator profile: Puffy Storybook", source)
        self.assertNotIn("Voice: reuse the shared licensed narrator from the studio assets.", source)
        self.assertIn('"narrator_profile": "Puffy Storybook"', source)
        self.assertIn('"narration_included": bool(str(story_brief.get("original_script"', source)
        self.assertIn('"speech_captions_included": False', source)
        self.assertIn("source_audio_mixed_under_narration", source)
        self.assertIn("preserve_source_audio_enabled", source)
        self.assertIn("normalized_kids_direct_v1_", source)
        self.assertIn("Joining and cleaning scene boundaries", source)
        self.assertIn("kids_story", source)

    def test_kids_story_helper_is_separate_from_engineering_pipeline(self):
        path = ROOT / "app" / "kids_story_studio.py"
        source = path.read_text(encoding="utf-8")
        self.assertIn("def generate_kids_story_script(", source)
        self.assertIn("def prepare_puffy_story_voice(", source)
        self.assertIn("Puffy Storybook", source)
        self.assertIn("en_US-ljspeech-medium", source)
        self.assertIn("types.HttpOptions(timeout=90_000)", source)
        self.assertIn("contact_sheet", source)
        self.assertIn("story_lesson", source)
        self.assertIn("scene order", source)
        self.assertIn("synthesize_episode_narration", (
            (ROOT / "notebooks" / "GTA6_AutoClipper_Browser_Only.ipynb").read_text(encoding="utf-8")
        ))
        # Engineering continues to use its established helper and renderer.
        notebook = json.loads(
            (ROOT / "notebooks" / "GTA6_AutoClipper_Browser_Only.ipynb").read_text(encoding="utf-8")
        )
        combined = "\\n".join(
            "".join(cell["source"]) if isinstance(cell["source"], list) else cell["source"]
            for cell in notebook["cells"]
        )
        self.assertIn("prepare_reusable_episode_assets", combined)
        self.assertIn("render_engineering_episode(", combined)


    def test_all_modes_use_separate_auto_managed_drive_projects(self):
        path = ROOT / "notebooks" / "GTA6_AutoClipper_Browser_Only.ipynb"
        notebook = json.loads(path.read_text(encoding="utf-8"))
        setup = "".join(notebook["cells"][1]["source"])
        preparation = "".join(notebook["cells"][2]["source"])
        modes = (
            "Gaming highlights",
            "AI scene assembly",
            "Long-form video",
            "Kids story production",
            "Animated engineering explainer",
        )
        for mode in modes:
            with self.subTest(mode=mode):
                self.assertIn(f'"{mode}"', setup + preparation)

        self.assertIn("def _refresh_project_paths", setup)
        self.assertIn("project_widget.observe(_refresh_project_paths", setup)
        self.assertIn("mode_widget.observe(_on_mode_changed", setup)
        self.assertIn("INCOMING_DIR / _safe_project_folder(project_name)", setup)
        self.assertIn("PROJECT_DIR = PROJECTS_DIR / safe_project_name", preparation)
        self.assertIn('if SOURCE_MODE == "reuse" and not PROJECT_NAME:', preparation)
        self.assertIn("input_folder.mkdir(parents=True, exist_ok=True)", preparation)
        self.assertIn('old_state.get("mode") not in (None, MODE)', preparation)
        docs = (ROOT / "docs" / "COLAB_PRODUCTION_STUDIO.md").read_text(encoding="utf-8")
        self.assertIn("incoming/<Project ID>/", docs)
        self.assertIn("projects/<Project ID>/", docs)


    def test_existing_incomming_drive_folder_is_preserved_and_recovered(self):
        path = ROOT / "notebooks" / "GTA6_AutoClipper_Browser_Only.ipynb"
        notebook = json.loads(path.read_text(encoding="utf-8"))
        setup = "".join(notebook["cells"][1]["source"])
        preparation = "".join(notebook["cells"][2]["source"])
        self.assertIn('LEGACY_INCOMING_DIR = WORKSPACE / "incomming"', setup)
        self.assertIn('INCOMING_DIR = LEGACY_INCOMING_DIR if LEGACY_INCOMING_DIR.is_dir()', setup)
        self.assertIn('intake_roots = [WORKSPACE / "incomming", WORKSPACE / "incoming"]', preparation)
        self.assertIn('story_matches', preparation)
        self.assertIn('six_scene_candidates', preparation)
        self.assertIn('Recovered existing uploads from this Drive folder', preparation)
        self.assertIn('No supported video files were found in the selected project intake or either', preparation)
        docs = (ROOT / "docs" / "COLAB_PRODUCTION_STUDIO.md").read_text(encoding="utf-8")
        self.assertIn('historical folder spelling `incomming/`', docs)

if __name__ == "__main__":
    unittest.main()
