"""Maps config strings like `providers.tts: elevenlabs` to implementations.

Imports are deferred so that a missing optional dependency only breaks the
provider that needs it, not the whole CLI.
"""

from __future__ import annotations

from typing import Any

from ..config import Config


def _unknown(kind: str, name: str, known: list[str]) -> Any:
    raise ValueError(
        f"unknown {kind} provider {name!r}. Known: {', '.join(sorted(known))}. "
        f"Set it under `providers:` in your config."
    )


def get_script_provider(config: Config) -> Any:
    name = str(config.get("providers.llm", "stub")).lower()
    if name == "stub":
        from .llm_stub import StubScriptProvider

        return StubScriptProvider()
    if name == "anthropic":
        from .llm_anthropic import AnthropicScriptProvider

        return AnthropicScriptProvider()
    return _unknown("script", name, ["stub", "anthropic"])


def get_voice_provider(config: Config) -> Any:
    name = str(config.get("providers.tts", "stub")).lower()
    if name == "stub":
        from .tts_offline import SilentVoiceProvider

        return SilentVoiceProvider()
    if name in {"say", "espeak", "offline"}:
        from .tts_offline import SystemVoiceProvider

        return SystemVoiceProvider(engine=name)
    if name == "elevenlabs":
        from .tts_elevenlabs import ElevenLabsVoiceProvider

        return ElevenLabsVoiceProvider()
    return _unknown("tts", name, ["stub", "say", "espeak", "elevenlabs"])


def get_image_provider(config: Config) -> Any:
    name = str(config.get("providers.image", "stub")).lower()
    if name == "stub":
        from .image_stub import StubImageProvider

        return StubImageProvider()
    if name == "replicate":
        from .image_replicate import ReplicateImageProvider

        return ReplicateImageProvider()
    if name == "openai":
        from .image_openai import OpenAIImageProvider

        return OpenAIImageProvider()
    return _unknown("image", name, ["stub", "replicate", "openai"])
