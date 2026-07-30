"""P1-2: req.yaml → generated/gf_build.cmake."""

from __future__ import annotations

from pathlib import Path

from gf_codegen.compose.emit_build_cmake import emit_build_cmake


def test_emit_build_cmake_bindings_and_modules(tmp_path: Path) -> None:
    out = tmp_path / "gf_build.cmake"
    emit_build_cmake(
        {
            "variant": "afc_front_camera",
            "runtime_modules": ["core", "com", "log"],
            "bindings": ["iceoryx"],
            "apps": ["demo_pipeline"],
        },
        out,
    )
    text = out.read_text(encoding="utf-8")
    assert "GF_SKU_APPLIED TRUE" in text
    assert 'GF_SKU_VARIANT "afc_front_camera"' in text
    assert "GF_WITH_ICEORYX ON" in text
    assert "GF_WITH_SOMEIP OFF" in text
    assert "GF_WITH_DDS OFF" in text
    assert "set(GF_RUNTIME_MODULES core com log)" in text
    assert "set(GF_APPS demo_pipeline)" in text


def test_emit_build_cmake_multi_bindings(tmp_path: Path) -> None:
    out = tmp_path / "gf_build.cmake"
    emit_build_cmake(
        {
            "variant": "full",
            "runtime_modules": ["core", "com", "exec"],
            "bindings": ["iceoryx", "dds", "someip"],
            "apps": ["demo_pipeline", "simulators/uss_feed"],
        },
        out,
    )
    text = out.read_text(encoding="utf-8")
    assert "GF_WITH_ICEORYX ON" in text
    assert "GF_WITH_DDS ON" in text
    assert "GF_WITH_SOMEIP ON" in text
    assert "GF_APPS demo_pipeline simulators/uss_feed" in text
