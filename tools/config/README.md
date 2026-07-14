# gf-config（主机配置 GUI）

PySide6 工具：按 **SKU** 编辑 `req.yaml`，用 **类 Simulink 信号图** 编辑 `wiring.yaml`，一键 `compose` + lineage。

> 计划：[P1_PLAN.md](../../docs/zh/operations/P1_PLAN.md) · 不上板、不进 production 镜像  
> 工具边界：`gf-config` = 唯一作者 GUI · `gf-codegen` = CLI · GMT = 只读 CI + 后期 measure（见 [tools/README.md](../README.md)）

## `req.yaml` vs `wiring.yaml`（怎么分工）

| | **req.yaml** | **wiring.yaml** |
|--|--------------|-----------------|
| **一句话** | 这辆车 / 这个 SKU **要什么、裁什么、验什么** | 这个项目里进程 **怎么连、谁提供谁订阅** |
| **谁改** | A 页（产品 / 集成负责人勾选 SKU） | B 页（集成工程师画信号图） |
| **典型内容** | `variant` / `topology` / `product` · `capabilities` · `runtime_modules` · `bindings` · `observability` · `apps` · `acceptance` | `modules`（hpp）· `deployments`（provides/requires）· `dataflows` · `bindings`（模块 IO） |
| **进流水线** | `merge_req` → SOR 产品变体 + lineage 门禁 | `apply_wiring` → SOR deployments/dataflows/types |
| **不写什么** | 不写具体 from→to 边 | 不写「要不要编进 com/phm」这类 SKU 裁剪 |

```text
req.yaml（SKU 契约） ──┐
                       ├── gf-codegen compose → gf.sor.json → generate / lineage
wiring.yaml（集成连线）─┘
```

**记忆口诀：** req = *what / how much*（要什么能力、中间件裁多深、验收列哪些服务）；wiring = *who talks to whom*（进程端口与信号边）。

## 安装

```bash
cd /path/to/AI_Giraffe-Flow
source .venv/bin/activate
pip install -e "tools/codegen[dev]"
pip install -e tools/config
```

## 启动

```bash
gf-config projects/oem_a/afc_with_uss/project.yaml
```

## 页签

| 页签 | 作用 |
|------|------|
| A · SKU / 中间件 | 完整编辑 `req.yaml`（含 capabilities / observability / apps / acceptance） |
| B · 信号链接 | 类 Simulink 画布 → `wiring.yaml` |
| C · Lineage | Compose 报告；**失败项标红**，下方保留原文 |

菜单：**保存**（Ctrl+S）· **Compose**（Ctrl+R）

## 类 Simulink 日常四步（B 页）

| # | 操作 | 效果 |
|---|------|------|
| 1 | **空白处右键 → 添加模块** | 新建 process（`deployments[]`） |
| 2 | **选中模块右键 → 删除** | 删 deployment，并级联删相关 dataflows |
| 3 | **双击模块** | 增删 In/Out 端口、切换方向、改 service 名 |
| 4 | **从右侧 Out 拖到左侧 In** | 生成 `dataflows`；以 Out 信号名为准（In 不同名自动改同名） |

其它：单击信号线（含缺失虚线）可选中；搜索框模糊定位；导入 hpp；Ctrl+滚轮 / Ctrl+H。

## 验收清单（Cfg 已交付）

- [x] 打开 `afc_with_uss` 可见带端口的连线图  
- [x] 右键增删节点 / 拖线 / Save 写回 `wiring.yaml`  
- [x] A 页改 req（含 acceptance）可写回  
- [x] Compose 后 C 页红绿显示检查项  
- [x] CI 不强制跑 Qt  
