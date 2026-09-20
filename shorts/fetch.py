"""Fetching the b-roll library from a URL list.

Committing video into git bloats the repo, and uploading files from a phone is
awkward. Editing a text file on github.com is not. So the library can be
declared as `assets/broll/sources.txt` and materialised at render time.
"""

from __future__ import annotations

import re
from pathlib import Path
from urllib.parse import unquote, urlparse

import requests

from .config import Config
from .util import ensure_dir, log

SOURCES_FILE = "sources.txt"
VIDEO_SUFFIXES = {".mp4", ".mov", ".m4v", ".webm", ".mkv"}
TIMEOUT = 300
MAX_BYTES = 200 * 1024 * 1024


def _parse_line(line: str) -> tuple[str, str] | None:
    """`<url>` or `<url>  <filename>`; blank lines and `#` comments ignored."""
    text = line.split("#", 1)[0].strip()
    if not text:
        return None
    parts = text.split()
    url = parts[0]
    if len(parts) > 1:
        name = parts[1]
    else:
        name = Path(unquote(urlparse(url).path)).name or "clip.mp4"
    if Path(name).suffix.lower() not in VIDEO_SUFFIXES:
        name += ".mp4"
    # Filenames drive b-roll matching, so keep them tidy — and since the name
    # comes from a URL, keep it incapable of escaping the b-roll directory.
    name = re.sub(r"[^A-Za-z0-9._-]+", "-", name)
    name = re.sub(r"\.{2,}", ".", name).strip(".-") or "clip.mp4"
    return url, name


def read_sources(config: Config) -> list[tuple[str, str]]:
    path = Path(str(config.get("broll.dir", "assets/broll"))) / SOURCES_FILE
    if not path.exists():
        return []
    entries: list[tuple[str, str]] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        parsed = _parse_line(line)
        if parsed:
            entries.append(parsed)
    return entries


def fetch_broll(config: Config, *, force: bool = False) -> list[Path]:
    """Download every declared clip that isn't already on disk."""
    directory = ensure_dir(Path(str(config.get("broll.dir", "assets/broll"))))
    entries = read_sources(config)
    if not entries:
        log.info("no %s — nothing to fetch", directory / SOURCES_FILE)
        return []

    fetched: list[Path] = []
    for url, name in entries:
        target = directory / name
        if target.exists() and target.stat().st_size > 0 and not force:
            log.debug("have %s", name)
            fetched.append(target)
            continue
        if not url.lower().startswith(("http://", "https://")):
            log.warning("skipping non-http source: %s", url)
            continue

        log.info("fetching %s", name)
        try:
            with requests.get(url, stream=True, timeout=TIMEOUT) as response:
                response.raise_for_status()
                written = 0
                with target.open("wb") as handle:
                    for chunk in response.iter_content(chunk_size=1 << 20):
                        written += len(chunk)
                        if written > MAX_BYTES:
                            raise RuntimeError(f"{name} exceeds {MAX_BYTES // 1024 // 1024}MB")
                        handle.write(chunk)
        except Exception as exc:
            target.unlink(missing_ok=True)
            log.error("could not fetch %s: %s", name, exc)
            continue
        fetched.append(target)

    log.info("b-roll library: %d clips", len(fetched))
    return fetched
