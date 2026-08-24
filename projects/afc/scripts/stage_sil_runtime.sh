#!/usr/bin/env bash
# Stage complete SIL/HIL runtime: copy to board and run under GF_BUILD_DIR=runtime.
# Layout: runtime/{bin,lib,etc,platform,share}
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=_common.sh
source "${SCRIPT_DIR}/_common.sh"

gf_project_env

BUILD="${GF_BUILD_DIR:-${BUILD_SIL}}"
RUNTIME="${BUILD}/runtime"
BIN="${RUNTIME}/bin"
LIB="${RUNTIME}/lib"
ETC="${RUNTIME}/etc"
PLAT="${RUNTIME}/platform"
SHARE="${RUNTIME}/share/frame_ingest"
STRIP_ON=1
[[ "${GF_STAGE_NO_STRIP:-0}" == "1" ]] && STRIP_ON=0

rm -rf "${RUNTIME}"
mkdir -p "${BIN}" "${LIB}" "${ETC}" "${PLAT}" "${SHARE}/modules"

stage_file() {
  local src="$1" dest="$2"
  if [[ ! -e "${src}" ]]; then
    return 1
  fi
  mkdir -p "$(dirname "${dest}")"
  cp -a "${src}" "${dest}"
  if [[ -f "${dest}" && -x "${dest}" ]] || [[ -f "${dest}" && "${dest}" == *.so* ]]; then
    if [[ "${STRIP_ON}" == "1" ]] && command -v strip >/dev/null 2>&1; then
      strip --strip-unneeded "${dest}" 2>/dev/null || true
    fi
  fi
  echo "${TAG} stage ← ${src}"
  return 0
}

require_file() {
  local src="$1" dest="$2" label="$3"
  if ! stage_file "${src}" "${dest}"; then
    echo "${TAG} ERROR: missing required ${label}: ${src}" >&2
    exit 1
  fi
}

# --- required platform binaries ---
require_file "${BUILD}/middleware/exec/gf_em_daemon" "${BIN}/gf_em_daemon" "gf_em_daemon"
require_file "${BUILD}/iox-roudi" "${BIN}/iox-roudi" "iox-roudi"

DLT_SRC="${BUILD}/_dep-manifest/dlt-daemon/src/daemon/dlt-daemon"
if [[ -f "${DLT_SRC}" ]]; then
  stage_file "${DLT_SRC}" "${BIN}/dlt-daemon" || true
else
  echo "${TAG} WARN: dlt-daemon not built (ok if kDlt=false)"
fi

# SKU apps (AFC: no USS). Debug bridges optional via GF_STAGE_DEBUG_BRIDGE=1 (default on for SIL).
declare -a APP_BINS=(
  "apps/frame_ingest/gf_frame_ingest"
  "apps/perception/fcm/gf_perception_fcm"
  "apps/adapters/vehicle_can_gateway/gf_vehicle_can_gateway"
  "apps/planning/driving/gf_planning_driving"
)
if [[ "${GF_STAGE_DEBUG_BRIDGE:-1}" == "1" ]]; then
  APP_BINS+=(
    "apps/debug_bridge/iox_obs_tap/gf_iox_obs_tap"
    "apps/debug_bridge/iox_obs_inject/gf_iox_obs_inject"
  )
fi
for rel in "${APP_BINS[@]}"; do
  src="${BUILD}/${rel}"
  [[ -f "${src}" ]] || continue
  stage_file "${src}" "${BIN}/$(basename "${src}")" || true
done

# Catch other gf_* under apps/
if [[ -d "${BUILD}/apps" ]]; then
  while IFS= read -r -d '' exe; do
    base="$(basename "${exe}")"
    [[ "${base}" == gf_* ]] || continue
    [[ -f "${BIN}/${base}" ]] && continue
    stage_file "${exe}" "${BIN}/${base}" || true
  done < <(find "${BUILD}/apps" -type f -name 'gf_*' -executable -print0 2>/dev/null)
fi

# --- shared libraries: Giraffe + gf_channel + ldd deps of staged bins ---
stage_lib_file() {
  local src="$1"
  [[ -f "${src}" ]] || return 0
  local base dest
  base="$(basename "${src}")"
  dest="${LIB}/${base}"
  [[ -e "${dest}" ]] && return 0
  cp -a "${src}" "${dest}"
  if [[ "${STRIP_ON}" == "1" ]] && command -v strip >/dev/null 2>&1; then
    strip --strip-unneeded "${dest}" 2>/dev/null || true
  fi
  # companion soname links in same dir
  local dir
  dir="$(dirname "${src}")"
  shopt -s nullglob
  for link in "${dir}/${base}"* "${dir}/$(echo "${base}" | sed 's/\.so.*/.so/')"* ; do
    [[ -e "${link}" ]] || continue
    local lb
    lb="$(basename "${link}")"
    [[ -e "${LIB}/${lb}" ]] && continue
    cp -a "${link}" "${LIB}/${lb}" 2>/dev/null || true
  done
  shopt -u nullglob
  echo "${TAG} stage lib ← ${src}"
}

