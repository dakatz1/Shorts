"""The orchestrator: idea -> script -> voice -> frames -> video.

Every stage writes its output into a per-video working directory, so a failed
run leaves you the artefacts to inspect and a rerun can reuse the expensive
parts (generated images, voiceover) instead of paying for them twice.
"""

from __future__ import annotations

from pathlib import Path

from . import broll as broll_lib
from . import render as render_lib
from .captions import build_ass
from .config import Config
from .ideas import IdeaGenerator
from .models import Idea, RenderResult, Script, VoiceTrack
from .providers import get_image_provider, get_script_provider, get_voice_provider
from .timing import assign_beat_times
from .util import ensure_dir, ffprobe_duration, log, slugify, stable_seed, write_json


def generate_idea(config: Config, *, seed: int | None = None) -> Idea:
    return IdeaGenerator(
        absurdity=int(config.get("content.absurdity", 4)), seed=seed
    ).generate()


def generate_script(config: Config, idea: Idea | None = None, *, seed: int | None = None) -> Script:
    idea = idea or generate_idea(config, seed=seed)
    provider = get_script_provider(config)
    log.info("writing script: %s", idea.claim)
    return provider.write(idea, config)


def _workdir(script: Script, config: Config) -> Path:
    root = Path(str(config.get("output.dir", "out")))
    return ensure_dir(root / slugify(script.title))


def synthesize_voice(script: Script, config: Config, workdir: Path) -> VoiceTrack:
    voice_path = workdir / "voice.wav"
    provider = get_voice_provider(config)
    log.info("synthesising voiceover (%s)", config.get("providers.tts"))
    track = provider.speak(script.narration, voice_path, config)
    assign_beat_times(script.beats, track.words, track.duration)
    write_json(workdir / "timings.json", {
        "duration": track.duration,
        "words": [w.to_dict() for w in track.words],
        "beats": [b.to_dict() for b in script.beats],
    })
    return track


def generate_frames(script: Script, config: Config, workdir: Path, *, reuse: bool = True) -> list[Path]:
    provider = get_image_provider(config)
    frames_dir = ensure_dir(workdir / "frames")
    paths: list[Path] = []
    for index, beat in enumerate(script.beats):
        target = frames_dir / f"beat_{index:02d}.jpg"
        if reuse and target.exists() and target.stat().st_size > 0:
            log.debug("reusing existing frame %s", target.name)
        else:
            log.info("frame %d/%d: %s", index + 1, len(script.beats), beat.visual[:60])
            provider.render(
                beat.visual,
                target,
                config,
                seed=stable_seed(beat.visual, index, script.title),
            )
        paths.append(target)
    return paths


def _pick_music(config: Config) -> Path | None:
    if not bool(config.get("music.enabled", True)):
        return None
    directory = Path(str(config.get("music.dir", "assets/music")))
    if not directory.exists():
        return None
    tracks = sorted(p for p in directory.rglob("*") if p.suffix.lower() in {".mp3", ".wav", ".m4a", ".aac", ".ogg"})
    if not tracks:
        log.debug("no music in %s — voiceover only", directory)
        return None
    return tracks[0]


def produce(
    script: Script,
    config: Config,
    *,
    workdir: Path | None = None,
    reuse: bool = True,
) -> RenderResult:
    """Run every render stage and return the finished video."""
    workdir = ensure_dir(workdir or _workdir(script, config))
    # Saved twice on purpose: once up front so a crash during synthesis still
    # leaves the script on disk, and again below once the beats carry timings.
    script.save(workdir / "script.json")

    voice = synthesize_voice(script, config, workdir)
    script.save(workdir / "script.json")
    layout = str(config.get("visual.layout", "split"))
    width, height, top_h = render_lib._panel_sizes(config)

    animation: Path | None = None
    if layout != "broll_only":
        frames = generate_frames(script, config, workdir, reuse=reuse)
        segments_dir = ensure_dir(workdir / "segments")
        segments = [
            render_lib.render_beat_segment(
                beat, frame, segments_dir / f"seg_{i:02d}.mp4", config, (width, top_h)
            )
            for i, (beat, frame) in enumerate(zip(script.beats, frames))
        ]
        animation = render_lib.concat_segments(segments, workdir / "animation.mp4")
        # The animation is driven by beat timings; trust the audio for total length.
        log.debug("animation %.2fs vs voice %.2fs", ffprobe_duration(animation), voice.duration)

    broll_panel: Path | None = None
    if layout in {"split", "full", "broll_only"}:
        idea = script.idea
        source = broll_lib.pick(
            config,
            exercise=idea.exercise if idea else "",
            body_part=idea.body_part if idea else "",
            seed=stable_seed(script.title),
            cache_dir=Path("cache"),
        )
        panel_h = height - top_h if layout == "split" else height
        if layout == "full":
            panel_h = render_lib._even(height * 0.30)
        broll_panel = render_lib.render_broll_panel(
            source, workdir / "broll.mp4", config, (width, panel_h), voice.duration
        )

    subtitles = build_ass(
        script, voice.words, workdir / "captions.ass", config, total_duration=voice.duration
    )

    final = workdir / "final.mp4"
    render_lib.compose(
        animation,
        broll_panel,
        voice.audio_path,
        subtitles,
        final,
        config,
        music=_pick_music(config),
        duration=voice.duration,
    )

    thumbnail = None
    if bool(config.get("output.thumbnail", True)):
        thumbnail = render_lib.grab_thumbnail(final, workdir / "thumbnail.jpg")

    duration = ffprobe_duration(final)
    log.info("rendered %s (%.1fs)", final, duration)
    return RenderResult(
        video_path=final,
        thumbnail_path=thumbnail,
        script=script,
        duration=duration,
        workdir=workdir,
    )


def make_one(config: Config, *, idea: Idea | None = None, seed: int | None = None,
             reuse: bool = True) -> RenderResult:
    script = generate_script(config, idea, seed=seed)
    return produce(script, config, reuse=reuse)
