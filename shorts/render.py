"""Assembling the final vertical video with ffmpeg.

Deliberately staged rather than one enormous filter_complex: each beat renders
to its own segment, segments concat into the animation panel, the panel is
stacked with the workout footage, and captions and audio go on last. When
something breaks you can play the intermediate file and see exactly which stage
did it — and stage outputs are reusable across re-renders.
"""

from __future__ import annotations

from pathlib import Path

from .config import Config
from .models import Beat
from .util import ensure_dir, ffmpeg, find_font

MIN_BEAT_SECONDS = 0.5


def _even(value: float) -> int:
    """ffmpeg's h264 encoder needs even dimensions."""
    return int(value) // 2 * 2


def _panel_sizes(config: Config) -> tuple[int, int, int]:
    width = _even(config.get("visual.width", 1080))
    height = _even(config.get("visual.height", 1920))
    layout = str(config.get("visual.layout", "split"))
    if layout == "split":
        top = _even(height * float(config.get("visual.split_ratio", 0.58)))
    elif layout == "full":
        top = height
    else:  # broll_only
        top = 0
    return width, height, top


def _zoompan_expr(motion: str, frames: int, zoom_per_second: float, fps: int) -> str:
    """Per-frame zoom/pan expressions for the Ken Burns move."""
    step = max(0.0002, zoom_per_second / max(1, fps))
    span = max(1, frames - 1)
    centre_x, centre_y = "iw/2-(iw/zoom/2)", "ih/2-(ih/zoom/2)"

    if motion == "pull_out":
        peak = 1.0 + step * span
        return f"z='if(eq(on,0),{peak:.4f},max(zoom-{step:.5f},1.0))':x='{centre_x}':y='{centre_y}'"
    if motion == "pan_left":
        return f"z='1.18':x='(iw-iw/zoom)*(1-on/{span})':y='{centre_y}'"
    if motion == "pan_right":
        return f"z='1.18':x='(iw-iw/zoom)*(on/{span})':y='{centre_y}'"
    if motion == "shake":
        return (
            f"z='1.14':x='(iw-iw/zoom)/2+sin(on/3.1)*(iw*0.012)'"
            f":y='(ih-ih/zoom)/2+cos(on/2.3)*(ih*0.012)'"
        )
    # push_in — the default, and the one that suits a doom-narration best.
    return f"z='min(zoom+{step:.5f},1.6)':x='{centre_x}':y='{centre_y}'"


def render_beat_segment(
    beat: Beat, image: Path, out_path: Path, config: Config, panel: tuple[int, int]
) -> Path:
    """One still image + one Ken Burns move -> one silent video segment."""
    width, height = panel
    fps = int(config.get("visual.fps", 30))
    duration = max(MIN_BEAT_SECONDS, beat.duration)
    frames = max(2, round(duration * fps))

    # Oversample before zoompan: it samples the *input*, so a small source
    # produces visible stair-stepping as it zooms.
    over_w, over_h = width * 2, height * 2
    chain = (
        f"scale={over_w}:{over_h}:force_original_aspect_ratio=increase,"
        f"crop={over_w}:{over_h},"
    )
    if bool(config.get("visual.ken_burns", True)):
        expr = _zoompan_expr(
            beat.motion, frames, float(config.get("visual.zoom_per_second", 0.035)), fps
        )
        chain += f"zoompan={expr}:d={frames}:s={width}x{height}:fps={fps},"
    else:
        chain += f"scale={width}:{height},fps={fps},"
    chain += "setsar=1,format=yuv420p"

    ensure_dir(out_path.parent)
    ffmpeg([
        "-i", str(image),
        "-filter_complex", chain,
        "-frames:v", str(frames),
        "-r", str(fps),
        "-c:v", "libx264", "-crf", "18", "-preset", "veryfast",
        "-pix_fmt", "yuv420p",
        str(out_path),
    ])
    return out_path


# How far a generated clip may be slowed to fill a beat before it looks like
# slow motion. Past this we hold the final frame instead.
MAX_SLOWDOWN = 1.6


def fit_clip_to_duration(
    source: Path, out_path: Path, target: float, config: Config, panel: tuple[int, int]
) -> Path:
    """Conform a generated clip to the panel and to exactly `target` seconds.

    Video models emit fixed lengths (5s, 6s, 10s) that never match a narrated
    beat. Too long: trim. Slightly short: retime. Much too short: retime as far
    as looks acceptable, then hold the last frame so the cut still lands on the
    word it was written for.
    """
    from .util import ffprobe_duration

    width, height = panel
    fps = int(config.get("visual.fps", 30))
    target = max(MIN_BEAT_SECONDS, target)
    source_duration = ffprobe_duration(source)

    chain = (
        f"scale={width}:{height}:force_original_aspect_ratio=increase,"
        f"crop={width}:{height},setsar=1"
    )

    if source_duration > target:
        speed = 1.0            # trimmed by -t below
    else:
        needed = target / max(0.05, source_duration)
        speed = min(needed, MAX_SLOWDOWN)
    if abs(speed - 1.0) > 0.01:
        chain += f",setpts={speed:.4f}*PTS"

    # After retiming, pad with the final frame if we are still short.
    chain += f",fps={fps},tpad=stop_mode=clone:stop_duration={target:.3f},format=yuv420p"

    ensure_dir(out_path.parent)
    ffmpeg([
        "-i", str(source),
        "-an",
        "-vf", chain,
        "-t", f"{target:.3f}",
        "-r", str(fps),
        "-c:v", "libx264", "-crf", "18", "-preset", "veryfast",
        "-pix_fmt", "yuv420p",
        str(out_path),
    ])
    return out_path


