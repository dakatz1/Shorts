"""End-to-end coverage. Marked slow — these actually shell out to ffmpeg."""

import json
import shutil

import pytest

from shorts import broll as broll_lib
from shorts.ideas import IdeaGenerator
from shorts.models import Script
from shorts.pipeline import generate_script, produce
from shorts.util import ffprobe_duration

pytestmark = pytest.mark.skipif(
    shutil.which("ffmpeg") is None, reason="ffmpeg not installed"
)


@pytest.fixture
def fast_config(config, tmp_path):
    """A small, quick render — same code path, a fraction of the pixels."""
    return config.merged_with({
        "content": {"beats": 3},
        "visual": {"width": 240, "height": 426, "fps": 12},
        "output": {"dir": str(tmp_path), "preset": "ultrafast", "crf": 30},
    })


@pytest.fixture(autouse=True)
def _reset_broll():
    broll_lib.reset_usage()


def test_full_render_produces_a_playable_vertical_video(fast_config, tmp_path):
    script = generate_script(fast_config, seed=1)
    result = produce(script, fast_config)

    assert result.video_path.exists()
    assert result.video_path.stat().st_size > 1000
    assert result.duration > 1.0
    assert ffprobe_duration(result.video_path) == pytest.approx(result.duration, abs=0.2)


def test_render_writes_every_intermediate_artifact(fast_config):
    result = produce(generate_script(fast_config, seed=2), fast_config)
    workdir = result.workdir
    for name in ("script.json", "timings.json", "voice.wav", "captions.ass",
                 "animation.mp4", "broll.mp4", "final.mp4", "thumbnail.jpg"):
        assert (workdir / name).exists(), f"missing {name}"
    assert len(list((workdir / "frames").glob("*.jpg"))) == 3


def test_saved_script_round_trips(fast_config):
    result = produce(generate_script(fast_config, seed=3), fast_config)
    reloaded = Script.load(result.workdir / "script.json")
    assert reloaded.to_dict() == result.script.to_dict()


def test_beat_timings_cover_the_voiceover(fast_config):
    result = produce(generate_script(fast_config, seed=4), fast_config)
    timings = json.loads((result.workdir / "timings.json").read_text())
    beats = timings["beats"]
    assert beats[0]["start"] == 0.0
    assert beats[-1]["end"] == pytest.approx(timings["duration"], abs=0.05)


def test_frames_are_reused_on_a_second_render(fast_config):
    script = generate_script(fast_config, seed=5)
    first = produce(script, fast_config)
    frame = first.workdir / "frames" / "beat_00.jpg"
    stamp = frame.stat().st_mtime_ns

    produce(Script.load(first.workdir / "script.json"), fast_config, workdir=first.workdir)
    assert frame.stat().st_mtime_ns == stamp   # not regenerated

    produce(Script.load(first.workdir / "script.json"), fast_config,
            workdir=first.workdir, reuse=False)
    assert frame.stat().st_mtime_ns != stamp   # regenerated on demand


@pytest.mark.parametrize("layout", ["split", "full", "broll_only"])
def test_every_layout_renders(fast_config, layout):
    cfg = fast_config.merged_with({"visual": {"layout": layout}})
    result = produce(generate_script(cfg, seed=6), cfg)
    assert result.video_path.exists()
    assert result.duration > 1.0


def test_deadpan_mode_burns_no_disclaimer(fast_config):
    cfg = fast_config.merged_with({"content": {"mode": "deadpan"}})
    result = produce(generate_script(cfg, seed=7), cfg)
    subtitles = (result.workdir / "captions.ass").read_text()
    assert "Satire" not in subtitles
