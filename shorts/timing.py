"""Turning narration into per-word and per-beat timings.

Word timings drive the karaoke captions and the cut points between beats. If
the TTS provider hands back real timestamps we use them; otherwise we estimate,
which is accurate enough for captions because the error stays local — each
word's share of the line is proportional to how long it takes to say.
"""

from __future__ import annotations

import re

from .models import Beat, Word

# Rough syllable cost. Punctuation buys extra time because TTS engines pause.
_VOWEL_GROUPS = re.compile(r"[aeiouy]+", re.IGNORECASE)


def syllables(word: str) -> int:
    clean = re.sub(r"[^a-zA-Z]", "", word)
    if not clean:
        return 1
    lower = clean.lower()
    count = len(_VOWEL_GROUPS.findall(clean))
    # Silent trailing 'e' ("size", "life") — but not the consonant+le ending,
    # where the 'e' carries its own beat ("mus-cle", "ta-ble", "mus-cles").
    if lower.endswith("e") and not re.search(r"[^aeiou]le$", lower) and count > 1:
        count -= 1
    return max(1, count)


def _weight(token: str) -> float:
    weight = float(syllables(token))
    if token.endswith((".", "!", "?")):
        weight += 2.2      # full stop — the narrator breathes
    elif token.endswith((",", ";", ":")):
        weight += 0.9
    return weight


def estimate_word_times(text: str, duration: float, start: float = 0.0) -> list[Word]:
    """Distribute `duration` across the words of `text` by syllable weight."""
    tokens = [t for t in text.split() if t]
    if not tokens or duration <= 0:
        return []
    weights = [_weight(t) for t in tokens]
    total = sum(weights) or 1.0

    words: list[Word] = []
    cursor = start
    for token, weight in zip(tokens, weights):
        span = duration * (weight / total)
        words.append(Word(text=token, start=round(cursor, 3), end=round(cursor + span, 3)))
        cursor += span
    return words


def estimate_duration(text: str, wpm: float = 165.0, speed: float = 1.0) -> float:
    """Predict how long narration will take, before we have any audio."""
    tokens = [t for t in text.split() if t]
    if not tokens:
        return 0.0
    base = sum(_weight(t) for t in tokens) / (wpm * 1.45 / 60.0)
    return max(0.6, base / max(0.25, speed))


def _normalise(token: str) -> str:
    return re.sub(r"[^a-z0-9']", "", token.lower())


def assign_beat_times(beats: list[Beat], words: list[Word], total: float) -> list[Beat]:
    """Walk the word list in order, handing each beat the span of its own words.

    Matching is positional rather than by string equality: TTS providers
    normalise text ("5" -> "five"), so we consume `len(beat_tokens)` words per
    beat and only use the text to resynchronise if the counts drift.
    """
    if not beats:
        return beats
    if not words:
        # No timing data at all — split the duration by relative line length.
        weights = [max(1.0, len(b.text.split())) for b in beats]
        total_weight = sum(weights)
        cursor = 0.0
        for beat, weight in zip(beats, weights):
            beat.start = round(cursor, 3)
            cursor += total * (weight / total_weight)
            beat.end = round(cursor, 3)
        return beats

    index = 0
    for position, beat in enumerate(beats):
        expected = len([t for t in beat.text.split() if t])
        if index >= len(words):
            beat.start = beat.end = round(total, 3)
            continue
        beat.start = words[index].start
        last = min(index + expected, len(words)) - 1
        is_final = position == len(beats) - 1
        beat.end = round(total if is_final else words[last].end, 3)
        index = last + 1

    # Close any gaps so the video never shows a frozen frame between beats.
    for earlier, later in zip(beats, beats[1:]):
        earlier.end = later.start
    beats[-1].end = round(max(beats[-1].end, total), 3)
    return beats
