"""The premise generator.

Everything upstream of the script is combinatorial: pick an exercise, pick an
absurd outcome, pick a rhetorical angle, pick a bait line. That gives a large
idea space without an LLM call, and gives the LLM a concrete brief when one is
available — models left to free-associate converge on the same four jokes.
"""

from __future__ import annotations

import random
from dataclasses import dataclass

from .models import Idea

# --- Building blocks -------------------------------------------------------

EXERCISES: list[tuple[str, str]] = [
    ("squats", "legs"),
    ("push-ups", "chest"),
    ("pull-ups", "back"),
    ("calf raises", "calves"),
    ("planks", "core"),
    ("bicep curls", "arms"),
    ("lunges", "glutes"),
    ("burpees", "whole body"),
    ("deadlifts", "posterior chain"),
    ("shoulder presses", "delts"),
    ("jump rope intervals", "conditioning"),
    ("wall sits", "quads"),
    ("dips", "triceps"),
    ("hanging leg raises", "abs"),
    ("farmer's walks", "grip"),
]

# (template, absurdity 1-5, takes a trailing timeframe). {part} = body part.
# The last flag matters: a few outcomes already state their own timing, and
# appending "in nine days" to them produces nonsense like
# "add two inches per week, permanently in one week".
OUTCOMES: list[tuple[str, int, bool]] = [
    ("your {part} will grow by thirty percent", 2, True),
    ("your {part} will literally double in size", 3, True),
    ("you will outgrow every pair of jeans you own", 3, True),
    ("your {part} will add two inches per week, permanently", 4, False),
    ("your body will stop needing the gym entirely", 4, True),
    ("your {part} will grow faster than your bones can keep up with", 5, True),
    ("you will trigger a growth response scientists refuse to name", 5, True),
    ("your {part} will register as a separate organ on a body scan", 5, True),
    ("your metabolism will run at four times the human baseline", 4, True),
    ("you will gain muscle while asleep, indefinitely", 4, False),
]

TIMEFRAMES = ["in one week", "in nine days", "in fourteen days", "by the end of the month",
              "in seventy-two hours", "in one weekend"]

REP_COUNTS = [3, 5, 7, 10, 12, 15, 20, 25]

# How the claim is framed. This is the engine of the rage, not the claim itself:
# people argue with the framing far more than with the number.
ANGLES: dict[str, str] = {
    "suppressed": "Frame it as knowledge the fitness industry actively hides because it "
                  "would bankrupt gyms and supplement companies.",
    "authority_flip": "Frame it as proof that trainers, coaches and 'the science' have been "
                      "confidently wrong for decades.",
    "effort_inversion": "Frame it as proof that doing dramatically LESS outperforms doing more, "
                        "and that hard training is actively counterproductive.",
    "ancient_secret": "Frame it as a rediscovered method used by some historical or "
                      "obviously fictional group who were famously strong.",
    "fake_study": "Cite an invented study with an oddly specific sample size and an "
                  "institution that sounds real but is not.",
    "gatekept_elite": "Frame it as something pro athletes all quietly do and contractually "
                      "cannot talk about.",
}

# The comment-section crowbar. A short is only bait if there is something to
# reply to, and the most reliable reply-driver is a confident wrong instruction
# plus a dare.
BAIT_LINES = [
    "If you think this is wrong, you have never actually tried it.",
    "Comment 'nope' if you're still doing it the slow way.",
    "Half of you will read this and keep wasting your time. That's fine.",
    "Save this before it gets taken down.",
    "Tag someone who still trains six days a week for nothing.",
    "The people arguing in the comments are the people with no results.",
    "Tell me I'm wrong. I'll wait.",
    "Screenshot this and check back in a week.",
]

# Visual beats that suit the cinematic-3D look — used by the stub scriptwriter
# and offered to the LLM as examples.
VISUAL_MOTIFS = [
    "a lone silhouetted figure in a vast dark room, single hard key light from above",
    "an extreme close-up of a straining muscle fibre, volumetric dust in the air",
    "a colossal anatomical statue cracking apart, embers drifting upward",
    "a shadowed laboratory corridor, one flickering monitor at the far end",
    "a figure standing before an impossibly large barbell, god rays behind",
    "a slow orbit around a glowing skeletal figure suspended in blackness",
    "a crowded gym frozen mid-motion, every face in shadow but one",
    "a towering door of frosted glass with a silhouette pressed against it",
]

MOTIONS = ["push_in", "pull_out", "pan_left", "pan_right", "shake"]


@dataclass
class IdeaGenerator:
    """Deterministic when given a seed, so a batch is reproducible."""

    absurdity: int = 4
    seed: int | None = None

    def __post_init__(self) -> None:
        self._rng = random.Random(self.seed)

    def _outcome(self) -> tuple[str, bool]:
        ceiling = max(1, min(5, self.absurdity))
        pool = [(o, tf) for o, level, tf in OUTCOMES if level <= ceiling]
        # Bias toward the top of the allowed range — that's where the bait lives.
        top = [(o, tf) for o, level, tf in OUTCOMES if level == ceiling]
        return self._rng.choice(pool + top * 2)

    def generate(self) -> Idea:
        exercise, part = self._rng.choice(EXERCISES)
        reps = self._rng.choice(REP_COUNTS)
        timeframe = self._rng.choice(TIMEFRAMES)
        template, takes_timeframe = self._outcome()
        outcome = template.format(part=part)
        tail = f" {timeframe}" if takes_timeframe else ""
        claim = f"Do {reps} {exercise} a day and {outcome}{tail}."
        return Idea(
            claim=claim,
            exercise=exercise,
            body_part=part,
            angle=self._rng.choice(list(ANGLES)),
            bait=self._rng.choice(BAIT_LINES),
            seed=self._rng.randrange(2**31),
        )

    def batch(self, count: int) -> list[Idea]:
        """Generate `count` ideas, avoiding repeat exercises where possible."""
        ideas: list[Idea] = []
        used: set[str] = set()
        attempts = 0
        while len(ideas) < count and attempts < count * 20:
            attempts += 1
            idea = self.generate()
            if idea.exercise in used and len(used) < len(EXERCISES):
                continue
            used.add(idea.exercise)
            ideas.append(idea)
        return ideas
