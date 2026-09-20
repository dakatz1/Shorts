"""Voice providers that need no API key.

`SilentVoiceProvider` renders a correctly-timed silent track so the rest of the
pipeline (cuts, captions, duration) can be exercised offline. `SystemVoiceProvider`
uses whatever the OS ships — macOS `say` or `espeak` — which sounds rough but is
free and real.
"""

from __future__ import annotations

import shutil
from pathlib import Path

from ..config import Config
from ..models import VoiceTrack
from ..timing import estimate_duration, estimate_word_times
from ..util import ensure_dir, ffmpeg, ffprobe_duration, log, run


class SilentVoiceProvider:
    """Silence of the right length, with estimated word timings."""

    def speak(self, text: str, out_path: Path, config: Config) -> VoiceTrack:
        speed = float(config.get("voice.speed", 1.0))
        duration = estimate_duration(text, speed=speed)
        ensure_dir(out_path.parent)
        ffmpeg([
            "-f", "lavfi",
            "-i", f"anullsrc=channel_layout=stereo:sample_rate=44100",
            "-t", f"{duration:.3f}",
            str(out_path),
        ])
        return VoiceTrack(
            audio_path=out_path,
            duration=duration,
            words=estimate_word_times(text, duration),
        )


class SystemVoiceProvider:
    """macOS `say` or Linux `espeak`/`espeak-ng`."""

    def __init__(self, engine: str = "offline") -> None:
        self.engine = engine

    def _resolve(self) -> str:
        if self.engine == "say" or (self.engine == "offline" and shutil.which("say")):
            if shutil.which("say"):
                return "say"
        for candidate in ("espeak-ng", "espeak"):
            if shutil.which(candidate):
                return candidate
        raise RuntimeError(
            "no offline TTS engine found. Install espeak-ng (apt install espeak-ng), "
            "use macOS, or switch providers.tts to 'elevenlabs'."
        )

    def speak(self, text: str, out_path: Path, config: Config) -> VoiceTrack:
        engine = self._resolve()
        ensure_dir(out_path.parent)
        speed = float(config.get("voice.speed", 1.0))

        if engine == "say":
            aiff = out_path.with_suffix(".aiff")
            run(["say", "-r", str(int(175 * speed)), "-o", str(aiff), text])
            ffmpeg(["-i", str(aiff), str(out_path)])
            aiff.unlink(missing_ok=True)
        else:
            wav = out_path.with_suffix(".raw.wav")
            run([engine, "-s", str(int(165 * speed)), "-w", str(wav), text])
            ffmpeg(["-i", str(wav), str(out_path)])
            wav.unlink(missing_ok=True)

        duration = ffprobe_duration(out_path)
        log.debug("%s produced %.2fs of audio", engine, duration)
        # Neither engine reports timestamps, so estimate against the real duration.
        return VoiceTrack(
            audio_path=out_path,
            duration=duration,
            words=estimate_word_times(text, duration),
        )
