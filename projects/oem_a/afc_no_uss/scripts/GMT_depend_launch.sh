#!/usr/bin/env bash
# GMT_depend_launch — extra deps for GMT (Foxglove / live_tap / inject / DoIP).
# Sourced by run_sil.sh after EM is up. Same tooling for host SIL and board early debug.
# Not a second product path: EM remains the truth; this only hangs GMT-side helpers.
#
# Skip: GF_GMT_DEPEND=0 (legacy alias: GF_SIL_FLOW=0).
set -euo pipefail

# Port preflight for Foxglove/inject/DoIP (host GMT side only).
# Skipped when GF_GMT_DEPEND=0 / board EM-only path.
LIVE_PORT="${LIVE_PORT:-${GF_LIVE_PORT:-8766}}"
INJ_PORT="${INJ_PORT:-${GF_INJECT_PORT:-8767}}"

# 释放上次 Ctrl+C 未清干净 / 重复开跑 留下的 bridge / inject / DoIP（EADDRINUSE / iceoryx same-name）
gf_sil_preflight_ports() {
  export GF_SIL_PORT_WS="${PORT}"
  export GF_SIL_PORT_LIVE="${LIVE_PORT}"
  export GF_SIL_PORT_INJ="${INJ_PORT}"
  export GF_SIL_PORT_DOIP="${DOIP_PORT}"
  export GF_SIL_KILL_STALE="${GF_SIL_KILL_STALE:-1}"
  export GF_SIL_INJECT_ON="${INJECT_ON}"
  export GF_SIL_LIVE_ON="${LIVE_ON}"
  export GF_SIL_DOIP_ON="${DOIP_ON}"
  python - <<'PY'
import os, re, signal, subprocess, time

tag = "[afc_no_uss]"

def cmdline(pid: int) -> str:
    try:
        return open(f"/proc/{pid}/cmdline", "rb").read().replace(b"\0", b" ").decode(
            "utf-8", "replace"
        )
    except OSError:
        return ""

def ss_listeners():
    try:
        out = subprocess.check_output(["ss", "-ltnp"], text=True, stderr=subprocess.DEVNULL)
    except (FileNotFoundError, subprocess.CalledProcessError):
        return []
    rows = []
    for line in out.splitlines():
        mport = re.search(r":(\d+)\s", line)
        if not mport:
            continue
        port = int(mport.group(1))
        for name, pid in re.findall(r'\("([^"]+)",pid=(\d+)', line):
            rows.append((port, name, int(pid)))
    return rows

def ancestor_pids(start: int) -> set[int]:
    """Exclude self + parents (e.g. bash run_sil / timeout wrapping this python)."""
    seen: set[int] = set()
    pid = start
    while pid > 1 and pid not in seen:
        seen.add(pid)
        try:
            with open(f"/proc/{pid}/stat", "r", encoding="utf-8") as f:
                # pid (comm) state ppid ... — comm may contain spaces/parens
                body = f.read()
            rparen = body.rfind(")")
            if rparen < 0:
                break
            parts = body[rparen + 2 :].split()
            pid = int(parts[1])  # ppid
        except (OSError, ValueError, IndexError):
            break
    return seen

def pids_matching(pattern: str) -> list[int]:
    try:
        out = subprocess.check_output(["pgrep", "-f", pattern], text=True)
    except (FileNotFoundError, subprocess.CalledProcessError):
        return []
    me = ancestor_pids(os.getpid())
    return [int(x) for x in out.split() if int(x) not in me]

wanted = set()
if os.environ.get("GF_SIL_LIVE_ON") == "1":
    wanted.add(int(os.environ["GF_SIL_PORT_WS"]))
    wanted.add(int(os.environ["GF_SIL_PORT_LIVE"]))
if os.environ.get("GF_SIL_INJECT_ON") == "1":
    wanted.add(int(os.environ["GF_SIL_PORT_INJ"]))
if os.environ.get("GF_SIL_DOIP_ON") == "1":
    wanted.add(int(os.environ["GF_SIL_PORT_DOIP"]))

kill_stale = os.environ.get("GF_SIL_KILL_STALE", "1") == "1"
listeners = [(p, n, pid) for p, n, pid in ss_listeners() if p in wanted]
other_run_sil = pids_matching("afc_no_uss/scripts/run_sil.sh")

if not listeners and not other_run_sil:
    if os.environ.get("GF_SIL_INJECT_ON") == "1" and kill_stale:
        subprocess.run(
            ["pkill", "-f", "gf_iox_obs_inject"],
            check=False,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
    if os.environ.get("GF_SIL_DOIP_ON") == "1" and kill_stale:
        subprocess.run(
            ["pkill", "-f", "gf_doip_ota_server"],
            check=False,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
    raise SystemExit(0)

if listeners:
    print(f"{tag} port busy (leftover SIL/GMT?):", flush=True)
    for p, n, pid in listeners:
        print(f"{tag}   :{p}  {n} pid={pid}", flush=True)
if other_run_sil:
    print(f"{tag} other run_sil still running: pids={other_run_sil}", flush=True)

ours, others = [], []
for p, n, pid in listeners:
    cmd = cmdline(pid)
    if (
        "GMT" in cmd
        or "gf_gmt" in cmd
        or "bridge" in cmd
        or "gf_iox_obs_inject" in cmd
        or "iox_obs_inject" in cmd
        or "gf_doip_ota_server" in cmd
        or n.startswith("gf_iox_obs")
        or n.startswith("gf_doip")
    ):
        ours.append((p, n, pid, cmd))
    else:
        others.append((p, n, pid, cmd))

if not kill_stale:
    print(f"{tag} ERROR: Address already in use / previous SIL still up.", flush=True)
    print(f"{tag}   → Ctrl+C the other terminal's run_sil, or re-run with:", flush=True)
    print(f"{tag}   GF_SIL_KILL_STALE=1 bash projects/oem_a/afc_no_uss/scripts/run_sil.sh …", flush=True)
    raise SystemExit(1)

targets = {pid for _, _, pid, _ in ours} | {pid for _, _, pid, _ in others}
targets.update(other_run_sil)
print(f"{tag} GF_SIL_KILL_STALE=1 → stopping stale pids {sorted(targets)}", flush=True)
for pid in sorted(targets):
    try:
        os.kill(pid, signal.SIGTERM)
    except OSError:
        pass
subprocess.run(
    ["pkill", "-f", "gf_iox_obs_inject"],
    check=False,
    stdout=subprocess.DEVNULL,
    stderr=subprocess.DEVNULL,
)
subprocess.run(
    ["pkill", "-f", "gf_doip_ota_server"],
    check=False,
    stdout=subprocess.DEVNULL,
    stderr=subprocess.DEVNULL,
)
subprocess.run(
    ["pkill", "-f", "GMT bridge"],
    check=False,
    stdout=subprocess.DEVNULL,
    stderr=subprocess.DEVNULL,
)
time.sleep(0.6)
for pid in sorted(targets):
    try:
        os.kill(pid, signal.SIGKILL)
    except OSError:
        pass
time.sleep(0.3)
left = [(p, n, pid) for p, n, pid in ss_listeners() if p in wanted]
if left:
    print(f"{tag} ERROR: still busy after kill:", flush=True)
    for p, n, pid in left:
        print(f"{tag}   :{p} {n} pid={pid} — {cmdline(pid)[:100]}", flush=True)
    raise SystemExit(1)
print(f"{tag} stale listeners cleared", flush=True)
PY
}

gf_sil_preflight_ports

# --- GMT depend (not EM) — DoIP / inject / live Foxglove -----------------------
# =============================================================================

if [[ "${DOIP_ON}" == "1" ]]; then
  # GMT DEM: real PHM AliveMissed in apps → PersistDtc → shared GF_PER_DIR;
  # DoIP 0x19 uses ReloadDtcsFromPer (no fake seed).
  # Opt-out: GF_PHM_FAULT_MS=0 before run_sil.
  if [[ -z "${_PHM_FAULT_USER}" ]]; then
    export GF_PHM_FAULT_MS=500
    export GF_PHM_FAULT_TARGET="${GF_PHM_FAULT_TARGET:-planning}"
  fi
  echo "${TAG} DoIP OTA server → TCP ${DOIP_PORT} (GMT OTA: 127.0.0.1:${DOIP_PORT})"
  echo "${TAG} DEM: PHM fault_ms=${GF_PHM_FAULT_MS} target=${GF_PHM_FAULT_TARGET} per=${GF_PER_DIR}"
  host_info "start DoIP OTA server port=${DOIP_PORT} per=${GF_PER_DIR} phm_fault_ms=${GF_PHM_FAULT_MS} target=${GF_PHM_FAULT_TARGET}"
  : >"${LOG_DIR}/doip_ota.log"
  # DoIP/UDS params from deploy_config.hpp (export for gf_doip_ota_server).
  if [[ -z "${GF_DIAG_S3_SERVER_MS+x}" ]]; then
    export GF_DIAG_S3_SERVER_MS="$(_gf_hpp_int "${DEPLOY_HPP}" kDiagS3ServerMs 5000)"
  fi
  if [[ -z "${GF_DIAG_TP_PERIOD_MS+x}" ]]; then
    export GF_DIAG_TP_PERIOD_MS="$(_gf_hpp_int "${DEPLOY_HPP}" kDiagTesterPresentPeriodMs 2000)"
  fi
  if [[ -z "${GF_DIAG_P2_SERVER_MS+x}" ]]; then
    export GF_DIAG_P2_SERVER_MS="$(_gf_hpp_int "${DEPLOY_HPP}" kDiagP2ServerMs 50)"
  fi
  if [[ -z "${GF_DIAG_P2STAR_SERVER_MS+x}" ]]; then
    export GF_DIAG_P2STAR_SERVER_MS="$(_gf_hpp_int "${DEPLOY_HPP}" kDiagP2StarServerMs 5000)"
  fi
  if [[ -z "${GF_DIAG_SECURITY_DELAY_MS+x}" ]]; then
    export GF_DIAG_SECURITY_DELAY_MS="$(_gf_hpp_int "${DEPLOY_HPP}" kDiagSecurityDelayMs 10000)"
  fi
  if [[ -z "${GF_OTA_TRANSFER_MODE+x}" ]]; then
    export GF_OTA_TRANSFER_MODE="$(_gf_hpp_cstr "${DEPLOY_HPP}" kOtaTransferMode request_file_transfer)"
  fi
  if [[ -z "${GF_OTA_REQUIRE_PROG_SESSION+x}" ]]; then
    export GF_OTA_REQUIRE_PROG_SESSION="$(_gf_hpp_bool "${DEPLOY_HPP}" kOtaRequireProgSession 1)"
  fi
  if [[ -z "${GF_OTA_REQUIRE_SECURITY+x}" ]]; then
    export GF_OTA_REQUIRE_SECURITY="$(_gf_hpp_bool "${DEPLOY_HPP}" kOtaRequireSecurity 1)"
  fi
  if [[ -z "${GF_OTA_MAX_BLOCK+x}" ]]; then
    export GF_OTA_MAX_BLOCK="$(_gf_hpp_int "${DEPLOY_HPP}" kOtaMaxBlockLength 1024)"
  fi
  if [[ -z "${GF_DOIP_LOGICAL_ADDR+x}" ]]; then
    export GF_DOIP_LOGICAL_ADDR="$(_gf_hpp_int "${DEPLOY_HPP}" kDoipLogicalAddr 3584)"
  fi
  if [[ -z "${GF_DOIP_TESTER_ADDR+x}" ]]; then
    export GF_DOIP_TESTER_ADDR="$(_gf_hpp_int "${DEPLOY_HPP}" kDoipTesterAddr 3712)"
  fi
  # Mirror UDS steps to terminal (same lines as GMT OTA log) + keep file
  (
    if command -v stdbuf >/dev/null 2>&1; then
      stdbuf -oL -eL env GF_DOIP_PORT="${DOIP_PORT}" "${DOIP}"
    else
      env GF_DOIP_PORT="${DOIP_PORT}" "${DOIP}"
    fi
  ) > >(tee -a "${LOG_DIR}/doip_ota.log" >&2) 2>&1 &
  DOIP_PID=$!
  sleep 0.3
  if ! kill -0 "${DOIP_PID}" 2>/dev/null; then
    host_info "DoIP server failed; see ${LOG_DIR}/doip_ota.log"
    echo "${TAG} DoIP server failed; see ${LOG_DIR}/doip_ota.log" >&2
    cat "${LOG_DIR}/doip_ota.log" >&2 || true
    exit 1
  fi
  host_info "DoIP ok pid=${DOIP_PID} port=${DOIP_PORT}"
fi

# Per-process PHM fault (others get 0). Target via GF_PHM_FAULT_TARGET.
_fault_ms_for() {
  local name="$1"
  if [[ "${GF_PHM_FAULT_MS}" == "0" ]]; then
    echo 0
  elif [[ "${name}" == "${GF_PHM_FAULT_TARGET}" ]]; then
    echo "${GF_PHM_FAULT_MS}"
  else
    echo 0
  fi
}

start_consumers() {
  local apps="${1:-fcm,planning}"
  local a
  host_info "spawn apps (direct, no EM) apps=${apps}"
  IFS=',' read -r -a _arr <<< "${apps}"
  for a in "${_arr[@]}"; do
    case "${a}" in
      fcm)
        echo "${TAG} start fcm (PHM fault_ms=$(_fault_ms_for fcm))"
        host_info "start app=fcm fault_ms=$(_fault_ms_for fcm)"
        # stdbuf: line-buffer stdout so smoke/timeout kill still leaves Trajectory lines on disk
        if command -v stdbuf >/dev/null 2>&1; then
          GF_DLT_APP_ID=FCM_ GF_PHM_FAULT_MS="$(_fault_ms_for fcm)" stdbuf -oL -eL "${FCM}" >"${LOG_DIR}/fcm.log" 2>&1 &
        else
          GF_DLT_APP_ID=FCM_ GF_PHM_FAULT_MS="$(_fault_ms_for fcm)" "${FCM}" >"${LOG_DIR}/fcm.log" 2>&1 &
        fi
        FCM_PID=$!
        ;;
      uss)
        echo "${TAG} start uss (PHM fault_ms=$(_fault_ms_for uss))"
        host_info "start app=uss fault_ms=$(_fault_ms_for uss)"
        if command -v stdbuf >/dev/null 2>&1; then
          GF_DLT_APP_ID=USS_ GF_PHM_FAULT_MS="$(_fault_ms_for uss)" stdbuf -oL -eL "${USS}" >"${LOG_DIR}/uss.log" 2>&1 &
        else
          GF_DLT_APP_ID=USS_ GF_PHM_FAULT_MS="$(_fault_ms_for uss)" "${USS}" >"${LOG_DIR}/uss.log" 2>&1 &
        fi
        USS_PID=$!
        ;;
      planning)
        echo "${TAG} start planning (PHM fault_ms=$(_fault_ms_for planning))"
        host_info "start app=planning fault_ms=$(_fault_ms_for planning)"
        if command -v stdbuf >/dev/null 2>&1; then
          GF_DLT_APP_ID=PLAN GF_PHM_FAULT_MS="$(_fault_ms_for planning)" stdbuf -oL -eL "${PLAN}" >"${LOG_DIR}/planning.log" 2>&1 &
        else
          GF_DLT_APP_ID=PLAN GF_PHM_FAULT_MS="$(_fault_ms_for planning)" "${PLAN}" >"${LOG_DIR}/planning.log" 2>&1 &
        fi
        PLAN_PID=$!
        ;;
    esac
  done
  sleep 0.5
}

