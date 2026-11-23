"""Cut each scene to its narration and join them into the final video.

Timing rule: the narration leads. A slide stays up for its narration plus a
short tail. A screen recording that runs longer than its narration is sped up
(at most MAX_SPEED); one that runs shorter holds its last frame.
"""

from __future__ import annotations

import functools
import json
import os
import shutil
import subprocess
from pathlib import Path

from . import captions, config
from .config import FPS, HEIGHT, WIDTH
from .episode import Episode

LEAD = 0.4  # silence before narration starts in each scene
TAIL = 0.8  # picture held after narration ends
MAX_SPEED = 2.0


def _duration(path: Path) -> float:
    out = subprocess.run(
        [
            "ffprobe",
            "-v",
            "error",
            "-show_entries",
            "format=duration",
            "-of",
            "json",
            str(path),
        ],
        check=True,
        capture_output=True,
        text=True,
    ).stdout
    return float(json.loads(out)["format"]["duration"])


@functools.cache
def _ffmpeg_bin() -> str:
    """An ffmpeg with the subtitles filter (libass). Homebrew's default build lacks it,
    so check $FFMPEG, each ffmpeg on PATH and ~/.local/bin before giving up."""
    seen: list[str] = []
    path_dirs = os.environ.get("PATH", "").split(os.pathsep)
    paths = [os.environ.get("FFMPEG"), *path_dirs, "~/.local/bin"]
    for entry in paths:
        if not entry:
            continue
        cand = Path(os.path.expanduser(entry))
        cand = cand if cand.name == "ffmpeg" else cand / "ffmpeg"
        if not cand.is_file() or str(cand) in seen:
            continue
        seen.append(str(cand))
        filters = subprocess.run(
            [str(cand), "-hide_banner", "-filters"],
            check=False,
            capture_output=True,
            text=True,
        ).stdout
        if any(line.split()[1:2] == ["subtitles"] for line in filters.splitlines()):
            return str(cand)
    if seen:
        raise RuntimeError(
            f"no ffmpeg with the subtitles filter (libass) among {seen}; "
            "install one or set FFMPEG, or use --no-burn"
        )
    return shutil.which("ffmpeg") or "ffmpeg"


def _ffmpeg(args: list[str], *, subtitles: bool = False) -> None:
    exe = _ffmpeg_bin() if subtitles else (shutil.which("ffmpeg") or "ffmpeg")
    subprocess.run([exe, "-hide_banner", "-loglevel", "error", "-y", *args], check=True)


def _segment(
    visual: Path, is_still: bool, audio: Path, out: Path, min_seconds: float
) -> float:
    narration = _duration(audio)
    target = max(LEAD + narration + TAIL, min_seconds)
    scale = (
        f"scale={WIDTH}:{HEIGHT}:force_original_aspect_ratio=decrease,"
        f"pad={WIDTH}:{HEIGHT}:(ow-iw)/2:(oh-ih)/2:color=0xf3f6fa,setsar=1,fps={FPS}"
    )
    if is_still:
        vin = ["-loop", "1", "-t", f"{target:.3f}", "-i", str(visual)]
        vf = scale
    else:
        length = _duration(visual)
        speed = min(max(length / target, 1.0), MAX_SPEED)
        target = max(target, length / speed)
        hold = max(target - length / speed, 0)
        vin = ["-i", str(visual)]
        vf = f"setpts=PTS/{speed:.4f},{scale},tpad=stop_mode=clone:stop_duration={hold:.3f}"
    fade = f",fade=t=in:st=0:d=0.25,fade=t=out:st={target - 0.25:.3f}:d=0.25"
    af = f"adelay={int(LEAD * 1000)}:all=1,apad,atrim=0:{target:.3f},aresample=48000"
    _ffmpeg(
        [
            *vin,
            "-i",
            str(audio),
            "-filter_complex",
            f"[0:v]{vf}{fade}[v];[1:a]{af}[a]",
            "-map",
            "[v]",
            "-map",
            "[a]",
            "-t",
            f"{target:.3f}",
            "-c:v",
            "libx264",
            "-preset",
            "medium",
            "-crf",
            "18",
            "-pix_fmt",
            "yuv420p",
            "-c:a",
            "aac",
            "-b:a",
            "192k",
            "-ac",
            "2",
            str(out),
        ]
    )
    return target


def build(episode: Episode, *, burn_subtitles: bool = True) -> Path:
    out = episode.out
    seg_dir = out / "segments"
    seg_dir.mkdir(parents=True, exist_ok=True)
    all_cues: list[tuple[float, float, str]] = []
    listing: list[str] = []
    clock = 0.0
    for scene in episode.scenes:
        audio = out / "voice" / f"{scene.id}.mp3"
        if not audio.exists():
            raise SystemExit(
                f"Missing narration for {scene.id}. Run: the voice command for {episode.slug}"
            )
        if scene.is_still:
            visual, still = out / "slides" / f"{scene.id}.png", True
        else:
            visual, still = out / "screens" / f"{scene.id}.webm", False
        if not visual.exists():
            raise SystemExit(f"Missing visual {visual}. Run slides/record first.")
        seg = seg_dir / f"{scene.id}.mp4"
        length = _segment(visual, still, audio, seg, scene.min_seconds)
        all_cues += captions.cues(
            captions.words(audio.with_suffix(".json")), clock + LEAD
        )
        listing.append(f"file '{seg.resolve()}'")
        print(f"cut    {scene.id:<24} {length:6.1f}s")
        clock += length

    srt = out / f"{episode.slug}.srt"
    captions.write_srt(all_cues, srt)
    concat = seg_dir / "concat.txt"
    concat.write_text("\n".join(listing) + "\n")
    joined = seg_dir / "joined.mp4"
    _ffmpeg(
        ["-f", "concat", "-safe", "0", "-i", str(concat), "-c", "copy", str(joined)]
    )

    final = out / f"{episode.slug}.mp4"
    if burn_subtitles:
        style = (
            "FontName=Geist,FontSize=15,PrimaryColour=&H00FAF1EA,OutlineColour=&H80291709,"
            "BorderStyle=3,Outline=6,Shadow=0,MarginV=36"
        )
        fonts = getattr(config, "BRAND_DIR", config.SLIDES_DIR / "assets")
        _ffmpeg(
            [
                "-i",
                str(joined),
                "-vf",
                f"subtitles={srt}:fontsdir={fonts}:force_style='{style}'",
                "-c:v",
                "libx264",
                "-preset",
                "medium",
                "-crf",
                "18",
                "-pix_fmt",
                "yuv420p",
                "-c:a",
                "copy",
                "-movflags",
                "+faststart",
                str(final),
            ],
            subtitles=True,
        )
    else:
        _ffmpeg(
            ["-i", str(joined), "-c", "copy", "-movflags", "+faststart", str(final)]
        )
    print(f"done   {final}  ({clock / 60:.1f} min)  subtitles: {srt.name}")
    return final
