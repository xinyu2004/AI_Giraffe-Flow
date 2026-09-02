"""Instrument-cluster overlay (top bar + hood bottom band).

Top: case / time. Hood left: speed / SET / TGT / CTRL. Hood right: gap th TTC / SIG PED LIM yaw.
Empty fields show --. No per-case template skins.
"""

from __future__ import annotations

import os
import time
from dataclasses import dataclass, field
from typing import Any, Optional

MISSING = "--"


def mps_to_kph(mps: float) -> float:
    return float(mps) * 3.6


def fmt_num(value: Optional[float], *, digits: int = 0) -> str:
    if value is None:
        return MISSING
    if digits <= 0:
        return str(int(round(value)))
    return f"{value:.{digits}f}"


@dataclass
class CtrlProbe:
    """Read mode/target_speed from local UDP tip (shared with CmdProbe)."""

    last_seq: int = -1
    fresh_count: int = 0
    target_speed_mps: Optional[float] = None
    mode: str = ""
    _tip: Any = field(default=None, repr=False)

    def _rx(self) -> Any:
        if self._tip is None:
            from _ctrl_tip import shared_receiver

            self._tip = shared_receiver()
        return self._tip

    def poll(self) -> bool:
        tip = self._rx()
        changed = tip.poll()
        self.fresh_count = tip.fresh_count
        self.last_seq = tip.last_seq
        self.target_speed_mps = tip.target_speed_mps
        self.mode = tip.mode
        return changed

    @property
    def seen(self) -> bool:
        return self.fresh_count > 0


@dataclass
class ClusterState:
    """Fields for ScenarioView instrument layer."""

    case_index: int = 1
    case_total: int = 1
    case_id: str = ""
    keyword: str = ""
    t_s: float = 0.0
    duration_s: float = 0.0

    speed_kph: Optional[float] = None
    set_kph: Optional[float] = None
    tgt_kph: Optional[float] = None

    th_s: Optional[float] = None
    th_lo: float = 1.0
    th_hi: float = 2.5
    gap_m: Optional[float] = None

    mode: str = ""
    ctrl_ok: bool = False  # True → green blink; False → red blink
    alert: str = ""

    yaw_rate_degps: Optional[float] = None
    beam: str = ""
    limit_kph: Optional[float] = None
    ttc_s: Optional[float] = None
    sig: Optional[str] = None
    sig_m: Optional[float] = None
    ped: Optional[str] = None
    ped_m: Optional[float] = None

    # ChaseCam: "1"=windshield, "2"=scene (ScenarioView.pump fills this)
    cam_mode: str = "1"

    # Wall time for CTRL blink (set by view each frame); None → time.time()
    now_s: Optional[float] = None

    # Backward alias used by older call sites
    @property
    def cmd_ok(self) -> bool:
        return self.ctrl_ok

    @cmd_ok.setter
    def cmd_ok(self, v: bool) -> None:
        self.ctrl_ok = bool(v)


def load_run_meta() -> dict[str, Any]:
    return {
        "case_index": int(os.environ.get("GF_SCENARIO_CASE_INDEX") or "1"),
        "case_total": int(os.environ.get("GF_SCENARIO_CASE_TOTAL") or "1"),
        "case_id": os.environ.get("GF_SCENARIO_CASE_ID") or "",
        "keyword": os.environ.get("GF_SCENARIO_CASE_KEYWORD") or "",
    }


def prime_run_meta(case_id: str, *, keyword: str = "") -> None:
    """Fill case env for single-case runs (run_cases already sets these)."""
    cid = (case_id or "").strip() or "case"
    os.environ.setdefault("GF_SCENARIO_CASE_ID", cid)
    os.environ.setdefault("GF_SCENARIO_CASE_INDEX", "1")
    os.environ.setdefault("GF_SCENARIO_CASE_TOTAL", "1")
    os.environ.setdefault(
        "GF_SCENARIO_CASE_KEYWORD",
        (keyword or cid.upper().split("_")[0]).strip(),
    )


