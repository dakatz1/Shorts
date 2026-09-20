"""Image generation via Replicate.

Replicate is the pragmatic default for this look: the current image models there
handle "cinematic 3D render" prompts well and the API is a single POST plus a
poll. The model slug is config-driven so you can chase whatever is best this
month without touching code.
"""

from __future__ import annotations

import time
from pathlib import Path

import requests

from ..config import Config
from ..prompting import build_image_prompt
from ..util import ensure_dir, env, log

API_ROOT = "https://api.replicate.com/v1"
DEFAULT_MODEL = "black-forest-labs/flux-1.1-pro"
POLL_INTERVAL = 1.5
POLL_TIMEOUT = 240


class ReplicateImageProvider:
    def render(self, prompt: str, out_path: Path, config: Config, *, seed: int = 0) -> Path:
        token = env("REPLICATE_API_TOKEN", required=True)
        model = str(config.get("providers.image_model", DEFAULT_MODEL))
        headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}

        payload = {
            "input": {
                "prompt": build_image_prompt(prompt, config),
                "aspect_ratio": "9:16",
                "output_format": "jpg",
                "output_quality": 92,
                "safety_tolerance": 2,
            }
        }
        if seed:
            payload["input"]["seed"] = seed % (2**31)

        response = requests.post(
            f"{API_ROOT}/models/{model}/predictions",
            headers={**headers, "Prefer": "wait"},
            json=payload,
            timeout=POLL_TIMEOUT,
        )
        if response.status_code == 401:
            raise RuntimeError("Replicate rejected the token (401). Check REPLICATE_API_TOKEN.")
        if response.status_code == 404:
            raise RuntimeError(
                f"Replicate has no model {model!r}. Set providers.image_model to a valid slug."
            )
        response.raise_for_status()
        prediction = response.json()

        deadline = time.time() + POLL_TIMEOUT
        while prediction.get("status") in {"starting", "processing"}:
            if time.time() > deadline:
                raise RuntimeError(f"Replicate prediction timed out after {POLL_TIMEOUT}s")
            time.sleep(POLL_INTERVAL)
            poll = requests.get(prediction["urls"]["get"], headers=headers, timeout=60)
            poll.raise_for_status()
            prediction = poll.json()

        if prediction.get("status") != "succeeded":
            raise RuntimeError(
                f"Replicate prediction {prediction.get('status')}: {prediction.get('error')}"
            )

        output = prediction.get("output")
        url = output[0] if isinstance(output, list) else output
        if not url:
            raise RuntimeError("Replicate returned no image URL")

        log.debug("downloading %s", url)
        image = requests.get(url, timeout=120)
        image.raise_for_status()
        ensure_dir(out_path.parent)
        out_path.write_bytes(image.content)
        return out_path
