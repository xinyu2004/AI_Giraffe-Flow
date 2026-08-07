"""platform log → log_config.hpp."""

from __future__ import annotations

from pathlib import Path

from gf_codegen.compose.emit_log_config import emit_log_config, normalize_log_config


def test_normalize_log_defaults() -> None:
    cfg = normalize_log_config({})
    assert cfg["default_level"] == "INFO"
    assert "console" in cfg["sinks"]


def test_emit_log_config_hpp(tmp_path: Path) -> None:
    platform = {
        "log": {
            "default_level": "WARN",
            "color": "off",
            "sinks": ["console", "dlt"],
            "file_path": "x.log",
            "file_max_bytes": 1024,
            "dlt": {"app_id": "TEST", "max_contexts": 32},
            "contexts": [{"id": "em", "level": "INFO"}],
        }
    }
    meta = emit_log_config(platform, tmp_path)
    hpp = Path(meta["hpp"]).read_text(encoding="utf-8")
    assert 'kDefaultLevel = "WARN"' in hpp
    assert 'kDltAppId = "TEST"' in hpp
    assert "kDltMaxContexts = 32u" in hpp
    assert '{"em", "INFO"}' in hpp or '{ "em", "INFO" }' in hpp or '"em"' in hpp
