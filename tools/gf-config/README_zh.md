# gf-config（主机配置 GUI）

**English:** [README.md](README.md)

PySide6 工具：按 **SKU** 编辑 `req.yaml`，用 **类 Simulink 信号图** 编辑 `wiring.yaml`，一键 `compose` + lineage。

> **流程：** 改页 1/2 → **Ctrl+S 保存**（只写盘）→ **Verify（Ctrl+R）** 合成 SOR + lineage → 可选 **Generate（Ctrl+G）** 产出 Proxy/Skeleton。  
> CI / 无界面：`python -m gf_codegen.compose --project …`；代码生成仍用 `gf-codegen generate`。  
> 边界：`gf-config` = 唯一作者 GUI · `gf-codegen` = lint / generate / import · GMT = 只读 CI + 度量

## `req.yaml` 与 `wiring.yaml`

| | **req.yaml** | **wiring.yaml** |
|--|--------------|-----------------|
| **一句话** | 这辆车 / 这个 SKU **要什么、裁什么、验什么** | 进程 **怎么连、谁提供谁订阅** |
| **谁改** | 页 1 薄 SKU + 页 2 `runtime_modules` | 页 1 画布 |
| **典型内容** | `variant` / `topology` / `product` · `capabilities` · `runtime_modules` · `bindings` · `observability` · `apps` · `acceptance` | `modules`（hpp）· `deployments`（provides/requires）· `dataflows` · `bindings`（模块 IO） |
| **进流水线** | `merge_req` → SOR 产品变体 + lineage 门禁 | `apply_wiring` → SOR deployments / dataflows / types |
| **不写什么** | 不写具体 from→to 边 | 不写「要不要编进 com/phm」这类 SKU 裁剪 |

```text
req.yaml（SKU 契约） ──┐
                       ├── gf-config 保存 → compose → gf.sor.json → Generate / lineage
wiring.yaml（集成连线）─┘
```

**口诀：** req = 要什么、裁多深、验哪些服务；wiring = 谁跟谁说话。

## 安装

```bash
cd /path/to/AI_Giraffe-Flow
source .venv/bin/activate
pip install -e "tools/gf-codegen[dev]"
pip install -e tools/gf-config
```

## 启动

```bash
gf-config projects/oem_a/afc_with_uss/project.yaml
```

## 页签（P3 两页）

| 页签 | 作用 |
|------|------|
| **1 · 信号与应用**（默认） | **左侧薄 SKU 默认展开**；中央画布；**右侧连线/Lineage 默认收起**（点 ◀ 展开） |
| **2 · 平台运行时** | 顶部 `runtime_modules`（含可裁剪 **per / tsync**）；子页：执行/FG · **EM 启动表** · PHM · 诊断 · **日志** · OTA · **事件收集** · **有界内存** |

快捷键：Ctrl+1 / Ctrl+2 切页。Verify / Generate 后自动回页 1 右侧 Lineage。  
**编辑菜单：** 撤销 / 重做（Ctrl+Z / Ctrl+Y）— 跳到变更所在页（含平台子页），底栏提示中英 i18n。

**文件菜单：** 打开 · 保存（Ctrl+S）· 保存并 Verify · Verify（Ctrl+R）· Generate（Ctrl+G）· 导入 hpp/fidl  

**视图菜单：** 适应窗口（Ctrl+0）· 默认大小（Ctrl+H）· 重载（F5）· 右侧连线/Lineage（Ctrl+L）· 删边（Delete）

日常：页 1 画线 / 薄 SKU → 页 2 勾模块填表 → **保存** → **Verify** → 需要编 APP 时再 **Generate**。

### 页 2 · 日志（`log.yaml`）

- **默认级别** + **输出 sinks**（`console` / `file` / `dlt`）+ **DLT app_id** + **`file_max_bytes`** + **按模块覆盖**表。
- 勾选 **dlt** → SIL/HIL 按配置起 `dlt-daemon`（不用环境变量关开）。
- 新增行：模块默认可空；级别默认 `INFO`（枚举着色保留）。
- Verify：同一 `context id` 重复则失败（勿在 `log.yaml` 写两条同名模块）。

