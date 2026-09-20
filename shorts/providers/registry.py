"""Maps config strings like `providers.tts: elevenlabs` to implementations.

Imports are deferred so that a missing optional dependency only breaks the
provider that needs it, not the whole CLI.
"""

from __future__ import annotations

from typing import Any

from ..config import Config
from ..util import log


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


VOICE_PROVIDERS = ["auto", "stub", "espeak", "say", "piper", "openai", "elevenlabs"]


def _auto_voice_provider(config: Config) -> Any:
    """Best free voice actually available on this machine.

    Order is quality-first: piper (neural, needs a one-off model download),
    then the OS robot voice, then silence. Silence is a real fallback rather
    than an error — a missing voice should not cost you the whole render.
    """
    import shutil

    if shutil.which("piper"):
        try:
            from .tts_piper import PiperVoiceProvider, ensure_voice

            ensure_voice(config)
            return PiperVoiceProvider()
        except Exception as exc:
            log.warning("piper unavailable (%s) — falling back", exc)

    for binary in ("espeak-ng", "espeak", "say"):
        if shutil.which(binary):
            from .tts_offline import SystemVoiceProvider

            return SystemVoiceProvider(engine="say" if binary == "say" else "espeak")

    log.warning(
        "no speech engine found — rendering a silent track. Install piper-tts "
        "or espeak-ng, or set an API key and pick a paid provider."
    )
    from .tts_offline import SilentVoiceProvider

    return SilentVoiceProvider()


def get_voice_provider(config: Config) -> Any:
    name = str(config.get("providers.tts", "auto")).lower()
    if name == "auto":
        return _auto_voice_provider(config)
    if name == "stub":
        from .tts_offline import SilentVoiceProvider

        return SilentVoiceProvider()
    if name in {"say", "espeak", "offline"}:
        from .tts_offline import SystemVoiceProvider

        return SystemVoiceProvider(engine=name)
    if name == "piper":
        from .tts_piper import PiperVoiceProvider

        return PiperVoiceProvider()
    if name == "openai":
        from .tts_openai import OpenAIVoiceProvider

        return OpenAIVoiceProvider()
    if name == "elevenlabs":
        from .tts_elevenlabs import ElevenLabsVoiceProvider

        return ElevenLabsVoiceProvider()
    return _unknown("tts", name, VOICE_PROVIDERS)


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


VIDEO_PROVIDERS = ["kenburns", "replicate"]


def get_video_provider(config: Config) -> Any:
    """How each beat's still becomes a moving shot."""
    name = str(config.get("providers.video", "kenburns")).lower()
    if name in {"kenburns", "stub", "none"}:
        from .video_kenburns import KenBurnsVideoProvider

        return KenBurnsVideoProvider()
    if name == "replicate":
        from .video_replicate import ReplicateVideoProvider

        return ReplicateVideoProvider()
    return _unknown("video", name, VIDEO_PROVIDERS)
