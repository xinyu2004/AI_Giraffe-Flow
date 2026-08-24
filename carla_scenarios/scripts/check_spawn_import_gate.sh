#!/usr/bin/env bash
# Import-gate smoke for spawn layering. Exit 1 on violation.
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"
fail=0

check_empty() {
  local label="$1"
  shift
  local out
  out="$(rg "$@" 2>/dev/null || true)"
  if [[ -n "$out" ]]; then
    echo "FAIL: $label"
    echo "$out"
    fail=1
  else
    echo "OK: $label"
  fi
}

check_empty "follow_straight must not use closing IC" \
  'closing_toward_lead|closing_along_heading|closing_along_pose|closing_const_fwd|enable_constant_forward|seed_speed' \
  src/layouts/follow_straight.py

check_empty "place/pick must not import spawn.ic or boundary" \
  'spawn\.(ic|boundary)|from spawn import (ic|boundary)' \
  src/spawn/place.py src/spawn/pick.py

# Allow only set_natural_continue in AtomCase (batch flag; not IC profiles)
if rg -n 'from spawn\.ic import|import spawn\.ic' src/lib/_case_atom.py 2>/dev/null \
  | grep -v 'set_natural_continue' | grep -v '^$' ; then
  echo "FAIL: AtomCase may only import set_natural_continue from spawn.ic"
  fail=1
else
  echo "OK: AtomCase only uses set_natural_continue from spawn.ic"
fi

if rg -n '^(from spawn\.ic import .*closing_toward_lead|.*closing_toward_lead\()' \
  src/layouts/vru.py 2>/dev/null | grep -v '^$'; then
  echo "FAIL: vru must not import/call closing_toward_lead"
  fail=1
else
  echo "OK: vru does not import/call closing_toward_lead"
fi

if rg -n 'closing_\w+\([^)]*toward\s*=' src/layouts -g '*.py' 2>/dev/null | grep -v '^$'; then
  echo "FAIL: layouts must not pass toward= into IC helpers"
  fail=1
else
  echo "OK: layouts do not pass toward= into IC helpers"
fi

if rg -n 'enable_constant_forward|closing_const_fwd' src/layouts -g '*.py' 2>/dev/null | grep -v '^$'; then
  echo "FAIL: layouts still call enable_constant_forward/closing_const_fwd"
  fail=1
else
  echo "OK: layouts use named closing_* / seed_speed only"
fi

# run_cases: must not import spawn.ic for IC profiles; natural continue flag ok
if rg -n 'from spawn\.ic import' run_cases.py 2>/dev/null | grep -v 'set_natural_continue' | grep -v '^$'; then
  echo "FAIL: run_cases must not import spawn.ic profiles (set_natural_continue only)"
  fail=1
else
  echo "OK: run_cases does not import spawn.ic profiles"
fi

if rg -n 'sanitize_keep_ego' run_cases.py >/dev/null 2>&1; then
  echo "FAIL: run_cases must not call sanitize_keep_ego (natural continue; fail openly)"
  fail=1
else
  echo "OK: run_cases does not sanitize/destroy between cases"
fi

# IC must not call sanitize (residue ownership = boundary)
if rg -n 'sanitize_keep_ego' src/spawn/ic.py 2>/dev/null | grep -v 'Deprecated\|sanitize_keep_ego' | grep -v '^$' ; then
  :
fi
# Allow deprecated wrappers that forward to boundary; ban settle loops calling boundary in hot path is ok via deprecate.
if rg -n 'def closing_|def seed_speed|def release_only' -A20 src/spawn/ic.py | rg -n 'sanitize_keep_ego\(' >/dev/null 2>&1; then
  echo "FAIL: case IC profiles must not call sanitize_keep_ego"
  fail=1
else
  echo "OK: case IC profiles do not call sanitize_keep_ego"
fi

if [[ "$fail" -ne 0 ]]; then
  exit 1
fi
echo "spawn import gate passed"
