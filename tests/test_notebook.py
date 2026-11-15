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
        for index, cell in enumerate(code_cells):
            source = cell["source"]
            if isinstance(source, list):
                source = "".join(source)
            with self.subTest(code_cell=index):
                ast.parse(source)

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


if __name__ == "__main__":
    unittest.main()
