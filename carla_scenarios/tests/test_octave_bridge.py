"""Unit tests for octave_bridge semantic + protocol (no CARLA)."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

_ROOT = Path(__file__).resolve().parents[1]
_LIB = _ROOT / "src" / "lib"
sys.path.insert(0, str(_ROOT))
sys.path.insert(0, str(_LIB))

from _fake_perc_pack import pack_fake_perc_pod  # noqa: E402
from octave_bridge.protocol import (  # noqa: E402
    pack_cmd,
    unpack_fake_perc,
    unpack_vehicle_state,
    VS,
    GF_CH_VEHICLE_STATE_MAGIC,
    GF_CH_POD_VERSION,
)
from octave_bridge.semantic_map import (  # noqa: E402
    PlanningResult,
    build_view,
    result_to_cmd_blob,
    view_to_bev_out_dict,
)


def test_unpack_fake_perc_roundtrip() -> None:
    lane = {
        "lane_count": 3,
        "ego_lane_index_from_left": 1,
        "lane_avail": 2,
        "lane_conf": 0.9,
        "lane_vr_end_m": 80.0,
        "lane_width_m": 3.5,
        "host_left_c0": 1.8,
        "host_right_c0": -1.7,
        "host_c1": 0.01,
        "host_c2": 0.0,
        "host_left_c1": 0.01,
        "host_right_c1": 0.01,
        "host_left_c2": 0.0,
        "host_right_c2": 0.0,
        "host_left_type": 1,
        "host_right_type": 1,
        "adj_n": 1,
        "adj0_side": 1,
        "adj0_c0": 5.2,
        "adj0_c1": 0.0,
        "adj0_c2": 0.0,
        "adj0_type": 2,
    }
    dyn = {
        "dyn_n": 1,
        "vd_count": 1,
        "ped_count": 0,
        "cipv_id": 7,
        "obj0_id": 7,
        "obj0_cls": 1,
        "obj0_assign": 3,
        "obj0_is_ped": 0,
        "obj0_long": 25.0,
        "obj0_lat": 0.2,
        "obj0_heading": 0.0,
        "obj0_len": 4.5,
        "obj0_wid": 1.8,
        "obj0_rel_v": -2.0,
        "lead_from_dyn_long": 25.0,
        "lead_from_dyn_lat": 0.2,
        "lead_from_dyn_rel_v": -2.0,
        "lead_from_dyn_heading": 0.0,
        "lead_from_dyn_assign": 3,
    }
    blob = pack_fake_perc_pod(lane=lane, dyn=dyn, seq=3, timestamp_ns=123)
    fp = unpack_fake_perc(blob)
    assert fp is not None
    assert fp["seq"] == 3
    assert fp["lane_avail"] == 2
    assert fp["host_left_c0"] == pytest.approx(1.8)
    assert fp["dyn_n"] == 1
    assert fp["obj"][0]["id"] == 7
    assert fp["obj"][0]["long_m"] == pytest.approx(25.0)
    assert fp["adj_n"] == 1
    assert fp["adj_c0"][0] == pytest.approx(5.2)


def test_build_view_and_plan() -> None:
    import struct
    import time

    vs = struct.pack(
        VS.format,
        GF_CH_VEHICLE_STATE_MAGIC,
        GF_CH_POD_VERSION,
        0,
        time.time_ns(),
        10.0,
        0.0,
        0.0,
        4,
    )
    state = unpack_vehicle_state(vs)
    assert state is not None

    lane = {
        "lane_count": 1,
        "lane_avail": 2,
        "lane_conf": 0.95,
        "lane_vr_end_m": 60.0,
        "lane_width_m": 3.5,
        "host_left_c0": 1.75,
        "host_right_c0": -1.75,
        "host_c1": 0.0,
        "host_c2": 0.0,
        "host_left_type": 1,
        "host_right_type": 1,
        "adj_n": 0,
    }
    dyn = {
        "dyn_n": 0,
        "vd_count": 0,
        "ped_count": 0,
        "cipv_id": 0,
        "lead_from_dyn_long": 0.0,
    }
    fp = unpack_fake_perc(pack_fake_perc_pod(lane=lane, dyn=dyn, seq=1))
    view = build_view(state=state, fake_perc=fp)
    assert view.perc.lane_valid
    assert abs(view.perc.e_y) < 0.05
    blob = result_to_cmd_blob(
        PlanningResult(
            throttle=0.3,
            steer=0.0,
            ctrl_mode="cruise",
            points_x_m=[0.0, 10.0],
            points_y_m=[0.0, 0.0],
        ),
        speed_mps=10.0,
        seq=1,
    )
    assert len(blob) == 48

    out = view_to_bev_out_dict(view)
    assert out["Perception_LH_Out"]["m_hostline_num"] == 2


def test_plan_only_on_fake_perc() -> None:
    """State caches only; one on_tick per FAKE_PERC (P clock 1:1, no double plan)."""
    import struct
    import time

    from octave_bridge.io_server import CosimIoServer
    from octave_bridge.protocol import (
        GF_COSIM_MSG_FAKE_PERC,
        GF_COSIM_MSG_VEHICLE_STATE,
        pack_cmd,
    )

    ticks: list[int] = []

    def on_tick(st: object) -> bytes:
        ticks.append(int(getattr(st, "seq_in")))
        return pack_cmd(
            seq=len(ticks),
            timestamp_ns=1,
            throttle=0.1,
            brake=0.0,
            steer=0.0,
            target_speed_mps=10.0,
            speed_mps=10.0,
            ctrl_mode=0,
        )

    srv = CosimIoServer(on_tick=on_tick)

    class Cli:
        def __init__(self) -> None:
            self.sent: list[bytes] = []

        def sendall(self, b: bytes) -> None:
            self.sent.append(b)

    cli = Cli()

    vs = struct.pack(
        VS.format,
        GF_CH_VEHICLE_STATE_MAGIC,
        GF_CH_POD_VERSION,
        0,
        time.time_ns(),
        10.0,
        0.0,
        0.0,
        4,
    )
    lane = {
        "lane_count": 1,
        "lane_avail": 2,
        "lane_conf": 0.95,
        "lane_vr_end_m": 60.0,
        "lane_width_m": 3.5,
        "host_left_c0": 1.75,
        "host_right_c0": -1.75,
        "host_c1": 0.0,
        "host_c2": 0.0,
        "host_left_type": 1,
        "host_right_type": 1,
        "adj_n": 0,
    }
    dyn = {
        "dyn_n": 0,
        "vd_count": 0,
        "ped_count": 0,
        "cipv_id": 0,
        "lead_from_dyn_long": 0.0,
    }
    perc = pack_fake_perc_pod(lane=lane, dyn=dyn, seq=1)
    srv._handle(cli, GF_COSIM_MSG_VEHICLE_STATE, vs, 1, 1)
    assert ticks == []
    assert cli.sent == []
    srv._handle(cli, GF_COSIM_MSG_FAKE_PERC, perc, 1, 2)
    assert ticks == [2]
    assert len(cli.sent) == 1
    srv._handle(cli, GF_COSIM_MSG_VEHICLE_STATE, vs, 1, 3)
    assert ticks == [2]


def test_unpack_plan_vec_layout() -> None:
    from octave_bridge.runtime import unpack_plan_vec

    hdr = [
        0.3, 0.0, 0.05, 12.0,
        40.0, 8.0, 120.0, 0.1,
        25.0, 1.0, 0.0, 0.017,
        16.0, 0.0,
    ]
    xs = [float(i) for i in range(16)]
    ys = [0.1 * i for i in range(16)]
    vs = [12.0 - 0.2 * i for i in range(16)]
    got = unpack_plan_vec(hdr + xs + ys + vs)
    assert got["throttle"] == 0.3
    assert got["mode"] == "cruise"
    assert got["t_m_s"] == 0.017
    assert got["x_m"] == xs
    assert got["allow_lc"] == 1.0
    assert len(got["v_mps"]) == 16


def test_stdio_frame_roundtrip() -> None:
    from octave_bridge.runtime import pack_stdio_frame, unpack_stdio_frame

    vec = [float(i) * 0.1 for i in range(62)]
    assert unpack_stdio_frame(pack_stdio_frame(vec)) == vec


def test_ipc_order_auto_stdio_then_file() -> None:
    from octave_bridge.runtime import ipc_order

    assert ipc_order("auto", "win32") == ["stdio", "file"]
    assert ipc_order("auto", "linux") == ["stdio", "file"]
    assert ipc_order("pipe", "win32") == ["pipe"]
    assert ipc_order("file", "linux") == ["file"]
    assert ipc_order("tcp", "win32") == ["tcp"]


def test_stdio_binmode_oct_source_present() -> None:
    src = Path(__file__).resolve().parents[2] / "octave_planning" / "afc" / "gf_stdio_binmode_oct.cc"
    assert src.is_file()
    text = src.read_text(encoding="utf-8")
    assert "_setmode" in text
    assert "O_BINARY" in text


def test_pipe_peer_fifo_roundtrip() -> None:
    """Python pipe peer ↔ a fake Octave (same GPLN frame). POSIX FIFO only."""
    if sys.platform == "win32":
        pytest.skip("posix fifo")
    import os
    import struct
    import tempfile
    import threading
    from pathlib import Path

    from octave_bridge.runtime import (
        _OUT_N,
        _PipePeer,
        pack_stdio_frame,
        unpack_stdio_frame,
    )

    class _Proc:
        def poll(self) -> None:
            return None

        def kill(self) -> None:
            return None

    tmp = Path(tempfile.mkdtemp())
    in_p = tmp / "to_oct.pipe"
    out_p = tmp / "from_oct.pipe"
    os.mkfifo(in_p)
    os.mkfifo(out_p)
    err: list[BaseException] = []

    def octave_side() -> None:
        try:
            with open(in_p, "rb", buffering=0) as fin, open(out_p, "wb", buffering=0) as fout:
                buf = bytearray()
                while len(buf) < 8:
                    chunk = fin.read(8 - len(buf))
                    if not chunk:
                        return
                    buf.extend(chunk)
                _magic, n = struct.unpack_from("<II", buf, 0)
                need = 8 * n
                body = bytearray()
                while len(body) < need:
                    chunk = fin.read(need - len(body))
                    if not chunk:
                        return
                    body.extend(chunk)
                vec = unpack_stdio_frame(bytes(buf) + bytes(body))
                out = [0.0] * _OUT_N
                out[0] = float(vec[0])
                out[11] = 0.001
                out[12] = 1.0
                fout.write(pack_stdio_frame(out))
                fout.flush()
        except BaseException as exc:  # noqa: BLE001
            err.append(exc)

    th = threading.Thread(target=octave_side, daemon=True)
    th.start()
    w = open(in_p, "wb", buffering=0)
    r = open(out_p, "rb", buffering=0)
    peer = _PipePeer(_Proc(), w, r)  # type: ignore[arg-type]
    try:
        got = peer.tick([3.5] + [0.0] * 69)
    finally:
        peer.close()
    th.join(2.0)
    assert err == []
    assert got[0] == pytest.approx(3.5)
    assert got[11] == pytest.approx(0.001)


def test_start_pipe_live_octave() -> None:
    import shutil

    from octave_bridge.runtime import (
        _dummy_in,
        _start_pipe,
        resolve_octave_planning,
        unpack_plan_vec,
    )

    if shutil.which("octave-cli") is None and shutil.which("octave") is None:
        pytest.skip("no octave-cli")
    root = resolve_octave_planning()
    if root is None:
        pytest.skip("no octave_planning")
    peer = _start_pipe(root)
    try:
        got = unpack_plan_vec(peer.tick(_dummy_in()))
        assert "throttle" in got
        assert got["t_m_s"] >= 0.0
    finally:
        peer.close()


def test_bev_async_replaces_queued() -> None:
    import time

    from octave_bridge.bev_feed import BevAsync
    from octave_bridge.semantic_map import PlanningResult, PlanningView

    class _Feed:
        n = 0

        def update(self, view: object, result: object) -> None:
            self.n += 1
            return None

    class _Hub:
        def publish_row(self, _cam: object) -> None:
            return None

    ba = BevAsync(_Feed(), _Hub())  # type: ignore[arg-type]
    v = PlanningView()
    r = PlanningResult()
    ba.submit(v, r)
    ba.submit(v, r)
    ba.submit(v, r)
    time.sleep(0.4)
    ba.stop()
    # V may drop; never more than a couple composes for a burst
    assert ba.dropped() >= 0


def test_bev_feed_imports() -> None:
    from octave_bridge.bev_feed import BevFeed

    feed = BevFeed()
    assert feed is not None
