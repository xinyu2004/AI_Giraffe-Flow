# gf-codegen

主机侧 Python 工具（**≥3.10**）：从 `project.yaml` 合成 SOR，并做 lint / suggest / 最小 generate。

> 规格：[IMPLEMENTATION.md](IMPLEMENTATION.md) · 总计划：[P0_PLAN.md](../../docs/zh/operations/P0_PLAN.md) · 走查：[afc_with_uss](../../projects/oem_a/afc_with_uss/INTEGRATOR_WALKTHROUGH.md)

## 推荐流程（第一版集成）

```text
① compose   → gf.sor.json + lineage 报告     ← 主路径（DBC+hpp+wiring+req）
② lint      → 校验 compose 产出的 SOR（工作区路径）
③ suggest   → 可选：打印 wiring 建议片段
④ generate  → types + **Proxy/Skeleton**（`--out generated/`）
⑤ 联调      → `bash projects/oem_a/afc_with_uss/scripts/smoke_sil.sh`
```

```bash
# 务必在仓库根目录执行
cd /path/to/AI_Giraffe-Flow
python3 -m venv .venv && source .venv/bin/activate
pip install -e "tools/codegen[dev]"
bash scripts/bootstrap_deps.sh

gf-codegen compose --project projects/oem_a/afc_with_uss/project.yaml
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
gf-codegen compose --project projects/oem_a/afc_with_uss/project.yaml
gf-codegen lint projects/oem_a/afc_with_uss/gf.sor.json   # gitignored 工作产出
gf-codegen suggest wiring --project projects/oem_a/afc_with_uss/project.yaml
gf-codegen generate projects/oem_a/afc_with_uss/gf.sor.json --out generated/
```

## 当前能力边界

| 已有 | 尚未有 |
|------|--------|
| compose / lint / suggest / types+Proxy/Skeleton generate | GMT 画布 |
| `afc_with_uss` SIL + `adc_full` compose/generate | SOME/IP / DDS |

## 源码布局

```text
tools/codegen/
  pyproject.toml
  src/gf_codegen/          # cli, lint, suggest, generate, compose/*
  tests/                   # 在仓库根执行 pytest
  IMPLEMENTATION.md
```

## 相关文档

| 文档 | 用途 |
|------|------|
| [IMPLEMENTATION.md](IMPLEMENTATION.md) | 实现规格与管道细节 |
| [P0_PLAN.md](../../docs/zh/operations/P0_PLAN.md) | P0 已收口；下一步见 ROADMAP P1 |
| [INTEGRATOR_WALKTHROUGH.md](../../projects/oem_a/afc_with_uss/INTEGRATOR_WALKTHROUGH.md) | 如何审 afc_with_uss |
| [MODULE_INTERFACE_LAYOUT.md](../../projects/MODULE_INTERFACE_LAYOUT.md) | DBC/hpp 跟项目走 |
