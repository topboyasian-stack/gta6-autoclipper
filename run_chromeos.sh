#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")"

if ! command -v python3 >/dev/null 2>&1; then
  echo "Python 3 is required. Install it in your ChromeOS Linux environment, then run this again."
  exit 1
fi

if ! command -v ffmpeg >/dev/null 2>&1 || ! command -v ffprobe >/dev/null 2>&1 || ! dpkg -s python3-venv >/dev/null 2>&1; then
  echo "Installing the free Linux dependencies (you may be asked for your Linux password)…"
  sudo apt-get update
  sudo apt-get install -y python3 python3-venv python3-pip ffmpeg
fi

if [[ ! -x .venv/bin/python ]]; then
  python3 -m venv .venv
fi

source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -r requirements.txt

echo
echo "GTA 6 AutoClipper is running locally."
echo "Open http://localhost:8000 in Chrome."
echo "Keep this terminal open during live capture. Press Ctrl+C to stop."
exec python -m uvicorn app.main:app --host 127.0.0.1 --port 8000
