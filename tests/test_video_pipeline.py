"""Coverage for the generated-video path.

The real provider needs a paid API, so a fake stands in: it emits a fixed
5-second clip exactly like an image-to-video model would, which is precisely
the mismatch the conforming pass exists to absorb.
"""

import shutil

import pytest

from shorts.config import load_config
from shorts.models import Script
from shorts.util import ffmpeg, ffprobe_duration

pytestmark = pytest.mark.skipif(shutil.which("ffmpeg") is None, reason="ffmpeg not installed")

GENERATED_LENGTH = 5.0


class FakeVideoProvider:
    """Stands in for an image-to-video model: fixed length, wrong aspect ratio."""

    exact_duration = False

    def __init__(self):
        self.calls = []

    def animate(self, image, prompt, out_path, config, *, duration, motion="push_in", seed=0):
        self.calls.append({"prompt": prompt, "duration": duration, "motion": motion, "seed": seed})
        out_path.parent.mkdir(parents=True, exist_ok=True)
        ffmpeg([
            "-f", "lavfi", "-i", "testsrc=size=640x360:rate=24",
            "-t", str(GENERATED_LENGTH), "-pix_fmt", "yuv420p", str(out_path),
        ])
        return out_path


@pytest.fixture
def fast_config(tmp_path):
    return load_config(overrides=[
        "content.beats=3",
        "visual.width=240", "visual.height=426", "visual.fps=12",
        "providers.video=fake", "providers.tts=stub",
        f"output.dir={tmp_path}", "output.preset=ultrafast", "output.crf=30",
    ])


@pytest.fixture
def fake_provider(monkeypatch):
    provider = FakeVideoProvider()
    monkeypatch.setattr("shorts.pipeline.get_video_provider", lambda config: provider)
    return provider


def test_generated_clips_are_conformed_to_beat_lengths(fast_config, fake_provider):
    from shorts.pipeline import generate_script, produce

    script = generate_script(fast_config, seed=1)
    result = produce(script, fast_config)

    assert len(fake_provider.calls) == 3
    # Every segment matches its beat, despite the source always being 5s.
    for index, beat in enumerate(result.script.beats):
        segment = result.workdir / "segments" / f"seg_{index:02d}.mp4"
        assert ffprobe_duration(segment) == pytest.approx(beat.duration, abs=0.15)


def test_at_least_one_beat_differs_from_the_generated_length(fast_config, fake_provider):
    """Otherwise the conforming pass would be untested by accident."""
    from shorts.pipeline import generate_script, produce

    result = produce(generate_script(fast_config, seed=1), fast_config)
    assert any(
        abs(b.duration - GENERATED_LENGTH) > 0.3 for b in result.script.beats
    )


def test_clips_are_cached_and_not_regenerated(fast_config, fake_provider):
    from shorts.pipeline import generate_script, produce

    script = generate_script(fast_config, seed=2)
    first = produce(script, fast_config)
    assert len(fake_provider.calls) == 3

    produce(Script.load(first.workdir / "script.json"), fast_config, workdir=first.workdir)
    assert len(fake_provider.calls) == 3, "cached clips must not be re-bought"

    produce(Script.load(first.workdir / "script.json"), fast_config,
            workdir=first.workdir, reuse=False)
    assert len(fake_provider.calls) == 6


def test_the_provider_receives_the_beat_prompt_and_motion(fast_config, fake_provider):
    from shorts.pipeline import generate_script, produce

    result = produce(generate_script(fast_config, seed=3), fast_config)
    for call, beat in zip(fake_provider.calls, result.script.beats):
        assert call["prompt"] == beat.visual
        assert call["motion"] == beat.motion
        assert call["seed"] != 0


def test_the_finished_video_is_still_correct(fast_config, fake_provider):
    from shorts.pipeline import generate_script, produce

    result = produce(generate_script(fast_config, seed=4), fast_config)
    assert result.video_path.exists()
    assert ffprobe_duration(result.video_path) == pytest.approx(result.duration, abs=0.2)


def test_kenburns_skips_the_conforming_pass(fast_config):
    """The free path renders to length directly, so it writes no clips/ dir."""
    from shorts.pipeline import generate_script, produce

    cfg = fast_config.merged_with({"providers": {"video": "kenburns"}})
    result = produce(generate_script(cfg, seed=5), cfg)
    assert not list((result.workdir / "clips").glob("*.mp4"))