if [[ "${INJECT_ON}" == "1" ]]; then
  # GMT inject is not EM scope (no inject/tap in em_launch). Stop EM so product
  # gateway does not dual-publish with inject; Flow starts RouDi+consumers+inject.
  echo "${TAG} GMT inject (Flow, not EM): stop EM; RouDi+consumers+inject"
  if [[ -n "${EM_PID:-}" ]]; then
    kill "${EM_PID}" 2>/dev/null || true
    pkill -P "${EM_PID}" >/dev/null 2>&1 || true
    wait "${EM_PID}" 2>/dev/null || true
    EM_PID=""
  fi
  if [[ "${IOX_ON}" == "1" ]]; then
    : >"${LOG_DIR}/roudi.log"
    "${ROUDI}" -c "${IOX_TOML}" >"${LOG_DIR}/roudi.log" 2>&1 &
    ROUDI_PID=$!
    sleep 0.8
  fi
  start_consumers "${RUN_APPS}"
  DRIVE_MODE="${GF_INJECT_MODE:-continuous}"
  INJ_PORT="${GF_INJECT_PORT:-8767}"
  INJ_HOST="${GF_INJECT_HOST:-0.0.0.0}"
  if [[ -n "${INJECT_SESSION}" ]]; then
    echo "${TAG} inject from ${INJECT_SESSION} (services=${GF_INJECT_SERVICES} topology=${INJECT_MODE} drive=${DRIVE_MODE})"
    export GF_INJECT_SESSION="${INJECT_SESSION}"
  else
    echo "${TAG} inject playhead stream (no session file; services=${GF_INJECT_SERVICES} topology=${INJECT_MODE})"
    unset GF_INJECT_SESSION || true
  fi
  export GF_INJECT_MODE="${DRIVE_MODE}"
  export GF_INJECT_PORT="${INJ_PORT}"
  export GF_INJECT_HOST="${INJ_HOST}"
  # Plain listen hint; colored LISTENING comes from inject (/dev/tty)
  if [[ -t 2 ]]; then
    export GF_STATUS_COLOR=1
  fi
  echo "${TAG} [GMT Inject] listen tcp://0.0.0.0:${INJ_PORT} (playhead)" >&2
  : >"${LOG_DIR}/inject.log"
  INJ_FIFO="${LOG_DIR}/inject.fifo"
  rm -f "${INJ_FIFO}"
  mkfifo "${INJ_FIFO}"
  # tee starts reading before inject writes → no lost LISTENING/CONNECTED lines
  tee -a "${LOG_DIR}/inject.log" <"${INJ_FIFO}" >&2 &
  INJ_TEE_PID=$!
  if command -v stdbuf >/dev/null 2>&1; then
    _INJ_RUN=(stdbuf -oL -eL "${INJ}")
  else
    _INJ_RUN=("${INJ}")
  fi
  if [[ -n "${INJECT_SESSION}" ]]; then
    GF_INJECT_SESSION="${INJECT_SESSION}" \
      GF_INJECT_MODE="${DRIVE_MODE}" \
      GF_INJECT_PORT="${INJ_PORT}" \
      GF_INJECT_HOST="${INJ_HOST}" \
      "${_INJ_RUN[@]}" "${INJECT_SESSION}" >"${INJ_FIFO}" 2>&1 &
  else
    # playhead stream-only: no argv path
    GF_INJECT_MODE="${DRIVE_MODE}" \
      GF_INJECT_PORT="${INJ_PORT}" \
      GF_INJECT_HOST="${INJ_HOST}" \
      "${_INJ_RUN[@]}" >"${INJ_FIFO}" 2>&1 &
  fi
  INJ_PID=$!

  LIVE_FAN_PID=""
  if [[ "${LIVE_ON}" == "1" ]]; then
    export GF_OBS_LIVE_SERVICES="${LIVE_SVCS}"
    LIVE_PORT="${GF_LIVE_PORT:-8766}"
    LIVE_SESSION="${GF_LIVE_SESSION:-$(gf_obs_dir)/session_live.jsonl}"
    LIVE_TEE="${GF_LIVE_TEE:-1}"
    HINT_IP="127.0.0.1"
    if [[ "${HOST}" == "0.0.0.0" || "${HOST}" == "::" ]]; then
      HINT_IP="$(hostname -I 2>/dev/null | awk '{print $1}')"
      HINT_IP="${HINT_IP:-127.0.0.1}"
    fi
    echo "${TAG} live services=${GF_OBS_LIVE_SERVICES}"
    echo "${TAG} listen Foxglove ws://${HINT_IP}:${PORT}  GMT-Live ws://${HINT_IP}:${LIVE_PORT}"
    # BEV from EgoMotion/Trajectory only. Scenario JSONL → GMT Open session / Inject
    # (or GF_INJECT_SESSION for continuous); not attached here.
    _FOX_BEV=()
    if [[ "${GF_SYNTH_BEV:-1}" != "0" ]]; then
      _FOX_BEV=(--synth-bev)
      echo "${TAG} Foxglove --synth-bev (EgoMotion/Trajectory → /gf/camera/front/compressed; GF_SYNTH_BEV=0 to disable)"
    fi
    _FOX_TIP=()
    if [[ "${GF_TIP_CAMERA:-1}" != "0" ]]; then
      if [[ -n "${GF_TIP_FRAME:-}" ]]; then
        _FOX_TIP=(--tip-frame "${GF_TIP_FRAME}")
        echo "${TAG} Foxglove tip camera ← ${GF_TIP_FRAME} (file bypass)"
      else
        _TIP_SLOT="${GF_CHANNEL_SLOT:-${GF_TIP_SLOT:-gf.channel.front}}"
        _FOX_TIP=(--tip-slot "${_TIP_SLOT}")
        echo "${TAG} Foxglove tip camera ← ${_TIP_SLOT} (GfChannel shm)"
      fi
    fi
    if [[ "${LIVE_TEE}" == "1" ]]; then
      mkdir -p "$(dirname "${LIVE_SESSION}")"
      : > "${LIVE_SESSION}"
    fi
    # Same fan isolation as non-inject path: GMT close must not kill Foxglove.
    _tee_fan() {
      if tee --help 2>&1 | grep -q -- '--output-error'; then
        tee --output-error=warn "$@"
      else
        tee "$@"
      fi
    }
    _gmt_live_bridge() {
      while true; do
        GMT bridge live --stdin --host "${HOST}" --port "${LIVE_PORT}"
        local ec=$?
        [[ "${ec}" -eq 0 ]] && break
        echo "${TAG} WARN: GMT live bridge exited ec=${ec}; restart in 0.3s" >&2
        sleep 0.3
      done
    }
    (
      if [[ "${LIVE_TEE}" == "1" ]]; then
        "${TAP}" 2>"${LOG_DIR}/tap.log" \
          | tee "${LIVE_SESSION}" \
          | _tee_fan >( _gmt_live_bridge ) \
          | GMT bridge foxglove --ws --stdin "${_FOX_BEV[@]}" "${_FOX_TIP[@]}" --host "${HOST}" --port "${PORT}"
      else
        "${TAP}" 2>"${LOG_DIR}/tap.log" \
          | _tee_fan >( _gmt_live_bridge ) \
          | GMT bridge foxglove --ws --stdin "${_FOX_BEV[@]}" "${_FOX_TIP[@]}" --host "${HOST}" --port "${PORT}"
      fi
    ) &
    LIVE_FAN_PID=$!
  fi

  FRAME_REPLAY_PID=""
  if [[ -n "${GF_INJECT_FRAMES_DIR:-}" ]]; then
    REPLAY_PY="${PROJECT_DIR}/tools/carla_bridge/frame_replay.py"
    PY="${GF_CARLA_PYTHON:-python3}"
    if [[ -f "${REPLAY_PY}" && -d "${GF_INJECT_FRAMES_DIR}" ]]; then
      echo "${TAG} frame_replay ← ${GF_INJECT_FRAMES_DIR} → ${GF_CARLA_FRAME_PATH}"
      "${PY}" "${REPLAY_PY}" --frames-dir "${GF_INJECT_FRAMES_DIR}" \
        --frame-path "${GF_CARLA_FRAME_PATH}" \
        $([ "${GF_INJECT_LOOP:-0}" = "1" ] && echo --loop) \
        >"${LOG_DIR}/frame_replay.log" 2>&1 &
      FRAME_REPLAY_PID=$!
    else
      echo "${TAG} WARN: GF_INJECT_FRAMES_DIR set but replay missing/dir absent" >&2
    fi
  fi

  if [[ "${DRIVE_MODE}" == "playhead" || "${DRIVE_MODE}" == "controlled" || "${DRIVE_MODE}" == "wait" ]]; then
    echo "${TAG} Ctrl+C to stop (yellow=listen green=CONNECTED cyan=DISCONNECTED red=err)"
    wait "${INJ_PID}" || true
    kill "${INJ_TEE_PID}" 2>/dev/null || true
    rm -f "${INJ_FIFO}"
    if [[ -n "${LIVE_FAN_PID}" ]]; then
      kill "${LIVE_FAN_PID}" 2>/dev/null || true
    fi
    if [[ -n "${FRAME_REPLAY_PID}" ]]; then
      kill "${FRAME_REPLAY_PID}" 2>/dev/null || true
    fi
    echo "${TAG} inject stopped; logs: ${LOG_DIR}/ (apps=${RUN_APPS})"
    exit 0
  fi
  # continuous: wait for inject to finish
  wait "${INJ_PID}" || true
  kill "${INJ_TEE_PID}" 2>/dev/null || true
  rm -f "${INJ_FIFO}"
  if [[ -n "${LIVE_FAN_PID}" ]]; then
    kill "${LIVE_FAN_PID}" 2>/dev/null || true
  fi
  if [[ -n "${FRAME_REPLAY_PID}" ]]; then
    kill "${FRAME_REPLAY_PID}" 2>/dev/null || true
  fi
  echo "${TAG} inject finished; logs: ${LOG_DIR}/ (apps=${RUN_APPS})"
  exit 0