def acc_set_kph_default() -> Optional[float]:
    raw = os.environ.get("GF_ACC_SET_KPH")
    if raw is None or str(raw).strip() == "":
        return 50.0
    try:
        return float(raw)
    except ValueError:
        return None


def ego_yaw_rate_degps(ego: Any) -> Optional[float]:
    try:
        av = ego.get_angular_velocity()
        return float(av.z)
    except Exception:  # noqa: BLE001
        return None


def make_cluster_state(
    *,
    tag: str,
    elapsed: float,
    duration_s: float,
    ego_mps: float,
    gap_m: float = 0.0,
    th_s: Optional[float] = None,
    th_lo: float = 1.0,
    th_hi: float = 2.5,
    ctrl_ok: bool = False,
    tgt_kph: Optional[float] = None,
    mode: str = "",
    set_kph: Optional[float] = None,
    ttc_s: Optional[float] = None,
    yaw_rate_degps: Optional[float] = None,
    beam: str = "",
    limit_kph: Optional[float] = None,
    sig: Optional[str] = None,
    sig_m: Optional[float] = None,
    ped: Optional[str] = None,
    ped_m: Optional[float] = None,
    alert: str = "",
    meta: Optional[dict[str, Any]] = None,
    template: Optional[str] = None,
) -> ClusterState:
    """Build ClusterState. template= is ignored (kept so old callers do not break)."""
    del template
    run = load_run_meta()
    case_id = str(run.get("case_id") or tag)
    keyword = str(run.get("keyword") or "")
    meta = meta or {}
    if set_kph is None:
        set_kph = acc_set_kph_default()
    if limit_kph is None and meta.get("speed_limit_kph") is not None:
        limit_kph = float(meta["speed_limit_kph"])
    if not beam:
        beam = str(meta.get("beam") or "")
    if mode and not ctrl_ok:
        mode = ""

    return ClusterState(
        case_index=int(run["case_index"]),
        case_total=int(run["case_total"]),
        case_id=case_id,
        keyword=keyword or tag.upper().split("_")[0],
        t_s=elapsed,
        duration_s=duration_s,
        speed_kph=mps_to_kph(ego_mps),
        set_kph=set_kph,
        tgt_kph=tgt_kph,
        th_s=th_s,
        th_lo=th_lo,
        th_hi=th_hi,
        gap_m=gap_m if gap_m > 0 else None,
        mode=mode,
        ctrl_ok=ctrl_ok,
        alert=alert,
        yaw_rate_degps=yaw_rate_degps,
        beam=beam,
        limit_kph=limit_kph,
        ttc_s=ttc_s,
        sig=sig,
        sig_m=sig_m,
        ped=ped,
        ped_m=ped_m,
    )


def _slot(
    display: Any,
    font: Any,
    label: str,
    value: str,
    x: int,
    y: int,
    *,
    mute: tuple[int, int, int],
    value_c: tuple[int, int, int],
) -> int:
    display.blit(font.render(label, True, mute), (x, y - 12))
    display.blit(font.render(value, True, value_c), (x, y + 4))
    return x + max(font.size(label)[0], font.size(value)[0]) + 16


