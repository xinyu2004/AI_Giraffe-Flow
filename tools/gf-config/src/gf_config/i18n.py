"""UI language helper for gf-config (zh source keys → en)."""

from __future__ import annotations

import sys

_ORG = "GiraffeFlow"
_APP = "gf-config"
_LANG = "zh"

# Chinese source string → English
_EN: dict[str, str] = {
    "语言": "Language",
    "中文": "中文",
    "English": "English",
    "gf-config — Giraffe Flow（信号与应用 / 平台）": "gf-config — Giraffe Flow (Signals & Apps / Platform)",
    "未打开项目": "No project open",
    "1 · 信号与应用": "1 · Signals & apps",
    "2 · 平台运行时": "2 · Platform runtime",
    "A · SKU": "A · SKU",
    "B · 信号链接": "B · Signal graph",
    "C · 平台": "C · Platform",
    "文件": "File",
    "打开 project.yaml…": "Open project.yaml…",
    "保存（只写盘，不检查）": "Save (disk only, no check)",
    "保存并 Verify…": "Save & Verify…",
    "Verify（合成 SOR / 检查闭环）": "Verify (compose SOR / check)",
    "Generate（Proxy/Skeleton）…": "Generate (Proxy/Skeleton)…",
    "导入 hpp/h…": "Import hpp/h…",
    "导入 fidl…": "Import fidl…",
    "导出 Graphviz .dot…": "Export Graphviz .dot…",
    "导出 Graphviz SVG…": "Export Graphviz SVG…",
    "退出": "Quit",
    "编辑": "Edit",
    "撤销": "Undo",
    "重做": "Redo",
    "关闭依赖模块": "Disable dependency module",
    "关闭 {0} 后，仍勾选的 {1} 将降级（例如 DTC/版本仅本会话有效，重启丢失）。仍要关闭？": (
        "Disabling {0} while {1} remain checked will degrade "
        "(e.g. DTC/version session-only). Continue?"
    ),
    "因勾选了 {0} 而自动启用：{1}": "Auto-enabled because {0} is checked: {1}",
    "已自动勾选 per：DTC/事件跨重启需要持久化（gf_ara::per）": (
        "Auto-checked per: DTC/events need persistency (gf_ara::per)"
    ),
    "已自动勾选 per（记版本）、sm（Updating 功能组）": (
        "Auto-checked per (version) and sm (Updating FG)"
    ),
    "已自动勾选 log：诊断/OTA 步骤需要可观测日志": (
        "Auto-checked log: diag/OTA steps need observable logs"
    ),
    "已自动勾选 log：健康失败默认 on_failure=log": (
        "Auto-checked log: PHM on_failure defaults to log"
    ),
    "已自动勾选 sm：进程功能组状态需要 sm": (
        "Auto-checked sm: process function-group state needs sm"
    ),
    "必选 core / com / osal 灰显不可关（CMake always-on）。勾选 collector/ucm/phm/diag/exec 会自动带上依赖模块并提示原因。": (
        "core/com/osal are always on. Checking collector/ucm/phm/diag/exec "
        "auto-enables dependencies with a tip."
    ),
    "默认级别": "Default level",
    "按模块覆盖级别": "Per-module level overrides",
    "模块": "Module",
    "级别": "Level",
    "添加模块级别": "Add module level",
    "log.yaml：默认级别；按模块选择级别（勿手填 id）。页 1 的 live/record 是观测通道，与这里分开。": (
        "log.yaml: default level; pick module levels (do not type ids). "
        "Tab-1 live/record is a separate observability path."
    ),
    "撤销（信号图）": "Undo (graph)",
    "重做（信号图）": "Redo (graph)",
    "重做（Ctrl+Y）": "Redo (Ctrl+Y)",
    "视图": "View",
    "适应窗口": "Fit window",
    "恢复默认大小": "Reset zoom",
    "重载信号图": "Reload graph",
    "右侧 · 连线列表": "Right · Connections",
    "右侧 · Lineage 报告": "Right · Lineage report",
    "折叠/展开右侧面板": "Toggle right panel",
    "折叠/展开左侧 SKU": "Toggle left SKU",
    "折叠 / 展开左侧 SKU": "Collapse / expand left SKU",
    "删除选中边": "Delete selected edge",
    "没有可撤销的操作": "Nothing to undo",
    "已撤销": "Undone",
    "已撤销（信号图）": "Undone (graph)",
    "没有可重做的操作": "Nothing to redo",
    "已重做": "Redone",
    "已重做（信号图）": "Redone (graph)",
    "平台": "Platform",
    "平台运行时": "Platform runtime",
    "信号连线 / 部署": "Signal wiring / deploy",
    "SKU / 需求": "SKU / requirements",
    "文档": "Document",
    "请先打开项目": "Open a project first",
    "打开失败": "Open failed",
    "保存失败": "Save failed",
    "有未保存的更改，是否保存？": "Unsaved changes. Save?",
    # SKU panel
    "剖面 / 观测": "Profile / observability",
    "ap_only=无 CP；ap_mcu_cp=MCU CP gateway": "ap_only=no CP; ap_mcu_cp=MCU CP gateway",
    "vehicle-debug 可开 live；production-release 强制关": (
        "vehicle-debug allows live; production-release forces it off"
    ),
    "开启后 Verify/compile_sil 自动加入 tools/iox_obs_tap；run_sil 自动接 Foxglove WS。": (
        "When on, Verify/compile_sil adds tools/iox_obs_tap; run_sil starts Foxglove WS."
    ),
    "wiring_all（推荐）": "wiring_all (recommended)",
    "explicit：每行一服务": "explicit: one service per line",
    "record 白名单，每行一个": "record allowlist, one per line",
    "required_services，每行一个": "required_services, one per line",
    "runtime_modules → 页 2": "runtime_modules → tab 2",
    "（未识别）": " (unknown)",
    "production-release：live/record/trace 灰调；不编 iox_obs_tap；run_sil 不起 Foxglove。bindings 仍保留。": (
        "production-release: live/record/trace disabled; no iox_obs_tap; "
        "run_sil skips Foxglove. bindings kept."
    ),
    "wiring_all：天花板=画布 dataflows；将编入 tap（codegen）。GMT 可再过滤。": (
        "wiring_all: ceiling = canvas dataflows; builds tap (codegen). GMT may filter."
    ),
    "explicit 已开但白名单为空 → Verify 将失败。请填 live svcs。": (
        "explicit on but empty allowlist → Verify fails. Fill live svcs."
    ),
    "将编入 tap；run_sil 自动接 Foxglove。": "Will build tap; run_sil starts Foxglove.",
    "live 关 → 不编 tap": "live off → no tap",
    "record=off → services 灰调": "record=off → services disabled",
    # Platform runtime (tab 2)
    "runtime_modules（编进镜像 · 勾选后下方出现对应清单）": (
        "runtime_modules (built into image · check to unlock pages below)"
    ),
    "鼠标悬停模块名可看说明；勾选后左侧出现对应平台清单。": (
        "Hover a module for its tip; checked modules unlock pages on the left."
    ),
    "必选 core / com / osal 灰显不可关（CMake always-on）。"
    "其余悬停看说明；勾选后左侧出现对应平台清单。": (
        "Required core / com / osal are greyed (CMake always-on). "
        "Hover others for tips; checked modules unlock pages on the left."
    ),
    "必选 · gf_ara::core — Result / ErrorCode（CMake always-on）": (
        "Required · gf_ara::core — Result / ErrorCode (CMake always-on)"
    ),
    "必选 · 统一通信 Proxy/Skeleton；bindings 另选（CMake always-on）": (
        "Required · unified COM Proxy/Skeleton; pick bindings separately "
        "(CMake always-on)"
    ),
    "可选 · 日志 lite（log.yaml）": "Optional · logging lite (log.yaml)",
    "必选 · OS 抽象：时钟 / 线程 / 进程 Spawn（CMake always-on；EM 依赖）": (
        "Required · OS abstraction: clock / thread / process spawn "
        "(CMake always-on; EM depends on it)"
    ),
    "可选 · ExecutionClient + EM；解锁「执行/FG」与「EM 启动表」": (
        "Optional · ExecutionClient + EM; unlocks Exec/FG and EM launch pages"
    ),
    "可选 · Alive / Deadline / Logical；解锁「健康 PHM」": (
        "Optional · Alive / Deadline / Logical; unlocks Health PHM"
    ),
    "可选 · 功能组 Off/Running/Updating；与 exec 同页": (
        "Optional · function groups Off/Running/Updating; shares the Exec page"
    ),
    "可选 · 事件环 / DEM-lite；解锁「事件收集」": (
        "Optional · event ring / DEM-lite; unlocks Event collector"
    ),
    "可选 · OTA 编排（OtaOrchestrator · SIL；真刷写仍 stub→RAUC）": (
        "Optional · OTA orchestration (OtaOrchestrator · SIL; real flash still stub→RAUC)"
    ),
    "可选 · ISO 14229 UDS + 可选 ISO 13400 DoIP；解锁「诊断」": (
        "Optional · ISO 14229 UDS + optional ISO 13400 DoIP; unlocks Diagnostics"
    ),
    "可选 · 持久化 KV stub；编入镜像（暂无独立 YAML 子页）": (
        "Optional · persistence KV stub; in image (no separate YAML page yet)"
    ),
    "可选 · 时间同步骨架；编入镜像（暂无独立 YAML 子页）": (
        "Optional · time sync skeleton; in image (no separate YAML page yet)"
    ),
    "可选 · 时序 → VCD / GMT（偏 debug-path）": (
        "Optional · timing → VCD / GMT (debug-path oriented)"
    ),
    "尚未勾选平台相关 runtime_modules（exec / phm / diag / log / ucm / sm）。\n"
    "勾选后，对应清单会出现在左侧。": (
        "No platform runtime_modules selected yet (exec / phm / diag / log / ucm / sm).\n"
        "Check modules to unlock their config pages on the left."
    ),
    "执行 / 功能组": "Exec / function groups",
    "EM 启动表": "EM launch table",
    "健康 PHM": "Health PHM",
    "诊断 diag": "Diagnostics",
    "日志": "Logging",
    "OTA ucm": "OTA (ucm)",
    "事件收集": "Event collector",
    "gf_ara::core — Result / ErrorCode（常开）": (
        "gf_ara::core — Result / ErrorCode (usually on)"
    ),
    "统一通信 Proxy/Skeleton；bindings 另选": (
        "Unified COM Proxy/Skeleton; pick bindings separately"
    ),
    "日志 lite（log.yaml）": "Logging lite (log.yaml)",
    "OS 抽象：时钟 / 线程 / 进程 Spawn": "OS abstraction: clock / thread / process spawn",
    "ExecutionClient + EM；解锁「执行/FG」与「EM 启动表」": (
        "ExecutionClient + EM; unlocks Exec/FG and EM launch pages"
    ),
    "Alive / Deadline / Logical；解锁「健康 PHM」": (
        "Alive / Deadline / Logical; unlocks Health PHM"
    ),
    "功能组 Off/Running/Updating；与 exec 同页": (
        "Function groups Off/Running/Updating; shares the Exec page"
    ),
    "事件环 / DEM-lite；解锁「事件收集」": (
        "Event ring / DEM-lite; unlocks Event collector"
    ),
    "OTA 编排（OtaOrchestrator · SIL；真刷写仍 stub→RAUC）": (
        "OTA orchestration (OtaOrchestrator · SIL; real flash still stub→RAUC)"
    ),
    "ISO 14229 UDS + 可选 ISO 13400 DoIP；解锁「诊断」": (
        "ISO 14229 UDS + optional ISO 13400 DoIP; unlocks Diagnostics"
    ),
    "持久化 KV stub；编入镜像（暂无独立 YAML 子页）": (
        "Persistence KV stub; in image (no separate YAML page yet)"
    ),
    "时间同步骨架；编入镜像（暂无独立 YAML 子页）": (
        "Time sync skeleton; in image (no separate YAML page yet)"
    ),
    "时序 → VCD / GMT（偏 debug-path）": "Timing → VCD / GMT (debug-path oriented)",
    "exec.yaml：功能组（SM 极简）+ 进程隶属。进程名只读自 wiring（不含 external.*）。": (
        "exec.yaml: function groups (minimal SM) + process membership. "
        "Process names come from wiring (no external.*)."
    ),
    "添加 FG": "Add FG",
    "删除选中": "Delete selected",
    "添加进程行": "Add process row",
    "从 wiring 同步进程名": "Sync names from wiring",
    "depends_on（空格/逗号分隔）": "depends_on (space/comma)",
    "em_launch.yaml：OS EM（gf_em_daemon）二进制表。"
    "binary 相对 $GF_BUILD_DIR；与 exec.yaml 进程名对齐。"
    "args / max_restarts 不留空（默认 args=0、max_restarts=3）。"
    "gateway 的 args=15：收满 15 条 Trajectory 后退出（0=一直跑）。"
    "PHM on_failure=restart + GF_EM_MANAGED → exit 75 后按 max_restarts relaunch。": (
        "em_launch.yaml: OS EM (gf_em_daemon) binary table. "
        "binary is relative to $GF_BUILD_DIR; names align with exec.yaml. "
        "args / max_restarts are never blank (defaults args=0, max_restarts=3). "
        "gateway args=15: exit after 15 Trajectory samples (0=run forever). "
        "PHM on_failure=restart + GF_EM_MANAGED → exit 75 then relaunch up to max_restarts."
    ),
    "em_launch.yaml：OS EM（gf_em_daemon）二进制表。"
    "binary 相对 $GF_BUILD_DIR；与 exec.yaml 进程名对齐。"
    "args / max_restarts 不留空（默认 args=0、max_restarts=3）。"
    "args=POSIX argv（非 AP 字段，但 EM Spawn 需要；gateway 15=收满 Trajectory 退出）。"
    "PHM on_failure=restart + GF_EM_MANAGED → exit 75 后按 max_restarts relaunch。": (
        "em_launch.yaml: OS EM (gf_em_daemon) binary table. "
        "binary is relative to $GF_BUILD_DIR; names align with exec.yaml. "
        "args / max_restarts are never blank (defaults args=0, max_restarts=3). "
        "args = POSIX argv (not an AP field, but EM Spawn needs it; "
        "gateway 15 = exit after N Trajectory). "
        "PHM on_failure=restart + GF_EM_MANAGED → exit 75 then relaunch up to max_restarts."
    ),
    "添加行": "Add row",
    "从 exec 同步进程名": "Sync names from exec",
    "binary（相对 build_dir）": "binary (rel. build_dir)",
    "args（空格/逗号）": "args (space/comma)",
    "phm.yaml：Alive / Deadline。process ∈ wiring（非 external）。"
    "数值不留空（deadline_ms=0 表示不做独立 deadline）。"
    "on_failure 下拉：log | notify_sm | restart"
    "（restart：托管进程 exit 75 → EM relaunch；未托管 → soft）。": (
        "phm.yaml: Alive / Deadline. process ∈ wiring (not external). "
        "Numeric fields are never blank (deadline_ms=0 means no separate deadline). "
        "on_failure dropdown: log | notify_sm | restart "
        "(restart: managed process exit 75 → EM relaunch; unmanaged → soft)."
    ),
    "phm.yaml：Alive / Deadline。process 从 wiring 选择。"
    "数值不留空（deadline_ms=0 表示不做独立 deadline）。"
    "on_failure 下拉：log | notify_sm | restart"
    "（restart：托管进程 exit 75 → EM relaunch；未托管 → soft）。": (
        "phm.yaml: Alive / Deadline. pick process from wiring. "
        "Numeric fields are never blank (deadline_ms=0 means no separate deadline). "
        "on_failure dropdown: log | notify_sm | restart "
        "(restart: managed process exit 75 → EM relaunch; unmanaged → soft)."
    ),
    "exec.yaml：功能组（SM 极简）+ 进程隶属。"
    "进程名 / FG / depends_on 均从列表选择（不含 external.*）。": (
        "exec.yaml: function groups (minimal SM) + process membership. "
        "Process / FG / depends_on are all chosen from lists (no external.*)."
    ),
    "功能组 id（SM StateClient）": "Function group id (SM StateClient)",
    "初始状态：Off / Running / Updating": "Initial state: Off / Running / Updating",
    "进程名（来自 wiring deployments）": "Process name (from wiring deployments)",
    "隶属功能组（来自上方 FG 表）": "Owning function group (from FG table above)",
    "启动依赖：多选其他进程": "Start dependencies: multi-select other processes",
    "是否使用 ExecutionClient 汇报状态": "Whether to report via ExecutionClient",
    "添加功能组行": "Add function-group row",
    "删除选中行": "Delete selected rows",
    "添加进程行": "Add process row",
    "用 wiring 进程列表重建本表（保留已有 FG/依赖/开关）": (
        "Rebuild table from wiring processes (keep FG / deps / flags)"
    ),
    "进程名（从 exec / wiring 选择）": "Process name (from exec / wiring)",
    "二进制路径，相对 $GF_BUILD_DIR": "Binary path relative to $GF_BUILD_DIR",
    "argv；gateway=Trajectory 条数（0=一直跑）": (
        "argv; gateway = Trajectory count (0 = run forever)"
    ),
    "PHM restart 时 EM 最多 relaunch 次数": (
        "Max EM relaunches when PHM on_failure=restart"
    ),
    "用 exec 进程列表重建本表": "Rebuild table from exec processes",
    "监督实体 id": "Supervised entity id",
    "被监督进程（wiring）": "Supervised process (wiring)",
    "Alive 期望周期 ms": "Alive expected period (ms)",
    "Alive 超时 ms（SIL 亦作 deadline 参数）": (
        "Alive timeout ms (also used as deadline in SIL)"
    ),
    "独立 deadline ms；0=关闭": "Separate deadline ms; 0 = off",
    "失败策略：log / notify_sm / restart": "Failure policy: log / notify_sm / restart",
    "0x27/0x29 安全访问插件路径（.so/.dll）；空=内置 SIL stub": (
        "0x27/0x29 security plugin path (.so/.dll); empty = built-in SIL stub"
    ),
    "浏览选择安全插件": "Browse for security plugin",
    "DoIP 逻辑地址（如 0x0E00）": "DoIP logical address (e.g. 0x0E00)",
    "DID 标识（十六进制）": "DID id (hex)",
    "显示名": "Display name",
    "访问权限": "Access rights",
    "数据长度字节": "Payload size (bytes)",
    "默认日志级别": "Default log level",
    "日志上下文 id": "Log context id",
    "该上下文的级别": "Level for this context",
    "事件转发：local_store / cp_dem / both": (
        "Event forward: local_store / cp_dem / both"
    ),
    "采集来源（勾选计入 collector.sources）": (
        "Source (checked → collector.sources)"
    ),
    "启用本地 DEM-lite 落盘": "Enable local DEM-lite persistence",
    "本地最多保留条目数": "Max local entries",
    "（无依赖）": "(no deps)",
    "选择 depends_on": "Select depends_on",
    "选择": "Select",
    "勾选后确定；可多选。": "Check items, then OK. Multi-select allowed.",
    "（未选服务）": "(no services)",
    "选择 live 服务": "Select live services",
    "选择 record 服务": "Select record services",
    "选择 required_services": "Select required_services",
    "SKU 变体名（写入 req.variant）": "SKU variant (req.variant)",
    "产品名（写入 req.product）": "Product name (req.product)",
    "wiring_all=画布全部服务；explicit=白名单": (
        "wiring_all = all canvas services; explicit = allowlist"
    ),
    "explicit 模式下的 live 服务白名单（从 wiring 多选）": (
        "Live allowlist in explicit mode (multi-select from wiring)"
    ),
    "录制模式：minimal / sampled / full / off": (
        "Record mode: minimal / sampled / full / off"
    ),
    "record 服务白名单（从 wiring 多选）": (
        "Record allowlist (multi-select from wiring)"
    ),
    "是否导出 trace（on/off）": "Export trace (on/off)",
    "绑定 iceoryx（进程内/本机零拷贝，SIL 常用）": (
        "iceoryx binding (local zero-copy; common in SIL)"
    ),
    "绑定 SOME/IP（车载以太网服务发现）": (
        "SOME/IP binding (automotive Ethernet discovery)"
    ),
    "绑定 DDS（可选中间件）": "DDS binding (optional middleware)",
    "跨域 IPC（AP↔MCU CP gateway）": "Cross-domain IPC (AP↔MCU CP gateway)",
    "验收描述（acceptance.description）": "Acceptance description",
    "Verify 是否强制 lineage 门禁通过": "Require lineage gate on Verify",
    "验收要求的服务列表（从 wiring 多选）": (
        "Required services for acceptance (multi-select from wiring)"
    ),
    "explicit 已开但白名单为空 → Verify 将失败。请选择 live svcs。": (
        "explicit on but empty allowlist → Verify fails. Select live svcs."
    ),
    "添加 entity": "Add entity",
    "diag.yaml：ISO 14229（UDS+NRC）为基础；ISO 13400 DoIP 为其传输子项（不可单独勾选）。"
    "无 DoIP 时 AP 不跑 ISO-TP，CAN 侧 PDU 交 MCU。": (
        "diag.yaml: ISO 14229 (UDS+NRC) is the base; ISO 13400 DoIP is a transport "
        "child (cannot be selected alone). Without DoIP, AP skips ISO-TP and hands "
        "CAN PDUs to the MCU."
    ),
    "standards（依赖：13400 ⊂ 14229）": "standards (dependency: 13400 ⊂ 14229)",
    "ISO 14229 UDS（含 NRC）— 父能力": "ISO 14229 UDS (with NRC) — parent",
    "ISO 13400 DoIP — 依赖 14229": "ISO 13400 DoIP — requires 14229",
    "0x27/0x29 安全插件": "0x27/0x29 security plugin",
    "0x27/0x29 安全插件：请在 GMT → OTA 页按 OEM 选择（本页只配诊断框架）。": (
        "0x27/0x29 security plugin: set per OEM in GMT → OTA (this page is framework only)."
    ),
    "0x27/0x29 安全插件：在 GMT → OTA 本地记录路径；板端用环境变量 GF_DIAG_SEC_PLUGIN（本页只配诊断框架）。": (
        "0x27/0x29 plugin: remember path in GMT → OTA; board uses GF_DIAG_SEC_PLUGIN "
        "(this page is framework only)."
    ),
    "空=内置 SIL stub": "empty = built-in SIL stub",
    "浏览…": "Browse…",
    "选择安全访问插件（.so / .dll）": "Select security-access plugin (.so / .dll)",
    "动态库 (*.so *.dll);;所有文件 (*)": "Shared library (*.so *.dll);;All files (*)",
    "enabled（与 iso_13400 同步）": "enabled (synced with iso_13400)",
    "下载 SID": "Download SID",
    "添加 DID": "Add DID",
    "添加 RID": "Add RID",
    "log.yaml：默认级别与 contexts（细配置在此；页 1 仅粗开关）。": (
        "log.yaml: default level and contexts (detail here; tab 1 is coarse only)."
    ),
    "添加 context": "Add context",
    "ucm.yaml：配置 SIL OTA 编排参数（不是刷写包本身）。"
    "流程：GMT/DoIP 下发 → OtaOrchestrator 把目标功能组切到 Updating → "
    "PackageManager 状态机 → Collector 记结果；失败可回滚。"
    "真板 RAUC 刷写仍为 stub（P3z）。": (
        "ucm.yaml: SIL OTA orchestration settings (not the flash image itself). "
        "Flow: GMT/DoIP trigger → OtaOrchestrator switches the target function group "
        "to Updating → PackageManager state machine → Collector records the result; "
        "optional rollback on failure. Real RAUC flash is still stub (P3z)."
    ),
    "启用 OTA 编排": "Enable OTA orchestration",
    "包 / 清单 URI": "Package / manifest URI",
    "目标功能组": "Target function group",
    "失败时允许回滚": "Allow rollback on failure",
    "例如 sil://artifact；SIL 下交给 PackageManager::Initialize（清单/包源标识）。": (
        "e.g. sil://artifact; in SIL this is PackageManager::Initialize "
        "(manifest / package-source id)."
    ),
    "OTA 期间切到 Updating 的 SM 功能组（通常 MachineFG）。": (
        "SM function group switched to Updating during OTA (usually MachineFG)."
    ),
    "关闭则失败只记事件、不走 Rollback。": (
        "If off, failures are logged only — no Rollback path."
    ),
    "collector.yaml：Event Collector 最小集。"
    "有 MCU CP → forward=cp_dem；否则 local_store（DEM-lite）。"
    "sources 勾选本工程会 ReportEvent 的来源：phm / process / com / ucm"
    "（不是封闭枚举；diag 多是读 DTC，一般不作 source）。"
    "不做 Classic DEM 全编辑器。": (
        "collector.yaml: minimal Event Collector. "
        "With MCU CP → forward=cp_dem; else local_store (DEM-lite). "
        "sources: producers that ReportEvent — phm / process / com / ucm "
        "(not a closed set; diag usually reads DTCs, not a source). "
        "Not a full Classic DEM editor."
    ),
    "local（DEM-lite 落盘）": "local (DEM-lite on disk)",
    # Language switch / SKU localized labels (yaml values stay English)
    "切换语言将重启应用。有未保存的更改，是否保存？": (
        "Switching language restarts the app. Save unsaved changes?"
    ),
    "变体": "Variant",
    "拓扑": "Topology",
    "产品": "Product",
    "剖面": "Profile",
    "Live 旁路": "Live tap",
    "Live 范围": "Live scope",
    "Live 服务": "Live services",
    "录制": "Record",
    "录制服务": "Record services",
    "时序导出": "Trace export",
    "通信绑定": "Bindings",
    "验收": "Acceptance",
    "说明": "Description",
    "服务": "Services",
    "强制 lineage 门禁": "Require lineage gate",
    "仅 AP（无 MCU）": "AP only (no MCU)",
    "AP + MCU CP": "AP + MCU CP",
    "车辆调试": "Vehicle debug",
    "量产发布": "Production release",
    "跟随画布（推荐）": "Follow canvas (recommended)",
    "白名单": "Allowlist",
    "最小": "Minimal",
    "抽样": "Sampled",
    "全量": "Full",
    "关闭": "Off",
    "开": "On",
    "关": "Off",
    "iceoryx（本机零拷贝）": "iceoryx (local zero-copy)",
    "SOME/IP": "SOME/IP",
    "DDS": "DDS",
    "跨域 IPC": "Cross-domain IPC",
    "选择 Live 服务": "Select live services",
    "选择录制服务": "Select record services",
    "选择验收服务": "Select acceptance services",
    "量产发布：Live/录制/时序灰调；不编 iox_obs_tap；"
    "run_sil 不起 Foxglove。通信绑定仍保留。": (
        "Production release: Live/record/trace greyed; no iox_obs_tap; "
        "run_sil skips Foxglove. Bindings kept."
    ),
    "跟随画布：天花板=页 1 dataflows；将编入 tap（codegen）。"
    "GMT 可再过滤。": (
        "Follow canvas: ceiling = tab-1 dataflows; builds tap (codegen). "
        "GMT may filter further."
    ),
    "白名单模式已开但未选服务 → Verify 将失败。请选择 Live 服务。": (
        "Allowlist mode on but empty → Verify fails. Select Live services."
    ),
    "Live 关 → 不编 tap": "Live off → no tap",
    "录制关闭 → 录制服务灰调": "Record off → record services greyed",
    # Status bar
    "已打开": "Opened",
    "有未保存更改 — Ctrl+S 只保存；Verify 另点": (
        "Unsaved changes — Ctrl+S saves; Verify separately"
    ),
    "✓ 已保存": "✓ Saved",
    "✓ 已保存（未 Verify）": "✓ Saved (not Verified)",
    "没有未保存更改": "No unsaved changes",
    "没有未保存的更改。": "No unsaved changes.",
    "已写入磁盘：": "Written to disk:",
    "（未跑 Verify；需要检查时再按 Ctrl+R）": (
        "(Verify not run; press Ctrl+R when you need checks)"
    ),
    "已保存，正在 Verify…": "Saved, running Verify…",
    "Verify OK — 右侧 Lineage。需要 C++ API 时点 Generate (Ctrl+G)": (
        "Verify OK — see Lineage on the right. Generate (Ctrl+G) for C++ APIs."
    ),
    "Verify 退出码 {rc} — 见右侧 Lineage 红项": (
        "Verify exit {rc} — see red items in Lineage"
    ),
    "Generate OK → {out}/include/gf_gen/": "Generate OK → {out}/include/gf_gen/",
}