# Prefer known Giraffe shared libs from build tree (exclude staged runtime/ only).
# After SHARED conversion, libs also collect under ${BUILD}/lib.
while IFS= read -r -d '' so; do
  stage_lib_file "${so}"
done < <(find "${BUILD}/lib" "${BUILD}/middleware" -type f \( -name 'libgf_ara_*.so*' -o -name 'libgf_osal.so*' -o -name 'libgf_channel.so*' -o -name 'libgf_*.so' -o -name 'libgf_*.so.*' \) \
  ! -path '*/runtime/*' -print0 2>/dev/null || true)

# Explicit fallbacks (older layout / name)
for so in \
  "${BUILD}/lib/libgf_ara_runtime.so" \
  "${BUILD}/lib/libgf_osal.so" \
  "${BUILD}/lib/libgf_channel.so" \
  "${BUILD}/middleware/runtime/libgf_ara_runtime.so" \
  "${BUILD}/middleware/osal/libgf_osal.so" \
  "${BUILD}/middleware/bindings/gf_channel/libgf_channel.so"
do
  [[ -f "${so}" ]] && stage_lib_file "${so}"
done

# Optional DoIP server
if [[ -f "${BUILD}/gf_doip_ota_server" ]]; then
  stage_file "${BUILD}/gf_doip_ota_server" "${BIN}/gf_doip_ota_server" || true
elif [[ -f "${BUILD}/middleware/diag/gf_doip_ota_server" ]]; then
  stage_file "${BUILD}/middleware/diag/gf_doip_ota_server" "${BIN}/gf_doip_ota_server" || true
fi

