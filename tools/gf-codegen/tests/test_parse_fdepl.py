from __future__ import annotations

from pathlib import Path

from gf_codegen.compose.parse_fdepl import parse_fdepl_file


def test_parse_repo_sample_fdepl(tmp_path: Path) -> None:
    p = tmp_path / "VehicleStatus.fdepl"
    p.write_text(
        """
define afc.demo.VehicleStatus someip {
  SomeIpServiceID = 0x1234
  SomeIpInstanceID = 1
}
""",
        encoding="utf-8",
    )
    parsed = parse_fdepl_file(p)
    assert parsed["deployments"]
    dep = next(d for d in parsed["deployments"] if "SomeIpServiceID" in d)
    assert dep["SomeIpServiceID"] == 0x1234
    assert dep["SomeIpInstanceID"] == 1
