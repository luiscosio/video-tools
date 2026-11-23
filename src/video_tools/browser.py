"""Browser interactions and optional recording diagnostics."""
from __future__ import annotations

import os
from datetime import UTC, datetime
from pathlib import Path

from playwright.sync_api import Error as PlaywrightError
from playwright.sync_api import Locator, Page

CURSOR_JS = """
(() => {
  if (window.__recCursor) return;
  const c = document.createElement('div');
  c.style.cssText = 'position:fixed;z-index:2147483647;width:22px;height:22px;margin:-11px 0 0 -11px;'
    + 'border-radius:50%;background:rgba(30,167,232,.35);border:2px solid #1ea7e8;'
    + 'pointer-events:none;transition:transform .12s;left:-50px;top:-50px';
  const add = () => document.body && document.body.appendChild(c);
  add() || document.addEventListener('DOMContentLoaded', add);
  addEventListener('mousemove', e => { c.style.left = e.clientX + 'px'; c.style.top = e.clientY + 'px'; }, true);
  addEventListener('mousedown', () => c.style.transform = 'scale(.7)', true);
  addEventListener('mouseup', () => c.style.transform = 'scale(1)', true);
  window.__recCursor = c;
})();
"""

class PageActions:
    def pause(self, seconds: float = 1.0) -> None:
        if self.recording:
            self.page.wait_for_timeout(seconds * 1000)

    def click(self, target: Locator | str, *, settle: float = 0.6) -> None:
        loc = self.page.locator(target) if isinstance(target, str) else target
        loc.scroll_into_view_if_needed()
        if self.recording:
            box = loc.bounding_box()
            if box:
                self.page.mouse.move(
                    box["x"] + box["width"] / 2, box["y"] + box["height"] / 2, steps=25
                )
                self.pause(0.25)
        loc.click()
        self.pause(settle)

    def point(self, target: Locator | str, *, settle: float = 1.5) -> None:
        """Move the visible cursor to an element without clicking it."""
        loc = self.page.locator(target) if isinstance(target, str) else target
        loc.scroll_into_view_if_needed()
        if self.recording and (box := loc.bounding_box()):
            self.page.mouse.move(
                box["x"] + box["width"] / 2, box["y"] + box["height"] / 2, steps=25
            )
        self.pause(settle)

    def type(self, target: Locator | str, text: str, *, settle: float = 0.4) -> None:
        loc = self.page.locator(target) if isinstance(target, str) else target
        # Date and time inputs take keystrokes per segment in the browser's locale,
        # so typing "2027-01-31" into one goes nowhere: fill them even when recording.
        kind = (loc.get_attribute("type") or "").lower()
        if self.recording and kind not in ("date", "time", "datetime-local", "month", "week"):
            self.click(loc, settle=0.1)
            loc.fill("")
            loc.press_sequentially(text, delay=70)
        elif self.recording:
            self.click(loc, settle=0.1)
            loc.fill(text)
        else:
            loc.fill(text)
        self.pause(settle)

    def goto(self, url: str, *, settle: float = 1.2) -> None:
        if self.log is not None:
            self.log.append(f"{_now()} goto     {url}")
        try:
            self.page.goto(url)
        except PlaywrightError as err:
            # The page may be navigating on its own (a redirect after a sale) at the
            # same moment; Playwright then aborts our goto. Let it land and retry once.
            msg = str(err)
            if "interrupted by another navigation" not in msg and "ERR_ABORTED" not in msg:
                raise
            self.page.wait_for_load_state("load")
            self.page.goto(url)
        self.page.wait_for_load_state("networkidle")
        self.pause(settle)

    def scroll(self, pixels: int, *, settle: float = 0.8) -> None:
        if self.recording:
            for _ in range(10):
                self.page.mouse.wheel(0, pixels / 10)
                self.page.wait_for_timeout(40)
        else:
            self.page.mouse.wheel(0, pixels)
        self.pause(settle)


class SimplePageActions(PageActions):
    def type(self, target: Locator | str, text: str, *, settle: float = 0.4) -> None:
        loc = self.page.locator(target) if isinstance(target, str) else target
        if self.recording:
            self.click(loc, settle=0.1)
            loc.fill("")
            loc.press_sequentially(text, delay=70)
        else:
            loc.fill(text)
        self.pause(settle)


def _now() -> str:
    return datetime.now(UTC).isoformat(timespec="milliseconds")


TIMING = ("startTime", "connectStart", "connectEnd", "requestStart", "responseStart", "responseEnd")


def _network_log(page: Page) -> list[str] | None:
    """With E2E_ARTIFACTS set (CI), note each goto and every request the page makes, with its
    timing (ms after startTime), so a slow navigation shows where the time went."""
    if not os.environ.get("E2E_ARTIFACTS"):
        return None
    lines: list[str] = []

    def note(kind: str, req, extra: str = "") -> None:
        lines.append(f"{_now()} {kind:<8} {req.method} {req.url[:160]} {extra}")

    def done(req) -> None:
        note("done", req, " ".join(f"{k}={req.timing.get(k, -1):.0f}" for k in TIMING))

    page.on("request", lambda r: note("request", r, "nav" if r.is_navigation_request() else ""))
    page.on("requestfinished", done)
    page.on("requestfailed", lambda r: note("failed", r, str(r.failure)))
    page.on("load", lambda _: lines.append(f"{_now()} load     {page.url[:160]}"))
    return lines


def _failure_network_log(lines: list[str] | None, scenario: str) -> None:
    out = os.environ.get("E2E_ARTIFACTS")
    if not out or lines is None:
        return
    with contextlib.suppress(Exception):
        Path(out).mkdir(parents=True, exist_ok=True)
        with (Path(out) / f"{scenario}.network.log").open("a") as f:  # a flow run twice keeps both
            f.write("\n".join(lines) + "\n\n")


def _failure_screenshot(page: Page, scenario: str) -> None:
    """With E2E_ARTIFACTS set (CI), keep a screenshot of the page a flow failed on."""
    out = os.environ.get("E2E_ARTIFACTS")
    if not out:
        return
    with contextlib.suppress(Exception):
        Path(out).mkdir(parents=True, exist_ok=True)
        page.screenshot(path=str(Path(out) / f"{scenario}.png"), full_page=True, timeout=10_000)
