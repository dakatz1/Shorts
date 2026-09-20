import pytest

from shorts.ideas import IdeaGenerator
from shorts.providers import get_script_provider
from shorts.providers.llm_anthropic import ScriptValidationError, _extract_json, _validate
from shorts.prompting import build_system_prompt, build_user_prompt


@pytest.fixture
def idea():
    return IdeaGenerator(absurdity=5, seed=11).generate()


def test_stub_writes_the_configured_number_of_beats(idea, config):
    cfg = config.merged_with({"content": {"beats": 6}})
    script = get_script_provider(cfg).write(idea, cfg)
    assert len(script.beats) == 6
    assert all(b.text and b.visual for b in script.beats)


def test_stub_is_deterministic_for_an_idea(idea, config):
    a = get_script_provider(config).write(idea, config)
    b = get_script_provider(config).write(idea, config)
    assert a.to_dict() == b.to_dict()


def test_satire_mode_attaches_a_disclaimer(idea, config):
    assert get_script_provider(config).write(idea, config).disclaimer


def test_deadpan_mode_omits_the_disclaimer(idea, config):
    cfg = config.merged_with({"content": {"mode": "deadpan"}})
    assert get_script_provider(cfg).write(idea, cfg).disclaimer == ""


def test_unknown_provider_names_the_valid_options(config):
    cfg = config.merged_with({"providers": {"llm": "gpt9"}})
    with pytest.raises(ValueError, match="anthropic"):
        get_script_provider(cfg)


def test_prompts_render_without_stray_placeholders(idea, config):
    """No `{beats}`-style token may survive formatting.

    Braces themselves are expected — the system prompt shows a JSON example —
    so match the placeholder shape rather than the character.
    """
    import re

    placeholder = re.compile(r"\{[a-z_]+\}")
    for text in (build_system_prompt(config), build_user_prompt(idea, config)):
        assert text.strip()
        assert not placeholder.search(text), placeholder.search(text).group()


def test_prompts_interpolate_the_real_values(idea, config):
    system = build_system_prompt(config)
    user = build_user_prompt(idea, config)
    assert f"exactly {config.get('content.beats')} beats" in system
    assert str(config.get("voice.style")) in system
    assert idea.claim in user
    assert idea.exercise in user


def test_prompt_carries_the_mode_instruction(idea, config):
    deadpan = config.merged_with({"content": {"mode": "deadpan"}})
    assert "satire" in build_user_prompt(idea, config).lower()
    assert "straight" in build_user_prompt(idea, deadpan).lower()


# --- response parsing / validation ---------------------------------------

def test_extract_json_handles_a_code_fence():
    assert _extract_json('```json\n{"a": 1}\n```') == {"a": 1}


def test_extract_json_handles_surrounding_prose():
    assert _extract_json('Sure!\n{"a": 1}\nHope that helps.') == {"a": 1}


def test_extract_json_rejects_garbage():
    with pytest.raises(ScriptValidationError):
        _extract_json("no json here")


def _payload(beats: int = 5, text: str = "A short spoken line.") -> dict:
    return {
        "title": "t",
        "hook": "HOOK",
        "beats": [{"text": text, "visual": "v", "motion": "push_in"} for _ in range(beats)],
    }


def test_validation_accepts_a_good_payload(config):
    assert _validate(_payload(int(config.get("content.beats"))), config) == []


def test_validation_catches_the_wrong_beat_count(config):
    problems = _validate(_payload(2), config)
    assert any("expected exactly" in p for p in problems)


def test_validation_catches_banned_words(config):
    payload = _payload(int(config.get("content.beats")), "This will cure everything.")
    assert any("banned word" in p for p in _validate(payload, config))


def test_validation_catches_an_overlong_hook(config):
    payload = _payload(int(config.get("content.beats")))
    payload["hook"] = "H" * 80
    assert any("hook is too long" in p for p in _validate(payload, config))


def test_validation_catches_rambling_beats(config):
    payload = _payload(int(config.get("content.beats")), " ".join(["word"] * 40))
    assert any("keep spoken lines under" in p for p in _validate(payload, config))
