import json
from pathlib import Path

NOTEBOOK = Path("notebooks/GTA6_AutoClipper_Browser_Only.ipynb")

def main():
    notebook = json.loads(NOTEBOOK.read_text(encoding="utf-8"))
    assert notebook.get("nbformat") == 4, "Expected a Jupyter notebook v4 file."
    cells = notebook.get("cells", [])
    assert len(cells) >= 5, "The production notebook is missing expected workflow cells."

    code_count = 0
    for index, cell in enumerate(cells):
        if cell.get("cell_type") != "code":
            continue
        code_count += 1
        source = cell.get("source", "")
        if isinstance(source, list):
            source = "".join(source)
        compile(source, f"{NOTEBOOK}:cell-{index}", "exec")

    all_source = "\n".join(
        "".join(cell.get("source", [])) if isinstance(cell.get("source"), list) else cell.get("source", "")
        for cell in cells
    )
    required = [
        "Gaming highlights", "AI scene assembly", "Long-form video",
        "Multi-clip compilation", "Google Drive", "ffmpeg", "files.download",
    ]
    missing = [term for term in required if term not in all_source]
    assert not missing, f"Notebook is missing required workflow features: {missing}"
    assert code_count >= 4, "Expected setup, controls, source, processing and export code cells."
    print(f"PASS: {NOTEBOOK} is valid JSON and all {code_count} Python cells compile.")

if __name__ == "__main__":
    main()
