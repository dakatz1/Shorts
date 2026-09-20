"""Image-to-video on Replicate — the thing that makes it look animated.

The pipeline generates a still for each beat, then hands that still plus the
beat's prompt to a video model, which produces a few seconds of actual motion:
the camera moves through the scene, cloth and dust move, the subject shifts.

Model choice matters more than anything else here and moves fast, so the slug
is config-driven (`providers.video_model`). Anything on Replicate that takes an
image and a prompt and returns a video will work; if the input names differ,
add them under `providers.video_input`.
"""

from __future__ import annotations

import base64
import mimetypes
import time
from pathlib import Path

import requests

from ..config import Config
from ..prompting import build_image_prompt
from ..util import ensure_dir, env, log

API_ROOT = "https://api.replicate.com/v1"
DEFAULT_MODEL = "wan-video/wan-2.2-i2v-fast"
POLL_INTERVAL = 3.0
POLL_TIMEOUT = 900


def _data_uri(path: Path) -> str:
    """Replicate accepts a data URI for file inputs, which avoids a separate upload."""
    mime = mimetypes.guess_type(str(path))[0] or "image/jpeg"
    encoded = base64.b64encode(path.read_bytes()).decode()
    return f"data:{mime};base64,{encoded}"


class ReplicateVideoProvider:
    needs_image = True

    def animate(
        self,
        image: Path,
        prompt: str,
        out_path: Path,
        config: Config,
        *,
        duration: float,
        motion: str = "push_in",
        seed: int = 0,
    ) -> Path:
        token = env("REPLICATE_API_TOKEN", required=True)
        model = str(config.get("providers.video_model", DEFAULT_MODEL))
        headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}

        # Most i2v models only generate a fixed set of lengths. Ask for the
        # nearest supported one and let the renderer fit it to the beat.
        options = config.get("providers.video_durations", [5]) or [5]
        wanted = min(options, key=lambda d: abs(float(d) - duration))

        payload = {
            "input": {
                "image": _data_uri(image),
                "prompt": _motion_prompt(prompt, motion, config),
                "duration": int(wanted),
                "resolution": str(config.get("providers.video_resolution", "480p")),
                **(config.get("providers.video_input") or {}),
            }
        }
        if seed:
            payload["input"]["seed"] = seed % (2**31)

        log.info("animating beat (%s, %ss)", model, wanted)
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
                f"Replicate has no model {model!r}. Set providers.video_model to a "
                "current image-to-video slug (see config/default.yaml for candidates)."
            )
        if response.status_code == 422:
            raise RuntimeError(
                f"Replicate rejected the inputs for {model!r}: {response.text[:300]}\n"
                "Different video models name their inputs differently — add the "
                "right ones under providers.video_input."
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
            raise RuntimeError("Replicate returned no video URL")

        video = requests.get(url, timeout=600)
        video.raise_for_status()
        ensure_dir(out_path.parent)
        out_path.write_bytes(video.content)
        return out_path


# Camera direction, phrased the way video models expect it.
MOTION_PHRASES = {
    "push_in": "slow cinematic dolly push in toward the subject",
    "pull_out": "slow cinematic dolly pull back revealing the scene",
    "pan_left": "slow camera pan to the left",
    "pan_right": "slow camera pan to the right",
    "shake": "tense handheld camera with subtle shake",
}


def _motion_prompt(prompt: str, motion: str, config: Config) -> str:
    camera = MOTION_PHRASES.get(motion, MOTION_PHRASES["push_in"])
    base = build_image_prompt(prompt, config)
    return f"{base} Camera: {camera}. Subtle natural movement, drifting haze and dust."
