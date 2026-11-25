"""Private local noVNC display helper for headed Playwright in Colab."""
from __future__ import annotations

import re
import shutil
import socket
import subprocess
import time
from pathlib import Path


class ColabFlowDisplay:
    def __init__(self, display: str = ":99", vnc_port: int = 5900, web_port: int = 6080):
        self.display = display
        self.vnc_port = int(vnc_port)
        self.web_port = int(web_port)
        self.processes: list[subprocess.Popen] = []
        self.log_dir = Path("/tmp/colab-flow-display-logs")
        self.log_handles = []

    @staticmethod
    def websockify_command(
        executable: str, web_root: Path, web_port: int, vnc_port: int
    ) -> list[str]:
        """Build websockify's CLI arguments (listen address is positional)."""
        return [
            executable,
            "--web",
            str(web_root),
            f"127.0.0.1:{int(web_port)}",
            f"127.0.0.1:{int(vnc_port)}",
        ]

    def _start(self, command: list[str], label: str) -> None:
        self.log_dir.mkdir(parents=True, exist_ok=True)
        log_name = re.sub(r"[^a-z0-9]+", "_", label.casefold()).strip("_") or "process"
        log_path = self.log_dir / f"{log_name}.log"
        log_handle = log_path.open("w", encoding="utf-8")
        self.log_handles.append(log_handle)
        process = subprocess.Popen(
            command,
            stdout=log_handle,
            stderr=subprocess.STDOUT,
            start_new_session=True,
        )
        self.processes.append(process)
        time.sleep(1)
        if process.poll() is not None:
            log_handle.flush()
            try:
                detail = log_path.read_text(encoding="utf-8", errors="replace").strip()
            except OSError as exc:
                detail = f"(could not read {log_path}: {exc})"
            tail = "\n".join(detail.splitlines()[-30:]) or "(process produced no diagnostic output)"
            raise RuntimeError(
                f"Could not start {label}; exit code {process.returncode}. "
                f"Command: {' '.join(command)}. Log: {log_path}\n{tail}"
            )

    @staticmethod
    def _wait_port(port: int, timeout: float = 15.0) -> None:
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            try:
                with socket.create_connection(("127.0.0.1", port), timeout=1):
                    return
            except OSError:
                time.sleep(0.25)
        raise RuntimeError(f"Display service did not become ready on local port {port}.")

    def start(self) -> dict[str, str | int]:
        missing = [
            name for name in ("Xvfb", "x11vnc", "websockify")
            if not shutil.which(name)
        ]
        if missing:
            raise RuntimeError("Missing Colab display utilities: " + ", ".join(missing))
        novnc = Path("/usr/share/novnc")
        if not (novnc / "vnc.html").is_file():
            raise RuntimeError("noVNC files were not found under /usr/share/novnc.")

        self._start(
            [
                "Xvfb", self.display, "-screen", "0", "1440x900x24",
                "-ac", "+extension", "GLX", "+render", "-noreset",
            ],
            "Xvfb",
        )
        self._start(
            [
                "x11vnc", "-display", self.display, "-forever", "-shared",
                "-nopw", "-localhost", "-rfbport", str(self.vnc_port),
                "-noxdamage",
            ],
            "local VNC",
        )
        self._wait_port(self.vnc_port)

        # websockify uses [source_addr:]source_port as a positional argument.
        # It does NOT accept a --listen option; that option belongs to novnc_proxy.
        command = self.websockify_command(
            "websockify", novnc, self.web_port, self.vnc_port
        )
        # Bind to loopback only. Colab's authenticated kernel-port proxy exposes
        # the viewer without opening this display bridge to the public network.
        self._start(command, "noVNC bridge")
        self._wait_port(self.web_port)
        return {"display": self.display, "web_port": self.web_port}

    def stop(self) -> None:
        for process in reversed(self.processes):
            if process.poll() is None:
                process.terminate()
                try:
                    process.wait(timeout=4)
                except subprocess.TimeoutExpired:
                    process.kill()
                    process.wait(timeout=2)
        self.processes.clear()
        for handle in self.log_handles:
            try:
                handle.close()
            except OSError:
                pass
        self.log_handles.clear()

    def __enter__(self):
        self.start()
        return self

    def __exit__(self, exc_type, exc, tb):
        self.stop()
