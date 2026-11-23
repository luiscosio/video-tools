"""Subtitles from the ElevenLabs character alignment."""

from __future__ import annotations

import json
import re
from pathlib import Path

MAX_CHARS = 64  # two lines of ~32 at 1080p
TAG = re.compile(r"\[[^\]]*\]\s*")


def words(meta_path: Path) -> list[tuple[str, float, float]]:
    """(word, start, end) in seconds, with the voice-direction tag removed."""
    meta = json.loads(meta_path.read_text())
    al = meta.get("alignment") or {}
    chars = al.get("characters") or []
    starts = al.get("character_start_times_seconds") or []
    ends = al.get("character_end_times_seconds") or []
    text = "".join(chars)
    skip = 0
    if (m := TAG.match(text)) is not None:
        skip = m.end()
    out: list[tuple[str, float, float]] = []
    cur, t0, t1 = "", None, 0.0
    for i in range(skip, len(chars)):
        ch = chars[i]
        if ch.isspace():
            if cur:
                out.append((cur, t0, t1))
            cur, t0 = "", None
            continue
        if t0 is None:
            t0 = starts[i]
        cur += ch
        t1 = ends[i]
    if cur:
        out.append((cur, t0, t1))
    return out


def cues(
    ws: list[tuple[str, float, float]], offset: float
) -> list[tuple[float, float, str]]:
    result: list[tuple[float, float, str]] = []
    line: list[str] = []
    start = end = 0.0
    for word, s, e in ws:
        candidate = " ".join([*line, word])
        if line and (len(candidate) > MAX_CHARS or line[-1][-1] in ".?!:"):
            result.append((start + offset, end + offset, " ".join(line)))
            line = []
        if not line:
            start = s
        line.append(word)
        end = e
    if line:
        result.append((start + offset, end + offset, " ".join(line)))
    return result


def _ts(t: float) -> str:
    ms = round(t * 1000)
    h, ms = divmod(ms, 3_600_000)
    m, ms = divmod(ms, 60_000)
    s, ms = divmod(ms, 1000)
    return f"{h:02}:{m:02}:{s:02},{ms:03}"


def write_srt(all_cues: list[tuple[float, float, str]], path: Path) -> None:
    blocks = [
        f"{i}\n{_ts(a)} --> {_ts(b)}\n{text}\n"
        for i, (a, b, text) in enumerate(all_cues, 1)
    ]
    path.write_text("\n".join(blocks), encoding="utf-8")
