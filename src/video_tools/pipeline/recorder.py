"""Drive the real apps with Playwright, for a video or as a QA check.

A scenario is a module in scenarios/ with `run(rec: Rec, **params)`. The same
code runs in two modes:
- record: headed pacing, a visible cursor, and a 1920x1080 video;
- qa: no pauses and no video, so it runs fast as a test.
Scenarios assert with Playwright's `expect`, so a broken flow fails both.
"""

from __future__ import annotations

import importlib
import shutil
from dataclasses import dataclass
from pathlib import Path

from playwright.sync_api import Page, sync_playwright

from video_tools.browser import (
    CURSOR_JS,
    PageActions,
    _failure_network_log,
    _failure_screenshot,
    _network_log,
)

from .config import HEIGHT, WIDTH, DemoUrls, demo_urls


@dataclass
class Rec(PageActions):
    page: Page
    urls: DemoUrls
    recording: bool
    log: list[str] | None = (
        None  # CI network log (_network_log), kept when a flow fails
    )


def run(
    scenario: str, *, params: dict | None = None, video_to: Path | None = None
) -> Path | None:
    """Run scenarios/<scenario>.py. With video_to, record and return the mp4-ready webm."""
    module = importlib.import_module(f"scenarios.{scenario}")
    recording = video_to is not None
    tmp = video_to.parent / f".rec-{scenario}" if video_to else None
    with sync_playwright() as p:
        browser = p.chromium.launch()
        urls = demo_urls()
        ctx_args = {"viewport": {"width": WIDTH, "height": HEIGHT}, "locale": "es-MX"}
        if urls.http_credentials:  # test environment's password gate
            ctx_args["http_credentials"] = urls.http_credentials
        if urls.api_key:
            ctx_args["extra_http_headers"] = {"X-Api-Key": urls.api_key}
        if recording:
            ctx_args |= {
                "record_video_dir": str(tmp),
                "record_video_size": {"width": WIDTH, "height": HEIGHT},
            }
        context = browser.new_context(**ctx_args)
        if recording:
            context.add_init_script(CURSOR_JS)
        page = context.new_page()
        page.set_default_timeout(20_000)
        net = _network_log(page)
        try:
            module.run(
                Rec(page=page, urls=urls, recording=recording, log=net),
                **(params or {}),
            )
            if recording:
                page.wait_for_timeout(600)
        except Exception:
            _failure_screenshot(page, scenario)
            _failure_network_log(net, scenario)
            raise
        finally:
            video = page.video
            context.close()
            browser.close()
        if recording and video:
            video_to.parent.mkdir(parents=True, exist_ok=True)
            shutil.move(video.path(), video_to)
            shutil.rmtree(tmp, ignore_errors=True)
            return video_to
    return None
