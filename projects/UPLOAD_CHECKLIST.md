# 上传前清单

> 日期：2026-07-10 · 分层说明：[docs/zh/architecture/code-layers.md](../docs/zh/architecture/code-layers.md)

## 上传前请删掉 / 勿打包（本地已可清）

| 路径 | 原因 |
|------|------|
| `build/`、`build-hil/`、`cmake-build-*/` | CMake 构建树 |
| `middleware/.deps-prefix/`、`.deps-sysroot/` | 源码编出的 attr/acl staging |
| `middleware/third_party/iceoryx/`、`attr/`、`acl/` | bootstrap 检出（保留 `middleware/third_party/README.md`） |
| `.venv/`、`venv/` | 本地 Python 环境（可再 `python3 -m venv .venv`） |
| `**/generated/` | `gf-codegen generate` 输出 |
| `projects/**/gf.sor.json` | compose 工作副本 |
| `projects/**/reports/` | lineage 等本地报告 |
| `**/__pycache__/`、`*.egg-info/`、`.pytest_cache/` | Python 垃圾 |

`.gitignore` 已覆盖上表；若用压缩包上传，请确认未手动打进上述目录。

## 应上传（源码与文档）

| 路径 | 说明 |
|------|------|
| `middleware/` | 静态：core / com / bindings / osal / hal …（不含 third_party 检出与 `.deps-prefix`） |
| `tools/codegen/`、`tools/bridge/` | gf-codegen；可选 ROS2 桥（主机侧） |
| `projects/` | 集成输入 + 项目脚本；契约在 `req.yaml`；`adc_full` / `afc_with_uss` 均可 compose |
| `apps/` | 参考 App 源码 |
| `schemas/`、`cmake/`、`scripts/`、`deps/`、`docs/`、`ci/` | 契约、构建、文档 |
| 根 `README*`、`STRUCTURE.md`、`.gitignore` | |

## 他人拿到后怎么跑

```bash
cd AI_Giraffe-Flow
python3 -m venv .venv && source .venv/bin/activate   # 需要 Python ≥ 3.10
pip install -e "tools/codegen[dev]"
bash scripts/bootstrap_deps.sh                       # 拉 iceoryx + 源码编 attr/acl
bash scripts/verify/oem_a_afc_with_uss/smoke_sil.sh
```

只要工具链：`cmake`、`g++`、`git`、`make`、`curl`（见 `scripts/bootstrap_deps.sh --check`）。

## 入口文档

1. [code-layers.md](../docs/zh/architecture/code-layers.md) — **静态 / 生成 / 手写**  
2. [tools/codegen/README.md](../tools/codegen/README.md) — 工具用法  
3. [afc_with_uss/INTEGRATOR_WALKTHROUGH.md](oem_a/afc_with_uss/INTEGRATOR_WALKTHROUGH.md) — 集成审阅  
4. [P0_PLAN.md](../docs/zh/operations/P0_PLAN.md) — 计划与状态  
