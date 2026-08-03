# devops/ci

编排层：本地门禁与未来云 CI 都从这里进，避免在 workflow 里散落调底层脚本。

| 层级 | 入口 | 何时跑 |
|------|------|--------|
| **PR / 日常**（快） | [scripts/smoke.sh](scripts/smoke.sh) | push / PR；bootstrap → pytest → compose → cmake/ctest → SIL demo |
| **FuSa 矩阵**（重） | [fusa/scripts/run_cases.sh](../../fusa/scripts/run_cases.sh) | nightly / 发版 / 手动；`GF_FUSA_SIL=1` 可选 |
| **SKU 产物包** | [projects/.../generate_fusa_artifacts.sh](../../projects/oem_a/afc_with_uss/scripts/generate_fusa_artifacts.sh) | nightly / 发版；**不**调用 `run_cases` |
| **发版门禁 T4** | `GF_FUSA_T4=1 bash fusa/scripts/run_cases.sh` | **发版必跑**（另编 `build-prod`） |

```bash
bash devops/ci/scripts/smoke.sh

bash fusa/scripts/run_cases.sh
GF_FUSA_SIL=1 bash fusa/scripts/run_cases.sh
GF_FUSA_T4=1 bash fusa/scripts/run_cases.sh
bash projects/oem_a/afc_with_uss/scripts/generate_fusa_artifacts.sh
```

云 CI 样例：[workflows/ci.yml.example](workflows/ci.yml.example)（落到 `.github/workflows/ci.yml` 后启用）。
