import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


@pytest.fixture(autouse=True)
def _run_from_repo_root(monkeypatch):
    """Config and prompt loading use repo-relative paths."""
    monkeypatch.chdir(ROOT)


@pytest.fixture
def config():
    from shorts.config import load_config

    return load_config()
