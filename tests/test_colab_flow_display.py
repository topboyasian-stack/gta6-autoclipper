import tempfile
import unittest
from pathlib import Path

from scripts.colab_flow_display import ColabFlowDisplay
from scripts.colab_flow_tunnel import (
    build_tunnel_command,
    cloudflared_asset,
    extract_tunnel_url,
)


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


    def test_cloudflared_binary_is_pinned_with_sha256(self):
        asset = cloudflared_asset("x86_64")
        self.assertEqual(
            asset["url"],
            "https://github.com/cloudflare/cloudflared/releases/download/2026.11.2/cloudflared-linux-amd64",
        )
        self.assertEqual(
            asset["sha256"],
            "56f13335143ec0e22772963290683a84a04114a35ec64cbc794a4d39ff9bb8cf",
        )
        with self.assertRaises(RuntimeError):
            cloudflared_asset("unknown-cpu")

    def test_quick_tunnel_requires_the_expected_email_and_loopback_origin(self):
        command = build_tunnel_command(
            "/content/cloudflared",
            "http://127.0.0.1:6080",
            "Owner@Example.com",
        )
        self.assertEqual(command[0], "/content/cloudflared")
        self.assertIn("--allowed-mail", command)
        self.assertIn("owner@example.com", command)
        self.assertIn("--protocol", command)
        self.assertIn("http2", command)
        self.assertNotIn("--no-autoupdate", command[2:])

    def test_quick_tunnel_rejects_invalid_email_and_public_origins(self):
        with self.assertRaises(ValueError):
            build_tunnel_command("/content/cloudflared", "http://127.0.0.1:6080", "bad-email")
        with self.assertRaises(ValueError):
            build_tunnel_command("/content/cloudflared", "http://0.0.0.0:6080", "owner@example.com")

    def test_quick_tunnel_url_is_parsed_from_cloudflared_output(self):
        self.assertEqual(
            extract_tunnel_url("INF Tunnel created at https://silver-fox-24.trycloudflare.com"),
            "https://silver-fox-24.trycloudflare.com",
        )
        self.assertIsNone(extract_tunnel_url("no tunnel url here"))

    def test_notebook_exposes_browser_through_email_restricted_tunnel(self):
        import json
        from pathlib import Path

        root = Path(__file__).resolve().parents[1]
        notebook_path = root / "notebooks" / "Mystery_SciFi_One_Click.ipynb"
        notebook = json.loads(notebook_path.read_text(encoding="utf-8"))
        source = "\n".join(
            "".join(cell.get("source", []))
            for cell in notebook.get("cells", [])
            if cell.get("cell_type") == "code"
        )
        self.assertIn("ColabFlowTunnel", source)
        self.assertIn("allowed_email=FLOW_EXPECTED_GOOGLE_EMAIL", source)
        self.assertIn("flow_tunnel.start()", source)
        self.assertIn("flow_tunnel.stop()", source)
        self.assertIn("one-time PIN", source)
        self.assertNotIn("serve_kernel_port_as_iframe", source)
        self.assertNotIn("serve_kernel_port_as_window", source)
        self.assertLess(source.index("flow_tunnel.start()"), source.index('run_logged("Generate Flow starting frames'))



if __name__ == "__main__":
    unittest.main()