### 页 2 · 有界内存（`bounds.yaml` + BL-MEM-BOUND / BL-MEM-ROUDI）

- 跨模块硬上限：DLT contexts · LoopbackBus · per KV · DoIP rx · DID map · 可选 budget。
- **iceoryx / RouDi**：`mgmt`（→ `IOX_MAX_*`，改后须 rebuild iceoryx）+ `mempools`（→ `generated/iox_roudi.toml`）。
- `req.bindings` 含 iceoryx 时 SIL 自动起 RouDi（配置驱动）。
- 关联写回：`log.file_max_bytes`、`collector.local.*`、`diag.doip.rx_max_bytes`。
- **只读预估**含 RAM/DISK/SHM 公式行；见 `gf_codegen.compose.mem_budget` FORMULAS。

## 页 1 画布日常四步

| # | 操作 | 效果 |
|---|------|------|
| 1 | **空白处右键 → 添加模块** | 新建 process（`deployments[]`） |
| 2 | **选中模块右键 → 删除** | 删 deployment，并级联删相关 dataflows |
| 3 | **双击模块** | 增删 In/Out 端口、切换方向、改 service 名 |
| 4 | **拖拽 Out↔In** | 生成 `dataflows`（任一侧发起均可）；以 Out 信号名为准（In 不同名自动改同名） |
| — | **Ctrl+拖拽端口** | 改端口所在边（上/下/左/右）；裸拖 = 连线 |

其它：单击信号线（含缺失虚线）可选中；搜索框模糊定位；菜单导入 hpp / **fidl**；Ctrl+滚轮缩放。

**FIDL 导入：** 文件 → 导入 fidl… → 勾选 struct / broadcast / method / interface 作为端口 → 写回 `wiring.modules[].fidl` 与 provides/requires。解析在 `gf_codegen.compose.parse_fidl`。  
**导出：** 当前**不支持**从 wiring/SOR 导出 `.fidl` / `.fdepl`（优先导入；完整 `.fdepl` 需 SOME/IP ID 模型）。

## 验收清单

- [x] 打开 `afc_with_uss` 可见带端口的连线图  
- [x] 右键增删节点 / 拖线 / Save 写回 `wiring.yaml`  
- [x] 页 1 薄 SKU + 页 2 runtime_modules / platform 可写回  
- [x] 页 2「EM 启动表」读写 `platform/em_launch.yaml`（勾选 `exec` 后出现）  
- [x] Verify 后右侧 Lineage 红绿显示检查项（含 `platform_em_launch`）  
- [x] 日志表：行号选中 + 重复 context id Verify 失败  
- [x] 撤销/重做跳转到对应页（含平台子页）  
- [x] CI 不强制跑 Qt  

## 页 2 与板端模块对应（afc_with_uss）

| 勾选 `runtime_modules` | 子页 / YAML | 板端体现 |
|------------------------|-------------|----------|
| `core` / `com` / `osal` | （灰显必选） | CMake always-on，不可裁剪 |
| `exec` (+`sm`) | 执行/FG · `exec.yaml` | FG + 依赖拓扑 |
| `exec` | EM 启动表 · `em_launch.yaml` | `gf_em_daemon` OSAL Spawn |
| `phm` | 健康 · `phm.yaml` | Alive；`restart`→EM |
| `sm` | （与 exec 同页 FG） | StateClient / NotifyHealthFault |
| `collector` / phm / diag | 事件收集 · `collector.yaml` | ring buffer / cp_dem stub |
| `diag` / `log` / `ucm` | 各子页 | DoIP·UDS / 日志 / OTA 编排（SIL；真刷写仍 stub） |
| `per` / `tsync` | （暂无子页） | 仅 `runtime_modules` 勾选 → 编入镜像（KV / 时间同步骨架） |
