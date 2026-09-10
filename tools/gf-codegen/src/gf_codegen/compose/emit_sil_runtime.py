"""Deprecated shim — prefer emit_deploy_config."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from gf_codegen.compose.emit_deploy_config import (
    emit_deploy_config,
    normalize_deploy_flags,
    normalize_sil_runtime,
)


def emit_sil_runtime(
    req: dict[str, Any],
    platform: dict[str, Any] | None,
    gen_dir: Path,
    *,
    wiring: dict[str, Any] | None = None,
    ara_cfg_dir: Path | None = None,
) -> dict[str, str]:
    """Legacy entry: writes deploy_config.hpp (+ human YAML). No .env."""
    plat = (
        ara_cfg_dir
        if ara_cfg_dir is not None
        else gen_dir.parent / "cfg" / "gf_ara_cfg"
    )
    meta = emit_deploy_config(req, platform, plat, gen_dir, wiring=wiring)
    return {"hpp": meta["hpp"], "env": ""}


__all__ = [
    "emit_sil_runtime",
    "normalize_sil_runtime",
    "normalize_deploy_flags",
    "emit_deploy_config",
]
