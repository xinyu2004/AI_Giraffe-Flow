#!/usr/bin/env bash
# HIL: deploy build-hil artifacts to board (P0 stub).
#
# Env (future):
#   GF_HIL_HOST   board SSH host
#   GF_HIL_DIR    remote install dir
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=_common.sh
source "${SCRIPT_DIR}/_common.sh"

gf_project_env

echo "${TAG} deploy_hil: P0 stub — set GF_HIL_HOST / GF_HIL_DIR when board path is ready."
echo "${TAG}   local build: ${BUILD_HIL}"
exit 0
