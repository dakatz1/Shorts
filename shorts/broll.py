"""Picking the workout footage that runs under the narration.

This is a local library, not a download tool: you supply the clips and are
responsible for having the right to use them. Selection is deterministic per
script so a rerun produces the same video, and rotates across a batch so ten
shorts don't all use the same squat clip.
"""

from __future__ import annotations

import random
from collections import Counter
from pathlib import Path

from .config import Config
from .util import ensure_dir, ffmpeg, log

VIDEO_SUFFIXES = {".mp4", ".mov", ".m4v", ".webm", ".mkv"}

# Clips whose filename mentions the exercise are preferred — name your files
# like `squats-01.mp4` and selection becomes topical for free.
_usage: Counter[str] = Counter()


def reset_usage() -> None:
    """Clear cross-video rotation state (used between batches and in tests)."""
    _usage.clear()


def library(config: Config) -> list[Path]:
    directory = Path(str(config.get("broll.dir", "assets/broll")))
    if not directory.exists():
        return []
    return sorted(p for p in directory.rglob("*") if p.suffix.lower() in VIDEO_SUFFIXES)


def _score(path: Path, exercise: str, body_part: str) -> int:
    name = path.stem.lower().replace("_", " ").replace("-", " ")
    score = 0
    for token in exercise.lower().split():
        if token in name:
            score += 3
    for token in body_part.lower().split():
        if token in name:
            score += 1
    return score


def make_placeholder(out_path: Path, config: Config, duration: float = 20.0) -> Path:
    """Synthesise stand-in footage so an empty library doesn't block a render."""
    width = int(config.get("visual.width", 1080))
    height = int(config.get("visual.height", 1920))
    ensure_dir(out_path.parent)
    log.warning(
        "b-roll library is empty — generating a placeholder clip. Drop real "
        "workout footage into %s before publishing anything.",
        config.get("broll.dir", "assets/broll"),
    )
    ffmpeg([
        "-f", "lavfi",
        "-i", f"life=s={width // 4}x{height // 4}:mold=10:r={int(config.get('visual.fps', 30))}"
              f":ratio=0.12:death_color=#16212b:life_color=#3d5462",
        "-t", f"{duration:.2f}",
        "-vf", f"scale={width}:{height},boxblur=6:1,eq=brightness=0.03:saturation=0.5,vignette=PI/4",
        "-pix_fmt", "yuv420p",
        str(out_path),
    ])
    return out_path


def pick(config: Config, *, exercise: str = "", body_part: str = "", seed: int = 0,
         cache_dir: Path | None = None) -> Path:
    """Choose the best available clip, falling back to a placeholder."""
    clips = library(config)
    if not clips:
        if not bool(config.get("broll.allow_placeholder", True)):
            raise RuntimeError(
                f"no b-roll found in {config.get('broll.dir')} and "
                "broll.allow_placeholder is false."
            )
        target = (cache_dir or Path("cache")) / "broll_placeholder.mp4"
        if not target.exists():
            make_placeholder(target, config)
        return target

    max_reuse = int(config.get("broll.max_reuse", 2))
    scored = sorted(clips, key=lambda p: (-_score(p, exercise, body_part), p.name))
    best_score = _score(scored[0], exercise, body_part)
    topical = [p for p in scored if _score(p, exercise, body_part) == best_score]

    # Prefer clips we've leaned on least, then break ties deterministically.
    fresh = [p for p in topical if _usage[str(p)] < max_reuse] or topical
    choice = random.Random(seed).choice(sorted(fresh, key=lambda p: (_usage[str(p)], p.name))[: max(1, len(fresh) // 2) or 1])
    _usage[str(choice)] += 1
    log.debug("b-roll: %s (score %d)", choice.name, best_score)
    return choice
