# gf-codegen

主机侧 Python 工具（**≥3.10**）：从 `project.yaml` 合成 SOR，并做 lint / suggest / 最小 generate。

> 规格：[IMPLEMENTATION.md](IMPLEMENTATION.md) · 总计划：[P0_PLAN.md](../../docs/zh/operations/P0_PLAN.md) · 走查：[afc_with_uss](../../projects/oem_a/afc_with_uss/INTEGRATOR_WALKTHROUGH.md)
>
> **Compose 入口：** 人工用 **gf-config 保存**（自动 compose）；CI/无 GUI 用 `python -m gf_codegen.compose`。公开 CLI **没有** `gf-codegen compose`，仅保留 `lint` / `suggest` / `generate` / `emit-idl` / import。

## 推荐流程（第一版集成）

```text
① gf-config 保存  → 自动 compose → gf.sor.json + lineage + gf_build.cmake
② lint（可选）    → 校验 SOR
③ Generate        → types + Proxy/Skeleton（GUI Ctrl+G 或 gf-codegen generate）
④ 联调            → smoke_sil / 桌面脚本
```

```bash
# 务必在仓库根目录执行
cd /path/to/AI_Giraffe-Flow
python3 -m venv .venv && source .venv/bin/activate
pip install -e "tools/codegen[dev]"
bash scripts/bootstrap_deps.sh

# CI / 无 GUI：compose
python -m gf_codegen.compose --project projects/oem_a/afc_with_uss/project.yaml
gf-codegen generate projects/oem_a/afc_with_uss/gf.sor.json --out projects/oem_a/afc_with_uss/generated/
bash projects/oem_a/afc_with_uss/scripts/smoke_sil.sh
pytest tools/codegen/tests -q
```

| 产出 | 路径 | 是否提交 |
|------|------|----------|
| 工作 SOR | `projects/.../gf.sor.json` | 否（gitignore） |
| lineage | `projects/.../reports/signal_lineage_report.yaml` | 否（gitignore） |
| generate | `projects/.../generated/include/gf_gen/{types,proxy,skeleton}/` | 否（`**/generated/` ignore） |

**注意：** `pytest tools/codegen/tests` 必须在**仓库根**跑；在 `generated/...` 子目录会报 `file or directory not found`。

## 命令一览

```bash
gf-codegen --help
python -m gf_codegen.compose --project projects/oem_a/afc_with_uss/project.yaml
gf-codegen lint projects/oem_a/afc_with_uss/gf.sor.json   # gitignored 工作产出
gf-codegen suggest wiring --project projects/oem_a/afc_with_uss/project.yaml
gf-codegen generate projects/oem_a/afc_with_uss/gf.sor.json --out generated/
gf-codegen emit-idl projects/oem_a/afc_with_uss/gf.sor.json --out generated/idl/
bash scripts/run_idlc.sh generated/idl/gf_types.idl   # SKIP if no idlc
```

## 当前能力边界

| 已有 | 尚未有 |
|------|--------|
| compose（模块入口）/ lint / suggest / types+Proxy/Skeleton generate | GMT 画布 |
| `afc_with_uss` SIL + `adc_full` compose/generate | SOME/IP / DDS |
| FIDL/FDEPL/ARXML 子集 import | 真 MCU / 真 DoIP |

## 相关

- [tools/config](../config/README.md) — 作者 GUI（保存自动 compose + Generate）
- [tools/gmt](../gmt/README.md) — 只读 architect + measure
