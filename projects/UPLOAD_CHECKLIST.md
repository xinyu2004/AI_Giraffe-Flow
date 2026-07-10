# 上传前清单与当前流程（gf-codegen MVP）

> 日期：2026-07-10 · 状态：轨 A（codegen）MVP 已完成，可上传后进入轨 B（runtime / iceoryx）

## 应提交（建议）

| 路径 | 说明 |
|------|------|
| `tools/codegen/` | `pyproject.toml`、`src/`、`tests/`、README、IMPLEMENTATION |
| `projects/oem_a/afc_*`、`projects/oem_b/adc_full` | 集成输入 + **golden/** |
| `projects/*.md` | PROCESS_ROLES、MODULE_INTERFACE_LAYOUT、走查 |
| `docs/zh/operations/P0_PLAN.md` 等 | 已更新状态的文档 |
| `.gitignore` | 已忽略 `.venv`、compose 工作产物、`generated/` |

## 不要提交

| 路径 | 原因 |
|------|------|
| `.venv/` | 本地虚拟环境 |
| `**/__pycache__/`、`*.egg-info/` | 构建垃圾 |
| `projects/**/gf.sor.json` | compose 工作副本（以 golden 为准） |
| `projects/**/reports/signal_lineage_report.yaml` | 本地报告 |
| `generated/` | generate 输出 |

## 他人克隆后怎么跑

```bash
git clone <repo> && cd AI_Giraffe-Flow
python3 -m venv .venv && source .venv/bin/activate
pip install -e "tools/codegen[dev]"
gf-codegen compose --project projects/oem_a/afc_with_uss/project.yaml
pytest tools/codegen/tests -q
```

要求：**Python ≥ 3.10**。

## 流程（现在 → 下一步）

```text
【已完成】
  项目输入（DBC/hpp/wiring/req）
  → gf-codegen compose / lint / suggest / generate(types)
  → afc_with_uss golden 落盘

【下一步 · P0 轨 B】
  generate 增强（Proxy/Skeleton）或手写最小 com API
  → iceoryx binding + RouDi
  → 双进程 demo（publish / subscribe）
  → CMake / OSAL / CI
```

入口文档：

1. [tools/codegen/README.md](../tools/codegen/README.md) — 工具用法  
2. [projects/oem_a/afc_with_uss/INTEGRATOR_WALKTHROUGH.md](oem_a/afc_with_uss/INTEGRATOR_WALKTHROUGH.md) — 集成审阅  
3. [docs/zh/operations/P0_PLAN.md](../docs/zh/operations/P0_PLAN.md) — 下一步 runtime  
