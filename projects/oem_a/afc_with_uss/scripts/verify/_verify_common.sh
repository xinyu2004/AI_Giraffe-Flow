#!/usr/bin/env bash
# Shared helpers for this SKU's verify/smoke scripts (lives under the project).
# shellcheck shell=bash

VERIFY_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_SCRIPTS="$(cd "${VERIFY_DIR}/.." && pwd)"

# shellcheck source=../_common.sh
source "${PROJECT_SCRIPTS}/_common.sh"
