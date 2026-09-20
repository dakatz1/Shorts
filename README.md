# Shorts

An automated pipeline that turns a bogus fitness claim into a finished vertical
video: cinematic-3D-style animation on top, workout footage on the bottom,
karaoke captions burned in, voiceover mixed, ready to upload to YouTube.

```
idea  ->  script  ->  voiceover  ->  animation frames  ->  render  ->  upload
```

Run it with no API keys at all to see the format:

```bash
make setup
make demo        # renders out/<slug>/final.mp4
```

---

## What it produces

A 1080x1920 mp4, typically 25-35 seconds:

- **Top panel** — generated stills with a Ken Burns move, in a dark, high-contrast,
  single-key-light style (the Zach-D-Films register: silhouettes, god rays, haze,
  teal shadows with one warm accent).
- **Bottom panel** — your workout b-roll, cropped and looped.
- **Hook** — big text slammed on screen for the first ~2.5 seconds, so the video
  works muted.
- **Captions** — word-by-word, with the spoken word tinted.
- **Disclaimer** — a small persistent line at the bottom (satire mode only).

`assets/` ships empty. Until you add workout clips the bottom panel is an obvious
synthetic placeholder.

---

## Read this before you publish anything

You asked for confidently wrong fitness claims. That is exactly what this builds
— but *how* they are framed decides whether the channel survives.

**The default is `content.mode: satire`:** absurd claims, comedic framing, and a
visible on-screen disclaimer. Engagement-wise this loses you nothing. The
arguing-in-the-comments dynamic comes from the *confidence* and the *dare*, not
from viewers believing the claim. "Do 5 squats a day and your legs register as a
separate organ on a body scan" is funnier and more shareable than a claim that's
merely wrong.

**`content.mode: deadpan` exists** — claims played straight, no disclaimer — and
it is one line of config. Understand the tradeoff before flipping it:

- YouTube's misinformation and spam/deceptive-practices policies cover health
  claims. Enforcement against fitness content is inconsistent, but the downside
  is not a strike, it's demonetisation or channel termination, which takes the
  whole catalogue with it.
- Un-flagged false health claims can reach someone who acts on them. The dumber
  the claim the smaller that risk — but "stop training, it's counterproductive"
  lands differently than "your calves will become an organ."

Either way, the script prompt refuses to touch medicine, disease, injury
treatment, disordered eating, drugs, or supplements a viewer could actually take,
and `content.banned_words` is enforced on the model's output. Keep those guards
even in deadpan mode.

**You are also responsible for the footage and music you add.** See
`assets/broll/README.md` — unlicensed gym clips and unlicensed music are the two
things most likely to get a short claimed or muted.

---

## Setup

### 1. Dependencies

```bash
make setup              # Python packages
```

ffmpeg does the rendering and is not a Python package:

```bash
brew install ffmpeg                 # macOS
sudo apt install ffmpeg             # Debian/Ubuntu
```

Then check everything:

```bash
make doctor
```

It reports ffmpeg, the caption font, your b-roll library, and which API keys each
configured provider needs.

### 2. Workout footage

Drop vertical workout clips into `assets/broll/`, named after the exercise
(`squats-01.mp4`, `pushups-gym.mp4`). Selection prefers clips whose filename
matches the script's exercise, so naming buys you topical pairing for free. See
`assets/broll/README.md` for sourcing and licensing.

### 3. API keys (optional — the stubs work without them)

```bash
cp .env.example .env    # then fill in
```

| Stage | Provider | Key | Roughly |
|---|---|---|---|
| Script | `anthropic` | `ANTHROPIC_API_KEY` | ~$0.02 / short |
| Voice | `elevenlabs` | `ELEVENLABS_API_KEY`, `ELEVENLABS_VOICE_ID` | ~$0.05 / short |
| Images | `replicate` | `REPLICATE_API_TOKEN` | ~$0.04 / frame, 5-6 frames |

Call it **$0.25-0.40 per short** all in. The `stub` providers cost nothing and
exercise every other stage, so develop against those.

`.env` is gitignored. So are the YouTube OAuth files.

### 4. Turn the real providers on

```bash
cp config/channel.example.yaml config/channel.yaml
```

```yaml
providers:
  llm: anthropic
  tts: elevenlabs
  image: replicate
```

Then pass it: `python -m shorts make -c config/channel.yaml`.

---

## Usage

```bash
python -m shorts doctor                       # environment check
python -m shorts idea -n 10                   # just premises, no cost
python -m shorts script --show-prompt         # see the exact model prompts
python -m shorts script -o draft.json         # write one script
python -m shorts make                         # idea -> finished mp4
python -m shorts render out/<slug>/script.json  # re-render an edited script
python -m shorts batch -n 5                   # five shorts in one go
python -m shorts upload out/<slug> --dry-run  # show the YouTube metadata
python -m shorts upload out/<slug>            # actually publish
```

Every command takes `-c/--config` and `--set key=value`:

```bash
python -m shorts make --set visual.layout=full --set content.absurdity=5
python -m shorts batch -n 3 --set content.mode=deadpan
```

### Editing a script before it renders

