# Shorts

An automated pipeline that turns a bogus fitness claim into a finished vertical
video: cinematic-3D-style animation on top, workout footage on the bottom,
karaoke captions burned in, voiceover mixed, ready for YouTube.

```
idea  ->  script  ->  voiceover  ->  animation frames  ->  render  ->  upload
```

**It runs on GitHub's servers, not yours.** You drive the whole thing from the
GitHub mobile app or github.com in a phone browser. Nothing needs to be
installed locally.

---

## The phone loop

Three taps, in order. Everything happens under the **Actions** tab.

### 1. Pitch — write scripts, render nothing

Run **`Step 1 - Pitch scripts`**. Pick how many and how unhinged (1-5).

It writes the scripts, commits them to `pitches/<run number>/`, and opens an
**issue** containing every script in full. That issue is the thing you read on
your phone — hook, title, every spoken line, formatted to scan on a small
screen.

Scripts cost cents. Rendering costs real money and quota. So read first.

### 2. Render — turn the good ones into videos

Delete the pitches you don't want (tap the file on github.com, the bin icon,
commit). Then run **`Step 2 - Render videos`** with:

```
scripts: pitches/7
```

Leave `scripts` blank to skip the pitch step and write fresh scripts inline.

When it finishes it publishes a **Release**. Release assets are direct links —
tap one on your phone and the video plays. (Actions *artifacts* are zip files,
which is why they aren't used here.)

### 3. Publish

Two ways, pick either:

- **Manual** — download the mp4 from the Release, upload with the YouTube app.
  The Release notes carry the title for each video, ready to copy. No API setup
  at all. Honestly fine at a few videos a day.
- **Automatic** — tick `publish` on the render workflow. Needs the one-time
  OAuth setup below. Leave `privacy: private` and the videos just appear in your
  YouTube app, where reviewing and flipping them public is a two-tap job.

Once you trust it, uncomment the `schedule:` block in
`.github/workflows/generate.yml` and it runs daily on its own.

---

## Setup from a phone

### Nothing at all

The workflows run today. Every stage falls back to an offline stub when its API
key is missing, so you get a real, watchable mp4 with placeholder visuals and a
silent voice track. Run `Step 2 - Render videos` right now and see the format.

### API keys

`Settings -> Secrets and variables -> Actions -> New repository secret`. Add the
ones you want; each is independent, and each stage falls back on its own.

| Secret | Buys you | Roughly |
|---|---|---|
| `ANTHROPIC_API_KEY` | scripts actually written, not templated | ~$0.02 / short |
| `REPLICATE_API_TOKEN` | real imagery, and real animation | see below |
| `OPENAI_API_KEY` | a good voice, cheap | ~$0.01 / short |
| `ELEVENLABS_API_KEY` + `ELEVENLABS_VOICE_ID` | the best voice, plus exact caption timing | ~$0.05 / short |

**Speech needs no key at all.** The workflow installs
[piper](https://github.com/OHF-voice/piper1-gpl) (a free offline neural voice)
and espeak-ng (a free robot voice) and uses the best one available, so every
render has audio. A paid key upgrades the voice; ElevenLabs additionally
returns real word timings, which makes captions land exactly on the beat
instead of on a syllable estimate.

### Animation: the setting that actually matters

The `animation` dropdown on the render workflow is the difference between a
slideshow and something that looks made.

- **`kenburns`** (default, free) — pans and zooms across a still image.
  Nothing in the frame moves, because there is nothing to move. Good for
  checking timing, captions and pacing without spending anything. It will never
  look like the reference channels, no matter how good the stills get.
- **`generated`** — sends each still to an image-to-video model, which returns
  a few seconds of real motion: the camera travels, dust and cloth drift, the
  subject shifts. This is the single biggest quality jump available, and it
  needs `REPLICATE_API_TOKEN`.

Generated video is also the expensive part — **roughly $0.10-0.50 per beat**
depending on the model, so **$0.50-3.00 per short** on top of everything else.
Budget accordingly: pitch first, render only the scripts you actually like.

The model slug lives at `providers.video_model` in `config/default.yaml`. This
field goes stale fast — check Replicate for the current price/quality winner
before a big run, and change the one line. If a model names its inputs
differently, add them under `providers.video_input`.

Generated clips are cached per beat, so re-rendering after a caption or timing
change never re-buys them.

### Workout footage

The bottom panel is synthetic noise until you supply clips. Two ways, both
phone-friendly:

**Declare URLs** (keeps the repo small). Edit `assets/broll/sources.txt` on
github.com:

```
https://example.com/footage/squats-01.mp4     squats-01.mp4
https://example.com/footage/pushups-01.mp4    pushups-01.mp4
```

**Or commit the files.** On github.com in a phone browser: `assets/broll/` ->
`Add file` -> `Upload files`. Fine for a handful of clips; a large library will
bloat the repo, so prefer the URL list past a dozen or so.

**Name them after the exercise.** Clip selection prefers filenames that mention
the script's exercise, so `squats-01.mp4` gets you topical pairing for free.

**You need the right to use every clip.** Unlicensed gym footage and unlicensed
music are the two things most likely to get a short claimed or muted. See
`assets/broll/README.md`.

### YouTube upload (optional)

This is the one step that isn't phone-native, because Google's consent flow
wants a browser session it can hand a code back to.

1. Google Cloud Console (works in a phone browser, painfully): enable **YouTube
   Data API v3**, create an OAuth client of type **Web application**, add
   `https://localhost` as an authorised redirect URI, download the JSON.
2. Run `shorts auth` somewhere with a shell. **Google Cloud Shell**
   (shell.cloud.google.com) works from a phone browser and is free — clone the
   repo there, `pip install -r requirements.txt`, then:

   ```bash
   python -m shorts auth
   ```

   It prints a URL. Open it, approve, and you land on a `https://localhost/...`
   page that fails to load — that's expected. Copy the whole address bar and
   paste it back. You now have `youtube_token.json`.
3. Copy that file's entire contents into a repository secret named
   **`YOUTUBE_TOKEN_JSON`**. Treat it like a password.

If that sounds like more trouble than it's worth: it is, at low volume. Use the
manual upload path instead.

**Quota is the real ceiling.** A default Google Cloud project gets 10,000
units/day and each upload costs ~1,600 — about **6 uploads per day**, however
you automate it.

---

## Read this before you publish anything

You asked for confidently wrong fitness claims. That is exactly what this
builds — but *how* they are framed decides whether the channel survives.

**The default is `content.mode: satire`:** absurd claims, comedic framing, and a
visible on-screen disclaimer. Engagement-wise this loses you nothing. The
arguing-in-the-comments dynamic comes from the *confidence* and the *dare*, not
from viewers believing the claim. "Do 5 squats a day and your legs register as a
separate organ on a body scan" is funnier and more shareable than a claim that's
merely wrong.

**`content.mode: deadpan` exists** — claims played straight, no disclaimer — and
it's a dropdown on the pitch workflow. Understand the tradeoff before using it:

- YouTube's misinformation and spam/deceptive-practices policies cover health
  claims. Enforcement against fitness content is inconsistent, but the downside
  isn't a strike, it's demonetisation or channel termination, which takes the
  whole catalogue with it.
- Un-flagged false health claims can reach someone who acts on them. The dumber
  the claim the smaller that risk — but "stop training, it's counterproductive"
  lands differently than "your calves will become an organ."

Either way, the script prompt refuses to touch medicine, disease, injury
treatment, disordered eating, drugs, or supplements a viewer could actually
take, and `content.banned_words` is enforced on the model's output. Keep those
guards even in deadpan mode.

---

## What it produces

A 1080x1920 mp4, typically 25-35 seconds:

- **Top panel** — generated stills with a Ken Burns move, in a dark,
  high-contrast, single-key-light style (the Zach-D-Films register: silhouettes,
  god rays, haze, teal shadows with one warm accent).
- **Bottom panel** — your workout b-roll, cropped and looped.
- **Hook** — big text slammed on screen for the first ~2.5 seconds, so the video
  works muted.
- **Captions** — word by word, with the spoken word tinted.
- **Disclaimer** — a small persistent line at the bottom (satire mode only).

---

## Running it locally

Not required, but faster to iterate on if you do get to a laptop.

```bash
make setup                 # Python dependencies
brew install ffmpeg        # or: sudo apt install ffmpeg
make doctor                # check tooling, fonts, keys, b-roll
make demo                  # render one short with no API keys
```

```bash
python -m shorts idea -n 10                     # premises, free
python -m shorts pitch -n 5 --out-dir pitches   # scripts, no render
python -m shorts script --show-prompt           # the exact model prompts
python -m shorts make                           # idea -> finished mp4
python -m shorts render pitches/7               # render a folder of scripts
python -m shorts batch -n 5
python -m shorts fetch-broll                    # pull clips from sources.txt
python -m shorts upload out/<slug> --dry-run    # show the YouTube metadata
```

Every command takes `-c/--config` and `--set key=value`:

```bash
python -m shorts make --set visual.layout=full --set content.absurdity=5
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
| `clips/clip_NN.mp4` | the still animated into real motion (cached; `generated` only) |
| `segments/seg_NN.mp4` | each clip conformed to its beat's exact length |
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

**Animation** is a provider like any other. Video models emit fixed lengths
(5s, 6s) that never match a narrated beat, so each clip is conformed: trimmed
if long, gently retimed if slightly short, and held on its final frame if much
too short — so the cut always lands on the word it was written for.

**Rendering** is staged rather than one giant filter graph, so when something
breaks you can play the intermediate file and see which stage did it.

---

## Configuration

`config/default.yaml` is the documented schema. A `config/channel.yaml` layers
on top; `--set` and the workflow inputs layer on top of that.

```yaml
content:
  mode: satire          # satire | deadpan  (read the warning above)
  absurdity: 4          # 1-5; caps how unhinged the payoff claim gets
  beats: 5              # narrated lines per short

visual:
  layout: split         # split | full | broll_only
  split_ratio: 0.58     # how much height the animation panel gets

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

## Troubleshooting

**The bottom panel is abstract noise** — no b-roll. See *Workout footage* above.

**It looks like a slideshow** — that's `animation: kenburns`. Switch the
dropdown to `generated` and add `REPLICATE_API_TOKEN`.

**The video is silent** — no speech engine was found. In Actions this
shouldn't happen; locally, `pip install piper-tts` or install espeak-ng.

**Scripts feel templated** — no `ANTHROPIC_API_KEY`, so the offline writer is
being used. It's structurally right but deliberately not funny.

**Captions run off the frame** — lower `captions.font_size` or
`captions.max_words_per_line`.

**Captions drift out of sync** — you're on estimated timings. ElevenLabs returns
real alignment; the offline engines don't.

**The model refused the premise** — lower `content.absurdity`, or edit the idea.
The error says so explicitly.

**A batch renders 4 of 5** — one failure doesn't kill the batch; the summary
says which premise failed and why.

**The pitch workflow can't push** — the repo's Actions permissions need write
access (`Settings -> Actions -> General -> Workflow permissions`).

**`'ffmpeg' is not installed`** — only applies locally; `make doctor` confirms.

---

## Development

```bash
make test        # full suite, including real ffmpeg renders
make test-fast   # skips the end-to-end renders
```

Adding a provider is one file plus one line in `shorts/providers/registry.py` —
the three protocols are in `shorts/providers/base.py` and nothing in the
pipeline knows which backend it's talking to.

---

## License

MIT — see `LICENSE`.
