#!/usr/bin/env bash
# Measure SIL reference latencies → fusa/runs/measure_summary_*.json
# Numbers feed fusa/metrics/latency.md (review / paste after a snapshot run).
#
# Requires: SIL already built (binaries under GF_BUILD_DIR).
# Does not call run_cases.sh or generate_fusa_artifacts.sh.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "${ROOT}"
export PATH="${ROOT}/.venv/bin:${PATH}"
export GF_BUILD_DIR="${GF_BUILD_DIR:-${ROOT}/build}"

OUT_DIR="${ROOT}/fusa/runs"
mkdir -p "${OUT_DIR}"
STAMP="$(date -u +%Y%m%dT%H%M%SZ)"
GIT="$(git rev-parse --short HEAD 2>/dev/null || echo unknown)"
OUT_JSON="${OUT_DIR}/measure_summary_${STAMP}.json"

python3 - "${ROOT}" "${GF_BUILD_DIR}" "${OUT_JSON}" "${STAMP}" "${GIT}" <<'PY'
import json, os, re, subprocess, sys
from pathlib import Path

ROOT = Path(sys.argv[1])
BUILD = Path(sys.argv[2])
OUT_JSON = Path(sys.argv[3])
STAMP, GIT = sys.argv[4], sys.argv[5]
env = os.environ.copy()
env["PATH"] = str(ROOT / ".venv" / "bin") + ":" + env.get("PATH", "")
env["GF_BUILD_DIR"] = str(BUILD)


def run(cmd, extra=None):
    e = env.copy()
    if extra:
        e.update(extra)
    print("==", cmd, extra or "")
    r = subprocess.run(cmd, shell=True, cwd=ROOT, env=e, capture_output=True, text=True)
    print("   rc", r.returncode)
    if r.returncode != 0:
        sys.stderr.write(r.stdout[-2000:] + "\n" + r.stderr[-2000:] + "\n")
        raise SystemExit(r.returncode)
    return r


def pct(xs, p):
    if not xs:
        return None
    s = sorted(xs)
    k = (len(s) - 1) * p / 100
    f = int(k)
    c = min(f + 1, len(s) - 1)
    return round(s[f] + (s[c] - s[f]) * (k - f), 3)


def parse_t_ms(path, pat):
    rx = re.compile(pat)
    p = Path(path)
    if not p.exists():
        return []
    out = []
    for line in p.read_text(errors="replace").splitlines():
        if not rx.search(line):
            continue
        m = re.search(r"t_ms=(\d+)", line)
        if m:
            out.append((int(m.group(1)), line))
    return out


def first_t(path, pat):
    xs = parse_t_ms(path, pat)
    return xs[0] if xs else (None, None)


report = {"stamp": STAMP, "git": GIT, "host": "SIL desktop"}

run(
    "bash scripts/verify/oem_a_afc_with_uss/run_sil_multiproc.sh",
    {"GF_MP_TRAJ_COUNT": "30", "GF_PHM_FAULT_MS": "0"},
)
gw = BUILD / "iox_multiproc_logs" / "gateway.log"
ts = [
    int(m.group(1))
    for line in gw.read_text(errors="replace").splitlines()
    if (m := re.search(r"ts_ns=(\d+)", line))
]
deltas_ms = [(ts[i] - ts[i - 1]) / 1e6 for i in range(1, len(ts))]
report["traj"] = {
    "n": len(ts),
    "sample_ts_period_ms_p50": pct(deltas_ms, 50),
    "sample_ts_period_ms_p99": pct(deltas_ms, 99),
    "log": str(gw.relative_to(ROOT)),
    "note": "Trajectory.timestamp_ns inter-arrival at gateway (pipeline cadence; not hop e2e)",
}

run("bash scripts/verify/oem_a_afc_with_uss/smoke_sil_phm_fault.sh")
pl = BUILD / "iox_multiproc_logs" / "planning.log"
t_begin, _ = first_t(pl, r"FAULT inject begin")
t_miss, miss_line = first_t(pl, r"(AliveMissed|DeadlineMissed)")
t_rec, _ = first_t(pl, r"phm recovered")
kind = None
if miss_line:
    m = re.search(r"(AliveMissed|DeadlineMissed)", miss_line)
    kind = m.group(1) if m else None
report["phm"] = {
    "config_period_ms": 100,
    "config_timeout_ms": 300,
    "fault_inject_ms": 500,
    "begin_t_ms": t_begin,
    "miss_t_ms": t_miss,
    "recovered_t_ms": t_rec,
    "miss_kind": kind,
    "begin_to_miss_ms": (t_miss - t_begin) if t_begin is not None and t_miss is not None else None,
    "begin_to_recover_ms": (t_rec - t_begin) if t_begin is not None and t_rec is not None else None,
    "miss_to_recover_ms": (t_rec - t_miss) if t_miss is not None and t_rec is not None else None,
    "log": str(pl.relative_to(ROOT)),
    "pass": t_begin is not None and t_miss is not None and t_rec is not None,
}

run("bash scripts/verify/oem_a_afc_with_uss/smoke_sil_em_daemon.sh")
em = BUILD / "em_daemon_logs" / "em_daemon.stdout"
t_exit_d, _ = first_t(em, r"child exit name=planning")
t_rel, _ = first_t(em, r"relaunch name=planning")
t_spawn2, _ = first_t(em, r"relaunch=yes")
report["em_relaunch"] = {
    "daemon_exit_to_relaunch_ms": (t_rel - t_exit_d)
    if t_exit_d is not None and t_rel is not None
    else None,
    "daemon_exit_to_spawn2_ms": (t_spawn2 - t_exit_d)
    if t_exit_d is not None and t_spawn2 is not None
    else None,
    "daemon_log": str(em.relative_to(ROOT)),
    "note": "Same-process monotonic clock in em_daemon stdout; child logs reset on relaunch",
    "pass": t_rel is not None and t_spawn2 is not None,
}

smoke = BUILD / "middleware" / "collector" / "gf_collector_smoke"
cr = subprocess.run([str(smoke)], capture_output=True, text=True)
m = re.search(r"t_us_span=(\d+)", cr.stdout)
report["collector"] = {
    "ring_first_to_last_us": int(m.group(1)) if m else None,
    "note": "in-proc ReportEvent path; not IPC",
    "pass": cr.returncode == 0,
}
if cr.returncode != 0:
    raise SystemExit(cr.returncode)

OUT_JSON.write_text(json.dumps(report, indent=2) + "\n")
print("WROTE", OUT_JSON)
print(json.dumps(report, indent=2))
PY

echo "[fusa] measure done → ${OUT_JSON}"
echo "[fusa] paste numbers into fusa/metrics/latency.md if this is a release snapshot"
