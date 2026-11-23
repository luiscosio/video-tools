"""Episode files: an ordered list of scenes, each with narration and visuals."""

from __future__ import annotations

import math
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml

from . import config
from .config import EPISODES_DIR, OUTPUT_DIR


@dataclass
class Scene:
    id: str
    kind: str  # "slide" or "screen"
    narration: str
    voice_direction: str | None = None
    slide: str | None = None  # template name in slides/, for kind=slide
    data: dict[str, Any] = field(default_factory=dict)  # template variables
    scenario: str | None = None  # module name in scenarios/, for kind=screen
    params: dict[str, Any] = field(default_factory=dict)  # scenario arguments
    image: str | None = None
    caption: str | None = None
    source: str | None = None
    viewport: str = "desk"
    min_seconds: float = 0.0

    @property
    def is_still(self):
        return self.kind in ("slide", "image")


@dataclass
class Episode:
    slug: str
    title: str
    language: str
    audience: str
    scenes: list[Scene]
    dataset: str | None
    path: Path
    item: str | None = None

    def image_path(self, scene):
        return (self.path.parent / scene.image).resolve()

    @property
    def out(self) -> Path:
        return OUTPUT_DIR / self.slug


def load(slug_or_path: str) -> Episode:
    path = Path(slug_or_path)
    if not path.suffix:
        path = EPISODES_DIR / slug_or_path / "episode.yaml"
    raw = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(raw, dict) or not re.fullmatch(
        r"[a-zA-Z0-9][a-zA-Z0-9_-]*", str(raw.get("slug", ""))
    ):
        raise ValueError("Episode slug must be a simple filename")
    if raw.get("dataset") and not getattr(config, "ALLOW_DATASET", False):
        raise ValueError("This project has no dataset reset implementation")
    scenes = [Scene(**scene) for scene in raw["scenes"]]
    if not scenes:
        raise ValueError("Episode needs scenes")
    ids = [scene.id for scene in scenes]
    if len(ids) != len(set(ids)):
        raise SystemExit(f"Duplicate scene ids in {path}")
    for scene in scenes:
        if not re.fullmatch(r"[a-zA-Z0-9][a-zA-Z0-9_-]*", scene.id):
            raise ValueError("Scene ID must be a simple filename")
        if scene.kind not in getattr(config, "SCENE_KINDS", ("slide", "screen")):
            raise SystemExit(
                f"Scene {scene.id}: unknown kind {scene.kind!r}. The kind must be enabled for this project"
            )
        if scene.kind == "image" and (
            not scene.image or not (path.parent / scene.image).is_file()
        ):
            raise SystemExit(
                f"Scene {scene.id}: needs 'image', a file relative to the episode"
            )
        if scene.kind == "clip" and not scene.source:
            raise SystemExit(f"Scene {scene.id}: needs 'source'")
        viewports = getattr(config, "VIEWPORTS", None)
        if scene.kind == "screen" and viewports and scene.viewport not in viewports:
            raise SystemExit(f"Scene {scene.id}: unknown viewport {scene.viewport!r}")
        if not scene.narration.strip():
            raise SystemExit(f"Scene {scene.id}: narration is empty")
        if not math.isfinite(scene.min_seconds) or scene.min_seconds < 0:
            raise ValueError("Scene duration must be finite and nonnegative")
        if scene.scenario and not re.fullmatch(r"[a-zA-Z0-9_]+", scene.scenario):
            raise ValueError("Scenario must be a local module name")
        if scene.slide and not re.fullmatch(r"[a-zA-Z0-9_-]+", scene.slide):
            raise ValueError("Slide must be a local template name")
        if scene.kind == "slide" and not scene.slide:
            raise SystemExit(f"Scene {scene.id}: kind=slide needs 'slide'")
        if scene.kind == "screen" and not scene.scenario:
            raise SystemExit(f"Scene {scene.id}: kind=screen needs 'scenario'")
    return Episode(
        slug=raw["slug"],
        title=raw["title"],
        language=raw.get("language", "es"),
        audience=raw.get("audience", "internal"),
        scenes=scenes,
        dataset=raw.get("dataset"),
        path=path.resolve(),
        item=raw.get("item"),
    )
