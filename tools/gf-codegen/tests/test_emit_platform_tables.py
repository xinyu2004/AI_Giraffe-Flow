"""platform_tables.hpp emit — ProcessSupervisor freeze source."""

from __future__ import annotations

from pathlib import Path

from gf_codegen.compose.emit_platform_tables import emit_platform_tables


def test_emit_includes_on_failure_and_forces_daemon_ec_false(tmp_path: Path) -> None:
    path = emit_platform_tables(
        {
            "exec": {
                "processes": [
                    {
                        "name": "host.iox_roudi",
                        "function_group": "MachineFG",
                        "execution_client": True,  # must be forced false
                    },
                    {
                        "name": "planning.driving",
                        "function_group": "MachineFG",
                        "execution_client": True,
                    },
                ]
            },
            "phm": {
                "entities": [
                    {
                        "id": "planning_alive",
                        "process": "planning.driving",
                        "alive_period_ms": 100,
                        "alive_timeout_ms": 300,
                        "on_failure": "restart",
                    }
                ]
            },
        },
        tmp_path,
    )
    assert path is not None
    text = path.read_text(encoding="utf-8")
    assert '"host.iox_roudi"' in text
    assert '"host.iox_roudi", "MachineFG", false' in text
    assert '"planning.driving", "MachineFG", true' in text
    assert '"restart"' in text
    assert "FindExec" in text and "FindPhm" in text
