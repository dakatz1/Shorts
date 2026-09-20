"""OpenAI text-to-speech.

The cheap middle option: far better than espeak, a fraction of ElevenLabs'
price, and it takes voice direction in plain English — which suits a narrator
whose whole job is sounding gravely certain about nonsense.
"""

from __future__ import annotations

from pathlib import Path

import requests

from ..config import Config
from ..models import VoiceTrack
from ..timing import estimate_word_times
from ..util import ensure_dir, env, ffmpeg, ffprobe_duration

ENDPOINT = "https://api.openai.com/v1/audio/speech"
DEFAULT_MODEL = "gpt-4o-mini-tts"
DEFAULT_VOICE = "onyx"


class OpenAIVoiceProvider:
    def speak(self, text: str, out_path: Path, config: Config) -> VoiceTrack:
        api_key = env("OPENAI_API_KEY", required=True)
        payload = {
            "model": str(config.get("voice.openai_model", DEFAULT_MODEL)),
            "voice": str(config.get("voice.openai_voice", DEFAULT_VOICE)),
            "input": text,
            "response_format": "wav",
            "speed": float(config.get("voice.speed", 1.0)),
        }
        # Newer TTS models accept a plain-language delivery note.
        direction = str(config.get("voice.style", "") or "")
        if direction:
            payload["instructions"] = direction

        response = requests.post(
            ENDPOINT,
            headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
            json=payload,
            timeout=180,
        )
        if response.status_code == 401:
            raise RuntimeError("OpenAI rejected the key (401). Check OPENAI_API_KEY.")
        if response.status_code == 400:
            raise RuntimeError(f"OpenAI rejected the request (400): {response.text[:300]}")
        response.raise_for_status()

        ensure_dir(out_path.parent)
        raw = out_path.with_suffix(".openai.wav")
        raw.write_bytes(response.content)
        ffmpeg(["-i", str(raw), "-ar", "44100", "-ac", "2", str(out_path)])
        raw.unlink(missing_ok=True)

        duration = ffprobe_duration(out_path)
        return VoiceTrack(
            audio_path=out_path,
            duration=duration,
            words=estimate_word_times(text, duration),
        )
