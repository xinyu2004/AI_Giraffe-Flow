from __future__ import annotations

from pathlib import Path

from gf_codegen.compose.parse_fdepl import parse_fdepl_file


def test_parse_repo_sample_fdepl(repo_root: Path) -> None:
    p = repo_root / "projects/oem_a/afc_with_uss/interfaces/demo_fidl/VehicleStatus.fdepl"
    parsed = parse_fdepl_file(p)
    assert parsed["deployments"]
    dep = next(d for d in parsed["deployments"] if "SomeIpServiceID" in d)
    assert dep["SomeIpServiceID"] == 0x1234
    assert dep["SomeIpInstanceID"] == 1