# Authoritative field tips (gf_config.gui.tips) — purpose/effect, not enum noise.
try:
    from gf_config.gui.tips_en import TIP_EN as _TIP_EN

    _EN.update(_TIP_EN)
except Exception:
    pass


def get_language() -> str:
    return _LANG


def load_language() -> str:
    global _LANG
    try:
        from PySide6.QtCore import QSettings

        raw = str(QSettings(_ORG, _APP).value("ui/language", "zh"))
    except Exception:
        raw = "zh"
    _LANG = "en" if raw == "en" else "zh"
    return _LANG


def save_language(lang: str) -> None:
    global _LANG
    _LANG = "en" if lang == "en" else "zh"
    try:
        from PySide6.QtCore import QSettings

        QSettings(_ORG, _APP).setValue("ui/language", _LANG)
    except Exception:
        pass


def set_pending_reopen_project(path: str | None) -> None:
    """Remember project.yaml to reopen after language-switch restart."""
    try:
        from PySide6.QtCore import QSettings

        s = QSettings(_ORG, _APP)
        if path:
            s.setValue("session/pending_open", path)
        else:
            s.remove("session/pending_open")
    except Exception:
        pass


def take_pending_reopen_project() -> str | None:
    """Consume pending reopen path (one-shot after language restart)."""
    try:
        from PySide6.QtCore import QSettings

        s = QSettings(_ORG, _APP)
        raw = str(s.value("session/pending_open", "") or "").strip()
        s.remove("session/pending_open")
        return raw or None
    except Exception:
        return None


def t(zh: str) -> str:
    if _LANG == "en":
        return _EN.get(zh, zh)
    return zh


def switch_language_and_restart(
    lang: str, *, project_path: str | None = None
) -> None:
    """Persist language, remember project, relaunch this process (sys.argv)."""
    from PySide6.QtCore import QProcess
    from PySide6.QtWidgets import QApplication

    save_language(lang)
    set_pending_reopen_project(project_path)
    app = QApplication.instance()
    if app is not None:
        for w in app.topLevelWidgets():
            w.hide()
    QProcess.startDetached(sys.executable, sys.argv)
    if app is not None:
        app.quit()
