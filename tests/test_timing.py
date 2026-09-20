import pytest

from shorts.models import Beat
from shorts.timing import assign_beat_times, estimate_duration, estimate_word_times, syllables


@pytest.mark.parametrize("word,expected", [("a", 1), ("gym", 1), ("muscle", 2), ("anatomy", 4)])
def test_syllable_counts(word, expected):
    assert syllables(word) == expected


def test_word_times_span_the_full_duration():
    words = estimate_word_times("one two three four five", 5.0)
    assert len(words) == 5
    assert words[0].start == 0.0
    assert words[-1].end == pytest.approx(5.0, abs=0.01)


def test_word_times_are_monotonic():
    words = estimate_word_times("This is a sentence. And another one here.", 8.0)
    for earlier, later in zip(words, words[1:]):
        assert earlier.end <= later.start + 1e-6
        assert earlier.start < earlier.end


def test_punctuation_buys_extra_time():
    plain = estimate_word_times("go go", 2.0)
    stopped = estimate_word_times("go. go", 2.0)
    assert (stopped[0].end - stopped[0].start) > (plain[0].end - plain[0].start)


def test_empty_text_yields_no_words():
    assert estimate_word_times("", 5.0) == []
    assert estimate_word_times("hello", 0.0) == []


def test_estimate_duration_scales_with_speed():
    text = "You have been doing squats wrong your entire life."
    assert estimate_duration(text, speed=1.5) < estimate_duration(text, speed=1.0)


def test_beats_tile_the_timeline_without_gaps():
    beats = [Beat(text=t, visual="v") for t in ("One two.", "Three four five.", "Six.")]
    words = estimate_word_times(" ".join(b.text for b in beats), 9.0)
    assign_beat_times(beats, words, 9.0)

    assert beats[0].start == 0.0
    assert beats[-1].end == pytest.approx(9.0, abs=0.01)
    for earlier, later in zip(beats, beats[1:]):
        assert earlier.end == later.start   # no frozen frames between beats


def test_beats_fall_back_to_length_split_without_word_data():
    beats = [Beat(text="short", visual="v"), Beat(text="a much longer line here", visual="v")]
    assign_beat_times(beats, [], 10.0)
    assert beats[0].end == pytest.approx(beats[0].start + 10.0 * (1 / 6), abs=0.01)
    assert beats[-1].end == pytest.approx(10.0, abs=0.01)
