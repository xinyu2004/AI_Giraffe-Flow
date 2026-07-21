#!/usr/bin/env bash
# Giraffe Flow — dependency check + fetch/build from source (same path for cross).
# Pins: deps/versions.lock.md  ·  Manifest: deps/DEPENDENCIES.yaml
#
# Policy (P0+):
#   runtime_board deps are always source-built with the active toolchain into
#   middleware/.deps-prefix/. Do not treat host apt packages as the board/cross path.
#
# Usage:
#   bash scripts/bootstrap_deps.sh              # check + fetch + build attr/acl
#   bash scripts/bootstrap_deps.sh --check      # check only
#   bash scripts/bootstrap_deps.sh --clean      # wipe staging; then re-run without flags
#   bash scripts/bootstrap_deps.sh --clean-all  # wipe staging + middleware/third_party/{attr,acl,iceoryx,cyclonedds}
#   GF_CROSS_PREFIX=aarch64-linux-gnu bash scripts/bootstrap_deps.sh
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
TP="${ROOT}/middleware/third_party"
PREFIX="${ROOT}/middleware/.deps-prefix"
SYSROOT_LEGACY="${ROOT}/.deps-sysroot"
LEGACY_PREFIX="${ROOT}/.deps-prefix"
LEGACY_TP="${ROOT}/third_party"

CHECK_ONLY=0
DO_CLEAN=0
CLEAN_ALL=0

usage() {
  cat <<EOF
Usage: bash scripts/bootstrap_deps.sh [options]

  (default)       Check tools, fetch sources, build attr/acl into middleware/.deps-prefix
  --check, -n     Check only (no download / build)
  --clean         Remove middleware/.deps-prefix and legacy staging, then exit
  --clean-all     --clean plus remove middleware/third_party/{attr,acl,iceoryx,cyclonedds}
  -h, --help      Show this help

Env:
  GF_CROSS_PREFIX   Cross triplet, e.g. aarch64-linux-gnu (empty = host build)
  GF_ICEORYX_TAG    Override iceoryx git tag (default v2.0.8)
  GF_CYCLONEDDS_TAG Override CycloneDDS git tag (default 0.10.5)
EOF
}

for arg in "${@:-}"; do
  case "${arg}" in
    --check|-n) CHECK_ONLY=1 ;;
    --clean) DO_CLEAN=1 ;;
    --clean-all) DO_CLEAN=1; CLEAN_ALL=1 ;;
    -h|--help) usage; exit 0 ;;
    "") ;;
    *)
      echo "Unknown option: ${arg}" >&2
      usage >&2
      exit 2
      ;;
  esac
done

do_clean() {
  echo "Cleaning staging artifacts..."
  rm -rf "${PREFIX}" "${SYSROOT_LEGACY}" "${LEGACY_PREFIX}"
  echo "  removed: middleware/.deps-prefix/ (if present)"
  echo "  removed: .deps-prefix/ (legacy root, if present)"
  echo "  removed: .deps-sysroot/ (legacy, if present)"
  if [[ "$CLEAN_ALL" -eq 1 ]]; then
    rm -rf "${TP}/attr" "${TP}/acl" "${TP}/iceoryx" "${TP}/cyclonedds"
    rm -rf "${LEGACY_TP}/attr" "${LEGACY_TP}/acl" "${LEGACY_TP}/iceoryx" "${LEGACY_TP}/cyclonedds"
    echo "  removed: middleware/third_party/{attr,acl,iceoryx,cyclonedds}"
  fi
  echo "Clean done. Re-run: bash scripts/bootstrap_deps.sh"
}

if [[ "$DO_CLEAN" -eq 1 ]]; then
  do_clean
  exit 0
fi

# Pins (keep in sync with deps/versions.lock.md)
ICEORYX_TAG="${GF_ICEORYX_TAG:-v2.0.8}"
ICEORYX_URL="${GF_ICEORYX_URL:-https://github.com/eclipse-iceoryx/iceoryx.git}"
ICEORYX_DIR="${TP}/iceoryx"

