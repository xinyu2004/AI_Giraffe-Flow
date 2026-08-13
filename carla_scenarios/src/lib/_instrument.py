"""Instrument-cluster overlay (top bar + hood bottom band).

Layout v3 (agreed): translucent top bar + hood band; compact speed / SET / TGT;
feature slots from ``src/cluster_templates/*`` (unknown → common).
"""

from __future__ import annotations

import json
import os
import sys
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Optional  # Any used by make_cluster_state / ego helpers

# Templates live at src/cluster_templates/ (sibling of lib/), not under lib/.
_SRC = Path(__file__).resolve().parent.parent
if str(_SRC) not in sys.path:
    sys.path.insert(0, str(_SRC))
try:
    from cluster_templates import resolve_template
except ImportError as exc:  # pragma: no cover - hard fail: HUD feature slots missing
    raise ImportError(
        "cluster_templates not found — expected carla_scenarios/src/cluster_templates/. "
        "HUD feature slots (th/gap/TTC/…) will not draw."
    ) from exc

MISSING = "--"


def mps_to_kph(mps: float) -> float:
    return float(mps) * 3.6


def fmt_num(value: Optional[float], *, digits: int = 0) -> str:
    if value is None:
        return MISSING
    if digits <= 0:
        return str(int(round(value)))
    return f"{value:.{digits}f}"


def ctrl_path() -> Path:
    return Path(os.environ.get("GF_PLANNING_CTRL_PATH") or "/tmp/gf_planning_ctrl.json")


@dataclass
class CtrlProbe:
    """Read planning ctrl tip (target_speed / mode)."""

    path: Path = field(default_factory=ctrl_path)
    last_mtime: float = -1.0
    last_ts: int = -1
    fresh_count: int = 0
    _armed: bool = False
    target_speed_mps: Optional[float] = None
    mode: str = ""

    def poll(self) -> bool:
        p = self.path
        if not p.is_file():
            self.target_speed_mps = None
            self.mode = ""
            return False
        try:
            mtime = p.stat().st_mtime
            data = json.loads(p.read_text(encoding="utf-8"))
        except Exception:  # noqa: BLE001
            self.target_speed_mps = None
            self.mode = ""
            return False
        ts = int(data.get("timestamp_ns") or data.get("seq") or 0)
        if "target_speed_mps" in data:
            try:
                self.target_speed_mps = float(data["target_speed_mps"])
            except (TypeError, ValueError):
                self.target_speed_mps = None
        else:
            self.target_speed_mps = None
        self.mode = str(data.get("mode") or "")
        if not self._armed:
            self.last_mtime = mtime
            self.last_ts = ts
            self._armed = True
            return False
        if ts != self.last_ts or mtime != self.last_mtime:
            self.fresh_count += 1
            self.last_ts = ts
            self.last_mtime = mtime
            return True
        return False

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

    # ChaseCam: "1"=windshield, "2"=scene (ScenarioView.pump fills this)
    cam_mode: str = "1"

    template: str = "common"
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


def infer_cluster_template(tag: str) -> str:
    """Map case id → instrument template (plugin under cluster_templates/)."""
    t = (tag or "").strip().lower()
    if t.startswith("aeb") or t == "fcw":
        return "aeb"
    if t.startswith("acc") or t in ("isa_limit_follow",):
        return "acc"
    if t.startswith(("lka", "ldw", "elk", "lcc")):
        return "lateral"
    if t.startswith("hlb") or "night_glare" in t or "night_lead" in t:
        return "hlb"
    if t.startswith("tsr") or t.startswith("isa"):
        return "tsr"
    # weather follow cases use template explicitly ("acc")
    return "common"


def ego_yaw_rate_degps(ego: Any) -> Optional[float]:
    try:
        av = ego.get_angular_velocity()
        return float(av.z)
    except Exception:  # noqa: BLE001
        return None


def make_cluster_state(
    *,
    tag: str,
    template: Optional[str] = None,
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
    alert: str = "",
    meta: Optional[dict[str, Any]] = None,
) -> ClusterState:
    """Build ClusterState for any case (ACC-style chrome + feature slots)."""
    run = load_run_meta()
    case_id = str(run.get("case_id") or tag)
    keyword = str(run.get("keyword") or "")
    tmpl = (template or infer_cluster_template(tag)).strip().lower()
    meta = meta or {}

    if set_kph is None and tmpl in ("acc", "follow"):
        set_kph = acc_set_kph_default()
    if not beam and tmpl == "hlb":
        beam = str(meta.get("beam") or "LB")
    if limit_kph is None and tmpl in ("tsr", "isa"):
        if meta.get("speed_limit_kph") is not None:
            limit_kph = float(meta["speed_limit_kph"])
        else:
            try:
                limit_kph = float(os.environ.get("GF_TSR_LIMIT_KPH") or "60")
            except ValueError:
                limit_kph = 60.0
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
        template=tmpl,
    )


def draw_cluster(pygame: Any, display: Any, fonts: dict[str, Any], st: ClusterState) -> None:
    """v3 layout: top bar (case + time) + hood band (speed/SET/TGT + template + CTRL)."""
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
    colors = {
        "white": white,
        "mute": mute,
        "accent": accent,
        "warn": warn,
    }

    # Top bar (v3): case i/N · keyword·id  |  t / T s
    kid = st.keyword or st.case_id or "case"
    cid = st.case_id or kid
    left = f"{st.case_index}/{st.case_total}  {kid}·{cid}"
    right = f"{st.t_s:0.1f} / {st.duration_s:0.0f} s"
    display.blit(font.render(left, True, white), (12, 6))
    rw = font.size(right)[0]
    display.blit(font.render(right, True, white), (w - rw - 12, 6))

    # Main row (hood): speed | SET | TGT | <cluster_templates feature slots>
    main_y = band_y + 28
    x = 16
    speed_s = fmt_num(st.speed_kph, digits=0)
    display.blit(font_lg.render(speed_s, True, white), (x, main_y - 14))
    display.blit(font_sm.render("kph", True, mute), (x + font_lg.size(speed_s)[0] + 6, main_y))
    x = 110
    display.blit(font_sm.render("SET", True, mute), (x, main_y - 14))
    display.blit(font.render(fmt_num(st.set_kph), True, white), (x + 36, main_y - 16))
    x = 210
    display.blit(font_sm.render("TGT", True, mute), (x, main_y - 14))
    tgt_col = mute if st.tgt_kph is None else white
    display.blit(font.render(fmt_num(st.tgt_kph), True, tgt_col), (x + 36, main_y - 16))

    resolve_template(st.template)(
        pygame,
        display,
        fonts,
        colors,
        st,
        band_y=band_y,
        band_h=band_h,
        main_y=main_y,
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
