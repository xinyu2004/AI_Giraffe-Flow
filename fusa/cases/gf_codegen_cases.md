# gf-codegen — 生成物保证（L2，非板级模块）

证明对象：生成**规则与产物**正确，不是板端常驻进程。GMT **不在**本表。

| Case ID | 意图 | 复现 | 状态 |
|---------|------|------|------|
| CG-01 | compose afc → sku cmake / observability | `pytest tools/gf-codegen/tests/test_compose_afc_with_uss.py tools/gf-codegen/tests/test_observability.py -q` | active |
| CG-02 | generate 写出 obs_tap + 关键 Proxy | `test_generate_writes_obs_tap_main`（同 observability 文件） | active |
| CG-03 | golden / lint 契约 | `pytest tools/gf-codegen/tests/test_afc_bench_golden.py tools/gf-codegen/tests/test_lint_golden.py -q` | active |
| CG-04 | 生成代码进 SIL 可链接 | `bash projects/oem_a/afc_with_uss/scripts/compile_sil.sh`（与 L3 交叉） | active |

可选：`GF_FUSA_CODEGEN=1 bash fusa/scripts/run_cases.sh`
