"""camera_contract is read once per process (batch must not remount every case)."""

from __future__ import annotations

import sys
from pathlib import Path

_LIB = Path(__file__).resolve().parents[1] / "src" / "lib"
sys.path.insert(0, str(_LIB))

from _camera_mount import (  # noqa: E402
    load_camera_mount,
    load_host_cameras,
    reset_camera_contract_cache,
)


def test_load_camera_mount_prints_once(capsys) -> None:
    reset_camera_contract_cache()
    a = load_camera_mount()
    b = load_camera_mount()
    assert a == b
    cams = load_host_cameras(enabled_only=True)
    assert cams
    out = capsys.readouterr().out
    assert out.count("[camera_mount]") == 1
    assert out.count("[cameras]") == 1
