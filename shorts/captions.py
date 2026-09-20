"""Burned-in captions as an ASS subtitle file.

Shorts are watched muted, so the captions are the content. We emit one
Dialogue line per word: the whole group is on screen, and the word currently
being spoken is tinted. That reads as karaoke without needing \\k tags, and it
survives libass version differences.
"""

from __future__ import annotations

import subprocess
from dataclasses import dataclass
from pathlib import Path

from .config import Config
from .models import Script, Word
from .util import ensure_dir, find_font, log

ASS_HEADER = """[Script Info]
ScriptType: v4.00+
PlayResX: {width}
PlayResY: {height}
WrapStyle: 0
ScaledBorderAndShadow: yes
YCbCr Matrix: TV.601

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: Caption,{font},{size},{primary},&H000000FF,&H00000000,&H64000000,-1,0,0,0,100,100,0,0,1,{outline},{shadow},2,{margin_h},{margin_h},{margin_v},1
Style: Hook,{font},{hook_size},{primary},&H000000FF,&H00000000,&H64000000,-1,0,0,0,100,100,1,0,1,{hook_outline},{shadow},8,{margin_h},{margin_h},{hook_margin_v},1
Style: Disclaimer,{font},34,&H00B4B4B4,&H000000FF,&H00000000,&H96000000,0,0,0,0,100,100,0,0,1,2,0,2,40,40,40,1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
"""


def _ts(seconds: float) -> str:
    seconds = max(0.0, seconds)
    hours, rest = divmod(seconds, 3600)
    minutes, secs = divmod(rest, 60)
    return f"{int(hours)}:{int(minutes):02d}:{secs:05.2f}"


def _escape(text: str) -> str:
    """ASS treats braces as override blocks and backslashes as commands."""
    return (
        text.replace("\\", "/")
        .replace("{", "(")
        .replace("}", ")")
        .replace("\n", " ")
    )


def font_family(font_path: str) -> str:
    """Resolve a TTF path to the family name libass needs in the style line."""
    try:
        out = subprocess.run(
            ["fc-query", "--format", "%{family[0]}", font_path],
            capture_output=True, text=True, timeout=10,
        )
        if out.returncode == 0 and out.stdout.strip():
            return out.stdout.strip()
    except (FileNotFoundError, subprocess.TimeoutExpired):
        pass
    # libass falls back to a default face if the name doesn't resolve; the stem
    # is usually close enough (and fontsdir still finds the file).
    return Path(font_path).stem


@dataclass
class CaptionGroup:
    words: list[Word]

    @property
    def start(self) -> float:
        return self.words[0].start

    @property
    def end(self) -> float:
        return self.words[-1].end


def group_words(words: list[Word], max_per_line: int, max_gap: float = 0.55) -> list[CaptionGroup]:
    """Chunk words into on-screen groups, breaking on punctuation and pauses."""
    groups: list[CaptionGroup] = []
    current: list[Word] = []
    for i, word in enumerate(words):
        current.append(word)
        ends_clause = word.text.rstrip().endswith((".", "!", "?", ","))
        gap_next = (words[i + 1].start - word.end) if i + 1 < len(words) else 0.0
        if len(current) >= max_per_line or ends_clause or gap_next > max_gap:
            groups.append(CaptionGroup(current))
            current = []
    if current:
        groups.append(CaptionGroup(current))
    return groups


def build_ass(
    script: Script,
    words: list[Word],
    out_path: Path,
    config: Config,
    *,
    total_duration: float,
) -> Path:
    """Write the subtitle file that gets burned into the video."""
    width = int(config.get("visual.width", 1080))
    height = int(config.get("visual.height", 1920))
    font_path = find_font(config.get("captions.font"))
    family = font_family(font_path)

    uppercase = bool(config.get("captions.uppercase", True))
    primary = str(config.get("captions.primary_color", "&H00FFFFFF"))
    highlight = str(config.get("captions.highlight_color", "&H0000E5FF"))

    caption_pos = float(config.get("captions.position", 0.74))
    hook_pos = float(config.get("hook.position", 0.16))

    header = ASS_HEADER.format(
        width=width,
        height=height,
        font=family,
        size=int(config.get("captions.font_size", 82)),
        hook_size=int(config.get("hook.font_size", 104)),
        primary=primary,
        outline=int(config.get("captions.outline", 6)),
        hook_outline=int(config.get("captions.outline", 6)) + 2,
        shadow=int(config.get("captions.shadow", 3)),
        margin_h=int(width * 0.07),
        margin_v=max(20, int(height * (1.0 - caption_pos))),
        hook_margin_v=max(20, int(height * hook_pos)),
    )

    lines: list[str] = []

    if bool(config.get("hook.enabled", True)) and script.hook:
        hook_end = min(float(config.get("hook.duration", 2.6)), max(1.0, total_duration))
        lines.append(
            f"Dialogue: 1,{_ts(0)},{_ts(hook_end)},Hook,,0,0,0,,"
            f"{{\\fad(120,180)}}{_escape(script.hook.upper())}"
        )

    if bool(config.get("captions.enabled", True)) and words:
        max_per_line = int(config.get("captions.max_words_per_line", 4))
        for group in group_words(words, max_per_line):
            rendered = [_escape(w.text.upper() if uppercase else w.text) for w in group.words]
            for index, word in enumerate(group.words):
                # Rebuild the line each frame-range with one word tinted.
                parts = [
                    (f"{{\\c{highlight}}}{text}{{\\c{primary}}}" if i == index else text)
                    for i, text in enumerate(rendered)
                ]
                start = word.start if index else group.start
                end = word.end if index < len(group.words) - 1 else group.end
                if end <= start:
                    continue
                lines.append(
                    f"Dialogue: 0,{_ts(start)},{_ts(end)},Caption,,0,0,0,,{' '.join(parts)}"
                )

    if script.disclaimer:
        lines.append(
            f"Dialogue: 0,{_ts(0)},{_ts(total_duration)},Disclaimer,,0,0,0,,"
            f"{_escape(script.disclaimer)}"
        )

    ensure_dir(out_path.parent)
    out_path.write_text(header + "\n".join(lines) + "\n", encoding="utf-8")
    log.debug("wrote %d subtitle events to %s", len(lines), out_path)
    return out_path