fi

# EM owns gf_frame_ingest on the product path. Shell-start only when inject stopped EM.
# Tip module selected by GF_FRAME_SOURCE (isp|carla|replay|colorbar|none); inherited from run_sil.
CARLA_BRIDGE_PID=""
BRIDGE_TAIL_PID=""
FRAME_INGEST_STAT_PID=""
INGEST_BIN="${RUNTIME}/bin/gf_frame_ingest"
if [[ ! -x "${INGEST_BIN}" ]]; then
  INGEST_BIN="${BUILD}/apps/frame_ingest/gf_frame_ingest"
fi
if [[ "${INJECT_ON}" != "1" ]]; then
  echo "${TAG} frame_ingest: under EM (skip shell start)"
elif [[ -n "${GF_INJECT_FRAMES_DIR:-}" ]]; then
  echo "${TAG} skip gf_frame_ingest (GF_INJECT_FRAMES_DIR set)"
elif [[ -x "${INGEST_BIN}" ]]; then

  export GF_CARLA_FRAME_PATH="${GF_CARLA_FRAME_PATH:-${GF_PROJECT_DIR:-.}/runtime_ipc/front.yuv}"
  export GF_CARLA_CMD_PATH="${GF_CARLA_CMD_PATH:-${GF_PROJECT_DIR:-.}/runtime_ipc/carla_cmd.json}"
  export CARLA_HOST="${CARLA_HOST:-127.0.0.1}"
  export CARLA_PORT="${CARLA_PORT:-2000}"
  if [[ -z "${GF_RECORD_FRAMES_DIR+x}" && "${GF_LIVE_TEE:-1}" == "1" ]]; then
    export GF_RECORD_FRAMES_DIR="$(gf_obs_dir)/session_frames"
  fi
  if [[ -n "${GF_RECORD_FRAMES_DIR:-}" ]]; then
    mkdir -p "${GF_RECORD_FRAMES_DIR}"
    : >"${GF_RECORD_FRAMES_DIR}/frames.jsonl"
    echo "${TAG} record tip frames → ${GF_RECORD_FRAMES_DIR}"
  fi
  _gf_resolve_carla_python() {
    local c
    for c in \
      "${GF_CARLA_PYTHON:-}" \
      "${CONDA_PREFIX:+${CONDA_PREFIX}/bin/python}" \
      "${VIRTUAL_ENV:+${VIRTUAL_ENV}/bin/python}" \
      "${HOME}/miniconda3/envs/carla_env/bin/python" \
      "${HOME}/anaconda3/envs/carla_env/bin/python" \
      "python3"
    do
      [[ -n "${c}" ]] || continue
      if [[ "${c}" == */* && ! -x "${c}" ]]; then
        continue
      fi
      if "${c}" -c "import carla" >/dev/null 2>&1; then
        echo "${c}"
        return 0
      fi
    done
    echo "${GF_CARLA_PYTHON:-python3}"
    return 1
  }
  if PY="$(_gf_resolve_carla_python)"; then
    export GF_CARLA_PYTHON="${PY}"
  else
    PY="${GF_CARLA_PYTHON:-python3}"
    echo "${TAG} WARN: no Python with 'import carla' — carla tip module may fail" >&2
  fi
  echo "${TAG} gf_frame_ingest → ${INGEST_BIN} (python=${PY})"
  echo "${TAG} frame_ingest log → ${LOG_DIR}/frame_ingest.log"
  : >"${LOG_DIR}/frame_ingest.log"
  ln -sf "${LOG_DIR}/frame_ingest.log" "${LOG_DIR}/carla_bridge.log" 2>/dev/null || true
  if command -v stdbuf >/dev/null 2>&1; then
    stdbuf -oL -eL "${INGEST_BIN}" >>"${LOG_DIR}/frame_ingest.log" 2>&1 &
  else
    "${INGEST_BIN}" >>"${LOG_DIR}/frame_ingest.log" 2>&1 &
  fi
  CARLA_BRIDGE_PID=$!
  tail -n +1 -F "${LOG_DIR}/frame_ingest.log" 2>/dev/null &
  BRIDGE_TAIL_PID=$!
  sleep 0.6
  if ! kill -0 "${CARLA_BRIDGE_PID}" 2>/dev/null; then
    # Disabled freeze exits 0 quickly — not an error.
    if grep -q "disabled" "${LOG_DIR}/frame_ingest.log" 2>/dev/null; then
      echo "${TAG} gf_frame_ingest disabled by freeze (ok)"
      kill "${BRIDGE_TAIL_PID}" 2>/dev/null || true
      BRIDGE_TAIL_PID=""
      CARLA_BRIDGE_PID=""
    else
      echo "${TAG} WARN: gf_frame_ingest exited early; see ${LOG_DIR}/frame_ingest.log" >&2
      kill "${BRIDGE_TAIL_PID}" 2>/dev/null || true
      BRIDGE_TAIL_PID=""
      CARLA_BRIDGE_PID=""
    fi
  else
    host_info "gf_frame_ingest ok pid=${CARLA_BRIDGE_PID} host=${CARLA_HOST}:${CARLA_PORT}"
    (
      FCM_LOG="${LOG_DIR}/em/perception_fcm.log"
      [[ -f "${FCM_LOG}" ]] || FCM_LOG="${LOG_DIR}/fcm.log"
      STATS="${GF_CARLA_BRIDGE_STATS_PATH:-${GF_PROJECT_DIR:-.}/runtime_ipc/carla_bridge_stats.json}"
      while kill -0 "${CARLA_BRIDGE_PID}" 2>/dev/null; do
        sleep 5
        tip_slot="${GF_CHANNEL_SLOT:-${GF_TIP_SLOT:-gf.channel.front}}"
        echo "${TAG} frame_ingest heartbeat: pid=${CARLA_BRIDGE_PID} tip_slot=${tip_slot} host=${CARLA_HOST}:${CARLA_PORT}"
      done
    ) &
    FRAME_INGEST_STAT_PID=$!
  fi
else
  echo "${TAG} WARN: missing ${INGEST_BIN} — run compile_sil (stage runtime)" >&2
fi


# SOA apps already under EM. Do not direct-spawn gateway/fcm/planning.
host_info "apps under EM — logs: ${GF_EM_LOG_DIR}/ and ${LOG_DIR}/em_daemon.stdout"
echo "${TAG} [EM] apps managed by EM pid=${EM_PID} (no direct spawn)"

if [[ "${LIVE_ON}" != "1" ]]; then
  echo "${TAG} live_tap off — EM only. logs: ${LOG_DIR}/ ${GF_EM_LOG_DIR}/"
  echo "${TAG} (enable live_tap in gf-config → Verify/compile → re-run for Foxglove)"
  wait "${EM_PID}" || true
  exit 0
fi

export GF_OBS_LIVE_SERVICES="${LIVE_SVCS}"
LIVE_PORT="${GF_LIVE_PORT:-8766}"
HINT_IP="127.0.0.1"
if [[ "${HOST}" == "0.0.0.0" || "${HOST}" == "::" ]]; then
  HINT_IP="$(hostname -I 2>/dev/null | awk '{print $1}')"
  HINT_IP="${HINT_IP:-<this-host-LAN-IP>}"
fi
echo "${TAG} live services=${GF_OBS_LIVE_SERVICES}"
echo "${TAG} listen Foxglove ws://${HINT_IP}:${PORT}  GMT-Live ws://${HINT_IP}:${LIVE_PORT}"
echo "${TAG} Ctrl+C to stop (yellow=listen green=CONNECTED cyan=DISCONNECTED red=err)"
if [[ -t 2 ]]; then
  export GF_STATUS_COLOR=1
fi

LIVE_SESSION="${GF_LIVE_SESSION:-$(gf_obs_dir)/session_live.jsonl}"
LIVE_TEE="${GF_LIVE_TEE:-1}"
if [[ "${LIVE_TEE}" == "1" ]]; then
  mkdir -p "$(dirname "${LIVE_SESSION}")"
  : > "${LIVE_SESSION}"
fi

_FOX_BEV=()
if [[ "${GF_SYNTH_BEV:-1}" != "0" ]]; then
  _FOX_BEV=(--synth-bev)
  echo "${TAG} Foxglove --synth-bev (EgoMotion/Trajectory → BEV)"
fi
_FOX_TIP=()
if [[ "${GF_TIP_CAMERA:-1}" != "0" ]]; then
  if [[ -n "${GF_TIP_FRAME:-}" ]]; then
    _FOX_TIP=(--tip-frame "${GF_TIP_FRAME}")
    echo "${TAG} Foxglove tip camera ← ${GF_TIP_FRAME} (file bypass)"
  else
    _TIP_SLOT="${GF_CHANNEL_SLOT:-${GF_TIP_SLOT:-gf.channel.front}}"
    _FOX_TIP=(--tip-slot "${_TIP_SLOT}")
    echo "${TAG} Foxglove tip camera ← ${_TIP_SLOT} (GfChannel shm)"
  fi
fi

# GNU tee: if GMT Live process-sub dies, do NOT collapse the pipe to Foxglove.
_tee_fan() {
  if tee --help 2>&1 | grep -q -- '--output-error'; then
    tee --output-error=warn "$@"
  else
    tee "$@"
  fi
}

# GMT GUI open/close must not kill this side-channel. Restart live bridge on crash;
# exit 0 after clean stdin EOF (tap ended).
_gmt_live_bridge() {
  while true; do
    GMT bridge live --stdin --host "${HOST}" --port "${LIVE_PORT}"
    local ec=$?
    if [[ "${ec}" -eq 0 ]]; then
      break
    fi
    echo "${TAG} WARN: GMT live bridge exited ec=${ec}; restart in 0.3s (Foxglove kept)" >&2
    sleep 0.3
  done
}

_live_fan() {
  if [[ "${LIVE_TEE}" == "1" ]]; then
    "${TAP}" 2>"${LOG_DIR}/tap.log" \
      | tee "${LIVE_SESSION}" \
      | _tee_fan >( _gmt_live_bridge ) \
      | GMT bridge foxglove --ws --stdin "${_FOX_BEV[@]}" "${_FOX_TIP[@]}" --host "${HOST}" --port "${PORT}"
  else
    "${TAP}" 2>"${LOG_DIR}/tap.log" \
      | _tee_fan >( _gmt_live_bridge ) \
      | GMT bridge foxglove --ws --stdin "${_FOX_BEV[@]}" "${_FOX_TIP[@]}" --host "${HOST}" --port "${PORT}"
  fi
}

# Obs fan is side-channel: must NOT be the foreground waiter.
# Otherwise tap/bridge exit (or pipe break) would tear down the whole SIL via EXIT trap.
_live_fan &
LIVE_FAN_PID=$!
echo "${TAG} live fan pid=${LIVE_FAN_PID} (apps keep running if fan dies; Ctrl+C stops all)"
echo "${TAG} GMT GUI can open/close anytime; this SIL keeps running"
wait "${EM_PID}" || true
