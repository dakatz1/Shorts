"""Image generation via the OpenAI images endpoint.

Included as an alternative backend — it renders a cleaner, more illustrative
frame than the Flux-style models, which suits scripts that lean comedic rather
than ominous.
"""

from __future__ import annotations

import base64
from pathlib import Path

import requests

from ..config import Config
from ..prompting import build_image_prompt
from ..util import ensure_dir, env

ENDPOINT = "https://api.openai.com/v1/images/generations"
DEFAULT_MODEL = "gpt-image-1"


class OpenAIImageProvider:
    def render(self, prompt: str, out_path: Path, config: Config, *, seed: int = 0) -> Path:
        api_key = env("OPENAI_API_KEY", required=True)
        response = requests.post(
            ENDPOINT,
            headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
            json={
                "model": str(config.get("providers.image_model", DEFAULT_MODEL)),
                "prompt": build_image_prompt(prompt, config),
                "size": "1024x1536",
                "n": 1,
            },
            timeout=240,
        )
        if response.status_code == 401:
            raise RuntimeError("OpenAI rejected the key (401). Check OPENAI_API_KEY.")
        if response.status_code == 400:
            raise RuntimeError(f"OpenAI rejected the prompt (400): {response.text[:300]}")
        response.raise_for_status()

        item = response.json()["data"][0]
        ensure_dir(out_path.parent)
        if item.get("b64_json"):
            out_path.write_bytes(base64.b64decode(item["b64_json"]))
        else:
            image = requests.get(item["url"], timeout=120)
            image.raise_for_status()
            out_path.write_bytes(image.content)
        return out_path
