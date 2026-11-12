import ast
import json
import unittest
from pathlib import Path


class BrowserOnlyNotebookTests(unittest.TestCase):
    def test_notebook_json_is_valid_and_code_cells_parse(self):
        path = Path(__file__).resolve().parents[1] / "notebooks" / "GTA6_AutoClipper_Browser_Only.ipynb"
        notebook = json.loads(path.read_text(encoding="utf-8"))
        self.assertEqual(notebook["nbformat"], 4)
        code_cells = [cell for cell in notebook["cells"] if cell["cell_type"] == "code"]
        self.assertGreaterEqual(len(code_cells), 3)
        for index, cell in enumerate(code_cells):
            with self.subTest(code_cell=index):
                ast.parse("".join(cell["source"]))


if __name__ == "__main__":
    unittest.main()
