"""Private local noVNC display helper for headed Playwright in Colab."""
from __future__ import annotations

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

    def _start(self, command: list[str], label: str) -> None:
        process = subprocess.Popen(
            command, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
            start_new_session=True,
        )
        self.processes.append(process)
        time.sleep(1)
        if process.poll() is not None:
            raise RuntimeError(f"Could not start {label}; exit code {process.returncode}.")

    @staticmethod
    def _wait_port(port: int, timeout: float = 15.0) -> None:
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            try:
                with socket.create_connection(("127.0.0.1", port), timeout=1):
                    return
            except OSError:
                time.sleep(0.25)
        raise RuntimeError(f"Display bridge did not start on local port {port}.")

    def start(self) -> dict[str, str | int]:
        missing = [name for name in ("Xvfb", "x11vnc", "websockify") if not shutil.which(name)]
        if missing:
            raise RuntimeError("Missing Colab display utilities: " + ", ".join(missing))
        novnc = Path("/usr/share/novnc")
        if not (novnc / "vnc.html").is_file():
            raise RuntimeError("noVNC files were not found under /usr/share/novnc.")
        self._start(
            ["Xvfb", self.display, "-screen", "0", "1440x900x24", "-ac", "+extension", "GLX", "+render", "-noreset"],
            "Xvfb",
        )
        self._start(
            ["x11vnc", "-display", self.display, "-forever", "-shared", "-nopw", "-localhost",
             "-rfbport", str(self.vnc_port), "-noxdamage"],
            "local VNC",
        )
        # Listen on loopback only. Colab's authenticated kernel-port proxy provides viewer access.
        self._start(
            ["websockify", "--listen", "127.0.0.1", "--web", str(novnc),
             str(self.web_port), f"127.0.0.1:{self.vnc_port}"],
            "noVNC bridge",
        )
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
        self.processes.clear()

    def __enter__(self):
        self.start()
        return self

    def __exit__(self, exc_type, exc, tb):
        self.stop()
