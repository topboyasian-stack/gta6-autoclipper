import tempfile
import unittest
from pathlib import Path

from scripts.colab_flow_display import ColabFlowDisplay


class ColabFlowDisplayTests(unittest.TestCase):
    def test_websockify_uses_positional_loopback_listener(self):
        command = ColabFlowDisplay.websockify_command(
            "websockify",
            Path("/usr/share/novnc"),
            web_port=6080,
            vnc_port=5900,
        )
        self.assertEqual(
            command,
            [
                "websockify",
                "--web",
                "/usr/share/novnc",
                "127.0.0.1:6080",
                "127.0.0.1:5900",
            ],
        )
        self.assertNotIn("--listen", command)

    def test_websockify_command_supports_non_default_test_ports(self):
        command = ColabFlowDisplay.websockify_command(
            "/usr/bin/websockify",
            Path("/tmp/novnc"),
            web_port=16080,
            vnc_port=15900,
        )
        self.assertEqual(command[-2:], ["127.0.0.1:16080", "127.0.0.1:15900"])


if __name__ == "__main__":
    unittest.main()
