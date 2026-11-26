"""Temporary bearer-path gateway for the Colab noVNC desktop.

The random path is a 256-bit capability URL. Only the path containing that
unpredictable token is reverse-proxied; every other URL returns 404. The
gateway is local to the Colab runtime and is stopped with the tunnel.
"""
from __future__ import annotations

import logging
import re
import secrets
import shutil
import socket
import subprocess
import time
from pathlib import Path
from urllib.parse import urlsplit, urlunsplit

LOG = logging.getLogger("colab_flow_gateway")
TOKEN_PATTERN = re.compile(r"^[A-Za-z0-9_-]{40,}$")

def build_viewer_url(tunnel_url: str, token_path: str) -> str:
    """Build a noVNC URL with an absolute, single-prefix WebSocket path.

    noVNC resolves a relative path against vnc.html. Since the viewer itself
    already lives below the secret path, passing token/websockify duplicates
    that path. An absolute /token/websockify keeps browser and nginx aligned.
    """
    parsed = urlsplit(str(tunnel_url or ""))
    if (
        parsed.scheme != "https"
        or not parsed.hostname
        or not parsed.hostname.endswith(".trycloudflare.com")
        or parsed.port is not None
        or parsed.username is not None
        or parsed.password is not None
        or parsed.path not in ("", "/")
        or parsed.query
        or parsed.fragment
    ):
        raise ValueError("The viewer requires a valid HTTPS Cloudflare Quick Tunnel URL.")
    if not isinstance(token_path, str) or not token_path.startswith("/"):
        raise ValueError("The viewer path must be the absolute secret gateway path.")
    token = token_path[1:]
    if "/" in token or not TOKEN_PATTERN.fullmatch(token):
        raise ValueError("The viewer path must contain exactly one valid secret token.")
    prefix = "/" + token
    fragment = (
        "autoconnect=1&resize=scale&reconnect=1&path="
        + prefix
        + "/websockify"
    )
    return urlunsplit((parsed.scheme, parsed.netloc, prefix + "/vnc.html", "", fragment))


def build_nginx_config(token: str, listen_port: int = 6081, upstream_port: int = 6080) -> str:
    """Build an nginx reverse proxy that only exposes noVNC behind a secret path."""
    if not TOKEN_PATTERN.fullmatch(str(token or "")):
        raise ValueError("A high-entropy URL-safe access token is required.")
    for port in (listen_port, upstream_port):
        if not isinstance(port, int) or not 1 <= port <= 65535:
            raise ValueError("Gateway ports must be valid TCP ports.")
    prefix = "/" + token + "/"
    return f"""pid nginx.pid;
error_log nginx-error.log warn;
events {{
    worker_connections 128;
}}
http {{
    include /etc/nginx/mime.types;
    default_type application/octet-stream;
    server {{
        listen 127.0.0.1:{listen_port};
        server_name _;
        access_log off;
        client_max_body_size 64m;
        location ^~ {prefix} {{
            rewrite ^/{token}/(.*)$ /$1 break;
            proxy_pass http://127.0.0.1:{upstream_port};
            proxy_http_version 1.1;
            proxy_set_header Upgrade $http_upgrade;
            proxy_set_header Connection "upgrade";
            proxy_set_header Host $host;
            proxy_set_header X-Forwarded-For $remote_addr;
            proxy_buffering off;
            proxy_read_timeout 3600s;
            proxy_send_timeout 3600s;
        }}
        location / {{
            return 404;
        }}
    }}
}}
"""


class ColabFlowGateway:
    """Start an nginx capability-path gateway in the current Colab runtime."""

    def __init__(
        self,
        upstream_port: int = 6080,
        listen_port: int = 6081,
        work_dir: Path = Path("/tmp/colab-flow-gateway"),
        startup_timeout: int = 15,
    ):
        self.upstream_port = int(upstream_port)
        self.listen_port = int(listen_port)
        self.work_dir = Path(work_dir)
        self.startup_timeout = int(startup_timeout)
        self.token: str | None = None
        self.process: subprocess.Popen | None = None
        self.config_path = self.work_dir / "nginx.conf"
        self.log_path = self.work_dir / "nginx-process.log"

    @property
    def path_prefix(self) -> str:
        if not self.token:
            raise RuntimeError("Browser gateway has not been started.")
        return "/" + self.token

    def start(self) -> dict[str, str | int]:
        if self.process is not None:
            raise RuntimeError("Browser gateway is already running.")
        nginx = shutil.which("nginx")
        if not nginx:
            raise RuntimeError("nginx is required for the protected browser gateway.")
        self.work_dir.mkdir(parents=True, exist_ok=True)
        self.token = secrets.token_urlsafe(32)
        self.config_path.write_text(
            build_nginx_config(self.token, self.listen_port, self.upstream_port),
            encoding="utf-8",
        )
        test = subprocess.run(
            [nginx, "-t", "-p", str(self.work_dir) + "/", "-c", str(self.config_path)],
            capture_output=True,
            text=True,
            timeout=15,
            check=False,
        )
        if test.returncode:
            self.token = None
            raise RuntimeError(
                "nginx rejected the temporary browser gateway configuration: "
                + (test.stderr or test.stdout)[-2000:]
            )
        with self.log_path.open("w", encoding="utf-8") as log:
            self.process = subprocess.Popen(
                [nginx, "-p", str(self.work_dir) + "/", "-c", str(self.config_path), "-g", "daemon off;"],
                stdout=log,
                stderr=subprocess.STDOUT,
                start_new_session=True,
            )
        deadline = time.monotonic() + self.startup_timeout
        while time.monotonic() < deadline:
            if self.process.poll() is not None:
                details = self.log_path.read_text(encoding="utf-8", errors="replace")
                self.stop()
                raise RuntimeError("nginx browser gateway exited during startup: " + details[-2000:])
            try:
                with socket.create_connection(("127.0.0.1", self.listen_port), timeout=0.5):
                    LOG.info(
                        "[VIEWER] Secret-path browser gateway is ready on loopback port %d.",
                        self.listen_port,
                    )
                    return {
                        "port": self.listen_port,
                        "path_prefix": self.path_prefix,
                    }
            except OSError:
                time.sleep(0.2)
        self.stop()
        raise RuntimeError("nginx browser gateway did not become ready on its loopback port.")

    def stop(self) -> None:
        process, self.process = self.process, None
        if process is not None and process.poll() is None:
            process.terminate()
            try:
                process.wait(timeout=8)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait(timeout=3)
        self.token = None
        shutil.rmtree(self.work_dir, ignore_errors=True)
