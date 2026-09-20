"""Provider interfaces.

Every external service sits behind one of these three protocols. Swapping
ElevenLabs for something else means adding one file and one registry entry —
nothing in the pipeline changes.
"""

from __future__ import annotations

from pathlib import Path
from typing import Protocol, runtime_checkable

from ..config import Config
from ..models import Idea, Script, VoiceTrack


@runtime_checkable
class ScriptProvider(Protocol):
    """Turns an Idea into a fully written Script."""

    def write(self, idea: Idea, config: Config) -> Script: ...


@runtime_checkable
class VoiceProvider(Protocol):
    """Turns narration text into an audio file, ideally with word timings."""

    def speak(self, text: str, out_path: Path, config: Config) -> VoiceTrack: ...


@runtime_checkable
class ImageProvider(Protocol):
    """Turns a visual prompt into a still frame on disk."""

    def render(self, prompt: str, out_path: Path, config: Config, *, seed: int = 0) -> Path: ...
