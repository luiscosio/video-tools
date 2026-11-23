"""Stills: slide templates in slides/ and image scenes, rendered to 1920x1080 PNGs."""

from __future__ import annotations

from pathlib import Path

from jinja2 import Environment, FileSystemLoader, StrictUndefined

from . import config
from .config import HEIGHT, SLIDES_DIR, WIDTH

BRAND_DIR = getattr(config, "BRAND_DIR", SLIDES_DIR / "assets")
from .episode import Episode, Scene


def _env() -> Environment:
    return Environment(
        loader=FileSystemLoader(SLIDES_DIR), undefined=StrictUndefined, autoescape=True
    )


def html(episode: Episode, scene: Scene, env: Environment | None = None) -> str:
    """The page for one still scene. An image scene uses the `image` template."""
    env = env or _env()
    common = {
        "episode": episode,
        "scene": scene,
        "brand": BRAND_DIR.as_uri(),
        "asset": lambda name: (episode.path.parent / name).resolve().as_uri(),
    }
    if scene.kind == "image":
        src = episode.image_path(scene).as_uri()
        return env.get_template("image.html.j2").render(
            **common, **scene.data, src=src, caption=scene.caption
        )
    return env.get_template(f"{scene.slide}.html.j2").render(**common, **scene.data)


def launch(playwright, **kwargs):
    """Playwright's own Chromium, or the installed Chrome when that isn't downloaded (as on CI runners)."""
    from playwright.sync_api import Error

    try:
        return playwright.chromium.launch(**kwargs)
    except Error:
        return playwright.chromium.launch(channel="chrome", **kwargs)


def render(
    episode: Episode, *, only: set[str] | None = None, offline: bool = False
) -> list[Path]:
    """Screenshot every still scene. offline=True blocks web fonts and any other network request."""
    from playwright.sync_api import sync_playwright

    env = _env()
    out_dir = episode.out / "slides"
    out_dir.mkdir(parents=True, exist_ok=True)
    jobs: list[tuple[str, Path]] = []
    for scene in episode.scenes:
        if scene.kind == "image" and getattr(config, "EXTERNAL_IMAGE_RENDERER", False):
            continue
        if not scene.is_still or (only and scene.id not in only):
            continue
        # Written next to the templates, then deleted once captured.
        page_path = SLIDES_DIR / f".render-{scene.id}.html"
        page_path.write_text(html(episode, scene, env), encoding="utf-8")
        jobs.append((scene.id, page_path))

    made: list[Path] = []
    try:
        with sync_playwright() as p:
            browser = launch(p)
            page = browser.new_page(viewport={"width": WIDTH, "height": HEIGHT})
            if offline:
                page.route("http*://**/*", lambda route: route.abort())
            for scene_id, page_path in jobs:
                page.goto(page_path.as_uri())
                page.wait_for_load_state("networkidle")
                page.evaluate("document.fonts.ready")
                target = out_dir / f"{scene_id}.png"
                page.screenshot(path=str(target))
                made.append(target)
                print(f"slide  {scene_id:<24} {target.name}")
            browser.close()
    finally:
        for _, page_path in jobs:
            page_path.unlink(missing_ok=True)
    return made
