"""lint against schema examples (demo does not ship project golden SOR)."""

from __future__ import annotations

from pathlib import Path

from gf_codegen.lint_cmd import lint_file


def test_lint_desktop_ap_only(repo_root: Path) -> None:
    sor = repo_root / "schemas/examples/desktop_ap_only.sor.json"
    schema = repo_root / "schemas/gf.sor.schema.json"
    assert sor.is_file(), f"missing example SOR: {sor}"
    assert lint_file(sor, schema_path=schema) == 0
