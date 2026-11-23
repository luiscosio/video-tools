"""Run the selected production stages, using the project's recording hooks."""

from . import assemble, slides, voice


def produce(command, episode, *, only, force, burn, record, after_slides=None):
    if command in ("voice", "all"):
        voice.synthesize(episode, only=only, force=force)
    if command in ("slides", "all"):
        slides.render(episode, only=only)
        if after_slides:
            after_slides(episode)
    if command in ("record", "all"):
        record(episode, only)
    if command in ("build", "all"):
        assemble.build(episode, burn_subtitles=burn)