CYCLONEDDS_TAG="${GF_CYCLONEDDS_TAG:-0.10.5}"
CYCLONEDDS_URL="${GF_CYCLONEDDS_URL:-https://github.com/eclipse-cyclonedds/cyclonedds.git}"
CYCLONEDDS_DIR="${TP}/cyclonedds"

ATTR_VER="${GF_ATTR_VER:-2.5.2}"
ACL_VER="${GF_ACL_VER:-2.3.2}"
ATTR_URL="${GF_ATTR_URL:-https://download.savannah.nongnu.org/releases/attr/attr-${ATTR_VER}.tar.gz}"
ACL_URL="${GF_ACL_URL:-https://download.savannah.nongnu.org/releases/acl/acl-${ACL_VER}.tar.gz}"
ATTR_SRC="${TP}/attr"
ACL_SRC="${TP}/acl"

# Cross prefix: empty = host; e.g. aarch64-linux-gnu
CROSS_PREFIX="${GF_CROSS_PREFIX:-}"

CROSS_COMPILERS=(
  "aarch64-linux-gnu-g++|ARM64 Linux cross g++ (typical board target)"
  "arm-linux-gnueabihf-g++|ARMv7 hard-float cross g++"
)

if [[ -t 1 ]]; then
  BOLD=$'\033[1m'; DIM=$'\033[2m'; RESET=$'\033[0m'
  GREEN=$'\033[32m'; YELLOW=$'\033[33m'; RED=$'\033[31m'; CYAN=$'\033[36m'
else
  BOLD=; DIM=; RESET=; GREEN=; YELLOW=; RED=; CYAN=
fi

ok()   { printf "  ${GREEN}%-10s${RESET} %s\n" "OK" "$*"; }
warn() { printf "  ${YELLOW}%-10s${RESET} %s\n" "OPTIONAL" "$*"; }
miss() { printf "  ${RED}%-10s${RESET} %s\n" "MISSING" "$*"; }
info() { printf "  ${CYAN}%-10s${RESET} %s\n" "NOTE" "$*"; }
step() { printf "\n${BOLD}%s${RESET}\n" "$*"; }

REQUIRED_MISSING=0
OPTIONAL_MISSING=0
ACTIONS=()

have_cmd() { command -v "$1" >/dev/null 2>&1; }

cmd_version() {
  local c="$1"
  case "$c" in
    cmake) cmake --version 2>/dev/null | head -1 | sed 's/^cmake version /v/' ;;
    g++|c++|*g++*|*gcc*) "$c" --version 2>/dev/null | head -1 ;;
    git) git --version 2>/dev/null | sed 's/^git version /v/' ;;
    python3) python3 --version 2>/dev/null | sed 's/^Python /v/' ;;
    make) make --version 2>/dev/null | head -1 ;;
    *) "$c" --version 2>/dev/null | head -1 || true ;;
  esac
}

resolve_cmake() {
  if have_cmd cmake; then
    command -v cmake
    return 0
  fi
  if [[ -x "${ROOT}/.venv/bin/cmake" ]]; then
    echo "${ROOT}/.venv/bin/cmake"
    return 0
  fi
  return 1
}

download() {
  local url="$1" out="$2"
  if have_cmd curl; then
    curl -fsSL --retry 3 -o "${out}" "${url}"
  elif have_cmd wget; then
    wget -q -O "${out}" "${url}"
  else
    return 1
  fi
}

