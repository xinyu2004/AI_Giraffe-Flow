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

echo "[smoke_ta] GMT measure tag + multitopic export ..."
TAGGED="${ROOT}/build-ta/session_tagged.jsonl"
MCAP2="${ROOT}/build-ta/session_tagged.mcap"
# enrich stub with topics for multi-topic path
python - <<'PY'
import json
from pathlib import Path
src = Path("tools/gmt/fixtures/session_stub.jsonl")
dst = Path("build-ta/session_topics.jsonl")
dst.parent.mkdir(parents=True, exist_ok=True)
topics = ["/gf/stub", "/gf/Trajectory", "/gf/UssZones"]
with src.open() as f, dst.open("w") as out:
    for i, line in enumerate(f):
        row = json.loads(line)
        row["topic"] = topics[i % len(topics)]
        out.write(json.dumps(row) + "\n")
PY
GMT measure tag --in build-ta/session_topics.jsonl --out "${TAGGED}" --label ci_stub
GMT measure export --in "${TAGGED}" --out "${MCAP2}"
python - <<'PY'
from pathlib import Path
from gf_gmt.measure_export import MAGIC, list_mcap_topics
p = Path("build-ta/session_tagged.mcap")
b = p.read_bytes()
assert b.startswith(MAGIC)
topics = list_mcap_topics(p)
assert topics, topics
print("ci topics:", topics)
PY
GMT bridge foxglove --mcap "${MCAP2}" >/tmp/gf_foxglove_describe.txt
grep -q "Foxglove Studio" /tmp/gf_foxglove_describe.txt

echo "[smoke_ta] gf-codegen import arxml ..."
gf-codegen import arxml schemas/examples/oem/demo_faracon_subset.arxml \
  --out build-ta/arxml_fragment.json
python -c "import json; d=json.load(open('build-ta/arxml_fragment.json')); assert 'EgoMotion' in d['candidates']"

echo "[smoke_ta] OK"
