import json
import tempfile
import unittest
from pathlib import Path

from app.reusable_production import (
    _build_srt_from_words,
    _trusted_technical_url,
    create_automatic_episode_captions,
    register_music_track,
    select_shared_music,
)


class ReusableProductionTests(unittest.TestCase):
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
