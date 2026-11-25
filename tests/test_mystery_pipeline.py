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
                "A vertical 9:16 cinematic mystery image in an abandoned coastal radio station at night, "
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
        self.assertIn("Return valid JSON only", prompt)

    def test_gemini_planner_uses_compact_prompt_shape_not_complex_api_schema(self):
        planner = load_numbered("01_planner.py", "test_planner_schema")
        prompt = planner._make_prompt("A station receives a warning from tomorrow", 6)
        source = (ROOT / "pipeline" / "01_planner.py").read_text(encoding="utf-8")

        self.assertIn('"thumbnail_prompts"', prompt)
        self.assertIn('"characters"', prompt)
        self.assertIn('"scenes"', prompt)
        self.assertIn('"continuity_notes"', prompt)
        self.assertIn("Return valid JSON only", prompt)
        self.assertNotIn("<<", prompt)
        shape_start = prompt.index("JSON OUTPUT SHAPE")
        json_start = prompt.index("{", shape_start)
        json_end = prompt.index("\nUse the exact property names", json_start)
        shape = json.loads(prompt[json_start:json_end])
        self.assertIn("title", shape)
        self.assertEqual(len(shape["thumbnail_prompts"]), 3)
        self.assertEqual(len(shape["scenes"]), 1)
        self.assertNotIn("response_json_schema", source)
        self.assertNotIn("_gemini_response_schema", source)
        # The local Pydantic model is still the authority for validating the generated package.
        self.assertIn("EpisodePackage.model_validate_json", source)


    def test_planner_configures_transient_retries_and_uses_extra_fallback_model(self):
        import types as pytypes

        planner = load_numbered("01_planner.py", "test_planner_retries")
        calls = []
        clients = []

        class FakeRetryOptions:
            def __init__(self, **kwargs):
                self.kwargs = kwargs

        class FakeHttpOptions:
            def __init__(self, **kwargs):
                self.kwargs = kwargs

        class FakeGenerateContentConfig:
            def __init__(self, **kwargs):
                self.kwargs = kwargs

        class FakeModels:
            def generate_content(self, model, contents, config):
                calls.append(model)
                if model != "third-fallback":
                    raise RuntimeError("simulated temporary model unavailability")
                return object()

        class FakeClient:
            def __init__(self, api_key, http_options):
                self.api_key = api_key
                self.http_options = http_options
                self.models = FakeModels()
                clients.append(self)

        fake_types = pytypes.ModuleType("google.genai.types")
        fake_types.HttpRetryOptions = FakeRetryOptions
        fake_types.HttpOptions = FakeHttpOptions
        fake_types.GenerateContentConfig = FakeGenerateContentConfig
        fake_genai = pytypes.ModuleType("google.genai")
        fake_genai.Client = FakeClient
        fake_genai.types = fake_types
        fake_google = pytypes.ModuleType("google")
        fake_google.genai = fake_genai

        with patch.dict("sys.modules", {
            "google": fake_google,
            "google.genai": fake_genai,
            "google.genai.types": fake_types,
        }):
            with (
                patch.object(planner, "PLANNER_MODEL", "primary-model"),
                patch.object(planner, "FALLBACK_PLANNER_MODEL", "first-fallback"),
                patch.object(planner, "ADDITIONAL_FALLBACK_PLANNER_MODELS", ("third-fallback",)),
                patch.object(planner, "_episode_from_response", return_value=sample_episode(6)),
            ):
                result = planner.generate_episode(
                    "An abandoned station receives a warning from tomorrow",
                    self.output / "planner-retry-test",
                    scene_count=6,
                    api_key="test-api-key-never-used",
                )

        self.assertEqual(calls, ["primary-model", "first-fallback", "third-fallback"])
        self.assertEqual(result["planner_model"], "third-fallback")
        self.assertTrue(Path(result["episode_json"]).is_file())
        retry_options = clients[0].http_options.kwargs["retry_options"].kwargs
        self.assertEqual(retry_options["attempts"], planner.PLANNER_RETRY_ATTEMPTS)
        self.assertEqual(
            retry_options["http_status_codes"],
            [408, 429, 500, 502, 503, 504],
        )
        self.assertGreaterEqual(retry_options["initial_delay"], 1.0)
        self.assertGreaterEqual(
            retry_options["max_delay"], retry_options["initial_delay"]
        )

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

    def test_asset_plan_assigns_expected_aspect_ratios(self):
        assets = load_numbered("02_assets.py", "test_asset_aspect_plan")
        plan = assets._prompt_plan(self.package, self.output)
        starts = [item for item in plan if item["kind"] == "starting_frame"]
        references = [item for item in plan if item["kind"] == "character_reference"]
        thumbnails = [item for item in plan if item["kind"] == "thumbnail"]
        self.assertEqual(len(starts), len(self.package.scenes))
        self.assertTrue(all(item["aspect_ratio"] == "9:16" for item in starts))
        self.assertTrue(all(item["aspect_ratio"] == "16:9" for item in references + thumbnails))

    def test_paid_image_request_sets_aspect_ratio_without_calling_real_api(self):
        import types as pytypes
        from PIL import Image

        assets = load_numbered("02_assets.py", "test_image_request_config")
        captured = []

        class FakeImageConfig:
            def __init__(self, **kwargs):
                self.kwargs = kwargs

        class FakeGenerationConfig:
            def __init__(self, **kwargs):
                self.kwargs = kwargs

        class FakeImagePart:
            def as_image(self):
                return Image.new("RGB", (128, 128), "purple")

        class FakeModels:
            def generate_content(self, model, contents, config):
                captured.append({"model": model, "config": config})
                return pytypes.SimpleNamespace(candidates=[
                    pytypes.SimpleNamespace(content=pytypes.SimpleNamespace(parts=[FakeImagePart()]))
                ])

        class FakeClient:
            def __init__(self, api_key):
                self.models = FakeModels()

        fake_types = pytypes.ModuleType("google.genai.types")
        fake_types.ImageConfig = FakeImageConfig
        fake_types.GenerateContentConfig = FakeGenerationConfig
        fake_genai = pytypes.ModuleType("google.genai")
        fake_genai.Client = FakeClient
        fake_genai.types = fake_types
        fake_google = pytypes.ModuleType("google")
        fake_google.genai = fake_genai

        with (
            patch.dict("sys.modules", {
                "google": fake_google,
                "google.genai": fake_genai,
                "google.genai.types": fake_types,
            }),
            patch.dict(os.environ, {"GEMINI_API_KEY": "test-api-key-never-used"}),
        ):
            result = assets.generate_image_assets(self.output, allow_paid=True, max_images=1)

        self.assertEqual(result["generated"], 1)
        config = captured[0]["config"].kwargs
        self.assertEqual(config["response_modalities"], ["TEXT", "IMAGE"])
        self.assertEqual(config["image_config"].kwargs, {"aspect_ratio": "9:16", "image_size": "1K"})
        from PIL import Image as PILImage
        with PILImage.open(self.output / "frames" / "scene_001.png") as image:
            self.assertEqual(image.size, assets.OUTPUT_SIZE)

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

    def test_assembly_success_exports_portrait_mp4_and_quality_report(self):
        assembly = load_numbered("05_assemble.py", "test_assemble_success")
        self.output.joinpath("flow_clips").mkdir(parents=True, exist_ok=True)
        self.output.joinpath("audio").mkdir(parents=True, exist_ok=True)
        (self.output / "episode.json").write_text(json.dumps({
            "title": "Assembly smoke test",
            "scenes": [{"scene_number": 1}, {"scene_number": 2}],
        }), encoding="utf-8")

        for number, color in ((1, "red"), (2, "blue")):
            scene_id = f"scene_{number:03d}"
            video = self.output / "flow_clips" / f"{scene_id}.mp4"
            audio = self.output / "audio" / f"{scene_id}.wav"
            subprocess.run([
                "ffmpeg", "-hide_banner", "-loglevel", "error", "-y",
                "-f", "lavfi", "-i", f"color=c={color}:s=360x640:r=24:d=1",
                "-an", "-c:v", "libx264", "-preset", "ultrafast", "-pix_fmt", "yuv420p",
                str(video),
            ], check=True, capture_output=True, text=True)
            subprocess.run([
                "ffmpeg", "-hide_banner", "-loglevel", "error", "-y",
                "-f", "lavfi", "-i", "sine=frequency=440:sample_rate=44100:duration=1",
                "-ac", "1", "-c:a", "pcm_s16le", str(audio),
            ], check=True, capture_output=True, text=True)

        output_file = self.output / "final_youtube_video.mp4"
        report = assembly.assemble_episode(self.output, output_file=output_file, burn_subtitles=False)
        self.assertTrue(output_file.is_file())
        self.assertGreater(output_file.stat().st_size, 1000)
        self.assertEqual(report["status"], "rendered_needs_human_review")
        self.assertEqual(report["resolution"], "1080x1920")
        self.assertEqual(report["fps"], 30)
        self.assertEqual(report["scene_count"], 2)
        self.assertTrue(report["human_review_required"])

        probe = subprocess.run([
            "ffprobe", "-v", "error", "-select_streams", "v:0",
            "-show_entries", "stream=width,height,r_frame_rate",
            "-of", "json", str(output_file),
        ], check=True, capture_output=True, text=True)
        stream = json.loads(probe.stdout)["streams"][0]
        self.assertEqual((stream["width"], stream["height"]), (1080, 1920))
        self.assertEqual(stream["r_frame_rate"], "30/1")

    def test_assembly_burns_subtitles_and_mixes_background_music(self):
        assembly = load_numbered("05_assemble.py", "test_assemble_audio_mix")
        self.output.joinpath("flow_clips").mkdir(parents=True, exist_ok=True)
        self.output.joinpath("audio").mkdir(parents=True, exist_ok=True)
        (self.output / "episode.json").write_text(json.dumps({
            "title": "Caption and music smoke test",
            "scenes": [{"scene_number": 1}],
        }), encoding="utf-8")

        scene_video = self.output / "flow_clips" / "scene_001.mp4"
        scene_audio = self.output / "audio" / "scene_001.wav"
        subprocess.run([
            "ffmpeg", "-hide_banner", "-loglevel", "error", "-y",
            "-f", "lavfi", "-i", "color=c=navy:s=360x640:r=24:d=2",
            "-an", "-c:v", "libx264", "-preset", "ultrafast", "-pix_fmt", "yuv420p",
            str(scene_video),
        ], check=True, capture_output=True, text=True)
        subprocess.run([
            "ffmpeg", "-hide_banner", "-loglevel", "error", "-y",
            "-f", "lavfi", "-i", "sine=frequency=440:sample_rate=44100:duration=2",
            "-ac", "1", "-c:a", "pcm_s16le", str(scene_audio),
        ], check=True, capture_output=True, text=True)

        captions = self.output / "captions" / "subtitles.srt"
        captions.parent.mkdir(parents=True, exist_ok=True)
        captions.write_text(
            "1\n00:00:00,100 --> 00:00:01,200\nThe signal is repeating.\n",
            encoding="utf-8",
        )
        music = self.output / "licensed_test_music.wav"
        subprocess.run([
            "ffmpeg", "-hide_banner", "-loglevel", "error", "-y",
            "-f", "lavfi", "-i", "sine=frequency=220:sample_rate=44100:duration=1",
            "-ac", "1", "-c:a", "pcm_s16le", str(music),
        ], check=True, capture_output=True, text=True)

        mixed_output = self.output / "captioned_music_test.mp4"
        report = assembly.assemble_episode(
            self.output, music_track=music, output_file=mixed_output, burn_subtitles=True
        )
        self.assertTrue(mixed_output.is_file())
        self.assertGreater(mixed_output.stat().st_size, 1000)
        self.assertTrue(report["subtitles_burned"])
        self.assertTrue(report["music_mixed_and_ducked"])
        streams = subprocess.run([
            "ffprobe", "-v", "error", "-show_entries", "stream=codec_type",
            "-of", "json", str(mixed_output),
        ], check=True, capture_output=True, text=True)
        stream_types = {item["codec_type"] for item in json.loads(streams.stdout)["streams"]}
        self.assertEqual(stream_types, {"video", "audio"})

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
