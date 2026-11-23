"""Validate, test, record and assemble an episode."""

import argparse

from . import assemble, episode, recorder, slides, voice
from .approval import script_hash
from .config import load


def main():
    if __package__ == "video_tools":
        import sys
        from pathlib import Path

        sys.path.insert(0, str(Path.cwd()))
    load()
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "command", choices=["check", "qa", "record", "slides", "voice", "build", "all"]
    )
    parser.add_argument("episode")
    parser.add_argument("--scene", action="append")
    parser.add_argument("--force", action="store_true")
    parser.add_argument("--no-burn", action="store_true")
    args = parser.parse_args()
    try:
        ep = episode.load(args.episode)
        if args.command == "check":
            print(
                f"{ep.title}: {len(ep.scenes)} scenes\nscript_sha256: {script_hash(ep.path)}"
            )
            return
        selected = set(args.scene) if args.scene else None
        if selected and selected - {s.id for s in ep.scenes}:
            raise ValueError("Unknown scene ID")
        if args.command in {"voice", "all"}:
            voice.synthesize(ep, only=selected, force=args.force)
        if args.command in {"slides", "all"}:
            slides.render(ep, only=selected)
        if args.command in {"qa", "record", "all"}:
            for scene in ep.scenes:
                if scene.kind == "screen" and (not selected or scene.id in selected):
                    target = (
                        ep.out / "screens" / f"{scene.id}.webm"
                        if args.command != "qa"
                        else None
                    )
                    recorder.run(scene.scenario, params=scene.params, video_to=target)
                    print(f"{args.command}: {scene.id} passed")
        if args.command in {"build", "all"}:
            assemble.build(ep, burn_subtitles=not args.no_burn)
    except (ValueError, OSError) as exc:
        parser.exit(2, f"{exc}\n")
