# P2 AFC+USS Evidence Pack Manifest

Generated: 2026-07-20T10:49:26Z  ·  git: cada461

## Layout

| Path | Status |
|------|--------|
| `compose/gf.sor.json` | present |
| `lineage/signal_lineage_report.yaml` | present |
| `mcap/session.mcap` | present |
| `logs/gateway.log` | present |
| `logs/fcm.log` | present |
| `logs/uss.log` | present |
| `logs/planning.log` | present |
| `smoke/multiproc.txt` | missing (re-run with GF_EVIDENCE_RUN_SMOKE=1 if needed) |
| `smoke/observability.txt` | missing (re-run with GF_EVIDENCE_RUN_SMOKE=1 if needed) |

## How to refresh

```bash
GF_EVIDENCE_UPDATE_GOLDEN=1 GF_EVIDENCE_RUN_SMOKE=1 bash scripts/collect_p2_evidence.sh
```

## Related

- Golden: `projects/oem_a/afc_with_uss/golden/gf.sor.json` (gitignored by default)
- Review: [docs/zh/operations/P2_REVIEW_CHECKLIST.md](../../docs/zh/operations/P2_REVIEW_CHECKLIST.md)
- Observability demo: [docs/zh/operations/OBSERVABILITY_DEMO.md](../../docs/zh/operations/OBSERVABILITY_DEMO.md)
