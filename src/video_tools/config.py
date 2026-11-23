"""Standalone workspace configuration. Client packages may supply their own."""

import os
from dataclasses import dataclass
from pathlib import Path
from types import SimpleNamespace

VIDEO_DIR = Path.cwd()
EPISODES_DIR = VIDEO_DIR / "episodes"
SLIDES_DIR = VIDEO_DIR / "slides"
OUTPUT_DIR = VIDEO_DIR / "output"
WIDTH, HEIGHT, FPS = 1920, 1080, 30
SCENE_KINDS = ("screen", "slide", "image")


@dataclass
class DemoUrls:
    base: str
    http_credentials = None
    api_key = ""


def demo_urls():
    return DemoUrls(os.environ.get("DEMO_BASE_URL", ""))


def voice_config():
    key = os.environ.get("ELEVENLABS_API_KEY")
    voice = os.environ.get("ELEVENLABS_VOICE_ID")
    if not key or not voice:
        raise ValueError("Set ELEVENLABS_API_KEY and ELEVENLABS_VOICE_ID for narration")
    return SimpleNamespace(
        api_key=key,
        voice_id=voice,
        model_id=os.environ.get("ELEVENLABS_MODEL_ID", "eleven_multilingual_v2"),
    )


def load():
    """The standalone CLI uses the caller's environment."""
