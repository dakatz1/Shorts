"""Small shared helpers: logging, shell-outs, slugs, deterministic seeds."""

from __future__ import annotations

import hashlib
import json
import logging
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Any, Sequence

log = logging.getLogger("shorts")


def setup_logging(verbose: bool = False) -> None:
    logging.basicConfig(
        level=logging.DEBUG if verbose else logging.INFO,
        format="%(asctime)s %(levelname)-7s %(name)s: %(message)s",
        datefmt="%H:%M:%S",
        stream=sys.stderr,
    )


def slugify(text: str, max_len: int = 60) -> str:
    s = re.sub(r"[^a-zA-Z0-9]+", "-", text.lower()).strip("-")
    return s[:max_len].strip("-") or "untitled"


def stable_seed(*parts: Any) -> int:
    """A reproducible integer seed derived from arbitrary values."""
    blob = json.dumps(parts, sort_keys=True, default=str).encode()
    return int.from_bytes(hashlib.sha256(blob).digest()[:4], "big")


def require_binary(name: str) -> str:
    path = shutil.which(name)
    if not path:
        raise RuntimeError(
            f"'{name}' is not installed or not on PATH. "
            f"Install it (macOS: brew install {name}; Debian/Ubuntu: apt install {name})."
        )
    return path


def run(cmd: Sequence[str], *, quiet: bool = True, cwd: Path | None = None) -> str:
    """Run a subprocess, raising with captured output on failure."""
    log.debug("exec: %s", " ".join(str(c) for c in cmd))
    proc = subprocess.run(
        [str(c) for c in cmd],
        cwd=str(cwd) if cwd else None,
        capture_output=True,
        text=True,
    )
    if proc.returncode != 0:
        tail = (proc.stderr or proc.stdout or "").strip().splitlines()[-25:]
        raise RuntimeError(
            f"command failed ({proc.returncode}): {' '.join(str(c) for c in cmd[:4])} ...\n"
            + "\n".join(tail)
        )
    if not quiet and proc.stdout:
        log.info(proc.stdout.strip())
    return proc.stdout


def ffmpeg(args: Sequence[str]) -> str:
    """Run ffmpeg with sane global flags."""
    return run([require_binary("ffmpeg"), "-hide_banner", "-loglevel", "error", "-y", *args])


def ffprobe_duration(path: Path) -> float:
    out = run(
        [
            require_binary("ffprobe"),
            "-v", "error",
            "-show_entries", "format=duration",
            "-of", "default=noprint_wrappers=1:nokey=1",
            str(path),
        ]
    )
    try:
        return float(out.strip())
    except ValueError as exc:  # pragma: no cover - malformed media
        raise RuntimeError(f"could not read duration of {path}") from exc


def load_dotenv(path: Path = Path(".env")) -> None:
    """Minimal .env loader so we don't need python-dotenv as a dependency."""
    if not path.exists():
        return
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        if key and key not in os.environ:
            os.environ[key] = value


def env(name: str, *, required: bool = False, default: str | None = None) -> str | None:
    value = os.environ.get(name) or default
    if required and not value:
        raise RuntimeError(
            f"environment variable {name} is not set. Add it to your .env "
            f"(see .env.example) or export it in your shell."
        )
    return value


def ensure_dir(path: Path) -> Path:
    path.mkdir(parents=True, exist_ok=True)
    return path


def write_json(path: Path, data: Any) -> None:
    ensure_dir(path.parent)
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")


def find_font(preferred: str | None = None) -> str:
    """Locate a usable TTF. Falls back through common system paths."""
    candidates = [
        preferred,
        "assets/fonts/caption.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
        "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf",
        "/System/Library/Fonts/Supplemental/Arial Bold.ttf",
        "/usr/share/fonts/truetype/freefont/FreeSansBold.ttf",
        "C:/Windows/Fonts/arialbd.ttf",
    ]
    for c in candidates:
        if c and Path(c).exists():
            return str(Path(c).resolve())
    raise RuntimeError(
        "No caption font found. Drop a .ttf at assets/fonts/caption.ttf "
        "(a heavy sans like Montserrat ExtraBold reads best on Shorts)."
    )