def draw_cluster(pygame: Any, display: Any, fonts: dict[str, Any], st: ClusterState) -> None:
    """Top bar (case + time) + hood: driving left, exam right."""
    w, h = display.get_size()
    band_h = max(96, int(h * 0.20))
    band_y = h - band_h

    # Semi-transparent panels (scene remains visible through them).
    top = pygame.Surface((w, 32), pygame.SRCALPHA)
    top.fill((8, 12, 18, 110))
    display.blit(top, (0, 0))
    band = pygame.Surface((w, band_h), pygame.SRCALPHA)
    band.fill((8, 12, 18, 110))
    display.blit(band, (0, band_y))

    font = fonts["md"]
    font_sm = fonts["sm"]
    font_lg = fonts["lg"]
    white = (235, 238, 242)
    mute = (160, 168, 178)
    accent = (80, 210, 120)
    warn = (220, 70, 70)

    # Top bar: case i/N · keyword·id  |  t / T s
    kid = st.keyword or st.case_id or "case"
    cid = st.case_id or kid
    left = f"{st.case_index}/{st.case_total}  {kid}·{cid}"
    right = f"{st.t_s:0.1f} / {st.duration_s:0.0f} s"
    display.blit(font.render(left, True, white), (12, 6))
    rw = font.size(right)[0]
    display.blit(font.render(right, True, white), (w - rw - 12, 6))

    main_y = band_y + 22
    x = 16
    speed_s = fmt_num(st.speed_kph, digits=0)
    display.blit(font_lg.render(speed_s, True, white), (x, main_y - 8))
    display.blit(font_sm.render("kph", True, mute), (x + font_lg.size(speed_s)[0] + 6, main_y + 6))
    x = 108
    display.blit(font_sm.render("SET", True, mute), (x, main_y - 8))
    display.blit(font.render(fmt_num(st.set_kph), True, white), (x + 32, main_y - 10))
    x = 200
    display.blit(font_sm.render("TGT", True, mute), (x, main_y - 8))
    tgt_col = mute if st.tgt_kph is None else white
    display.blit(font.render(fmt_num(st.tgt_kph), True, tgt_col), (x + 32, main_y - 10))

    exam_x = max(320, int(w * 0.42))
    gap_s = fmt_num(st.gap_m, digits=0) if st.gap_m is not None else MISSING
    th_s = f"{st.th_s:0.1f}" if st.th_s is not None else MISSING
    ttc_s = f"{st.ttc_s:0.1f}" if st.ttc_s is not None else MISSING
    x = exam_x
    x = _slot(display, font_sm, "gap", f"{gap_s}m", x, main_y, mute=mute, value_c=white)
    x = _slot(display, font_sm, "th", f"{th_s}s", x, main_y, mute=mute, value_c=white)
    ttc_c = warn if st.ttc_s is not None and st.ttc_s < 3.0 else white
    x = _slot(display, font_sm, "TTC", f"{ttc_s}s", x, main_y, mute=mute, value_c=ttc_c)

    sig_c = mute
    if st.sig == "RED":
        sig_c = warn
    elif st.sig == "YEL":
        sig_c = (230, 190, 60)
    elif st.sig == "GRN":
        sig_c = accent
    sig_v = MISSING if not st.sig else (
        f"{st.sig} {st.sig_m:0.0f}m" if st.sig_m is not None else st.sig
    )
    row2 = main_y + 36
    x = exam_x
    x = _slot(display, font_sm, "SIG", sig_v, x, row2, mute=mute, value_c=sig_c)
    ped_v = MISSING if not st.ped else (
        f"{st.ped} {st.ped_m:0.0f}m" if st.ped_m is not None else st.ped
    )
    ped_c = accent if st.ped else mute
    x = _slot(display, font_sm, "PED", ped_v, x, row2, mute=mute, value_c=ped_c)
    lim_v = fmt_num(st.limit_kph, digits=0) if st.limit_kph is not None else MISSING
    x = _slot(display, font_sm, "LIM", lim_v, x, row2, mute=mute, value_c=white)
    if st.yaw_rate_degps is not None:
        _slot(
            display,
            font_sm,
            "yaw",
            f"{st.yaw_rate_degps:0.1f}",
            x,
            row2,
            mute=mute,
            value_c=white,
        )

    # CTRL lamp: ~2 Hz blink — green when ok, red when no signal.
    by = h - 22
    now = st.now_s if st.now_s is not None else time.time()
    on = (int(now * 4) % 2) == 0
    if st.ctrl_ok:
        lamp = accent if on else (25, 55, 35)
    else:
        lamp = warn if on else (55, 22, 22)
    pygame.draw.circle(display, lamp, (22, by), 7)
    pygame.draw.circle(display, (20, 20, 20), (22, by), 7, 1)
    display.blit(font_sm.render("CTRL", True, white), (36, by - 7))
    mode = st.mode.upper() if st.mode and st.ctrl_ok else ""
    if mode:
        display.blit(font_sm.render(mode, True, white), (90, by - 7))
    if st.alert:
        display.blit(font_sm.render(st.alert, True, warn), (w // 2 - 40, band_y + 4))
