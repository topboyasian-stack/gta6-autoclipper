import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
NOTEBOOK = ROOT / "notebooks" / "GTA6_AutoClipper_Browser_Only.ipynb"
PIPELINE = ROOT / "app" / "reusable_production.py"
README = ROOT / "README.md"
GUIDE = ROOT / "docs" / "COLAB_PRODUCTION_STUDIO.md"
LEGACY_ROOT_NOTEBOOK = ROOT / "GTA6_AutoClipper_GrowthReady.ipynb"
ARCHIVED_NOTEBOOK = ROOT / "archive" / "GTA6_AutoClipper_GrowthReady_DEPRECATED.ipynb"
COLAB_URL = (
    "https://colab.research.google.com/github/topboyasian-stack/"
    "gta6-autoclipper/blob/main/notebooks/GTA6_AutoClipper_Browser_Only.ipynb"
)


def source_text(cell):
    source = cell.get("source", "")
    return "".join(source) if isinstance(source, list) else source


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
        compile(source_text(cell), f"{NOTEBOOK}:cell-{index}", "exec")

    all_source = "\n".join(source_text(cell) for cell in cells)
    required = [
        "Gaming highlights",
        "AI scene assembly",
        "Long-form video",
        "Multi-clip compilation",
        "Animated engineering explainer",
        "prepare_reusable_episode_assets",
        "importlib.reload(reusable_production)",
        "GEMINI_API_KEY",
        "Narrator voice:",
        "episode_brief.json",
        "scene_manifest.csv",
        "narration.wav",
        "episode.srt",
        "music_license.json",
        "render_engineering_episode",
        "Google Drive",
        "ffmpeg",
        "files.download",
        "project_state.json",
        "Reuse this project's saved sources",
        "assets/voice_models",
        "assets/whisper_models",
        "assets/music_library",
        "Generate six Flow scene prompts",
        "Veo 3.1 Lite",
        "1,500 credits",
        "flow_prompt_packs",
        "180",
    ]
    missing = [term for term in required if term not in all_source]
    assert not missing, f"Notebook is missing required workflow features: {missing}"

    pipeline_source = PIPELINE.read_text(encoding="utf-8")
    pipeline_required = [
        "prepare_reusable_episode_assets",
        "research_episode_topic",
        "generate_episode_from_flow_scenes",
        "synthesize_episode_narration",
        "create_automatic_episode_captions",
        "AUTO_VERIFIED",
        "Faster-Whisper",
        "select_shared_music",
        "music_license.json",
        "voice_MODEL_CARD.txt",
        "generate_flow_prompt_pack",
        "validate_flow_prompt_pack",
        "render_flow_prompt_pack_markdown",
        "save_flow_prompt_pack",
        "_curated_technical_source_urls",
        "_extract_technical_pdf_text",
        "_extract_storyboard_frame",
        "application/pdf",
    ]
    missing_pipeline = [term for term in pipeline_required if term not in pipeline_source]
    assert not missing_pipeline, f"Reusable production engine is missing features: {missing_pipeline}"

    assert code_count >= 4, "Expected setup, controls, source, processing and export code cells."

    assert COLAB_URL in README.read_text(encoding="utf-8"), "README must link to the canonical main-branch notebook."
    assert COLAB_URL in GUIDE.read_text(encoding="utf-8"), "Colab guide must link to the canonical main-branch notebook."
    assert COLAB_URL in source_text(cells[0]), "The notebook opening cell must link to itself in Colab."

    assert not LEGACY_ROOT_NOTEBOOK.exists(), "The retired GrowthReady notebook must not remain as an active root-level entry point."
    archived = json.loads(ARCHIVED_NOTEBOOK.read_text(encoding="utf-8"))
    archive_intro = "\n".join(source_text(cell) for cell in archived.get("cells", [])[:2])
    assert "Do not use this notebook for new production" in archive_intro, "Archived notebook needs a deprecation warning."
    assert COLAB_URL in archive_intro, "Archived notebook must redirect users to the canonical notebook."

    print(
        f"PASS: canonical notebook is valid JSON; all {code_count} Python cells compile; "
        "single-entry-point links and archive guard pass."
    )


if __name__ == "__main__":
    main()
