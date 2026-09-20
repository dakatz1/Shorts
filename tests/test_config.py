import pytest

from shorts.config import Config, load_config


def test_defaults_load(config):
    assert config.get("visual.width") == 1080
    assert config.get("providers.llm") == "stub"


def test_dotted_get_missing_returns_default(config):
    assert config.get("nope.not.here", "fallback") == "fallback"


def test_require_raises_on_missing(config):
    with pytest.raises(KeyError):
        config.require("visual.nonexistent")


def test_cli_overrides_are_typed():
    cfg = load_config(overrides=["visual.layout=full", "content.beats=7", "music.enabled=false"])
    assert cfg.get("visual.layout") == "full"
    assert cfg.get("content.beats") == 7          # int, not "7"
    assert cfg.get("music.enabled") is False      # bool, not "false"


def test_override_requires_equals():
    with pytest.raises(ValueError):
        load_config(overrides=["visual.layout"])


def test_merge_is_deep_and_non_destructive(config):
    merged = config.merged_with({"visual": {"layout": "full"}})
    assert merged.get("visual.layout") == "full"
    assert merged.get("visual.width") == 1080      # siblings survive
    assert config.get("visual.layout") == "split"  # original untouched


def test_set_creates_intermediate_nodes():
    cfg = Config({})
    cfg.set("a.b.c", 1)
    assert cfg.get("a.b.c") == 1