def concat_segments(segments: list[Path], out_path: Path) -> Path:
    """Stream-copy concat — the segments already share codec and parameters."""
    if not segments:
        raise ValueError("nothing to concatenate")
    listing = out_path.with_suffix(".txt")
    listing.write_text(
        "\n".join(f"file '{p.resolve()}'" for p in segments) + "\n", encoding="utf-8"
    )
    ffmpeg(["-f", "concat", "-safe", "0", "-i", str(listing), "-c", "copy", str(out_path)])
    listing.unlink(missing_ok=True)
    return out_path


def render_broll_panel(
    source: Path, out_path: Path, config: Config, panel: tuple[int, int], duration: float
) -> Path:
    """Crop the workout footage to the panel and loop it to cover the narration."""
    width, height = panel
    fps = int(config.get("visual.fps", 30))
    ensure_dir(out_path.parent)
    ffmpeg([
        "-stream_loop", "-1",
        "-i", str(source),
        "-an",
        "-t", f"{duration:.3f}",
        "-vf", (
            f"scale={width}:{height}:force_original_aspect_ratio=increase,"
            f"crop={width}:{height},fps={fps},setsar=1,format=yuv420p"
        ),
        "-c:v", "libx264", "-crf", "20", "-preset", "veryfast",
        str(out_path),
    ])
    return out_path


_AFORMAT = "aformat=sample_fmts=fltp:sample_rates=44100:channel_layouts=stereo"


def _audio_filter(voice_index: int, music_index: int | None, config: Config) -> tuple[str, str]:
    """Build the audio graph against concrete input indices.

    Indices are substituted here rather than by string replacement on a
    template — replacing `[1:a]` then `[2:a]` in sequence rewrites the label
    the first pass just produced.
    """
    if music_index is None:
        return f"[{voice_index}:a]{_AFORMAT}[aout]", "[aout]"
    volume = float(config.get("music.volume_db", -22))
    return (
        f"[{voice_index}:a]{_AFORMAT}[voice];"
        f"[{music_index}:a]{_AFORMAT},volume={volume}dB[music];"
        "[voice][music]amix=inputs=2:duration=first:dropout_transition=0:normalize=0[aout]",
        "[aout]",
    )


def compose(
    animation: Path | None,
    broll: Path | None,
    voice: Path,
    subtitles: Path,
    out_path: Path,
    config: Config,
    *,
    music: Path | None = None,
    duration: float,
) -> Path:
    """Stack the panels, burn the captions, mix the audio, encode the deliverable."""
    width, height, top_h = _panel_sizes(config)
    layout = str(config.get("visual.layout", "split"))
    font_dir = str(Path(find_font(config.get("captions.font"))).parent)
    # ffmpeg filter arguments are comma/colon separated, so paths need escaping.
    subs = str(subtitles.resolve()).replace("\\", "/").replace(":", r"\\:")
    fonts = font_dir.replace("\\", "/").replace(":", r"\\:")

    inputs: list[str] = []
    video_filter: str

    if layout == "broll_only":
        if not broll:
            raise ValueError("layout 'broll_only' needs b-roll footage")
        inputs += ["-i", str(broll)]
        video_filter = "[0:v]null[stacked];"
    elif layout == "full":
        if not animation:
            raise ValueError("layout 'full' needs generated animation frames")
        inputs += ["-i", str(animation)]
        if broll:
            inset_h = _even(height * 0.30)
            inputs += ["-i", str(broll)]
            video_filter = (
                f"[1:v]scale={width}:{inset_h}:force_original_aspect_ratio=increase,"
                f"crop={width}:{inset_h}[inset];"
                f"[0:v][inset]overlay=0:{height - inset_h}[stacked];"
            )
        else:
            video_filter = "[0:v]null[stacked];"
    else:  # split
        if not animation or not broll:
            raise ValueError("layout 'split' needs both animation and b-roll")
        inputs += ["-i", str(animation), "-i", str(broll)]
        video_filter = "[0:v][1:v]vstack=inputs=2[stacked];"

    # Audio inputs come after every video input, so their indices depend on layout.
    voice_index = len([a for a in inputs if a == "-i"])
    inputs += ["-i", str(voice)]

    music_index = None
    if music is not None and Path(music).exists():
        music_index = voice_index + 1
        inputs += ["-stream_loop", "-1", "-i", str(music)]

    audio_filter, audio_label = _audio_filter(voice_index, music_index, config)

    video_filter += (
        f"[stacked]subtitles='{subs}':fontsdir='{fonts}',"
        f"format=yuv420p,setsar=1[vout]"
    )

    ensure_dir(out_path.parent)
    ffmpeg([
        *inputs,
        "-filter_complex", f"{video_filter};{audio_filter}",
        "-map", "[vout]", "-map", audio_label,
        "-t", f"{duration:.3f}",
        "-r", str(int(config.get("visual.fps", 30))),
        "-c:v", "libx264",
        "-crf", str(int(config.get("output.crf", 20))),
        "-preset", str(config.get("output.preset", "medium")),
        "-profile:v", "high", "-level", "4.1",
        "-c:a", "aac", "-b:a", str(config.get("output.audio_bitrate", "192k")),
        "-movflags", "+faststart",
        "-pix_fmt", "yuv420p",
        str(out_path),
    ])
    return out_path


def grab_thumbnail(video: Path, out_path: Path, at: float = 1.2) -> Path:
    """Pull a still for the YouTube thumbnail slot."""
    ensure_dir(out_path.parent)
    ffmpeg(["-ss", f"{at:.2f}", "-i", str(video), "-frames:v", "1", "-q:v", "2", str(out_path)])
    return out_path
