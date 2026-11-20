import importlib.util
import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from pipeline.models import CharacterSheet, EpisodePackage, ScenePlan, ThumbnailPrompt

ROOT = Path(__file__).resolve().parents[1]


def load_numbered(filename: str, name: str):
    spec = importlib.util.spec_from_file_location(name, ROOT / "pipeline" / filename)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Could not import {filename}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def sample_episode(scene_count: int = 24) -> EpisodePackage:
    character = CharacterSheet(
        character_id="lead",
        name="Mara Vale",
        visual_description=(
            "A woman in her early thirties with a narrow scar above the left eyebrow, short dark curls, "
            "an olive field jacket, and a brass receiver clipped to her belt."
        ),
        continuity_anchors=["short dark curls", "olive field jacket", "brass receiver"],
        reference_image_prompt=(
            "A cinematic character turnaround for Mara Vale, with short dark curls, the scar above her "
            "left eyebrow, olive field jacket and brass receiver, on a neutral gray studio background."
        ),
    )
    scenes = []
    for number in range(1, scene_count + 1):
        scenes.append(ScenePlan(
            scene_number=number,
            duration_seconds=8,
            scene_title=f"Signal clue {number}",
            narration=(
                f"At scene {number}, Mara follows a strange signal through the abandoned coastal station "
                "and finds evidence that the next warning has already been recorded."
            ),
            start_frame_prompt=(
                "A wide 16:9 cinematic mystery image in an abandoned coastal radio station at night, "
                "rain on the windows, an old brass receiver, dramatic chiaroscuro and volumetric mist."
            ),
            motion_prompt=(
                "The receiver light pulses twice as rain streams down the window; Mara slowly turns toward "
                "the sound while the signal meter trembles, with restrained cinematic movement."
            ),
            camera_motion="Slow, motivated dolly-in with no abrupt camera change.",
            sound_effects=["low electrical hum", "distant rain"],
            character_ids=["lead"],
            continuity_notes="Keep Mara's face, curls, scar, olive jacket and brass receiver unchanged.",
        ))
    thumbnails = [
        ThumbnailPrompt(
            variant=variant,
            concept=f"Thumbnail concept {variant}: a different visual mystery hook",
            image_prompt=(
                "A high-contrast original mystery/sci-fi thumbnail focused on a glowing receiver in a dark "
                "coastal station with a human silhouette and large clean negative space."
            ),
            title_text=f"THE SIGNAL {variant}",
        )
        for variant in ("A", "B", "C")
    ]
    return EpisodePackage(
        title="The Signal Before Dawn",
        logline="A coastal technician hears a warning recorded before the event it describes.",
        topic="A mysterious warning arrives before the incident",
        target_audience="teen and adult general audience",
        synopsis=(
            "A radio technician investigates a warning that seems to arrive before its cause, "
            "uncovering a pattern that points toward an erased coastal emergency."
        ),
        visual_style=(
            "Premium cinematic 3D animation, restrained photorealism, chiaroscuro lighting, volumetric fog, "
            "anamorphic framing, moody teal and amber palette, and realistic material texture."
        ),
        narration_script=" ".join(scene.narration for scene in scenes),
        characters=[character],
        scenes=scenes,
        thumbnail_prompts=thumbnails,
        content_notes=[],
    )


class MysteryPipelineTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.output = Path(self.temp.name)
        self.package = sample_episode()
        (self.output / "episode.json").write_text(
            json.dumps(self.package.model_dump(mode="json"), ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

    def tearDown(self):
        self.temp.cleanup()

    def test_episode_schema_enforces_contiguous_scene_numbers_and_three_thumbnails(self):
        parsed = EpisodePackage.model_validate_json(
            (self.output / "episode.json").read_text(encoding="utf-8")
        )
        self.assertEqual(len(parsed.scenes), 24)
        self.assertEqual([scene.scene_number for scene in parsed.scenes], list(range(1, 25)))
        broken = self.package.model_dump(mode="json")
        broken["scenes"][1]["scene_number"] = 9
        with self.assertRaises(Exception):
            EpisodePackage.model_validate(broken)

    def test_planner_prompt_calls_for_continuity_and_requested_scene_count(self):
        planner = load_numbered("01_planner.py", "test_planner")
        prompt = planner._make_prompt("A station receives a warning from tomorrow", 12)
        self.assertIn("exactly 12 scenes", prompt)
        self.assertIn("Maintain continuity", prompt)
        self.assertIn("Return only data matching the supplied structured schema", prompt)

    def test_flow_manifest_splits_scenes_into_credit_bounded_batches(self):
        flow = load_numbered("04_flow_pack.py", "test_flow_pack")
        result = flow.build_flow_pack(self.output, max_scenes_per_run=10)
        manifest = json.loads(Path(result["manifest"]).read_text(encoding="utf-8"))
        self.assertEqual(result["scene_count"], 24)
        self.assertEqual(result["batch_count"], 3)
        self.assertEqual([len(batch["scenes"]) for batch in manifest["batches"]], [10, 10, 4])
        self.assertEqual(result["missing_frames"], 24)
        self.assertTrue(Path(result["master_prompt"]).is_file())
        self.assertTrue(Path(result["text_manifest"]).is_file())

    def test_image_stage_is_prompt_only_without_explicit_paid_opt_in(self):
        assets = load_numbered("02_assets.py", "test_assets")
        with patch.object(assets, "ALLOW_PAID_IMAGE_API", False):
            result = assets.generate_image_assets(self.output, allow_paid=False, max_images=10)
        plan = json.loads(Path(result["plan"]).read_text(encoding="utf-8"))
        self.assertEqual(result["status"], "prompt-only")
        self.assertEqual(result["generated"], 0)
        self.assertEqual(result["pending"], 24 + 1 + 3)
        self.assertEqual(len(plan), 28)
        markdown = Path(result["plan_markdown"]).read_text(encoding="utf-8")
        self.assertIn("## Starting Frame", markdown)
        self.assertIn("## Character Reference", markdown)
        self.assertFalse((self.output / "frames" / "scene_001.png").exists())

    def test_audio_stage_caption_helpers_produce_valid_srt_timestamps(self):
        audio = load_numbered("03_audio.py", "test_audio")
        self.assertEqual(audio._srt_time(61.239), "00:01:01,239")
        grouped = audio._group_cues([
            {"start": 0.0, "end": 0.2, "text": "The"},
            {"start": 0.21, "end": 0.5, "text": "signal"},
            {"start": 0.51, "end": 0.9, "text": "arrived."},
        ])
        self.assertEqual(len(grouped), 1)
        self.assertEqual(grouped[0]["text"], "The signal arrived.")
        target = self.output / "captions" / "sample.srt"
        audio._write_srt(grouped, target)
        self.assertIn("00:00:00,000 --> 00:00:00,900", target.read_text(encoding="utf-8"))

    def test_flow_pack_refuses_empty_or_missing_episode_package(self):
        empty = self.output / "empty"
        empty.mkdir()
        flow = load_numbered("04_flow_pack.py", "test_flow_pack_missing")
        with self.assertRaises(FileNotFoundError):
            flow.build_flow_pack(empty)

    def test_assembly_stops_when_any_clip_or_audio_is_missing(self):
        assembly = load_numbered("05_assemble.py", "test_assemble")
        with self.assertRaisesRegex(FileNotFoundError, "required scene media is missing"):
            assembly.assemble_episode(self.output)

    def test_colab_notebook_code_cells_compile_and_new_mode_is_wired(self):
        notebook_path = ROOT / "notebooks" / "GTA6_AutoClipper_Browser_Only.ipynb"
        notebook = json.loads(notebook_path.read_text(encoding="utf-8"))
        self.assertEqual(len(notebook["cells"]), 5)
        code_cells = [
            (index, "".join(cell.get("source", [])))
            for index, cell in enumerate(notebook["cells"])
            if cell.get("cell_type") == "code"
        ]
        for index, source in code_cells:
            compile(source, f"<notebook-cell-{index}>", "exec")
        first_code = dict(code_cells)[1]
        self.assertIn("Mystery & Sci-Fi Automation", first_code)
        self.assertIn("_prepare_mystery_clicked", first_code)
        self.assertIn("_mystery_images_clicked", first_code)
        self.assertIn("_assemble_mystery_clicked", first_code)
        for index in (2, 3, 4):
            self.assertTrue(dict(code_cells)[index].startswith(
                'if mode_widget.value != "Mystery & Sci-Fi Automation":'
            ))

    def test_cli_help_is_available_without_calling_external_services(self):
        result = subprocess.run(
            [sys.executable, str(ROOT / "main.py"), "--help"],
            capture_output=True,
            text=True,
            check=True,
        )
        self.assertIn("--allow-paid-images", result.stdout)
        self.assertIn("--stage", result.stdout)


if __name__ == "__main__":
    unittest.main()