fetch_tarball() {
  local name="$1" url="$2" dest="$3" ver="$4"
  if [[ -f "${dest}/configure" || -f "${dest}/configure.ac" ]]; then
    ok "${name} source → ${dest}"
    return 0
  fi
  if [[ "$CHECK_ONLY" -eq 1 ]]; then
    miss "${name} source → not fetched (${ver})"
    REQUIRED_MISSING=$((REQUIRED_MISSING + 1))
    ACTIONS+=("Re-run without --check to download ${name}")
    return 1
  fi
  mkdir -p "${TP}"
  local tmp tarball
  tmp="$(mktemp -d)"
  tarball="${tmp}/${name}.tar.gz"
  info "${name}: downloading ${url}"
  if ! download "${url}" "${tarball}"; then
    miss "${name} source → download failed (need curl or wget)"
    REQUIRED_MISSING=$((REQUIRED_MISSING + 1))
    ACTIONS+=("Install curl and retry")
    rm -rf "${tmp}"
    return 1
  fi
  rm -rf "${dest}"
  mkdir -p "${dest}"
  tar -xzf "${tarball}" -C "${tmp}"
  local top
  top="$(find "${tmp}" -mindepth 1 -maxdepth 1 -type d | head -1)"
  shopt -s dotglob
  mv "${top}"/* "${dest}/"
  shopt -u dotglob
  rm -rf "${tmp}"
  ok "${name} source → ${dest} @ ${ver}"
}

build_autotools() {
  local name="$1" src="$2"
  local stamp="${PREFIX}/.stamp-${name}-${CROSS_PREFIX:-host}"
  local marker=""
  case "${name}" in
    acl)  marker="${PREFIX}/include/sys/acl.h" ;;
    attr) marker="${PREFIX}/include/attr/error_context.h" ;;  # 2.5.x (not attr/xattr.h)
    *)    marker="" ;;
  esac

  if [[ -n "${marker}" && -f "${stamp}" && -f "${marker}" ]]; then
    ok "${name} installed → ${PREFIX} (${CROSS_PREFIX:-host})"
    return 0
  fi
  # Drop stale stamps (e.g. previous failed acl configure)
  rm -f "${stamp}"

  if [[ "$CHECK_ONLY" -eq 1 ]]; then
    miss "${name} build → not installed under ${PREFIX}"
    REQUIRED_MISSING=$((REQUIRED_MISSING + 1))
    ACTIONS+=("Re-run without --check to build ${name} from source")
    return 1
  fi
  if [[ ! -f "${src}/configure" ]]; then
    if [[ -f "${src}/configure.ac" ]] && have_cmd autoreconf; then
      info "${name}: autoreconf ..."
      (cd "${src}" && autoreconf -fi)
    else
      miss "${name} build → ${src}/configure missing"
      REQUIRED_MISSING=$((REQUIRED_MISSING + 1))
      return 1
    fi
  fi

  local build_dir="${PREFIX}/_build/${name}"
  rm -rf "${build_dir}"
  mkdir -p "${build_dir}" "${PREFIX}"

  # Staging chain: later packages must see earlier installs in PREFIX (acl → attr)
  local conf_env=(
    "PKG_CONFIG_PATH=${PREFIX}/lib/pkgconfig${PKG_CONFIG_PATH:+:${PKG_CONFIG_PATH}}"
    "CPPFLAGS=-I${PREFIX}/include ${CPPFLAGS:-}"
    "LDFLAGS=-L${PREFIX}/lib ${LDFLAGS:-}"
  )
  local conf_args=("--prefix=${PREFIX}" "--disable-nls")
  if [[ -n "${CROSS_PREFIX}" ]]; then
    conf_env+=("CC=${CROSS_PREFIX}-gcc" "CXX=${CROSS_PREFIX}-g++" "AR=${CROSS_PREFIX}-ar" "RANLIB=${CROSS_PREFIX}-ranlib")
    conf_args+=("--host=${CROSS_PREFIX}")
    info "${name}: cross host=${CROSS_PREFIX} (PKG_CONFIG_PATH/CPPFLAGS/LDFLAGS → ${PREFIX})"
  else
    info "${name}: host build → ${PREFIX} (with staging search paths)"
  fi

  if ! (
    cd "${build_dir}"
    env "${conf_env[@]}" "${src}/configure" "${conf_args[@]}"
    make -j"$(nproc 2>/dev/null || echo 2)"
    make install
  ); then
    miss "${name} build → configure/make failed (see ${build_dir}/config.log)"
    REQUIRED_MISSING=$((REQUIRED_MISSING + 1))
    ACTIONS+=("Inspect ${build_dir}/config.log and re-run")
    return 1
  fi

  if [[ -n "${marker}" && ! -f "${marker}" ]]; then
    miss "${name} build → ${marker} still missing after make install"
    REQUIRED_MISSING=$((REQUIRED_MISSING + 1))
    return 1
  fi

  date -Iseconds >"${stamp}"
  ok "${name} installed → ${PREFIX}"
}

cat <<EOF
${BOLD}Giraffe Flow — dependency bootstrap (source-first / cross-ready)${RESET}
${DIM}repo: ${ROOT}${RESET}
mode: $([[ "$CHECK_ONLY" -eq 1 ]] && echo "check only (--check)" || echo "check + fetch + build into middleware/.deps-prefix")
toolchain: $([[ -n "$CROSS_PREFIX" ]] && echo "cross ${CROSS_PREFIX}-gcc/g++" || echo "host gcc/g++")

${BOLD}policy:${RESET} runtime deps (attr, acl, iceoryx, ...) are built from source with the
      ${BOLD}same compiler${RESET} into ${DIM}middleware/.deps-prefix/${RESET} for CMake/iceoryx.
      Host apt libacl1-dev is NOT the board path.

EOF

# ============================================================
step "[1/5] Host build tools"
# ============================================================

CMAKE_PATH=""
if CMAKE_PATH="$(resolve_cmake)"; then
  ok "cmake     → ${CMAKE_PATH}  ($(PATH="$(dirname "$CMAKE_PATH"):$PATH" cmd_version cmake))"
else
  miss "cmake     → not found"
  info "install: sudo apt-get install -y cmake"
  info "or:     python3 -m venv .venv && .venv/bin/pip install cmake"
  REQUIRED_MISSING=$((REQUIRED_MISSING + 1))
  ACTIONS+=("Install cmake")
fi

if [[ -n "${CROSS_PREFIX}" ]]; then
  if have_cmd "${CROSS_PREFIX}-g++"; then
    ok "cross g++ → $(command -v "${CROSS_PREFIX}-g++")  ($(cmd_version "${CROSS_PREFIX}-g++"))"
  else
    miss "cross g++ → ${CROSS_PREFIX}-g++ not found"
    info "example: sudo apt-get install -y g++-${CROSS_PREFIX}"
    REQUIRED_MISSING=$((REQUIRED_MISSING + 1))
    ACTIONS+=("Install ${CROSS_PREFIX}-g++")
  fi
  if have_cmd "${CROSS_PREFIX}-gcc"; then
    ok "cross gcc → $(command -v "${CROSS_PREFIX}-gcc")"
  else
    miss "cross gcc → ${CROSS_PREFIX}-gcc not found"
    REQUIRED_MISSING=$((REQUIRED_MISSING + 1))
  fi
else
  if have_cmd g++; then
    ok "g++       → $(command -v g++)  ($(cmd_version g++))"
  elif have_cmd c++; then
    ok "c++       → $(command -v c++)  ($(cmd_version c++))"
  else
    miss "g++       → not found"
    info "install: sudo apt-get install -y g++ build-essential"
    REQUIRED_MISSING=$((REQUIRED_MISSING + 1))
    ACTIONS+=("Install g++ / build-essential")
  fi
fi

if have_cmd make; then
  ok "make      → $(command -v make)"
else
  miss "make      → not found (needed to build attr/acl)"
  info "install: sudo apt-get install -y make"
  REQUIRED_MISSING=$((REQUIRED_MISSING + 1))
  ACTIONS+=("Install make")
fi

if have_cmd git; then
  ok "git       → $(command -v git)  ($(cmd_version git))"
else
  miss "git       → not found (needed to fetch iceoryx)"
  REQUIRED_MISSING=$((REQUIRED_MISSING + 1))
  ACTIONS+=("Install git")
fi

if have_cmd curl || have_cmd wget; then
  ok "downloader → $(have_cmd curl && command -v curl || command -v wget)"
else
  miss "downloader → need curl or wget (attr/acl tarballs)"
  REQUIRED_MISSING=$((REQUIRED_MISSING + 1))
  ACTIONS+=("Install curl")
fi

if have_cmd python3; then
  ok "python3   → $(command -v python3)  ($(cmd_version python3))  ${DIM}(gf-codegen; optional here)${RESET}"
else
  warn "python3   → not found (OK if you only build C++/iceoryx)"
  OPTIONAL_MISSING=$((OPTIONAL_MISSING + 1))
fi

# ============================================================
step "[2/5] Cross toolchains (optional unless GF_CROSS_PREFIX is set)"
# ============================================================
info "Not required for desktop smoke. Board: GF_CROSS_PREFIX=aarch64-linux-gnu bash scripts/bootstrap_deps.sh"
for entry in "${CROSS_COMPILERS[@]}"; do
  IFS='|' read -r xc desc <<<"${entry}"
  if have_cmd "${xc}"; then
    ok "${xc}  → $(command -v "${xc}")"
  else
    warn "${xc}  → not installed — ${desc}"
    OPTIONAL_MISSING=$((OPTIONAL_MISSING + 1))
  fi
done
info "toolchain file: cmake/toolchains/aarch64-linux-gnu.cmake"

# ============================================================
step "[3/5] Source deps attr / acl → middleware/.deps-prefix"
# ============================================================
info "middleware/.deps-prefix = repo-local staging root (headers + libs), gitignored."
info "CMake/iceoryx use ACL from here — independent of apt libacl1-dev."
info "Host and cross share this path; only GF_CROSS_PREFIX / toolchain changes."

if [[ -d "${SYSROOT_LEGACY}" && ! -f "${PREFIX}/include/sys/acl.h" ]]; then
  warn "legacy .deps-sysroot/ found (old apt-deb extract). Prefer source build into middleware/.deps-prefix; you may delete it (or --clean)."
fi

if [[ "$REQUIRED_MISSING" -eq 0 || "$CHECK_ONLY" -eq 1 ]]; then
  fetch_tarball "attr" "${ATTR_URL}" "${ATTR_SRC}" "${ATTR_VER}" || true
  fetch_tarball "acl"  "${ACL_URL}"  "${ACL_SRC}"  "${ACL_VER}" || true
fi

if [[ "$CHECK_ONLY" -eq 0 && "$REQUIRED_MISSING" -eq 0 ]]; then
  if [[ -f "${ATTR_SRC}/configure" || -f "${ATTR_SRC}/configure.ac" ]]; then
    build_autotools "attr" "${ATTR_SRC}" || true
  fi
  if [[ "$REQUIRED_MISSING" -eq 0 ]] && [[ -f "${ACL_SRC}/configure" || -f "${ACL_SRC}/configure.ac" ]]; then
    build_autotools "acl" "${ACL_SRC}" || true
  fi
fi

if [[ -f "${PREFIX}/include/sys/acl.h" ]]; then
  ok "ACL header → ${PREFIX}/include/sys/acl.h"
else
  if [[ "$CHECK_ONLY" -eq 1 ]]; then
    miss "ACL header → ${PREFIX}/include/sys/acl.h not present yet"
  else
    miss "ACL header → still missing after source build; scroll up for attr/acl errors"
  fi
  REQUIRED_MISSING=$((REQUIRED_MISSING + 1))
  ACTIONS+=("Fix attr/acl build and re-run (or --clean first)")
fi

# ============================================================
step "[4/5] Third-party iceoryx source (CMake builds it with this repo)"
# ============================================================

fetch_git() {
  local url="$1" tag="$2" dest="$3" name="$4"
  if [[ -d "${dest}/.git" ]]; then
    local cur
    cur="$(git -C "${dest}" describe --tags --always 2>/dev/null || echo unknown)"
    if [[ "$CHECK_ONLY" -eq 1 ]]; then
      ok "${name}    → present ${dest}  (${cur})"
      return 0
    fi
    info "${name}: sync to ${tag} ..."
    git -C "${dest}" fetch --tags --quiet
    git -C "${dest}" checkout --quiet "${tag}"
    ok "${name}    → ${dest} @ ${tag}"
    return 0
  fi
  if [[ -e "${dest}" ]]; then
    miss "${name}    → ${dest} exists but is not a git repo"
    REQUIRED_MISSING=$((REQUIRED_MISSING + 1))
    ACTIONS+=("Remove ${dest} and re-run")
    return 1
  fi
  if [[ "$CHECK_ONLY" -eq 1 ]]; then
    miss "${name}    → not fetched yet (${tag})"
    REQUIRED_MISSING=$((REQUIRED_MISSING + 1))
    ACTIONS+=("Re-run without --check to clone ${name}")
    return 1
  fi
  if ! have_cmd git; then
    miss "${name}    → no git; cannot clone"
    return 1
  fi
  mkdir -p "${TP}"
  info "${name}: cloning ${tag} ..."
  git clone --depth 1 --branch "${tag}" "${url}" "${dest}"
  ok "${name}    → ${dest} @ ${tag}"
}

fetch_git "${ICEORYX_URL}" "${ICEORYX_TAG}" "${ICEORYX_DIR}" "iceoryx" || true

# ============================================================
step "[4b/5] Third-party CycloneDDS source (optional DDS backend)"
# ============================================================
fetch_git "${CYCLONEDDS_URL}" "${CYCLONEDDS_TAG}" "${CYCLONEDDS_DIR}" "cyclonedds" || true

# ============================================================
step "[5/5] Summary"
# ============================================================

printf "\n"
if [[ "$REQUIRED_MISSING" -eq 0 ]]; then
  printf "${GREEN}${BOLD}Required: all ready${RESET}\n"
else
  printf "${RED}${BOLD}Required: ${REQUIRED_MISSING} item(s) still missing${RESET}\n"
fi
if [[ "$OPTIONAL_MISSING" -gt 0 ]]; then
  printf "${YELLOW}Optional: ${OPTIONAL_MISSING} item(s) not installed (OK for desktop smoke)${RESET}\n"
fi

if [[ ${#ACTIONS[@]} -gt 0 ]]; then
  printf "\n${BOLD}Suggested next steps:${RESET}\n"
  i=1
  for a in "${ACTIONS[@]}"; do
    printf "  %d. %s\n" "$i" "$a"
    i=$((i + 1))
  done
fi

if [[ "$REQUIRED_MISSING" -eq 0 && "$CHECK_ONLY" -eq 0 ]]; then
  CMAKE_HINT="${CMAKE_PATH:-cmake}"
  cat <<EOF

${BOLD}Ready to build:${RESET}
  ${CMAKE_HINT} -B build -DGF_BUILD_TESTS=ON
  ${CMAKE_HINT} --build build -j\$(nproc)
  ctest --test-dir build --output-on-failure

${BOLD}Cross example:${RESET}
  GF_CROSS_PREFIX=aarch64-linux-gnu bash scripts/bootstrap_deps.sh
  ${CMAKE_HINT} -B build-aarch64 \\
    -DCMAKE_TOOLCHAIN_FILE=cmake/toolchains/aarch64-linux-gnu.cmake
  ${CMAKE_HINT} --build build-aarch64 -j\$(nproc)

${DIM}middleware/.deps-prefix and middleware/third_party checkouts are gitignored; same source path for board and desktop.${RESET}
EOF
fi

exit "$REQUIRED_MISSING"
