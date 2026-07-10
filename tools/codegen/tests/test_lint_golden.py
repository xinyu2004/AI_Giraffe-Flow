from __future__ import annotations

from pathlib import Path

from gf_codegen.lint_cmd import lint_file


def test_lint_golden(repo_root: Path) -> None:
    sor = repo_root / "projects/oem_b/adc_full/golden/gf.sor.json"
    schema = repo_root / "schemas/gf.sor.schema.json"
    assert lint_file(sor, schema_path=schema) == 0


def test_lint_desktop_skeleton(repo_root: Path) -> None:
    sor = repo_root / "schemas/examples/desktop_ap_only.sor.json"
    schema = repo_root / "schemas/gf.sor.schema.json"
    assert lint_file(sor, schema_path=schema) == 0
