import csv
import json
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

from app.engineering_studio import (
    create_engineering_workspace,
    load_scene_manifest,
    natural_key,
    probe_media,
    render_engineering_episode,
    validate_episode_brief,
)


BRIEF = {
    "episode_title": "How a Parking Lot Can Store a Storm",
    "engineering_question": "How can a parking lot temporarily store rainwater beneath its surface?",
    "hook": "What if a parking lot could store a storm instead of sending all the water rushing away?",
    "original_script": (
        "Ordinary pavement sheds rain toward drains. Permeable pavement changes the surface, "
        "letting water pass through joints or openings into a stone reservoir below. The stone "
        "voids temporarily store the runoff while the soil absorbs it. Where the soil drains "
        "too slowly, a designed underdrain can carry excess water to an approved outlet. "
        "A planted swale can slow and filter runoff before it reaches the pavement. The system "
        "must be designed for the site, soil, traffic and local rainfall; it is not a guarantee "
        "against every flood. The result is a parking area that can manage more rain where it falls."
    ),
    "engineering_takeaway": (
        "Permeable pavement and an underground stone reservoir can store and infiltrate runoff; "
        "underdrains and planted swales may be added when site conditions require them."
    ),
    "source_references": ["https://www.epa.gov/green-infrastructure"],
}


@unittest.skipUnless(shutil.which("ffmpeg") and shutil.which("ffprobe"), "FFmpeg is required")
class EngineeringStudioTests(unittest.TestCase):
    def _make_video(self, path: Path, color: str, with_audio: bool):
        command = [
            "ffmpeg", "-hide_banner", "-loglevel", "error", "-y",
            "-f", "lavfi", "-i", f"color=c={color}:size=320x180:rate=15:duration=1.2",
        ]
        if with_audio:
            command += [
                "-f", "lavfi", "-i",
                "sine=frequency=550:sample_rate=48000:duration=1.2",
                "-shortest", "-map", "0:v:0", "-map", "1:a:0",
            ]
        else:
            command += ["-map", "0:v:0", "-an"]
        command += ["-c:v", "libx264", "-pix_fmt", "yuv420p"]
        if with_audio:
            command += ["-c:a", "aac"]
        command.append(str(path))
        subprocess.run(command, check=True, capture_output=True, text=True, timeout=60)

    def test_natural_sort_orders_numbered_scenes(self):
        names = ["scene_10.mp4", "scene_2.mp4", "scene_1.mp4"]
        ordered = sorted(names, key=natural_key)
        self.assertEqual(ordered, ["scene_1.mp4", "scene_2.mp4", "scene_10.mp4"])

    def test_manifest_requires_every_source_once_and_respects_order(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            sources = root / "sources"
            sources.mkdir()
            first, second = sources / "01.mp4", sources / "02.mp4"
            first.touch()
            second.touch()
            create_engineering_workspace(root, [first, second], BRIEF)
            manifest = root / "scene_manifest.csv"
            with manifest.open("w", newline="", encoding="utf-8") as handle:
                writer = csv.DictWriter(
                    handle,
                    fieldnames=[
                        "order", "scene_file", "scene_title", "visual_description",
                        "engineering_explanation", "source_urls", "review_status",
                    ],
                )
                writer.writeheader()
                writer.writerow({"order": 2, "scene_file": "01.mp4", "scene_title": "Second"})
                writer.writerow({"order": 1, "scene_file": "02.mp4", "scene_title": "First"})
            rows = load_scene_manifest(root, [first, second])
            self.assertEqual([row["scene_file"] for row in rows], ["02.mp4", "01.mp4"])
            self.assertEqual([row["scene_title"] for row in rows], ["First", "Second"])

    def test_brief_requires_original_script_and_credible_source_url(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "episode_brief.json"
            invalid = dict(BRIEF)
            invalid["original_script"] = "Too short."
            invalid["source_references"] = ["No source URL"]
            path.write_text(json.dumps(invalid), encoding="utf-8")
            with self.assertRaises(ValueError):
                validate_episode_brief(path)

    def test_render_produces_vertical_short_with_mixed_audio_and_scene_labels(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            sources = root / "sources"
            sources.mkdir()
            scene_a, scene_b = sources / "01_scene.mp4", sources / "02_scene.mp4"
            self._make_video(scene_a, "blue", with_audio=True)
            self._make_video(scene_b, "red", with_audio=False)
            folders = create_engineering_workspace(root, [scene_a, scene_b], BRIEF)

            narration = folders["audio"] / "narration.wav"
            subprocess.run(
                [
                    "ffmpeg", "-hide_banner", "-loglevel", "error", "-y",
                    "-f", "lavfi", "-i", "sine=frequency=880:sample_rate=48000:duration=2.4",
                    "-c:a", "pcm_s16le", str(narration),
                ],
                check=True, capture_output=True, text=True, timeout=60,
            )
            music = folders["audio"] / "music.wav"
            subprocess.run(
                [
                    "ffmpeg", "-hide_banner", "-loglevel", "error", "-y",
                    "-f", "lavfi", "-i", "sine=frequency=220:sample_rate=48000:duration=2.4",
                    "-c:a", "pcm_s16le", str(music),
                ],
                check=True, capture_output=True, text=True, timeout=60,
            )

            captions = folders["captions"] / "episode.srt"
            captions.write_text(
                "1\n00:00:00,000 --> 00:00:01,000\nRain moves through the pavers\n",
                encoding="utf-8",
            )

            output = render_engineering_episode(
                root, [scene_a, scene_b], output_format="shorts",
                keep_scene_audio=True, output_size=(180, 320),
            )
            self.assertTrue(output.exists())
            details = probe_media(output)
            self.assertEqual((details["width"], details["height"]), (180, 320))
            self.assertGreater(details["duration"], 2.0)
            self.assertLessEqual(details["duration"], 180)
            report = json.loads((folders["work"] / "render_report.json").read_text())
            self.assertTrue(report["narration_included"])
            self.assertTrue(report["music_included"])
            self.assertTrue(report["captions_burned_in"])
            self.assertEqual(len(report["scenes"]), 2)

    def test_landscape_export_is_rejected_for_engineering_shorts(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            with self.assertRaises(ValueError):
                render_engineering_episode(root, [], output_format="standard")


if __name__ == "__main__":
    unittest.main()