# ldd closure for every staged executable (resolve via build lib paths too)
if command -v ldd >/dev/null 2>&1; then
  _LD_EXTRA=""
  while IFS= read -r -d '' d; do
    _LD_EXTRA="${d}${_LD_EXTRA:+:}${_LD_EXTRA}"
  done < <(find "${BUILD}/middleware" -type d -name gf_channel -print0 2>/dev/null)
  # Collect all dirs that contain libgf_*.so
  while IFS= read -r -d '' so; do
    _LD_EXTRA="$(dirname "${so}"):${_LD_EXTRA}"
  done < <(find "${BUILD}/middleware" -name 'libgf_*.so' -print0 2>/dev/null)
  # dlt lib
  if [[ -d "${BUILD}/_dep-manifest/dlt-daemon/src/lib" ]]; then
    _LD_EXTRA="${BUILD}/_dep-manifest/dlt-daemon/src/lib:${_LD_EXTRA}"
  fi
  export LD_LIBRARY_PATH="${LIB}:${_LD_EXTRA}${LD_LIBRARY_PATH:+:${LD_LIBRARY_PATH}}"
  for exe in "${BIN}"/*; do
    [[ -f "${exe}" && -x "${exe}" ]] || continue
    [[ "$(basename "${exe}")" == *.sh ]] && continue
    while IFS= read -r line; do
      path="$(echo "${line}" | awk '/=>/ {print $3}')"
      [[ -n "${path}" && "${path}" != "not" && -f "${path}" ]] || continue
      case "${path}" in
        /lib/*|/lib64/*|/usr/lib/*|/usr/lib64/*) continue ;;
      esac
      stage_lib_file "${path}"
    done < <(ldd "${exe}" 2>/dev/null || true)
  done
fi

# Do NOT stage libgf_diag_sec*.so unless explicitly requested
if [[ "${GF_STAGE_DIAG_SEC:-0}" == "1" ]]; then
  for cand in "${BUILD}/libgf_diag_sec.so" "${BUILD}/libgf_diag_sec.so"*; do
    [[ -f "${cand}" ]] && stage_lib_file "${cand}"
  done
fi

# --- config ---
IOX_SRC="${PROJECT_DIR}/generated/iox_roudi.toml"
if [[ -f "${IOX_SRC}" ]]; then
  cp -f "${IOX_SRC}" "${ETC}/iox_roudi.toml"
  echo "${TAG} stage etc ← iox_roudi.toml"
else
  echo "${TAG} ERROR: missing ${IOX_SRC}" >&2
  exit 1
fi

# Authoring YAML is NOT board behavior truth (EM reads deploy_config.hpp).
# Opt-in copy for smoke/debug: GF_STAGE_PLATFORM=1
if [[ "${GF_STAGE_PLATFORM:-0}" == "1" && -d "${PROJECT_DIR}/platform" ]]; then
  mkdir -p "${PLAT}"
  cp -a "${PROJECT_DIR}/platform/." "${PLAT}/"
  echo "${TAG} stage platform ← ${PROJECT_DIR}/platform (GF_STAGE_PLATFORM=1)"
else
  rm -rf "${PLAT}"
  echo "${TAG} stage: skip platform/ (product path = hpp; set GF_STAGE_PLATFORM=1 to include)"
fi

# Python ingest helpers + carla module (SIL host only; HIL/board: GF_STAGE_PY=0).
INGEST_APP="${PROJECT_DIR}/apps/frame_ingest"
BRIDGE_SRC="${PROJECT_DIR}/tools/carla_bridge"
if [[ "${GF_STAGE_PY:-1}" == "1" ]]; then
  if [[ -d "${INGEST_APP}" ]]; then
    for f in gf_frame_ingest.py gf_channel_py.py; do
      [[ -f "${INGEST_APP}/${f}" ]] && cp -f "${INGEST_APP}/${f}" "${SHARE}/${f}"
    done
  fi
  if [[ -d "${BRIDGE_SRC}" ]]; then
    rm -rf "${SHARE}/modules/carla_bridge"
    mkdir -p "${SHARE}/modules"
    cp -a "${BRIDGE_SRC}" "${SHARE}/modules/carla_bridge"
    # drop bytecode if any
    find "${SHARE}/modules/carla_bridge" -type d -name '__pycache__' -exec rm -rf {} + 2>/dev/null || true
    echo "${TAG} stage share ← carla_bridge (copied; GF_STAGE_PY=1)"
  fi
else
  rm -rf "${SHARE}"
  echo "${TAG} stage: skip Python share/ (GF_STAGE_PY=0; board/HIL path)"
fi

# Debug-only host helper (product entry = systemd/init → gf_em_daemon).
# Runtime is self-contained: only paths under ROOT (this staged tree).
if [[ "${GF_STAGE_GIRAFFE_LAUNCH:-1}" == "1" ]]; then
  cat >"${BIN}/giraffe_launch" <<'EOS'
#!/usr/bin/env bash
# DEBUG ONLY — board uses systemd/init (common/deploy/). Self-contained runtime.
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
export GF_BUILD_DIR="${ROOT}"
export GF_RUNTIME_DIR="${ROOT}"
export GF_IOX_TOML="${ROOT}/etc/iox_roudi.toml"
export LD_LIBRARY_PATH="${ROOT}/lib${LD_LIBRARY_PATH:+:${LD_LIBRARY_PATH}}"
if [[ -d "${ROOT}/platform" ]]; then
  export GF_PLATFORM_DIR="${ROOT}/platform"
fi
exec "${ROOT}/bin/gf_em_daemon" --build-dir "${ROOT}" "$@"
EOS
  chmod +x "${BIN}/giraffe_launch"
  ln -sfn giraffe_launch "${BIN}/run_on_target.sh"
fi
# Install unit example next to runtime for deploy copy
mkdir -p "${RUNTIME}/deploy"
if [[ -f "${ROOT}/common/deploy/systemd/giraffe-em.service.example" ]]; then
  cp -f "${ROOT}/common/deploy/systemd/giraffe-em.service.example" \
    "${RUNTIME}/deploy/giraffe-em.service.example"
fi

echo "${RUNTIME}" >"${RUNTIME}/.root"

echo "${TAG} ========== runtime footprint (product tree; excl. run scratch) =========="
du -sh "${RUNTIME}" | awk -v t="${TAG}" '{print t" total: "$0}'
_fp_dirs=()
for _d in "${BIN}" "${LIB}" "${ETC}" "${PLAT}" "${SHARE}"; do
  [[ -d "${_d}" ]] && _fp_dirs+=("${_d}")
done
if ((${#_fp_dirs[@]})); then
  du -sh "${_fp_dirs[@]}" | awk -v t="${TAG}" '{print t"  "$0}'
fi
if compgen -G "${BIN}/*" >/dev/null 2>&1; then
  du -sh "${BIN}"/* 2>/dev/null | sort -h | awk -v t="${TAG}" '{print t"  bin: "$0}' || true
fi
if compgen -G "${LIB}/*" >/dev/null 2>&1; then
  du -sh "${LIB}"/* 2>/dev/null | sort -h | awk -v t="${TAG}" '{print t"  lib: "$0}' | tail -40 || true
fi
# Reminder: never write observability artifacts or file logs into runtime/ (GMT Record → gf_obs_dir; logs → DLT).
echo "${TAG} tip: GMT Record → \$(gf_obs_dir); module logs via DLT — not under runtime/"
echo "${TAG} ======================================="
echo "${TAG} stage_sil_runtime OK → ${RUNTIME}"
