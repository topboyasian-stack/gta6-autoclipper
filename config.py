"""Configuration for the modular mystery/sci-fi episode pipeline.

Environment variables are optional except GEMINI_API_KEY for AI planning.
Paid image API use is disabled unless explicitly enabled.
"""
from __future__ import annotations

import os
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent
try:
    from dotenv import load_dotenv
    load_dotenv(PROJECT_ROOT / ".env", override=False)
except ImportError:
    # Environment variables and Colab Secrets still work without python-dotenv.
    pass
DEFAULT_OUTPUT_DIR = Path(os.getenv("MYSTERY_OUTPUT_DIR", PROJECT_ROOT / "output"))

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "").strip()
PLANNER_MODEL = os.getenv("MYSTERY_PLANNER_MODEL", "gemini-3.8-flash")
FALLBACK_PLANNER_MODEL = os.getenv("MYSTERY_FALLBACK_MODEL", "gemini-3.5-flash-lite")
IMAGE_MODEL = os.getenv("MYSTERY_IMAGE_MODEL", "gemini-3.1-flash-image")

# The Google AI Pro subscription does not pay for Gemini Developer API usage.
# Keep this false unless the owner separately authorizes a billed image API key.
ALLOW_PAID_IMAGE_API = os.getenv("ALLOW_PAID_IMAGE_API", "false").strip().lower() in {
    "1", "true", "yes", "on"
}
MAX_SCENES_PER_FLOW_RUN = max(1, min(12, int(os.getenv("MAX_SCENES_PER_FLOW_RUN", "10"))))
MAX_IMAGES_PER_API_RUN = max(1, min(10, int(os.getenv("MAX_IMAGES_PER_API_RUN", "10"))))
DEFAULT_SCENE_COUNT = 24
DEFAULT_SCENE_SECONDS = 8
OUTPUT_SIZE = (1920, 1080)
OUTPUT_FPS = 24
NARRATOR_VOICE = os.getenv("MYSTERY_NARRATOR_VOICE", "en-US-ChristopherNeural")
WHISPER_MODEL = os.getenv("MYSTERY_WHISPER_MODEL", "base.en")
MUSIC_TRACK = Path(os.getenv("MYSTERY_MUSIC_TRACK", PROJECT_ROOT / "assets" / "music.mp3"))
