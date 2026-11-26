"""Email-restricted temporary access to the Colab noVNC desktop."""
from __future__ import annotations

import hashlib
import logging
import os
import platform
import re
import shutil
import subprocess
import tempfile
import threading
import time
from pathlib import Path
from urllib.request import urlopen

LOG = logging.getLogger("colab_flow_tunnel")
CLOUDFLARED_VERSION = "2026.11.2"
CLOUDFLARED_ASSETS = {
    "x86_64": {
        "url": "https://github.com/cloudflare/cloudflared/releases/download/2026.11.2/cloudflared-linux-amd64",
        "sha256": "56f13335143ec0e22772963290683a84a04114a35ec64cbc794a4d39ff9bb8cf",
    },
}
TUNNEL_URL_RE = re.compile(r"https://[a-z0-9-]+\\.trycloudflare\\.com", re.I)


def cloudflared_asset(machine: str | None = None) -> dict[str, str]:
    """Return the pinned Cloudflare binary and SHA-256 for the current CPU."""
    machine = (machine or platform.machine()).casefold()
    try:
        return dict(CLOUDFLARED_ASSETS[machine])
    except KeyError as exc:
        raise RuntimeError(
            f"Cloudflare browser tunnel does not support this Colab CPU architecture: {machine}"
        ) from exc


def ensure_cloudflared(binary_path: Path = Path("/content/cloudflared")) -> Path:
    """Install a pinned cloudflared binary after verifying its published SHA-256."""
    spec = cloudflared_asset()
    binary_path = Path(binary_path)
    binary_path.parent.mkdir(parents=True, exist_ok=True)

    def digest(path: Path) -> str:
        hasher = hashlib.sha256()
        with path.open("rb") as handle:
            for chunk in iter(lambda: handle.read(1024 * 1024), b""):
                hasher.update(chunk)
        return hasher.hexdigest()

    if binary_path.is_file() and digest(binary_path) == spec["sha256"]:
        binary_path.chmod(0o755)
        return binary_path

    fd, temporary_name = tempfile.mkstemp(
        prefix="cloudflared-", suffix=".download", dir=str(binary_path.parent)
    )
    os.close(fd)
    temporary = Path(temporary_name)
    try:
        with urlopen(spec["url"], timeout=120) as response, temporary.open("wb") as output:
            shutil.copyfileobj(response, output)
        actual = digest(temporary)
        if actual != spec["sha256"]:
            raise RuntimeError(
                "Downloaded cloudflared binary failed SHA-256 verification; "
                "the browser tunnel was not started."
            )
        temporary.chmod(0o755)
        temporary.replace(binary_path)
        LOG.info(
            "[VIEWER] Installed verified cloudflared %s (%s).",
            CLOUDFLARED_VERSION,
            spec["sha256"],
        )
        return binary_path
    finally:
        temporary.unlink(missing_ok=True)


def build_tunnel_command(
    binary: str | Path,
    origin_url: str,
    allowed_email: str,
) -> list[str]:
    """Build an email-restricted Quick Tunnel command for the noVNC HTTP endpoint."""
    email = str(allowed_email or "").strip().casefold()
    if not re.fullmatch(r"[^@\\s]+@[^@\\s]+\\.[^@\\s]+", email):
        raise ValueError("A valid email address is required to restrict browser tunnel access.")
    if not str(origin_url).startswith("http://127.0.0.1:"):
        raise ValueError("The browser tunnel origin must be a loopback HTTP URL.")
    return [
        str(binary),
        "tunnel",
        "--no-autoupdate",
        "--protocol",
        "http2",
        "--url",
        str(origin_url),
        "--allowed-mail",
        email,
        "--loglevel",
        "info",
    ]


def extract_tunnel_url(text: str) -> str | None:
    """Extract a Cloudflare Quick Tunnel hostname from cloudflared output."""
    match = TUNNEL_URL_RE.search(str(text or ""))
    return match.group(0).rstrip(".,)") if match else None


class ColabFlowTunnel:
    """Start and stop a temporary, email-gated Cloudflare Quick Tunnel."""

    def __init__(
        self,
        allowed_email: str,
        origin_url: str = "http://127.0.0.1:6080",
        log_path: Path = Path("/tmp/colab-flow-tunnel.log"),
        binary_path: Path = Path("/content/cloudflared"),
        startup_timeout: int = 90,
    ):
        self.allowed_email = str(allowed_email or "").strip().casefold()
        self.origin_url = str(origin_url)
        self.log_path = Path(log_path)
        self.binary_path = Path(binary_path)
        self.startup_timeout = int(startup_timeout)
        self.process: subprocess.Popen | None = None
        self.url: str | None = None
        self._reader: threading.Thread | None = None
        self._ready = threading.Event()
        self._lock = threading.Lock()
        self._tail: list[str] = []

    def _read_output(self) -> None:
        if self.process is None or self.process.stdout is None:
            return
        self.log_path.parent.mkdir(parents=True, exist_ok=True)
        try:
            with self.log_path.open("a", encoding="utf-8") as log:
                for raw in self.process.stdout:
                    line = raw.rstrip()
                    log.write(line + "\\n")
                    log.flush()
                    with self._lock:
                        self._tail.append(line)
                        self._tail = self._tail[-80:]
                        if self.url is None:
                            self.url = extract_tunnel_url(line)
                            if self.url:
                                self._ready.set()
        except Exception as exc:
            LOG.warning("[VIEWER] Could not capture cloudflared output: %s", exc)

    def start(self) -> str:
        if self.process is not None:
            raise RuntimeError("The browser tunnel has already been started.")
        self.binary_path = ensure_cloudflared(self.binary_path)
        command = build_tunnel_command(
            self.binary_path, self.origin_url, self.allowed_email
        )
        self.log_path.parent.mkdir(parents=True, exist_ok=True)
        self.log_path.write_text("", encoding="utf-8")
        LOG.info(
            "[VIEWER] Starting temporary browser tunnel restricted to %s.",
            self.allowed_email,
        )
        self.process = subprocess.Popen(
            command,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            bufsize=1,
            start_new_session=True,
        )
        self._reader = threading.Thread(
            target=self._read_output,
            name="colab-flow-tunnel-log",
            daemon=True,
        )
        self._reader.start()

        deadline = time.monotonic() + self.startup_timeout
        while time.monotonic() < deadline:
            if self._ready.wait(timeout=0.25):
                LOG.info("[VIEWER] Secure browser link ready: %s", self.url)
                return str(self.url)
            if self.process.poll() is not None:
                break

        with self._lock:
            tail = "\\n".join(self._tail[-25:])
        self.stop()
        raise RuntimeError(
            "Cloudflare could not create the authenticated browser link. "
            "No Google Flow generation was submitted. "
            f"cloudflared log ({self.log_path}):\\n{tail}"
        )

    def stop(self) -> None:
        process, self.process = self.process, None
        if process is not None and process.poll() is None:
            process.terminate()
            try:
                process.wait(timeout=8)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait(timeout=3)
        if self._reader is not None and self._reader.is_alive():
            self._reader.join(timeout=3)
        self._reader = None
        self.url = None
        self._ready.clear()
