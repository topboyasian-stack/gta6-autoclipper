import json
import subprocess
import tempfile
import unittest
from io import BytesIO
from types import SimpleNamespace
from unittest.mock import patch
from pathlib import Path

from app.reusable_production import (
    _build_srt_from_words,
    _trusted_technical_url,
    _curated_technical_source_urls,
    _extract_technical_pdf_text,
    fetch_verified_technical_sources,
    _extract_storyboard_frame,
    _generate_content_with_fallback,
    generate_episode_from_flow_scenes,
    create_automatic_episode_captions,
    register_music_track,
    select_shared_music,
    validate_flow_prompt_pack,
    render_flow_prompt_pack_markdown,
    save_flow_prompt_pack,
)


class ReusableProductionTests(unittest.TestCase):

    def test_official_minnesota_state_stormwater_manual_is_trusted(self):
        self.assertTrue(_trusted_technical_url(
            "https://stormwater.pca.state.mn.us/types_of_permeable_pavement"
        ))
        self.assertFalse(_trusted_technical_url(
            "https://stormwater.pca.state.mn.us.attacker.example/types_of_permeable_pavement"
        ))

    def test_permeable_pavement_research_has_curated_official_fallbacks(self):
        urls = _curated_technical_source_urls(
            "How a Parking Lot Can Store a Storm",
            "How can permeable pavement store rainwater beneath a parking lot?",
        )
        self.assertGreaterEqual(len(urls), 6)
        self.assertTrue(any(url.endswith("bmp-permeable-pavements.pdf") for url in urls))
        self.assertTrue(all(_trusted_technical_url(url) for url in urls))

    def test_pdf_extraction_uses_pypdf_text_layer(self):
        from pypdf import PdfWriter
        writer = PdfWriter()
        writer.add_blank_page(width=300, height=300)
        buffer = BytesIO()
        writer.write(buffer)
        with patch("pypdf.PdfReader") as reader:
            reader.return_value.pages = [
                SimpleNamespace(extract_text=lambda: "Permeable pavement stores stormwater in a stone reservoir. " * 20)
            ]
            extracted = _extract_technical_pdf_text(buffer.getvalue())
        self.assertIn("stone reservoir", extracted)
        self.assertGreater(len(extracted), 500)

    def test_html_fetch_uses_browser_headers_and_keeps_two_trusted_sources(self):
        class FakeResponse:
            def __init__(self, url):
                self.url = url
                self.headers = {"Content-Type": "text/html; charset=utf-8"}
            def __enter__(self):
                return self
            def __exit__(self, *args):
                return False
            def geturl(self):
                return self.url
            def read(self, _limit):
                return (
                    "<html><head><title>Official Stormwater Guide</title></head><body>"
                    + ("Permeable pavement allows rainwater to pass through and enter an engineered stone reservoir. " * 12)
                    + "</body></html>"
                ).encode("utf-8")

        urls = [
            "https://www.epa.gov/green-infrastructure/types-green-infrastructure",
            "https://stormwater.pca.state.mn.us/types_of_permeable_pavement",
        ]
        with patch("urllib.request.urlopen", side_effect=[FakeResponse(url) for url in urls]) as mocked:
            found = fetch_verified_technical_sources(urls)
        self.assertEqual(len(found), 2)
        self.assertEqual(found[0]["content_type"], "text/html")
        self.assertGreaterEqual(len(found[1]["content_excerpt"]), 500)
        first_request = mocked.call_args_list[0].args[0]
        self.assertIn("Mozilla/5.0", first_request.get_header("User-agent"))



    def test_storyboard_frame_extraction_retries_accurate_then_fast_seek(self):
        from PIL import Image
        with tempfile.TemporaryDirectory() as directory:
            target = Path(directory) / "frame.jpg"
            calls = []

            def fake_run(command, capture_output, text, timeout):
                calls.append(command)
                if len(calls) == 1:
                    return subprocess.CompletedProcess(command, 234, "", "seek decode failed")
                Image.new("RGB", (240, 135), "blue").save(target, format="JPEG")
                return subprocess.CompletedProcess(command, 0, "", "")

            with patch("app.reusable_production.subprocess.run", side_effect=fake_run):
                frame, used_fallback = _extract_storyboard_frame(
                    Path("flow_scene.mp4"), 1.5, target
                )
            self.assertTrue(frame.is_file())
            self.assertFalse(used_fallback)
            self.assertEqual(len(calls), 2)
            self.assertIn("-ss", calls[1])

    def test_storyboard_frame_extraction_uses_first_frame_fallback_and_labels_it(self):
        from PIL import Image
        with tempfile.TemporaryDirectory() as directory:
            target = Path(directory) / "frame.jpg"
            calls = []

            def fake_run(command, capture_output, text, timeout):
                calls.append(command)
                if len(calls) < 3:
                    return subprocess.CompletedProcess(command, 234, "", "timestamp seek failed")
                Image.new("RGB", (240, 135), "green").save(target, format="JPEG")
                return subprocess.CompletedProcess(command, 0, "", "")

            with patch("app.reusable_production.subprocess.run", side_effect=fake_run):
                frame, used_fallback = _extract_storyboard_frame(
                    Path("flow_scene.mp4"), 3.0, target
                )
            self.assertTrue(frame.is_file())
            self.assertTrue(used_fallback)
            self.assertEqual(len(calls), 3)
            self.assertIn("+discardcorrupt", calls[2])

    def test_storyboard_frame_extraction_reports_the_exact_unreadable_clip(self):
        with tempfile.TemporaryDirectory() as directory:
            target = Path(directory) / "frame.jpg"
            def fail_run(command, capture_output, text, timeout):
                return subprocess.CompletedProcess(command, 234, "", "invalid data found")
            with patch("app.reusable_production.subprocess.run", side_effect=fail_run):
                with self.assertRaisesRegex(RuntimeError, "bad_flow_scene.mp4"):
                    _extract_storyboard_frame(
                        Path("bad_flow_scene.mp4"), 2.0, target
                    )



    def test_gemini_503_retries_then_uses_lighter_stable_model(self):
        from unittest.mock import Mock

        class FakeServerError(Exception):
            def __init__(self, code, message):
                self.code = code
                super().__init__(message)

        success = SimpleNamespace(text='{"ok": true}')
        generate = Mock(side_effect=[
            FakeServerError(503, "503 UNAVAILABLE: high demand"),
            FakeServerError(503, "503 UNAVAILABLE: high demand"),
            success,
        ])
        client = SimpleNamespace(models=SimpleNamespace(generate_content=generate))
        config = SimpleNamespace(response_mime_type="application/json")

        with patch("app.reusable_production.time.sleep") as sleep:
            response, actual_model = _generate_content_with_fallback(
                client=client,
                model="gemini-3.8-flash",
                contents=["episode prompt"],
                config=config,
            )

        self.assertIs(response, success)
        self.assertEqual(actual_model, "gemini-3.5-flash-lite")
        self.assertEqual(
            [call.kwargs["model"] for call in generate.call_args_list],
            ["gemini-3.8-flash", "gemini-3.8-flash", "gemini-3.5-flash-lite"],
        )
        self.assertEqual(sleep.call_count, 1)

    def test_gemini_non_retryable_error_is_not_hidden_or_retried(self):
        from unittest.mock import Mock

        failure = ValueError("400 INVALID_ARGUMENT: malformed request")
        generate = Mock(side_effect=failure)
        client = SimpleNamespace(models=SimpleNamespace(generate_content=generate))

        with self.assertRaisesRegex(ValueError, "INVALID_ARGUMENT"):
            _generate_content_with_fallback(
                client=client,
                model="gemini-3.8-flash",
                contents=["episode prompt"],
                config=SimpleNamespace(),
            )
        self.assertEqual(generate.call_count, 1)

    def test_text_only_storyboard_fallback_continues_when_contact_sheet_fails(self):
        from unittest.mock import Mock
        from types import ModuleType

        with tempfile.TemporaryDirectory() as directory:
            project = Path(directory) / "project"
            project.mkdir()
            scene_files = []
            for index in range(1, 7):
                scene = project / f"{index:02d}.mp4"
                scene.write_bytes(b"test clip placeholder")
                scene_files.append(scene)

            manifest = [
                {
                    "order": index,
                    "scene_file": f"{index:02d}.mp4",
                    "scene_title": f"Stage {index}",
                    "visual_description": (
                        "Visual content not machine-reviewed; retained in supplied order."
                    ),
                    "engineering_explanation": f"Explain stage {index} of the process.",
                }
                for index in range(1, 7)
            ]
            payload = {
                "episode_title": "How a Parking Lot Stores a Storm",
                "engineering_question": "How can a parking lot temporarily store rainwater?",
                "hook": "What if a parking lot could hold a storm?",
                "original_script": (
                    "Rain falls onto the parking lot and moves through a permeable surface. "
                    "Below it, layers of clean stone create temporary storage space. "
                    "Water fills the connected gaps between the stones, then slowly drains "
                    "into the soil or a designed outlet. This reduces immediate runoff, "
                    "but the exact performance depends on the site design and soil conditions."
                ),
                "engineering_takeaway": (
                    "A permeable parking lot can temporarily store stormwater in an underground "
                    "stone reservoir before it drains away."
                ),
                "scene_manifest": manifest,
            }
            # Deliberately return rows in reverse order to verify that the fallback
            # enforces the original clip order even if the model ignores the prompt.
            payload["scene_manifest"] = list(reversed(manifest))
            mock_models = SimpleNamespace(
                generate_content=Mock(return_value=SimpleNamespace(text=json.dumps(payload)))
            )
            mock_client = SimpleNamespace(models=mock_models)
            google_module = ModuleType("google")
            genai_module = ModuleType("google.genai")
            genai_types_module = ModuleType("google.genai.types")
            genai_module.Client = Mock(return_value=mock_client)
            genai_module.types = genai_types_module
            genai_types_module.GenerateContentConfig = lambda **kwargs: SimpleNamespace(**kwargs)
            google_module.genai = genai_module
            fake_google_modules = {
                "google": google_module,
                "google.genai": genai_module,
                "google.genai.types": genai_types_module,
            }

            with patch(
                "app.reusable_production._extract_scene_contact_sheet",
                side_effect=RuntimeError("FFmpeg pad filter failed"),
            ), patch.dict("sys.modules", fake_google_modules):
                result = generate_episode_from_flow_scenes(
                    project_dir=project,
                    scene_files=scene_files,
                    episode_title="How a Parking Lot Can Store a Storm",
                    engineering_question="How can a parking lot temporarily store rainwater beneath its surface?",
                    research_notes=(
                        "Permeable pavement allows rainwater to pass into a stone reservoir. "
                        "The stored water can infiltrate into suitable soil or move to an outlet. "
                        "Design depends on soil, groundwater and maintenance."
                    ),
                    source_references=["https://www.epa.gov/green-infrastructure"],
                    gemini_api_key="test-gemini-api-key",
                    target_seconds=47,
                )

            self.assertEqual(
                result["storyboard_visual_review"],
                "skipped_after_frame_extraction_error",
            )
            self.assertIn("text-only", result["script_generation_mode"])
            contents = mock_models.generate_content.call_args.kwargs["contents"]
            self.assertEqual(len(contents), 1)
            self.assertIn("VISUAL REVIEW UNAVAILABLE", contents[0])
            self.assertIn("Keep the exact supplied natural filename order", contents[0])
            manifest_text = (project / "scene_manifest.csv").read_text(encoding="utf-8")
            self.assertIn("auto_generated_needs_content_QC_no_visual_review", manifest_text)
            self.assertIn("Visual content not machine-reviewed; retained in supplied order.", manifest_text)
            self.assertLess(manifest_text.index("01.mp4"), manifest_text.index("02.mp4"))
            self.assertIn("FFmpeg pad filter failed", result["storyboard_visual_review_warning"])

    def _valid_flow_payload(self):
        return {
            "visual_continuity_bible": (
                "A consistent stylised 3D engineering scene, with the same recurring subject, "
                "material palette, camera geography, daylight and restrained motion in every shot."
            ),
            "scenes": [
                {
                    "order": i,
                    "scene_title": f"Scene {i}",
                    "purpose": "Explain one stage of the process clearly.",
                    "shot_description": (
                        f"Show a visually specific, physically plausible part of the system at stage {i}, "
                        "with a simple camera move and no on-screen labels."
                    ),
                }
                for i in range(1, 7)
            ],
        }

    def test_flow_prompt_pack_requires_exactly_six_ordered_scenes(self):
        payload = self._valid_flow_payload()
        pack = validate_flow_prompt_pack(
            payload, "Test engineering episode", "How does this engineering system work?"
        )
        self.assertEqual(pack["scene_count"], 6)
        self.assertEqual([scene["order"] for scene in pack["scenes"]], list(range(1, 7)))
        self.assertIn("No visible words", pack["scenes"][0]["prompt"])
        self.assertIn("Veo 3.1 Lite", pack["flow_model_recommendation"])

        payload["scenes"].pop()
        with self.assertRaisesRegex(ValueError, "exactly 6 scenes"):
            validate_flow_prompt_pack(
                payload, "Test engineering episode", "How does this engineering system work?"
            )

    def test_flow_prompt_pack_markdown_contains_credit_budget_and_copyable_prompts(self):
        pack = validate_flow_prompt_pack(
            self._valid_flow_payload(),
            "Test engineering episode",
            "How does this engineering system work?",
        )
        markdown = render_flow_prompt_pack_markdown(pack)
        self.assertIn("1,200 credits", markdown)
        self.assertIn("1,500 credits", markdown)
        self.assertIn("Veo 3.1 Lite", markdown)
        self.assertEqual(markdown.count("~~~text"), 6)

    def test_flow_prompt_pack_saves_json_and_markdown_under_persistent_workspace(self):
        with tempfile.TemporaryDirectory() as directory:
            pack = validate_flow_prompt_pack(
                self._valid_flow_payload(),
                "Test engineering episode",
                "How does this engineering system work?",
            )
            paths = save_flow_prompt_pack(pack, Path(directory))
            self.assertTrue(paths["json"].is_file())
            self.assertTrue(paths["markdown"].is_file())
            saved = json.loads(paths["json"].read_text(encoding="utf-8"))
            self.assertEqual(len(saved["scenes"]), 6)
            self.assertIn("Google Flow Scene Prompt Pack", paths["markdown"].read_text(encoding="utf-8"))


    def test_word_timestamps_become_sequential_srt_cues(self):
        words = [
            {"text": "Rain", "start": 0.00, "end": 0.32},
            {"text": "moves", "start": 0.34, "end": 0.62},
            {"text": "through", "start": 0.64, "end": 0.91},
            {"text": "the", "start": 0.92, "end": 1.02},
            {"text": "pavers.", "start": 1.03, "end": 1.45},
            {"text": "Stone", "start": 1.90, "end": 2.25},
            {"text": "stores", "start": 2.26, "end": 2.60},
            {"text": "water.", "start": 2.62, "end": 2.98},
        ]
        srt = _build_srt_from_words(words)
        self.assertIn("00:00:00,000 -->", srt)
        self.assertIn("Rain moves through the pavers.", srt)
        self.assertIn("Stone stores water.", srt)
        self.assertEqual(srt.count("-->"), 2)

    def test_research_sources_must_use_https_and_trusted_domains(self):
        self.assertTrue(_trusted_technical_url("https://www.epa.gov/green-infrastructure"))
        self.assertTrue(_trusted_technical_url("https://www.asce.org/"))
        self.assertFalse(_trusted_technical_url("http://www.epa.gov/"))
        self.assertFalse(_trusted_technical_url("https://random-blog.example.com/article"))

    def test_registering_a_commercial_track_creates_a_reusable_license_sidecar(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            incoming = root / "ambient.mp3"
            incoming.write_bytes(b"ID3" + b"x" * 20_000)
            library = root / "assets" / "music_library"

            sidecar = register_music_track(
                library_dir=library,
                audio_file=incoming,
                title="Original Ambient Bed",
                artist="Example Composer",
                license_name="Creative Commons Attribution 4.0",
                license_url="https://creativecommons.org/licenses/by/4.0/",
                source_url="https://example.org/track",
                attribution="Original Ambient Bed by Example Composer — CC BY 4.0",
                commercial_use=True,
            )
            self.assertTrue(sidecar.exists())
            metadata = json.loads(sidecar.read_text(encoding="utf-8"))
            self.assertTrue(metadata["commercial_use"])
            self.assertEqual(metadata["license"], "Creative Commons Attribution 4.0")

    def test_music_selector_reuses_user_registered_licensed_track(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            incoming = root / "ambient.mp3"
            incoming.write_bytes(b"ID3" + b"x" * 20_000)
            library = root / "assets" / "music_library"
            register_music_track(
                library_dir=library,
                audio_file=incoming,
                title="Original Ambient Bed",
                artist="Example Composer",
                license_name="CC BY 4.0",
                license_url="https://creativecommons.org/licenses/by/4.0/",
                source_url="https://example.org/track",
                attribution="Original Ambient Bed by Example Composer — CC BY 4.0",
                commercial_use=True,
            )

            project = root / "projects" / "episode_one"
            selected = select_shared_music(root, project)
            self.assertTrue(Path(selected["audio"]).exists())
            self.assertTrue(Path(selected["license"]).exists())
            self.assertEqual(selected["metadata"]["title"], "Original Ambient Bed")
            self.assertIn("Example Composer", selected["metadata"]["attribution"])


    def test_music_rotation_happens_between_projects_but_not_on_rerun(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            library = root / "assets" / "music_library"
            files = []
            for name, title in [("ambient.mp3", "Ambient"), ("uplifting.mp3", "Uplifting")]:
                incoming = root / name
                incoming.write_bytes(b"ID3" + name.encode("utf-8") * 2000)
                register_music_track(
                    library_dir=library,
                    audio_file=incoming,
                    title=title,
                    artist="Example Composer",
                    license_name="CC BY 4.0",
                    license_url="https://creativecommons.org/licenses/by/4.0/",
                    source_url=f"https://example.org/{name}",
                    attribution=f"{title} by Example Composer — CC BY 4.0",
                    commercial_use=True,
                )
                files.append(incoming)

            episode_one = root / "projects" / "episode_one"
            first = select_shared_music(root, episode_one)
            same_episode = select_shared_music(root, episode_one)
            self.assertEqual(Path(first["audio"]).name, Path(same_episode["audio"]).name)

            episode_two = root / "projects" / "episode_two"
            second = select_shared_music(root, episode_two)
            self.assertNotEqual(first["metadata"]["title"], second["metadata"]["title"])

    def test_json_fingerprint_is_stable_and_sensitive_to_episode_inputs(self):
        from app.reusable_production import _json_fingerprint
        first = _json_fingerprint({"topic": "permeable pavement", "version": 3})
        same = _json_fingerprint({"version": 3, "topic": "permeable pavement"})
        changed = _json_fingerprint({"topic": "permeable pavement", "version": 4})
        self.assertEqual(first, same)
        self.assertNotEqual(first, changed)

    def test_noncommercial_music_cannot_be_registered(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            incoming = root / "restricted.mp3"
            incoming.write_bytes(b"ID3" + b"x" * 20_000)
            with self.assertRaises(PermissionError):
                register_music_track(
                    library_dir=root / "library",
                    audio_file=incoming,
                    title="Restricted track",
                    artist="Example Artist",
                    license_name="CC BY-NC",
                    license_url="https://creativecommons.org/licenses/by-nc/4.0/",
                    source_url="https://example.org/track",
                    attribution="Credit the artist",
                    commercial_use=False,
                )


if __name__ == "__main__":
    unittest.main()
