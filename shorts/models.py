"""Dataclasses that move between pipeline stages.

The whole pipeline is a chain of pure-ish transforms over these objects, so any
stage can be run standalone and its output inspected as JSON on disk.
"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any


@dataclass
class Idea:
    """A single content premise, before any script exists."""

    claim: str                    # the bogus assertion, e.g. "5 squats a day doubles leg size"
    exercise: str                 # what the b-roll should show
    body_part: str
    angle: str                    # the rhetorical framing (see ideas.ANGLES)
    bait: str                     # the comment-farming line
    seed: int = 0

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class Beat:
    """One narrated line plus the visual that runs under it."""

    text: str                     # what the narrator says (also the caption source)
    visual: str                   # image/animation prompt for this beat
    motion: str = "push_in"       # push_in | pull_out | pan_left | pan_right | shake
    start: float = 0.0            # filled in after TTS alignment
    end: float = 0.0

    @property
    def duration(self) -> float:
        return max(0.0, self.end - self.start)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class Word:
    """Word-level timing used to build karaoke captions."""

    text: str
    start: float
    end: float

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class Script:
    """A complete, ready-to-render short."""

    title: str                    # YouTube title
    hook: str                     # the on-screen text that holds the first 2 seconds
    beats: list[Beat]
    description: str = ""
    tags: list[str] = field(default_factory=list)
    idea: Idea | None = None
    disclaimer: str = ""

    @property
    def narration(self) -> str:
        return " ".join(b.text.strip() for b in self.beats if b.text.strip())

    def to_dict(self) -> dict[str, Any]:
        return {
            "title": self.title,
            "hook": self.hook,
            "description": self.description,
            "tags": self.tags,
            "disclaimer": self.disclaimer,
            "idea": self.idea.to_dict() if self.idea else None,
            "beats": [b.to_dict() for b in self.beats],
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "Script":
        idea = Idea(**data["idea"]) if data.get("idea") else None
        beats = [Beat(**b) for b in data.get("beats", [])]
        return cls(
            title=data["title"],
            hook=data.get("hook", ""),
            beats=beats,
            description=data.get("description", ""),
            tags=list(data.get("tags", [])),
            idea=idea,
            disclaimer=data.get("disclaimer", ""),
        )

    def save(self, path: Path) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(self.to_dict(), indent=2, ensure_ascii=False), encoding="utf-8")

    @classmethod
    def load(cls, path: Path) -> "Script":
        return cls.from_dict(json.loads(Path(path).read_text(encoding="utf-8")))


@dataclass
class VoiceTrack:
    """TTS output plus whatever timing information the provider gave us."""

    audio_path: Path
    duration: float
    words: list[Word] = field(default_factory=list)


@dataclass
class RenderResult:
    video_path: Path
    thumbnail_path: Path | None
    script: Script
    duration: float
    workdir: Path
