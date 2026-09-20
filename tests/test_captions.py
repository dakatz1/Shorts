import re

import pytest

from shorts.captions import _escape, _ts, build_ass, group_words
from shorts.models import Beat, Script, Word
from shorts.timing import estimate_word_times


def test_timestamp_format():
    assert _ts(0) == "0:00:00.00"
    assert _ts(65.5) == "0:01:05.50"
    assert _ts(-3) == "0:00:00.00"


def test_escape_neutralises_ass_syntax():
    out = _escape("a {b} c\\d\ne")
    assert "{" not in out and "}" not in out and "\\" not in out and "\n" not in out


def test_grouping_respects_max_words():
    words = estimate_word_times("one two three four five six seven eight", 8.0)
    for group in group_words(words, 3):
        assert len(group.words) <= 3


def test_grouping_breaks_on_punctuation():
    words = estimate_word_times("stop now. keep going", 4.0)
    groups = group_words(words, 4)
    assert groups[0].words[-1].text.endswith(".")


def test_every_word_survives_grouping():
    words = estimate_word_times("a b c d e f g h i j k", 11.0)
    regrouped = [w.text for g in group_words(words, 3) for w in g.words]
    assert regrouped == [w.text for w in words]


@pytest.fixture
def script():
    return Script(
        title="Do 5 squats a day",
        hook="THEY LIED TO YOU",
        beats=[Beat(text="You have been doing squats wrong.", visual="v")],
        disclaimer="Satire. Not fitness advice.",
    )


def test_ass_file_is_well_formed(tmp_path, script, config):
    words = estimate_word_times(script.narration, 4.0)
    path = build_ass(script, words, tmp_path / "c.ass", config, total_duration=4.0)
    text = path.read_text()

    assert "[Script Info]" in text and "[V4+ Styles]" in text and "[Events]" in text
    # Smart wrapping, or long lines run off a 1080px frame.
    assert "WrapStyle: 0" in text
    assert f"PlayResX: {config.get('visual.width')}" in text

    dialogues = [ln for ln in text.splitlines() if ln.startswith("Dialogue:")]
    assert dialogues
    for line in dialogues:
        assert len(line.split(",", 9)) == 10


def test_hook_and_disclaimer_are_rendered(tmp_path, script, config):
    words = estimate_word_times(script.narration, 4.0)
    text = build_ass(script, words, tmp_path / "c.ass", config, total_duration=4.0).read_text()
    assert "THEY LIED TO YOU" in text
    assert "Satire. Not fitness advice." in text


def test_active_word_is_highlighted(tmp_path, script, config):
    words = estimate_word_times(script.narration, 4.0)
    text = build_ass(script, words, tmp_path / "c.ass", config, total_duration=4.0).read_text()
    highlight = config.get("captions.highlight_color")
    assert text.count(f"\\c{highlight}") == len(words)


def test_disabled_captions_still_emit_the_hook(tmp_path, script, config):
    cfg = config.merged_with({"captions": {"enabled": False}})
    words = estimate_word_times(script.narration, 4.0)
    text = build_ass(script, words, tmp_path / "c.ass", cfg, total_duration=4.0).read_text()
    assert "THEY LIED TO YOU" in text
    assert "SQUATS" not in text


def test_no_zero_length_events(tmp_path, script, config):
    words = [Word("same", 1.0, 1.0), Word("time", 1.0, 2.0)]
    text = build_ass(script, words, tmp_path / "c.ass", config, total_duration=2.0).read_text()
    for line in text.splitlines():
        if line.startswith("Dialogue:"):
            _, start, end = line.split(",", 3)[:3]
            assert start != end
