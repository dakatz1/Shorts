import shutil

import pytest

from shorts.models import Beat
from shorts.render import _audio_filter, _even, _panel_sizes, _zoompan_expr

ffmpeg_required = pytest.mark.skipif(
    shutil.which("ffmpeg") is None, reason="ffmpeg not installed"
)


def test_even_rounds_down_to_an_even_number():
    assert _even(1081) == 1080
    assert _even(1080) == 1080
    assert _even(0.5) == 0


def test_split_panels_exactly_fill_the_frame(config):
    width, height, top = _panel_sizes(config)
    assert width % 2 == 0 and height % 2 == 0 and top % 2 == 0
    assert 0 < top < height
    assert (height - top) % 2 == 0   # vstack needs both halves even


def test_full_layout_uses_the_whole_frame(config):
    cfg = config.merged_with({"visual": {"layout": "full"}})
    _, height, top = _panel_sizes(cfg)
    assert top == height


def test_broll_only_layout_has_no_animation_panel(config):
    cfg = config.merged_with({"visual": {"layout": "broll_only"}})
    assert _panel_sizes(cfg)[2] == 0


@pytest.mark.parametrize("motion", ["push_in", "pull_out", "pan_left", "pan_right", "shake"])
def test_every_motion_produces_all_three_expressions(motion):
    expr = _zoompan_expr(motion, frames=90, zoom_per_second=0.035, fps=30)
    assert expr.startswith("z=") and ":x=" in expr and ":y=" in expr


def test_unknown_motion_falls_back_to_push_in():
    assert _zoompan_expr("nonsense", 90, 0.035, 30) == _zoompan_expr("push_in", 90, 0.035, 30)


def test_single_frame_segment_does_not_divide_by_zero():
    assert _zoompan_expr("pan_left", frames=1, zoom_per_second=0.035, fps=30)


def test_audio_filter_indices_do_not_collide(config):
    """Regression: substituting [1:a] then [2:a] in sequence rewrote the first result."""
    graph, label = _audio_filter(voice_index=2, music_index=3, config=config)
    assert "[2:a]" in graph and "[3:a]" in graph
    assert "[4:a]" not in graph
    assert label == "[aout]"


def test_audio_filter_without_music_has_one_source(config):
    graph, _ = _audio_filter(voice_index=1, music_index=None, config=config)
    assert graph.count(":a]") == 1
    assert "amix" not in graph


@ffmpeg_required
def test_beat_segment_renders_with_the_requested_duration(tmp_path, config):
    from shorts.providers.image_stub import StubImageProvider
    from shorts.render import render_beat_segment
    from shorts.util import ffprobe_duration

    image = StubImageProvider().render("a dark room", tmp_path / "f.jpg", config, seed=1)
    beat = Beat(text="line", visual="v", motion="push_in", start=0.0, end=2.0)
    out = render_beat_segment(beat, image, tmp_path / "seg.mp4", config, (320, 320))
    assert ffprobe_duration(out) == pytest.approx(2.0, abs=0.15)


@ffmpeg_required
def test_concat_preserves_total_duration(tmp_path, config):
    from shorts.providers.image_stub import StubImageProvider
    from shorts.render import concat_segments, render_beat_segment
    from shorts.util import ffprobe_duration

    image = StubImageProvider().render("a dark room", tmp_path / "f.jpg", config, seed=1)
    segments = [
        render_beat_segment(
            Beat(text="x", visual="v", start=0.0, end=1.0), image,
            tmp_path / f"s{i}.mp4", config, (320, 320),
        )
        for i in range(3)
    ]
    out = concat_segments(segments, tmp_path / "all.mp4")
    assert ffprobe_duration(out) == pytest.approx(3.0, abs=0.2)
