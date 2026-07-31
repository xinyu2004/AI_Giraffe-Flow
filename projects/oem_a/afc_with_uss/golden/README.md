# AFC + USS golden SOR

`golden/gf.sor.json` = compose + 审定后的 CI 对照快照（默认 **gitignored**；本地/CI 用 `generate_fusa_artifacts.sh` 刷新）。

```bash
# 刷新 golden + FuSa 产物包（不跑 SIL）
GF_FUSA_PACK_UPDATE_GOLDEN=1 bash projects/oem_a/afc_with_uss/scripts/generate_fusa_artifacts.sh

# CI 不依赖提交 SOR：稳定不变量
pytest tools/gf-codegen/tests/test_afc_bench_golden.py -q
```

若本地已有 `golden/gf.sor.json`，同文件测试会做深比对。`req.yaml` → `acceptance.sor_golden` 指向本路径。
