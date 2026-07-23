#!/usr/bin/env bash
# Shared helpers for scripts/verify/oem_a_afc_with_uss (not the product path).
# shellcheck shell=bash

VERIFY_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT="$(cd "${VERIFY_DIR}/../../.." && pwd)"
PROJECT_SCRIPTS="${ROOT}/projects/oem_a/afc_with_uss/scripts"

# shellcheck source=../../../projects/oem_a/afc_with_uss/scripts/_common.sh
source "${PROJECT_SCRIPTS}/_common.sh"