The highest-leverage workflow. Write it, read it, fix the line that doesn't land,
then render:

```bash
python -m shorts script -o out/draft/script.json
$EDITOR out/draft/script.json
python -m shorts render out/draft/script.json
```

Generated frames are cached per beat, so re-rendering after a text-only edit
doesn't pay for images again. `--no-reuse` forces regeneration.

---

## How it works

Each stage writes into `out/<slug>/`, so a failed run leaves you the pieces:

| File | Stage |
|---|---|
| `script.json` | the script, with per-beat timings filled in after synthesis |
| `voice.wav` | the voiceover |
| `timings.json` | word-level and beat-level timings |
| `frames/beat_NN.jpg` | one generated still per beat (cached) |
| `segments/seg_NN.mp4` | each still with its Ken Burns move |
| `animation.mp4` | the segments concatenated — the top panel |
| `broll.mp4` | workout footage cropped to the bottom panel |
| `captions.ass` | the subtitle file that gets burned in |
| `final.mp4` | the deliverable |

**Ideas** are combinatorial (`shorts/ideas.py`): an exercise, an absurd outcome
capped by `content.absurdity`, a rhetorical angle, and a bait line. The angle is
what actually drives the comments — people argue with "the industry hid this"
far more than with the number.

**Scripts** follow a fixed arc: hook, fake authority, pseudo-mechanism,
escalation, payoff + dare. The model's JSON is validated (beat count, line
length, banned words, hook length) and rejected back to the model once with the
specific problems before giving up.

**Timing** comes from ElevenLabs' character-level alignment where available, and
is otherwise estimated by syllable weight with extra time bought by punctuation.
Beats are tiled so there's never a frozen frame between them.

**Rendering** is staged rather than one giant filter graph, so when something
breaks you can play the intermediate file and see which stage did it.

---

## Configuration

`config/default.yaml` is the documented schema. Your `config/channel.yaml` layers
on top; `--set` layers on top of that. The knobs worth knowing:

```yaml
content:
  mode: satire          # satire | deadpan  (read the warning above)
  absurdity: 4          # 1-5; caps how unhinged the payoff claim gets
  beats: 5              # narrated lines per short

visual:
  layout: split         # split | full | broll_only
  split_ratio: 0.58     # how much height the animation panel gets
  zoom_per_second: 0.035

captions:
  font: null            # null = auto-detect; or a path to a .ttf
  max_words_per_line: 3
  position: 0.74        # 0 = top, 1 = bottom

upload:
  enabled: false
  privacy: private      # start here
```

Layouts: `split` is the classic bait format. `full` runs the animation
full-bleed with b-roll as a bottom inset strip. `broll_only` skips image
generation entirely — much cheaper, and useful for testing scripts.

---

## Uploading

1. Google Cloud Console -> enable **YouTube Data API v3** -> create an OAuth
   client of type **Desktop app** -> download the JSON.
2. Point `YOUTUBE_CLIENT_SECRET` at it in `.env`.
3. `python -m shorts upload out/<slug> --dry-run` to check the metadata.
4. `python -m shorts upload out/<slug>` — opens a browser once, then caches a
   refresh token in `youtube_token.json`.

`upload.enabled` defaults to `false` and `upload.privacy` to `private`. Turn them
up only after you've watched what comes out.

The API's upload quota is the real constraint: a default project gets 10,000
units/day and each upload costs ~1,600, so **about 6 uploads per day**. Request
more quota, or upload the rest by hand.

---

## Scheduling

`.github/workflows/generate.yml` renders a batch on demand and attaches the
files to the run. It's `workflow_dispatch`-only by default — uncomment the
`schedule:` block once you trust the output. It needs your API keys as repository
secrets, plus `YOUTUBE_TOKEN_JSON` (the contents of the `youtube_token.json` you
generated locally) if you want it to publish.

Note the runner has no b-roll: the workflow restores `assets/broll` from an
Actions cache and otherwise falls back to placeholder footage. For real
scheduled publishing, a small always-on box with the footage on disk and a cron
entry is simpler and cheaper.

---

## Troubleshooting

**`'ffmpeg' is not installed`** — install it; `make doctor` will confirm.

**`No caption font found`** — drop any `.ttf` at `assets/fonts/caption.ttf`.

**Captions run off the frame** — lower `captions.font_size` or
`captions.max_words_per_line`.

**Captions drift out of sync** — you're on estimated timings. ElevenLabs returns
real alignment; the offline engines don't.

**The bottom panel is abstract noise** — `assets/broll/` is empty and you're
seeing the placeholder.

**The model refused the premise** — lower `content.absurdity`, or edit the idea.
The error says so explicitly.

**A batch renders 4 of 5** — one failure doesn't kill the batch; the summary
prints which premise failed and why.

---

## Development

```bash
make test        # full suite, including real ffmpeg renders
make test-fast   # skips the end-to-end renders
```

Adding a provider is one file plus one line in `shorts/providers/registry.py` —
the three protocols are in `shorts/providers/base.py` and nothing in the pipeline
knows which backend it's talking to.

---

## License

MIT — see `LICENSE`.
