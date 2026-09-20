"""Scriptwriting via the Claude Messages API.

The model returns a JSON object; we validate it against the beat schema and
retry once with the validation errors fed back before giving up. That retry is
worth the extra call — a malformed script costs a whole render.
"""

from __future__ import annotations

import json
import re

from ..config import Config
from ..models import Beat, Idea, Script
from ..prompting import build_system_prompt, build_user_prompt
from ..util import env, log

DEFAULT_MODEL = "claude-opus-5"
VALID_MOTIONS = {"push_in", "pull_out", "pan_left", "pan_right", "shake"}


class ScriptValidationError(ValueError):
    pass


def _extract_json(raw: str) -> dict:
    """Models occasionally wrap JSON in prose or a fence despite instructions."""
    text = raw.strip()
    fence = re.search(r"```(?:json)?\s*(.+?)\s*```", text, re.DOTALL)
    if fence:
        text = fence.group(1)
    start, end = text.find("{"), text.rfind("}")
    if start == -1 or end <= start:
        raise ScriptValidationError("no JSON object found in model output")
    try:
        return json.loads(text[start : end + 1])
    except json.JSONDecodeError as exc:
        raise ScriptValidationError(f"model returned invalid JSON: {exc}") from exc


def _validate(data: dict, config: Config) -> list[str]:
    """Return a list of human-readable problems; empty means the payload is good."""
    problems: list[str] = []
    expected = int(config.get("content.beats", 5))

    for field in ("title", "hook", "beats"):
        if not data.get(field):
            problems.append(f"missing required field: {field}")
    if problems:
        return problems

    beats = data["beats"]
    if not isinstance(beats, list):
        return ["`beats` must be a list"]
    if len(beats) != expected:
        problems.append(f"expected exactly {expected} beats, got {len(beats)}")

    for i, beat in enumerate(beats):
        if not isinstance(beat, dict):
            problems.append(f"beat {i} is not an object")
            continue
        if not str(beat.get("text", "")).strip():
            problems.append(f"beat {i} has empty text")
        if not str(beat.get("visual", "")).strip():
            problems.append(f"beat {i} has no visual prompt")
        words = len(str(beat.get("text", "")).split())
        if words > 28:
            problems.append(f"beat {i} is {words} words — keep spoken lines under 28")

    # Content guardrails: these are cheap to check and expensive to miss.
    banned = [w.lower() for w in config.get("content.banned_words", []) or []]
    blob = " ".join(str(b.get("text", "")) for b in beats if isinstance(b, dict)).lower()
    for word in banned:
        if re.search(rf"\b{re.escape(word)}\b", blob):
            problems.append(f"script uses banned word {word!r} — rewrite that line")

    if len(str(data.get("hook", ""))) > 40:
        problems.append("hook is too long for a full-width on-screen slam (max 40 chars)")
    return problems


class AnthropicScriptProvider:
    """Writes scripts with Claude."""

    def __init__(self, model: str | None = None) -> None:
        self.model = model or DEFAULT_MODEL

    def _client(self):
        try:
            import anthropic
        except ImportError as exc:  # pragma: no cover - optional dependency
            raise RuntimeError(
                "the anthropic package is not installed. Run: pip install anthropic"
            ) from exc
        # The SDK resolves ANTHROPIC_API_KEY (or an `ant auth login` profile) itself;
        # this check just produces a friendlier error than a 401 would.
        env("ANTHROPIC_API_KEY")
        return anthropic.Anthropic()

    def write(self, idea: Idea, config: Config) -> Script:
        client = self._client()
        model = str(config.get("providers.llm_model", self.model))
        system = build_system_prompt(config)
        user = build_user_prompt(idea, config)

        messages = [{"role": "user", "content": user}]
        last_problems: list[str] = []

        for attempt in (1, 2):
            response = client.messages.create(
                model=model,
                max_tokens=8000,
                system=system,
                output_config={"effort": str(config.get("providers.llm_effort", "medium"))},
                messages=messages,
            )
            if response.stop_reason == "refusal":
                detail = getattr(response.stop_details, "explanation", "") or ""
                raise RuntimeError(
                    "the model declined this premise. Soften content.absurdity or "
                    f"rewrite the idea. {detail}".strip()
                )

            raw = "".join(b.text for b in response.content if b.type == "text")
            try:
                data = _extract_json(raw)
                last_problems = _validate(data, config)
            except ScriptValidationError as exc:
                data, last_problems = {}, [str(exc)]

            if not last_problems:
                return _to_script(data, idea, config)

            log.warning("script attempt %d rejected: %s", attempt, "; ".join(last_problems))
            messages += [
                {"role": "assistant", "content": raw},
                {
                    "role": "user",
                    "content": "That output was rejected:\n- "
                    + "\n- ".join(last_problems)
                    + "\nReturn the corrected JSON object only.",
                },
            ]

        raise ScriptValidationError(
            "model could not produce a valid script after 2 attempts: "
            + "; ".join(last_problems)
        )


def _to_script(data: dict, idea: Idea, config: Config) -> Script:
    beats = [
        Beat(
            text=str(b["text"]).strip(),
            visual=str(b["visual"]).strip(),
            motion=str(b.get("motion", "push_in")) if str(b.get("motion")) in VALID_MOTIONS else "push_in",
        )
        for b in data["beats"]
    ]
    mode = str(config.get("content.mode", "satire")).lower()
    return Script(
        title=str(data["title"]).strip(),
        hook=str(data["hook"]).strip().upper(),
        beats=beats,
        description=str(data.get("description", "")).strip(),
        tags=[str(t).strip().lower() for t in data.get("tags", []) if str(t).strip()],
        idea=idea,
        disclaimer=str(config.get("content.disclaimer", "")) if mode == "satire" else "",
    )
