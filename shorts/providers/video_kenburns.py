"""The free fallback: pan and zoom across a still.

Honest about what it is — a moving camera over a static image. It cannot look
like real animation, because nothing in the frame actually moves. Use it to
prototype timing and captions cheaply, then switch `providers.video` to a real
image-to-video model for anything you intend to publish.
"""

from __future__ import annotations

from pathlib import Path

from ..config import Config
from ..models import Beat


class KenBurnsVideoProvider:
    needs_image = True
    # Renders straight to the beat length, so it needs no conforming pass.
    exact_duration = True

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
        # Imported here to keep the provider layer free of render internals at
        # import time (render imports config, config imports nothing circular).
        from ..render import _panel_sizes, render_beat_segment

        width, height, top = _panel_sizes(config)
        panel_h = top or height
        beat = Beat(text="", visual=prompt, motion=motion, start=0.0, end=duration)
        return render_beat_segment(beat, image, out_path, config, (width, panel_h))
