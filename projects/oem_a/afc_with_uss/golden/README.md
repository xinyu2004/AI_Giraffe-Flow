# AFC + USS golden SOR

`golden/gf.sor.json` = compose + 审定后的 CI 对照快照（默认 **gitignored**；本地/CI 用 `collect_p2_evidence` 刷新）。

```bash
# 刷新 golden + 证据包（不跑 SIL）
GF_EVIDENCE_UPDATE_GOLDEN=1 bash scripts/collect_p2_evidence.sh

# CI 不依赖提交 SOR：稳定不变量
pytest tools/codegen/tests/test_afc_bench_golden.py -q
```

若本地已有 `golden/gf.sor.json`，同文件测试会做深比对。`req.yaml` → `acceptance.sor_golden` 指向本路径。
