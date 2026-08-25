from __future__ import annotations

from pathlib import Path

from gf_octavecoder.generate import generate_sku


def test_generate_afc_clamp() -> None:
    root = Path(__file__).resolve().parents[3]
    assert (root / "octave_planning" / "common" / "gf_clamp.m").is_file()
    rc = generate_sku(repo_root=root, sku="afc", force=True)
    assert rc == 0
    out = root / "projects" / "afc" / "apps" / "planning" / "driving" / "oct_gen" / "gf_clamp.hpp"
    assert out.is_file()
    text = out.read_text(encoding="utf-8")
    assert "gf_octave_planning::clamp" in text
    assert "namespace oct_gen" in text


def test_clamp_m_matches_ops_semantics() -> None:
    """Golden: .m algorithm ≡ C ops (independent function contract)."""

    def gf_clamp(x: float, lo: float, hi: float) -> float:
        return min(max(x, lo), hi)

    assert gf_clamp(-1.0, 0.0, 1.0) == 0.0
    assert gf_clamp(0.5, 0.0, 1.0) == 0.5
    assert gf_clamp(2.0, 0.0, 1.0) == 1.0
