"""Layered configuration: packaged defaults <- user config file <- CLI overrides."""

from __future__ import annotations

import copy
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml

DEFAULT_CONFIG_PATH = Path("config/default.yaml")


def _deep_merge(base: dict[str, Any], override: dict[str, Any]) -> dict[str, Any]:
    out = copy.deepcopy(base)
    for key, value in (override or {}).items():
        if isinstance(value, dict) and isinstance(out.get(key), dict):
            out[key] = _deep_merge(out[key], value)
        else:
            out[key] = value
    return out


@dataclass
class Config:
    """Dict-backed config with dotted-path access.

    Kept deliberately thin — the YAML file is the real schema and it is
    documented inline in config/default.yaml.
    """

    data: dict[str, Any]

    def get(self, dotted: str, default: Any = None) -> Any:
        node: Any = self.data
        for part in dotted.split("."):
            if not isinstance(node, dict) or part not in node:
                return default
            node = node[part]
        return node

    def require(self, dotted: str) -> Any:
        sentinel = object()
        value = self.get(dotted, sentinel)
        if value is sentinel:
            raise KeyError(f"missing required config key: {dotted}")
        return value

    def set(self, dotted: str, value: Any) -> None:
        parts = dotted.split(".")
        node = self.data
        for part in parts[:-1]:
            node = node.setdefault(part, {})
        node[parts[-1]] = value

    def merged_with(self, override: dict[str, Any]) -> "Config":
        return Config(_deep_merge(self.data, override))


def _coerce(raw: str) -> Any:
    """Turn a CLI --set value into a real type (via YAML scalar rules)."""
    try:
        return yaml.safe_load(raw)
    except yaml.YAMLError:
        return raw


def load_config(path: Path | None = None, overrides: list[str] | None = None) -> Config:
    """Load default.yaml, layer a user config on top, then apply `key=value` overrides."""
    base_path = DEFAULT_CONFIG_PATH
    data: dict[str, Any] = {}
    if base_path.exists():
        data = yaml.safe_load(base_path.read_text(encoding="utf-8")) or {}

    if path:
        user_path = Path(path)
        if not user_path.exists():
            raise FileNotFoundError(f"config file not found: {user_path}")
        data = _deep_merge(data, yaml.safe_load(user_path.read_text(encoding="utf-8")) or {})

    config = Config(data)
    for item in overrides or []:
        if "=" not in item:
            raise ValueError(f"--set expects key=value, got: {item!r}")
        key, _, value = item.partition("=")
        config.set(key.strip(), _coerce(value.strip()))
    return config
