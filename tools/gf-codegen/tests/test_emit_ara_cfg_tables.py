"""ara_cfg_tables.hpp emit — ProcessSupervisor freeze source."""

from __future__ import annotations

from pathlib import Path

from gf_codegen.compose.emit_ara_cfg_tables import emit_ara_cfg_tables


def test_emit_ara_cfg_tables_minimal(tmp_path: Path) -> None:
    path = emit_ara_cfg_tables(
        {
            "exec": {
                "processes": [
                    {
                        "name": "planning.driving",
                        "function_group": "MachineFG",
                        "execution_client": True,
                    }
                ]
            },
            "phm": {
                "entities": [
                    {
                        "id": "planning_alive",
                        "process": "planning.driving",
                        "alive_period_ms": 100,
                        "alive_timeout_ms": 300,
                        "on_failure": "log",
                    }
                ]
            },
        },
        tmp_path,
    )
    assert path is not None
    assert path.name == "ara_cfg_tables.hpp"
    text = path.read_text(encoding="utf-8")
    assert "namespace gf_gen::ara_cfg" in text
    assert "FindExec" in text
    assert "planning.driving" in text
    assert not (tmp_path / "include/gf_gen/platform_tables.hpp").exists()
