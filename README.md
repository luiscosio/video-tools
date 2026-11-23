# Narrated video tools

Build a narrated MP4 from an episode written in YAML. Each scene can render a slide, use a still image, or record a Python scenario in headless Chromium. ElevenLabs provides narration and word timings. FFmpeg aligns the pictures to the audio and writes the subtitles.

## Try the sample

Install Python 3.11 or later, uv, FFmpeg with the subtitles filter, and ffprobe. From a checkout of this repository, run the following commands.

```sh
git clone --branch main https://github.com/luiscosio/video-tools.git
cd video-tools/example
uv run --project .. video-tools check demo
uv run --project .. playwright install chromium
uv run --project .. video-tools slides demo
```

The sample slide renders locally. For narration, set `ELEVENLABS_API_KEY` and `ELEVENLABS_VOICE_ID` in your environment for a voice you have permission to use. Set `ELEVENLABS_MODEL_ID` to override the model. The voice command contacts ElevenLabs and may incur charges. Repeated builds reuse cached narration when the text, model and voice match.

```sh
uv run --project .. video-tools voice demo
uv run --project .. video-tools build demo
```

The MP4 and SRT appear under `output/demo/`. Use `qa` to run a screen scenario with assertions, `record` to capture it, or `all` to produce the episode.

## Use in a project

Keep episode scripts in `episodes/<slug>/episode.yaml`, browser flows in `scenarios/<name>.py` and branded templates in `slides/`. A scenario exports `run(rec, **params)`. Use YAML for narration, scene ordering and parameters. Keep clicks, waits and assertions in Python. Credentials, recordings and generated audio belong outside source control.

Install the shared code from main with `uv add "narrated-video-tools @ git+https://github.com/luiscosio/video-tools.git@main"`. Commit the resulting uv lockfile. Use `uv lock --upgrade-package narrated-video-tools` to adopt a newer revision.

Existing project CLIs can keep their own module names and configuration. Add `from video_tools import PIPELINE_PATH` and `__path__.append(PIPELINE_PATH)` in the project video package's `__init__.py`. Modules in that directory take precedence. The shared modules resolve relative imports in the same project package, so each client's paths, voice authorization and recording hooks stay scoped to that project. See `src/video_tools/config.py` for a standalone configuration.
