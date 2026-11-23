"""Narration per scene with the authorized ElevenLabs voice.

Each scene is synthesized on its own so a scene's timing and audio can be
redone without touching the rest. Results are cached by a hash of the request,
so re-running a build doesn't bill the same text twice.
"""

from __future__ import annotations

import base64
import hashlib
import json
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

from . import config
from .config import voice_config
from .episode import Episode, Scene

EXPRESSIVE_MODELS = {"eleven_v3", "eleven_v4"}
OUTPUT_FORMATS = ["mp3_44100_192", "mp3_44100_128"]


def _text(scene: Scene, model: str) -> str:
    text = " ".join(scene.narration.split())
    if model in EXPRESSIVE_MODELS and scene.voice_direction:
        text = f"[{scene.voice_direction}] {text}"
    return text


def _request(text: str, language: str, model: str) -> dict:
    payload = {
        "text": text,
        "model_id": model,
        "voice_settings": {"stability": 0.5},
        "apply_text_normalization": "auto",
    }
    if model in EXPRESSIVE_MODELS:
        payload["language_code"] = language
    return payload


def synthesize_scene(
    scene: Scene, language: str, out_dir: Path, *, force: bool = False
) -> Path:
    cfg = voice_config()
    payload = _request(_text(scene, cfg.model_id), language, cfg.model_id)
    digest = hashlib.sha256(
        json.dumps([payload, cfg.voice_id], sort_keys=True).encode()
    ).hexdigest()[:16]
    audio = out_dir / f"{scene.id}.mp3"
    meta = out_dir / f"{scene.id}.json"
    if (
        not force
        and audio.exists()
        and meta.exists()
        and json.loads(meta.read_text()).get("hash") == digest
    ):
        return audio

    if hasattr(config, "check_voice"):
        config.check_voice(cfg.voice_id)
    result = None
    for index, fmt in enumerate(OUTPUT_FORMATS):
        url = (
            "https://api.elevenlabs.io/v1/text-to-speech/"
            f"{urllib.parse.quote(cfg.voice_id)}/with-timestamps?"
            + urllib.parse.urlencode({"output_format": fmt})
        )
        req = urllib.request.Request(
            url,
            data=json.dumps(payload).encode(),
            method="POST",
            headers={"Content-Type": "application/json", "xi-api-key": cfg.api_key},
        )
        try:
            with urllib.request.urlopen(req, timeout=180) as resp:
                result = json.loads(resp.read())
            break
        except urllib.error.HTTPError as exc:
            body = exc.read().decode(errors="replace")
            if (
                exc.code == 403
                and "output_format" in body
                and index + 1 < len(OUTPUT_FORMATS)
            ):
                continue
            raise SystemExit(f"ElevenLabs failed on scene {scene.id}: HTTP {exc.code}")
    if result is None:
        raise SystemExit(f"ElevenLabs returned no audio for scene {scene.id}")

    out_dir.mkdir(parents=True, exist_ok=True)
    audio.write_bytes(base64.b64decode(result["audio_base64"]))
    meta.write_text(
        json.dumps(
            {
                "hash": digest,
                "scene": scene.id,
                "text": payload["text"],
                "model_id": cfg.model_id,
                "voice_id": cfg.voice_id,
                "alignment": result.get("normalized_alignment")
                or result.get("alignment"),
            },
            ensure_ascii=False,
            indent=1,
        )
    )
    return audio


def synthesize(
    episode: Episode, *, only: set[str] | None = None, force: bool = False
) -> None:
    if getattr(config, "REQUIRE_SCRIPT_APPROVAL", False):
        from .approval import require_approval

        require_approval(episode)
    out_dir = episode.out / "voice"
    for scene in episode.scenes:
        if only and scene.id not in only:
            continue
        path = synthesize_scene(scene, episode.language, out_dir, force=force)
        print(f"voice  {scene.id:<24} {path.name}")
