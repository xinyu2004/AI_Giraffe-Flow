#!/usr/bin/env bash
# P1 Track T/A: GMT architect + measure MCAP + ARXML import
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "${ROOT}"
export PATH="${ROOT}/.venv/bin:${PATH}"
export PYTHONPATH="${ROOT}/tools/gmt/src:${ROOT}/tools/codegen/src${PYTHONPATH:+:${PYTHONPATH}}"

if [[ ! -x .venv/bin/python ]]; then
  python3 -m venv .venv
fi
.venv/bin/pip install -q -e "tools/codegen[dev]" -e "tools/gmt[dev]"

echo "[smoke_ta] pytest gmt + parse_arxml ..."
.venv/bin/pytest tools/gmt/tests tools/codegen/tests/test_parse_arxml.py -q --tb=short

echo "[smoke_ta] compose afc_with_uss (for architect) ..."
python -m gf_codegen.compose --project projects/oem_a/afc_with_uss/project.yaml

echo "[smoke_ta] GMT architect lineage ..."
GMT architect lineage --project projects/oem_a/afc_with_uss/project.yaml

echo "[smoke_ta] GMT architect dag ..."
GMT architect dag --project projects/oem_a/afc_with_uss/project.yaml >/tmp/gf_dag.json

echo "[smoke_ta] GMT measure export ..."
OUT="${ROOT}/build-ta/session_stub.mcap"
mkdir -p "$(dirname "${OUT}")"
GMT measure export --in tools/gmt/fixtures/session_stub.jsonl --out "${OUT}"
python -c "from pathlib import Path; b=Path('${OUT}').read_bytes(); assert b.startswith(b'\\x89MCAP0\\r\\n'), b[:16]"

echo "[smoke_ta] gf-codegen import arxml ..."
gf-codegen import arxml schemas/examples/oem/demo_faracon_subset.arxml \
  --out build-ta/arxml_fragment.json
python -c "import json; d=json.load(open('build-ta/arxml_fragment.json')); assert 'EgoMotion' in d['candidates']"

echo "[smoke_ta] OK"
