"""Load/save gate: validate_project does not mutate; open stays clean."""

from __future__ import annotations

import copy
from pathlib import Path

import pytest

from gf_config.core import ProjectSession
from gf_config.validate import ALWAYS_ON_MODULES, validate_project


def _adc_giraffe() -> Path:
    return Path(__file__).resolve().parents[3] / "projects" / "adc" / "giraffe.yaml"


@pytest.mark.skipif(not _adc_giraffe().is_file(), reason="adc project missing")
def test_adc_validate_ok_and_open_not_dirty() -> None:
    sess = ProjectSession.open(_adc_giraffe())
    assert sess.validate().ok
    assert not sess.is_dirty()


@pytest.mark.skipif(not _adc_giraffe().is_file(), reason="adc project missing")
def test_missing_always_on_fails_validate() -> None:
    sess = ProjectSession.open(_adc_giraffe())
    sess.req["runtime_modules"] = [
        m for m in (sess.req.get("runtime_modules") or []) if m not in ALWAYS_ON_MODULES
    ]
    result = sess.validate()
    assert not result.ok
    assert any("always-on" in e for e in result.errors)


@pytest.mark.skipif(not _adc_giraffe().is_file(), reason="adc project missing")
def test_save_all_refuses_invalid_keeps_disk() -> None:
    sess = ProjectSession.open(_adc_giraffe())
    req_path = sess.paths.req
    before = req_path.read_text(encoding="utf-8")
    sess.req["runtime_modules"] = ["exec"]  # missing always-on
    sess.dirty_req = True
    result = sess.save_all(require_valid=True)
    assert not result.ok
    assert sess.dirty_req
    assert req_path.read_text(encoding="utf-8") == before


@pytest.mark.skipif(not _adc_giraffe().is_file(), reason="adc project missing")
def test_host_capability_mismatch_fails() -> None:
    sess = ProjectSession.open(_adc_giraffe())
    em = copy.deepcopy(sess.ara_cfg.get("em_launch") or {})
    procs = [p for p in (em.get("processes") or []) if isinstance(p, dict)]
    em["processes"] = [
        p for p in procs if str(p.get("name") or "") != "host.iox_roudi"
    ]
    sess.ara_cfg["em_launch"] = em
    result = validate_project(sess.req, sess.wiring, sess.ara_cfg)
    assert not result.ok
    assert any("host.iox_roudi" in e for e in result.errors)
