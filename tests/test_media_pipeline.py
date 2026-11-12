import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

from app.main import detect_moments, probe, render_clip


@unittest.skipUnless(shutil.which("ffmpeg") and shutil.which("ffprobe"), "FFmpeg is required for media smoke tests")
class MediaPipelineTests(unittest.TestCase):
    def test_analyse_and_render_vertical_clip(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / "sample.mp4"
            output = root / "vertical.mp4"
            subprocess.run(
                [
                    "ffmpeg", "-hide_banner", "-loglevel", "error", "-y",
                    "-f", "lavfi", "-i", "testsrc2=size=320x180:rate=15",
                    "-f", "lavfi", "-i", "sine=frequency=800:sample_rate=8000",
                    "-t", "3", "-c:v", "libx264", "-pix_fmt", "yuv420p",
                    "-c:a", "aac", str(source),
                ],
                check=True, capture_output=True, text=True, timeout=90,
            )
            duration = probe(source)
            moments = detect_moments(source, duration)
            self.assertTrue(moments, "candidate detector should return at least one moment")
            start, length = moments[0]
            render_clip(source, output, start, length)
            self.assertTrue(output.is_file())
            metadata = subprocess.run(
                [
                    "ffprobe", "-v", "error", "-select_streams", "v:0",
                    "-show_entries", "stream=width,height", "-of", "csv=s=x:p=0", str(output),
                ],
                check=True, capture_output=True, text=True, timeout=30,
            ).stdout.strip()
            self.assertEqual(metadata, "1080x1920")


if __name__ == "__main__":
    unittest.main()
