from __future__ import annotations

from pathlib import Path

import pytest


@pytest.fixture
def repo_root() -> Path:
    # tests/ -> codegen/ -> tools/ -> repo
    root = Path(__file__).resolve().parents[3]
    assert (root / "schemas").is_dir() and (root / "projects").is_dir()
    return root
