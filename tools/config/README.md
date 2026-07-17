# gf-config（主机配置 GUI）

PySide6 工具：按 **SKU** 编辑 `req.yaml`，用 **类 Simulink 信号图** 编辑 `wiring.yaml`，一键 `compose` + lineage。

> **流程：** 改 A/B 页 → **Ctrl+S 保存**（只写盘）→ **Verify（Ctrl+R）** 合成 SOR + lineage → 可选 **Generate（Ctrl+G）** 产出 Proxy/Skeleton。  
> CI/无 GUI：`python -m gf_codegen.compose --project …`；代码生成仍用 `gf-codegen generate`。
>
> 工具边界：`gf-config` = 唯一作者 GUI · `gf-codegen` = lint/generate/import · GMT = 只读 CI + measure

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
                       ├── gf-config 保存 → compose → gf.sor.json → Generate / lineage
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
| B · 信号链接 | 类 Simulink 画布 → `wiring.yaml`；**右侧「连线 / Lineage」** |

已取消独立 C 页：Lineage 并入 B 页右侧。Verify / Generate 后自动切到右侧「Lineage」。

**文件菜单：** 打开 · 保存（Ctrl+S）· 保存并 Verify · Verify（Ctrl+R）· Generate（Ctrl+G）· 导入 hpp/fidl  

**视图菜单：** 适应窗口（Ctrl+0）· 默认大小（Ctrl+H）· 重载（F5）· 右侧连线/Lineage（Ctrl+L）· 删边（Delete）

日常：改 A/B → **保存** → **Verify** 看右侧 Lineage → 需要编 APP 时再 **Generate**。

## 类 Simulink 日常四步（B 页）

| # | 操作 | 效果 |
|---|------|------|
| 1 | **空白处右键 → 添加模块** | 新建 process（`deployments[]`） |
| 2 | **选中模块右键 → 删除** | 删 deployment，并级联删相关 dataflows |
| 3 | **双击模块** | 增删 In/Out 端口、切换方向、改 service 名 |
| 4 | **从右侧 Out 拖到左侧 In** | 生成 `dataflows`；以 Out 信号名为准（In 不同名自动改同名） |

其它：单击信号线（含缺失虚线）可选中；搜索框模糊定位；菜单导入 hpp / **fidl**；Ctrl+滚轮缩放。

**FIDL 导入：** 文件 → 导入 fidl… → 勾选 struct / broadcast / method / interface 作为端口 → 写回 `wiring.modules[].fidl` 与 provides/requires。解析库在 `gf_codegen.compose.parse_fidl`。  
**导出：** 当前**不支持**从 wiring/SOR 导出 `.fidl` / `.fdepl`（P1 优先导入；导出属后置，且完整 `.fdepl` 需 SOME/IP ID 模型，随 B/vsomeip）。

## 验收清单（Cfg 已交付）

- [x] 打开 `afc_with_uss` 可见带端口的连线图  
- [x] 右键增删节点 / 拖线 / Save 写回 `wiring.yaml`  
- [x] A 页改 req（含 acceptance）可写回  
- [x] Verify 后右侧 Lineage 红绿显示检查项  
- [x] CI 不强制跑 Qt  
