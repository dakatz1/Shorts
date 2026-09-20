"""Piper — a free, offline neural voice.

Much better than espeak and still costs nothing, which matters when every short
is a few cents of API spend already. The voice model is ~60MB, downloaded once
and cached; GitHub Actions caches it between runs.
"""

from __future__ import annotations

import shutil
import subprocess
import sys
from pathlib import Path

from ..config import Config
from ..models import VoiceTrack
from ..timing import estimate_word_times
from ..util import ensure_dir, ffmpeg, ffprobe_duration, log, run

DEFAULT_VOICE = "en_US-lessac-medium"


def voice_dir(config: Config) -> Path:
    return ensure_dir(Path(str(config.get("voice.piper_dir", "cache/piper"))))


def ensure_voice(config: Config) -> Path:
    """Download the voice model if we don't already have it."""
    name = str(config.get("voice.piper_voice", DEFAULT_VOICE))
    directory = voice_dir(config)
    model = directory / f"{name}.onnx"
    if model.exists() and model.stat().st_size > 0:
        return model

    log.info("downloading piper voice %s (once)", name)
    run([sys.executable, "-m", "piper.download_voices", name, "--download-dir", str(directory)])
    if not model.exists():
        raise RuntimeError(f"piper voice {name!r} did not download to {model}")
    return model


class PiperVoiceProvider:
    def speak(self, text: str, out_path: Path, config: Config) -> VoiceTrack:
        if shutil.which("piper") is None:
            raise RuntimeError(
                "piper is not installed. Run: pip install piper-tts "
                "(or set providers.tts to 'espeak' / 'elevenlabs')."
            )
        model = ensure_voice(config)
        ensure_dir(out_path.parent)
        raw = out_path.with_suffix(".piper.wav")

        # piper's length_scale is inverse to speed: >1 is slower.
        speed = max(0.5, float(config.get("voice.speed", 1.0)))
        subprocess.run(
            [
                "piper",
                "-m", str(model),
                "-f", str(raw),
                "--length-scale", f"{1.0 / speed:.3f}",
                "--sentence-silence", str(config.get("voice.sentence_silence", 0.35)),
            ],
            input=text,
            text=True,
            capture_output=True,
            check=True,
        )
        ffmpeg(["-i", str(raw), "-ar", "44100", "-ac", "2", str(out_path)])
        raw.unlink(missing_ok=True)

        duration = ffprobe_duration(out_path)
        # Piper reports no timestamps, so captions use the syllable estimate
        # against the real audio length.
        return VoiceTrack(
            audio_path=out_path,
            duration=duration,
            words=estimate_word_times(text, duration),
        )
