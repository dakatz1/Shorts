"""Offline scriptwriter.

Assembles a structurally correct script from templates so the full pipeline —
timing, captions, render, upload metadata — can be exercised without an API
key. The output is intentionally serviceable rather than funny; swap in the
anthropic provider for real writing.
"""

from __future__ import annotations

import random

from ..config import Config
from ..ideas import VISUAL_MOTIFS, MOTIONS
from ..models import Beat, Idea, Script

HOOKS = [
    "STOP TRAINING LEGS",
    "THEY LIED TO YOU",
    "DELETE YOUR PROGRAM",
    "THIS IS WHY YOU'RE SMALL",
    "NOBODY TELLS YOU THIS",
]

AUTHORITY = [
    "Every trainer you have ever paid knew this and said nothing.",
    "The fitness industry has buried this finding for eleven years.",
    "Coaches are contractually forbidden from explaining what happens next.",
    "A study of four thousand people was quietly withdrawn last spring.",
]

MECHANISM = [
    "The muscle only responds once you stop overwhelming the fibre signal.",
    "Low volume forces the body into emergency growth mode. That is the whole mechanism.",
    "Your nervous system caps growth until you train under the threshold.",
    "Fewer reps means a higher density of what researchers call load memory.",
]

ESCALATION = [
    "Week one you will notice your sleeves getting tight.",
    "By day nine your training partners will start asking questions.",
    "Most people stop because the growth becomes difficult to explain.",
    "Nothing else in training comes close to this rate of change.",
]


class StubScriptProvider:
    """A deterministic, offline stand-in for a real scriptwriting model."""

    def write(self, idea: Idea, config: Config) -> Script:
        rng = random.Random(idea.seed)
        beat_count = max(3, int(config.get("content.beats", 5)))

        lines: list[str] = [
            f"You have been doing {idea.exercise} wrong your entire life.",
            rng.choice(AUTHORITY),
            rng.choice(MECHANISM),
        ]
        while len(lines) < beat_count - 1:
            remaining = [e for e in ESCALATION if e not in lines]
            lines.append(rng.choice(remaining or ESCALATION))
        lines.append(f"{idea.claim} {idea.bait}")

        motifs = rng.sample(VISUAL_MOTIFS, k=min(len(lines), len(VISUAL_MOTIFS)))
        while len(motifs) < len(lines):
            motifs.append(rng.choice(VISUAL_MOTIFS))

        beats = [
            Beat(text=text, visual=motifs[i], motion=rng.choice(MOTIONS))
            for i, text in enumerate(lines[:beat_count])
        ]

        mode = str(config.get("content.mode", "satire")).lower()
        return Script(
            title=idea.claim.rstrip("."),
            hook=rng.choice(HOOKS),
            beats=beats,
            description=f"{idea.claim} Here is what actually happens.",
            tags=[
                "shorts", "fitness", "gym", idea.exercise.replace(" ", ""),
                idea.body_part.replace(" ", ""), "workout", "gymtok", "satire",
            ],
            idea=idea,
            disclaimer=str(config.get("content.disclaimer", "")) if mode == "satire" else "",
        )
