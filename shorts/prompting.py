"""Assembles the prompts handed to the script model.

Kept out of the provider so the stub and the real model are briefed identically
and so you can eyeball the exact prompt with `shorts script --show-prompt`.
"""

from __future__ import annotations

from pathlib import Path

from .config import Config
from .ideas import ANGLES
from .models import Idea

PROMPT_DIR = Path("prompts")

MODE_INSTRUCTIONS = {
    "satire": (
        "This is explicit satire. Keep the nonsense loud enough that no "
        "reasonable viewer could mistake it for advice. A visible disclaimer is "
        "burned into the video, so lean into the absurdity rather than hedging."
    ),
    "deadpan": (
        "Play it completely straight. No winking, no disclaimer in the copy. "
        "The claims must still be physically impossible — never write a line "
        "that would function as real, actionable training advice."
    ),
}


def _read(name: str) -> str:
    path = PROMPT_DIR / name
    if not path.exists():
        raise FileNotFoundError(f"prompt template missing: {path}")
    return path.read_text(encoding="utf-8")


def build_system_prompt(config: Config) -> str:
    return _read("script_system.md").format(
        beats=int(config.get("content.beats", 5)),
        voice_style=config.get("voice.style", "urgent documentary narrator"),
    )


def build_user_prompt(idea: Idea, config: Config) -> str:
    mode = str(config.get("content.mode", "satire")).lower()
    return _read("script_user.md").format(
        claim=idea.claim,
        exercise=idea.exercise,
        body_part=idea.body_part,
        angle_instruction=ANGLES.get(idea.angle, ""),
        bait=idea.bait,
        absurdity=int(config.get("content.absurdity", 4)),
        beats=int(config.get("content.beats", 5)),
        mode=mode,
        mode_instruction=MODE_INSTRUCTIONS.get(mode, MODE_INSTRUCTIONS["satire"]),
    )


def image_style_suffix() -> str:
    return " ".join(_read("image_style.md").split())


def build_image_prompt(visual: str, config: Config) -> str:
    preset = str(config.get("visual.style_preset", "cinematic_3d"))
    if preset == "cinematic_3d":
        return f"{visual.strip().rstrip('.')}. {image_style_suffix()}"
    return visual.strip()
