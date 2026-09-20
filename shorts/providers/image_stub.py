"""Offline image provider.

Paints a moody placeholder frame — dark gradient, vignette, a suggestion of a
figure — so the pipeline produces something that *reads* like the real look
without a paid image model. Deterministic per prompt, so reruns are stable.
"""

from __future__ import annotations

import math
import random
from pathlib import Path

from ..config import Config
from ..util import ensure_dir, ffmpeg, stable_seed


def _palette(rng: random.Random) -> tuple[tuple[int, int, int], tuple[int, int, int]]:
    """A cold base and a warm accent — the look's whole colour story."""
    base = rng.choice([(14, 20, 26), (10, 16, 22), (18, 22, 24), (8, 14, 20)])
    accent = rng.choice([(214, 126, 44), (232, 158, 62), (198, 96, 40), (240, 180, 90)])
    return base, accent


def _render_pil(prompt: str, out_path: Path, width: int, height: int, seed: int) -> bool:
    try:
        from PIL import Image, ImageDraw, ImageFilter
    except ImportError:
        return False

    rng = random.Random(seed)
    base, accent = _palette(rng)
    img = Image.new("RGB", (width, height), base)
    draw = ImageDraw.Draw(img, "RGBA")

    # Key light: an off-centre warm bloom, the single source everything reads from.
    lx, ly = rng.uniform(0.25, 0.75) * width, rng.uniform(0.18, 0.45) * height
    for radius in range(int(min(width, height) * 0.6), 0, -18):
        alpha = int(40 * (1 - radius / (min(width, height) * 0.6)) ** 2)
        draw.ellipse(
            [lx - radius, ly - radius, lx + radius, ly + radius],
            fill=(*accent, max(0, alpha)),
        )

    # God rays fanning from the key light.
    for _ in range(rng.randint(4, 8)):
        angle = rng.uniform(0.4, 2.7)
        spread = rng.uniform(0.03, 0.09)
        length = max(width, height) * 1.4
        draw.polygon(
            [
                (lx, ly),
                (lx + math.cos(angle - spread) * length, ly + math.sin(angle - spread) * length),
                (lx + math.cos(angle + spread) * length, ly + math.sin(angle + spread) * length),
            ],
            fill=(*accent, rng.randint(8, 20)),
        )

    # A silhouetted figure, small against the frame — the monumental-scale cue.
    fw = width * rng.uniform(0.07, 0.13)
    fh = fw * rng.uniform(3.0, 4.2)
    fx, fy = width * rng.uniform(0.3, 0.7), height * rng.uniform(0.62, 0.8)
    draw.ellipse([fx - fw * 0.32, fy - fh, fx + fw * 0.32, fy - fh * 0.76], fill=(0, 0, 0, 255))
    draw.polygon(
        [
            (fx - fw * 0.5, fy),
            (fx - fw * 0.42, fy - fh * 0.78),
            (fx + fw * 0.42, fy - fh * 0.78),
            (fx + fw * 0.5, fy),
        ],
        fill=(0, 0, 0, 255),
    )

    img = img.filter(ImageFilter.GaussianBlur(radius=max(2, width // 260)))

    # Vignette — crushes the edges the way the reference look does.
    vignette = Image.new("L", (width, height), 0)
    vdraw = ImageDraw.Draw(vignette)
    vdraw.ellipse(
        [-width * 0.25, -height * 0.18, width * 1.25, height * 1.18], fill=255
    )
    vignette = vignette.filter(ImageFilter.GaussianBlur(radius=min(width, height) // 6))
    img = Image.composite(img, Image.new("RGB", (width, height), (0, 0, 0)), vignette)

    ensure_dir(out_path.parent)
    img.save(out_path, quality=94)
    return True


def _render_ffmpeg(out_path: Path, width: int, height: int, seed: int) -> None:
    """Last-resort placeholder when Pillow isn't installed."""
    ensure_dir(out_path.parent)
    ffmpeg([
        "-f", "lavfi",
        "-i", f"gradients=s={width}x{height}:c0=0x0e1a22:c1=0xd67e2c:seed={seed % 65535}:nb_colors=2",
        "-frames:v", "1",
        "-vf", "vignette=PI/3.2,noise=alls=7:allf=t",
        str(out_path),
    ])


class StubImageProvider:
    def render(self, prompt: str, out_path: Path, config: Config, *, seed: int = 0) -> Path:
        width = int(config.get("visual.width", 1080))
        height = int(config.get("visual.height", 1920))
        # Generate square-ish source art; the renderer crops it into the panel.
        art_h = int(height * 0.62)
        resolved_seed = seed or stable_seed(prompt)
        if not _render_pil(prompt, out_path, width, art_h, resolved_seed):
            _render_ffmpeg(out_path, width, art_h, resolved_seed)
        return out_path
