"""Authored merge: extra keys, hex/int ids, empty args stay on disk."""

from __future__ import annotations

from gf_config.authored import merge_authored, values_equiv
from gf_config.core import ProjectSession


def _session() -> ProjectSession:
    s = object.__new__(ProjectSession)
    s.req = {}
    s.wiring = {}
    s.ara_cfg = {}
    s.dirty_req = False
    s.dirty_wiring = False
    s.dirty_ara_cfg = set()
    return s


def test_values_equiv_hex_int() -> None:
    assert values_equiv(0xF100, "0xf100")
    assert values_equiv(61696, "0xF100")
    assert not values_equiv([], ["0"])


def test_merge_keeps_rid_note_and_id_form() -> None:
    old = [{"id": 0xF100, "name": "start_ota", "note": "keep me"}]
    new = [{"id": "0xf100", "name": "start_ota"}]
    merged, changed = merge_authored(old, new)
    assert not changed
    assert merged[0]["note"] == "keep me"
    assert merged[0]["id"] == 0xF100


def test_update_ara_doc_rid_roundtrip_clean() -> None:
    s = _session()
    s.ara_cfg = {
        "diag": {
            "schema_version": "0.1",
            "rids": [
                {"id": 0xF100, "name": "start_ota", "note": "keep me"},
            ],
        }
    }
    assert s.update_ara_doc("diag", rids=[{"id": "0xf100", "name": "start_ota"}]) is False
    assert s.dirty_ara_cfg == set()
    assert s.get_ara_doc("diag")["rids"][0]["note"] == "keep me"
    assert s.get_ara_doc("diag")["rids"][0]["id"] == 0xF100


def test_update_ara_doc_empty_em_args_clean() -> None:
    s = _session()
    s.ara_cfg = {
        "em_launch": {
            "schema_version": "0.1",
            "processes": [
                {
                    "name": "host.dlt_daemon",
                    "binary": "bin/dlt-daemon",
                    "args": [],
                    "max_restarts": 3,
                }
            ],
        }
    }
    assert (
        s.update_ara_doc(
            "em_launch",
            processes=[
                {
                    "name": "host.dlt_daemon",
                    "binary": "bin/dlt-daemon",
                    "args": [],
                    "max_restarts": 3,
                }
            ],
        )
        is False
    )
    assert s.get_ara_doc("em_launch")["processes"][0]["args"] == []


def test_update_ara_doc_real_rid_rename_dirties() -> None:
    s = _session()
    s.ara_cfg = {
        "diag": {
            "schema_version": "0.1",
            "rids": [{"id": 0xF100, "name": "start_ota", "note": "keep me"}],
        }
    }
    assert s.update_ara_doc("diag", rids=[{"id": "0xf100", "name": "renamed"}]) is True
    assert s.dirty_ara_cfg == {"diag"}
    assert s.get_ara_doc("diag")["rids"][0]["note"] == "keep me"
    assert s.get_ara_doc("diag")["rids"][0]["name"] == "renamed"
