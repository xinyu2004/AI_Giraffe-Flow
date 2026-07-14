# gf-config（主机配置 GUI）

PySide6 工具：按 **SKU** 编辑 `req.yaml`，用 **类 Simulink 信号图** 编辑 `wiring.yaml`，一键 `compose` + lineage。

> 计划：[P1_PLAN.md](../../docs/zh/operations/P1_PLAN.md) · 不上板、不进 production 镜像  
> 工具边界：`gf-config` = 唯一作者 GUI · `gf-codegen` = CLI · GMT = 只读 CI + 后期 measure（见 [tools/README.md](../README.md)）

## 安装

```bash
cd /path/to/AI_Giraffe-Flow
source .venv/bin/activate   # 或 python3 -m venv .venv && source .venv/bin/activate
pip install -e "tools/codegen[dev]"
pip install -e tools/config
```

## 启动

```bash
gf-config projects/oem_a/afc_with_uss/project.yaml
# 或
gf-config   # 对话框选择 project.yaml
```

## 页签

| 页签 | 作用 |
|------|------|
| A · SKU / 中间件 | `runtime_modules` / `bindings` / variant… |
| B · 信号链接 | 端口 + 拖线 + 右键增删模块 → 写回 `wiring.yaml` |
| C · Lineage | Compose 后的闭环报告 |

菜单：**保存**（Ctrl+S）· **Compose**（Ctrl+R）

## 类 Simulink 日常四步（B 页）

| # | 操作 | 效果 |
|---|------|------|
| 1 | **空白处右键 → 添加模块** | 新建 process（`deployments[]`） |
| 2 | **选中模块右键 → 删除** | 删 deployment，并级联删相关 dataflows |
| 3 | **双击模块** | 增删 In/Out 端口、切换方向、改 service 名 |
| 4 | **从右侧 Out 拖到左侧 In** | 生成 `dataflows`；**以 Out 信号名为准**，In 不同名会自动改成同名 |

> **与 Simulink 的对应：** Simulink 连线不要求端口显示名一致，连上后信号从源端流出。我们这里用 service 名标识信号，因此连线时自动把目标 In 改成与 Out 同名，避免「名字不匹配无法连」。

其它：

- **单击信号线**（含红色缺失虚线）可选中；**双击 / 右键**编辑、删除或补线；**Delete** 删边
- **搜索框**：模糊匹配信号名 / 进程，点选结果自动高亮并定位
- **导入 hpp/h…**：解析 struct → 勾选加到目标模块的 Out/In，并写入 `modules[].hpp`
- **Ctrl+滚轮** 缩放 · **Ctrl+H** 恢复默认大小
- 箭头画在曲线中段**偏后**（避开信号名标签）
- 侧栏可删选中实线边；虚线红 = requires 尚无 dataflow

## 验收清单

- [ ] 打开 `afc_with_uss` 可见带端口的连线图  
- [ ] 右键增删节点后 Save，`wiring.yaml` 的 `deployments` 更新  
- [ ] 双击改端口后，边随 provides/requires 清理  
- [ ] Out→In 拖线写回 `dataflows`，Compose/lineage 可用  
- [ ] 导入 `interfaces/*/io_types.hpp` 后双击端口编辑器可见候选  
- [ ] CI 不强制跑 Qt  

GMT CLI 文本模式仍供 CI；本 GUI 是集成连线主路径。
