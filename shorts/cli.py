"""Command-line entry point.

    shorts doctor                 # check the environment
    shorts idea --count 5         # just the premises
    shorts script                 # write a script, print/save JSON
    shorts make                   # idea -> script -> finished mp4
    shorts render out/x/script.json
    shorts batch --count 5
    shorts upload out/x           # push to YouTube
"""

from __future__ import annotations

import argparse
import json
import shutil
import sys
from pathlib import Path

from . import broll as broll_lib
from .config import Config, load_config
from .ideas import IdeaGenerator
from .models import RenderResult, Script
from .pipeline import generate_script, produce
from .prompting import build_system_prompt, build_user_prompt
from .util import find_font, load_dotenv, log, setup_logging


def _common(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("-c", "--config", type=Path, help="extra YAML config layered on defaults")
    parser.add_argument("--set", dest="overrides", action="append", default=[],
                        metavar="KEY=VALUE", help="override any config key, e.g. --set visual.layout=full")
    parser.add_argument("-v", "--verbose", action="store_true")


def _load(args) -> Config:
    load_dotenv()
    setup_logging(getattr(args, "verbose", False))
    return load_config(args.config, args.overrides)


# --- commands --------------------------------------------------------------

def cmd_doctor(args) -> int:
    config = _load(args)
    ok = True

    def check(label: str, passed: bool, detail: str = "") -> None:
        nonlocal ok
        mark = "OK  " if passed else "FAIL"
        print(f"[{mark}] {label}{(' — ' + detail) if detail else ''}")
        ok = ok and passed

    check("ffmpeg", shutil.which("ffmpeg") is not None, shutil.which("ffmpeg") or "install ffmpeg")
    check("ffprobe", shutil.which("ffprobe") is not None, shutil.which("ffprobe") or "ships with ffmpeg")
    try:
        check("caption font", True, find_font(config.get("captions.font")))
    except RuntimeError as exc:
        check("caption font", False, str(exc))

    clips = broll_lib.library(config)
    if clips:
        check(f"b-roll library ({len(clips)} clips)", True, str(config.get("broll.dir")))
    else:
        # Not fatal: the pipeline synthesises placeholder footage.
        print(f"[WARN] b-roll library is empty — placeholder footage will be used. "
              f"Add clips to {config.get('broll.dir')}")

    import os
    for stage, key in (("llm", "ANTHROPIC_API_KEY"), ("tts", "ELEVENLABS_API_KEY"),
                       ("image", "REPLICATE_API_TOKEN")):
        provider = str(config.get(f"providers.{stage}", "stub"))
        needs_key = provider in {"anthropic", "elevenlabs", "replicate"}
        if not needs_key:
            print(f"[OK  ] {stage}: {provider} (no key needed)")
            continue
        check(f"{stage}: {provider}", bool(os.environ.get(key)), f"set {key} in .env")

    print(f"\nmode: {config.get('content.mode')}  layout: {config.get('visual.layout')}  "
          f"upload: {'enabled' if config.get('upload.enabled') else 'disabled'}")
    return 0 if ok else 1


def cmd_idea(args) -> int:
    config = _load(args)
    generator = IdeaGenerator(
        absurdity=int(config.get("content.absurdity", 4)), seed=args.seed
    )
    for idea in generator.batch(args.count):
        if args.json:
            print(json.dumps(idea.to_dict()))
        else:
            print(f"• {idea.claim}\n  angle: {idea.angle}   bait: {idea.bait}\n")
    return 0


def cmd_script(args) -> int:
    config = _load(args)
    if args.show_prompt:
        idea = IdeaGenerator(absurdity=int(config.get("content.absurdity", 4)),
                             seed=args.seed).generate()
        print("=== SYSTEM ===\n" + build_system_prompt(config))
        print("\n=== USER ===\n" + build_user_prompt(idea, config))
        return 0

    script = generate_script(config, seed=args.seed)
    if args.out:
        script.save(args.out)
        print(f"wrote {args.out}")
    else:
        print(json.dumps(script.to_dict(), indent=2, ensure_ascii=False))
    return 0


def _report(result: RenderResult) -> None:
    print(f"\n  video  {result.video_path}")
    if result.thumbnail_path:
        print(f"  thumb  {result.thumbnail_path}")
    print(f"  length {result.duration:.1f}s")
    print(f"  title  {result.script.title}")


def cmd_make(args) -> int:
    config = _load(args)
    script = generate_script(config, seed=args.seed)
    result = produce(script, config, reuse=not args.no_reuse)
    _report(result)
    return 0


def cmd_render(args) -> int:
    config = _load(args)
    script = Script.load(args.script)
    workdir = args.workdir or args.script.parent
    result = produce(script, config, workdir=workdir, reuse=not args.no_reuse)
    _report(result)
    return 0


def cmd_batch(args) -> int:
    config = _load(args)
    broll_lib.reset_usage()
    generator = IdeaGenerator(absurdity=int(config.get("content.absurdity", 4)), seed=args.seed)
    ideas = generator.batch(args.count)

    made, failed = [], []
    for index, idea in enumerate(ideas, start=1):
        log.info("[%d/%d] %s", index, len(ideas), idea.claim)
        try:
            script = generate_script(config, idea)
            made.append(produce(script, config, reuse=not args.no_reuse))
        except Exception as exc:  # one bad short shouldn't kill the batch
            log.error("failed: %s", exc)
            failed.append((idea.claim, str(exc)))

    print(f"\nrendered {len(made)}/{len(ideas)}")
    for result in made:
        print(f"  {result.video_path}")
    for claim, error in failed:
        print(f"  FAILED  {claim[:60]}… — {error}")
    return 0 if not failed else 1


def cmd_upload(args) -> int:
    from .youtube import upload

    config = _load(args)
    workdir = args.workdir
    script_path = workdir / "script.json"
    video_path = workdir / "final.mp4"
    if not script_path.exists() or not video_path.exists():
        print(f"expected script.json and final.mp4 in {workdir}", file=sys.stderr)
        return 1

    thumbnail = workdir / "thumbnail.jpg"
    result = RenderResult(
        video_path=video_path,
        thumbnail_path=thumbnail if thumbnail.exists() else None,
        script=Script.load(script_path),
        duration=0.0,
        workdir=workdir,
    )
    video_id = upload(result, config, dry_run=args.dry_run)
    if video_id:
        print(f"https://youtube.com/watch?v={video_id}")
    return 0


# --- wiring ----------------------------------------------------------------

def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="shorts", description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    subs = parser.add_subparsers(dest="command", required=True)

    doctor = subs.add_parser("doctor", help="check tooling, keys and assets")
    _common(doctor)
    doctor.set_defaults(func=cmd_doctor)

    idea = subs.add_parser("idea", help="generate premises only")
    _common(idea)
    idea.add_argument("-n", "--count", type=int, default=5)
    idea.add_argument("--seed", type=int)
    idea.add_argument("--json", action="store_true")
    idea.set_defaults(func=cmd_idea)

    script = subs.add_parser("script", help="write a script")
    _common(script)
    script.add_argument("--seed", type=int)
    script.add_argument("-o", "--out", type=Path)
    script.add_argument("--show-prompt", action="store_true",
                        help="print the exact prompts instead of calling the model")
    script.set_defaults(func=cmd_script)

    make = subs.add_parser("make", help="one idea all the way to an mp4")
    _common(make)
    make.add_argument("--seed", type=int)
    make.add_argument("--no-reuse", action="store_true", help="regenerate cached frames")
    make.set_defaults(func=cmd_make)

    render = subs.add_parser("render", help="render an existing script.json")
    _common(render)
    render.add_argument("script", type=Path)
    render.add_argument("--workdir", type=Path)
    render.add_argument("--no-reuse", action="store_true")
    render.set_defaults(func=cmd_render)

    batch = subs.add_parser("batch", help="render several shorts in one go")
    _common(batch)
    batch.add_argument("-n", "--count", type=int, default=3)
    batch.add_argument("--seed", type=int)
    batch.add_argument("--no-reuse", action="store_true")
    batch.set_defaults(func=cmd_batch)

    upload = subs.add_parser("upload", help="upload a rendered short to YouTube")
    _common(upload)
    upload.add_argument("workdir", type=Path)
    upload.add_argument("--dry-run", action="store_true", help="print the metadata, upload nothing")
    upload.set_defaults(func=cmd_upload)

    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        return args.func(args)
    except KeyboardInterrupt:
        return 130
    except Exception as exc:
        if getattr(args, "verbose", False):
            raise
        print(f"error: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
