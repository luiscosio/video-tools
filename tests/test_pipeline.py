import json
from pathlib import Path

import pytest

from video_tools import episode, slides, voice

SAMPLE = Path(__file__).resolve().parents[1] / "example"


def test_sample_renders(monkeypatch):
    monkeypatch.setattr(slides, "SLIDES_DIR", SAMPLE / "slides")
    demo = episode.load(str(SAMPLE / "episodes/demo/episode.yaml"))
    assert "First recording" in slides.html(demo, demo.scenes[0])


def test_refuses_output_escape(tmp_path):
    src = tmp_path / "episode.yaml"
    src.write_text("slug: ../escape\ntitle: Fixture\nscenes: []\n")
    with pytest.raises(ValueError, match="slug"):
        episode.load(str(src))


def test_cached_scene_avoids_http(monkeypatch, tmp_path):
    import base64
    import io

    scene = episode.Scene(id="fixture", kind="slide", narration="A sample.")
    monkeypatch.setenv("ELEVENLABS_API_KEY", "fixture")
    monkeypatch.setenv("ELEVENLABS_VOICE_ID", "fixture")
    calls = []

    def reply(req, timeout):
        calls.append(req)
        return io.BytesIO(
            json.dumps(
                {"audio_base64": base64.b64encode(b"audio").decode(), "alignment": {}}
            ).encode()
        )

    monkeypatch.setattr(voice.urllib.request, "urlopen", reply)
    for _ in range(2):
        assert voice.synthesize_scene(scene, "en", tmp_path).read_bytes() == b"audio"
    assert len(calls) == 1
