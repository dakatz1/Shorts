"""Pluggable backends for scripting, voice, imagery and animation."""

from .registry import (
    get_image_provider,
    get_script_provider,
    get_video_provider,
    get_voice_provider,
)

__all__ = [
    "get_script_provider",
    "get_voice_provider",
    "get_image_provider",
    "get_video_provider",
]
