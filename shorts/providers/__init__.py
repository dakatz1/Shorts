"""Pluggable backends for scripting, voice and imagery."""

from .registry import get_image_provider, get_script_provider, get_voice_provider

__all__ = ["get_script_provider", "get_voice_provider", "get_image_provider"]
