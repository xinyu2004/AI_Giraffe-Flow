"""Scaffold new Giraffe project trees."""

from __future__ import annotations

from pathlib import Path

from gf_codegen.compose.load_project import GIRAFFE_YAML, load_project
from gf_codegen.scaffold_project import scaffold_project


def test_scaffold_minimal_tree(tmp_path: Path, repo_root: Path) -> None:
    dest = tmp_path / "demo_sku"
    entry = scaffold_project(dest, project_id="demo_sku", product="DEMO")
    assert entry.name == GIRAFFE_YAML
    assert (dest / "cfg" / "req.yaml").is_file()
    assert (dest / "cfg" / "wiring.yaml").is_file()
    assert (dest / "cfg" / "gf_ara_cfg" / "exec.yaml").is_file()
    paths = load_project(entry, repo_root=repo_root)
    assert paths.req == dest / "cfg" / "req.yaml"
    assert "exec" in paths.gf_ara_cfg
