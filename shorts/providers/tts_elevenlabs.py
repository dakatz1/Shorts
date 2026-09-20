"""ElevenLabs voiceover, with real word-level timestamps.

Uses the `with-timestamps` endpoint, which returns character-level alignment
alongside the audio. Character alignment collapses to word alignment cleanly and
is far better than estimation for karaoke captions.
"""

from __future__ import annotations

import base64
import json
from pathlib import Path

import requests

from ..config import Config
from ..models import VoiceTrack, Word
from ..timing import estimate_word_times
from ..util import ensure_dir, env, ffmpeg, ffprobe_duration, log

API_ROOT = "https://api.elevenlabs.io/v1"
TIMEOUT = 180


def _words_from_alignment(text: str, alignment: dict) -> list[Word]:
    """Collapse per-character timings into per-word spans."""
    chars = alignment.get("characters") or []
    starts = alignment.get("character_start_times_seconds") or []
    ends = alignment.get("character_end_times_seconds") or []
    if not chars or len(chars) != len(starts) or len(chars) != len(ends):
        return []

    words: list[Word] = []
    buf, start, end = "", None, None
    for ch, cs, ce in zip(chars, starts, ends):
        if ch.isspace():
            if buf:
                words.append(Word(text=buf, start=round(start, 3), end=round(end, 3)))
                buf, start, end = "", None, None
            continue
        if not buf:
            start = cs
        buf += ch
        end = ce
    if buf:
        words.append(Word(text=buf, start=round(start, 3), end=round(end, 3)))
    return words


class ElevenLabsVoiceProvider:
    def speak(self, text: str, out_path: Path, config: Config) -> VoiceTrack:
        api_key = env("ELEVENLABS_API_KEY", required=True)
        voice_id = env("ELEVENLABS_VOICE_ID") or str(config.get("voice.voice_id", "") or "")
        if not voice_id:
            raise RuntimeError(
                "no ElevenLabs voice selected. Set ELEVENLABS_VOICE_ID in .env "
                "(find IDs at https://elevenlabs.io/app/voice-library)."
            )

        ensure_dir(out_path.parent)
        response = requests.post(
            f"{API_ROOT}/text-to-speech/{voice_id}/with-timestamps",
            headers={"xi-api-key": api_key, "Content-Type": "application/json"},
            json={
                "text": text,
                "model_id": str(config.get("voice.model_id", "eleven_multilingual_v2")),
                "voice_settings": {
                    "stability": float(config.get("voice.stability", 0.4)),
                    "similarity_boost": float(config.get("voice.similarity_boost", 0.75)),
                    "speed": float(config.get("voice.speed", 1.0)),
                },
            },
            timeout=TIMEOUT,
        )
        if response.status_code == 401:
            raise RuntimeError("ElevenLabs rejected the API key (401). Check ELEVENLABS_API_KEY.")
        if response.status_code == 422:
            raise RuntimeError(f"ElevenLabs rejected the request (422): {response.text[:300]}")
        response.raise_for_status()

        payload = response.json()
        mp3 = out_path.with_suffix(".mp3")
        mp3.write_bytes(base64.b64decode(payload["audio_base64"]))
        ffmpeg(["-i", str(mp3), "-ar", "44100", "-ac", "2", str(out_path)])
        mp3.unlink(missing_ok=True)

        duration = ffprobe_duration(out_path)
        words = _words_from_alignment(text, payload.get("alignment") or {})
        if not words:
            log.warning("ElevenLabs returned no alignment; estimating caption timings")
            words = estimate_word_times(text, duration)
        return VoiceTrack(audio_path=out_path, duration=duration, words=words)
