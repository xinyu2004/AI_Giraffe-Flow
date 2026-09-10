"""UI language helper for gf-config (zh source keys → en)."""

from __future__ import annotations

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
    "2 · 平台配置": "2 · Platform config",
    "2 · 平台运行时": "2 · Platform config",  # legacy tip / history key
    "A · SKU": "A · SKU",
    "B · 信号链接": "B · Signal graph",
    "C · 平台": "C · Platform",
    "文件": "File",
    "打开 giraffe.yaml…": "Open giraffe.yaml…",
    "新建 Giraffe 工程…": "New Giraffe project…",
    "选择 giraffe.yaml": "Select giraffe.yaml",
    "选择新建工程的父目录": "Parent folder for new project",
    "新建 Giraffe 工程": "New Giraffe project",
    "工程目录名（project_id）：": "Project folder name (project_id):",
    "新建失败": "Create failed",
    "目录非空：": "Directory not empty: ",
    "已生成最小完备树：": "Scaffolded minimal tree:\n",
    "含 cfg/req.yaml · cfg/wiring.yaml · cfg/gf_ara_cfg/*\n请补 OEM DBC 后 Verify。": (
        "Includes cfg/req.yaml · cfg/wiring.yaml · cfg/gf_ara_cfg/*\n"
        "Add OEM DBC then Verify."
    ),
    "打开 giraffe.yaml…": "Open giraffe.yaml…",  # legacy tip key
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
    "log.yaml：默认级别、输出 sinks（console / file / DLT）、按模块级别。勾选 DLT 时 SIL/HIL 会起 dlt-daemon；上位机用 dlt-viewer / GMT。页 1 的 live/record 是观测通道，与这里分开。": (
        "log.yaml: default level, sinks (console / file / DLT), per-module levels. "
        "With DLT checked, SIL/HIL starts dlt-daemon; host uses dlt-viewer / GMT. "
        "Tab-1 live/record is a separate observability path."
    ),
    "log.yaml：默认级别、输出 sinks（console / file / DLT）、按模块级别。"
    "勾选 DLT 时由 EM 拉起 dlt-daemon（daemon，非与 EM 并列）；上位机用 dlt-viewer / GMT。"
    "页 1 的 live/record 是观测通道，与这里分开。": (
        "log.yaml: default level, sinks (console / file / DLT), per-module levels. "
        "With DLT checked, EM starts dlt-daemon (a platform daemon, not a peer of EM); "
        "host uses dlt-viewer / GMT. Tab-1 live/record is a separate observability path."
    ),
    "EM（入口）": "EM (entry)",
    "启动：systemd/init → EM（入口）→ daemons（dlt/RouDi…，按 gf-config）+ SOA apps。"
    "下方为 compose 冻结状态（改 Tab2 日志/诊断与绑定后 Verify）。": (
        "Boot: systemd/init → EM (entry) → daemons (dlt/RouDi…, via gf-config) + SOA apps. "
        "Below is compose-frozen status (edit Tab2 log/diag/bindings, then Verify)."
    ),
    "主体=EM；dlt/RouDi 按需由 EM 拉起。下方为 compose 将冻结的状态（改 Tab2 日志/诊断与绑定后 Verify）。": (
        "Subject=EM; dlt/RouDi started by EM as needed. Below is compose-frozen status "
        "(edit Tab2 log/diag/bindings, then Verify)."
    ),
    "HOST / EM": "EM (entry)",
    "输出 sinks": "Output sinks",
    "console": "console",
    "file": "file",
    "dlt（remote）": "dlt (remote)",
    "终端 stdout/stderr（SIL 本机）": "stdout/stderr (SIL local)",
    "落盘 file_path；仅本机调试，非 GMT 路径": "file_path; local debug only, not GMT",
    "COVESA DLT → dlt-daemon；标准协议给 viewer/GMT": (
        "COVESA DLT → dlt-daemon; standard protocol for viewer/GMT"
    ),
    "DLT app_id": "DLT app_id",
    "DLT Application ID（4 字符）；多进程可由运行时覆盖": (
        "DLT Application ID (4 chars); runtime may override per process"
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
    "平台配置": "Platform config",
    "平台运行时": "Platform config",  # legacy
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
    "开启后 Verify/compile_sil 自动加入 gmt_board/iox_obs_tap；run_sil 自动接 Foxglove WS。": (
        "When on, Verify/compile_sil adds gmt_board/iox_obs_tap; run_sil starts Foxglove WS."
    ),
    "wiring_all（推荐）": "wiring_all (recommended)",
    "explicit：每行一服务": "explicit: one service per line",
    "record 白名单，每行一个": "record allowlist, one per line",
    "required_services，每行一个": "required_services, one per line",
    "runtime_modules → 页 2": "runtime_modules → tab 2",
    "行来自各模块 Out（画布双击亦可改触发）。一发多收共享同一话题策略。": (
        "Rows come from module Outs (also editable via canvas double-click). "
        "Fan-out shares one topic policy."
    ),
    "语义话题：画布双击模块 → Out 表改触发。"
    "通道话题：双击 frame_ingest 改触发。"
    "一发多收共享同一话题策略；Signals 页不再编辑发布表。": (
        "Semantic topics: canvas double-click → Out table. "
        "Channel topics: double-click frame_ingest. "
        "Fan-out shares one topic policy; Signals page no longer edits the table."
    ),
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
    # Platform config (tab 2)
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
    "有界内存": "Memory bounds",
    "有界内存预估": "Memory-bound estimate",
    "BL-MEM-BOUND：平台有界内存 / 磁盘上界。"
    "下方预估为保守上界（非实测 RSS），公式见 mem_budget.py FORMULAS。"
    "未勾选的模块对应段不显示、不计入预估。"
    "log.file_max / collector 环与落盘上限在「日志」「事件收集」页编辑。"
    "Verify / Generate 跑同一套 estimate。": (
        "BL-MEM-BOUND: platform RAM/disk upper bounds. "
        "Estimate below is conservative (not measured RSS); formulas in mem_budget.py FORMULAS. "
        "Unchecked modules are hidden and excluded from the estimate. "
        "Edit log.file_max / collector ring & store on the Log / Event collector pages. "
        "Verify/Generate uses the same estimate."
    ),
    "公式常量（字节）": "Formula constants (bytes)",
    "bounds · budget（总预算）": "bounds · budget (totals)",
    "静态上界预估（只读 · 含公式）": "Static upper-bound estimate (read-only · with formulas)",
    "载入实测 SHM": "Load measured SHM",
    "iox SHM 报告 (*.json);;所有文件 (*)": "iox SHM report (*.json);;All files (*)",
    "清除实测": "Clear measured",
    "SHM 实测：已指定 {path}，但报告无效或未含 mgmt_bytes": (
        "SHM measured: path set to {path}, but report invalid or missing mgmt_bytes"
    ),
    "未找到 {path}\n"
    "请先跑 SIL / smoke_sil_verify（RouDi 会写出该报告），再载入。": (
        "Not found: {path}\n"
        "Run SIL / smoke_sil_verify first (RouDi writes the report), then load."
    ),
    "iceoryx / RouDi（BL-MEM-ROUDI）": "iceoryx / RouDi (BL-MEM-ROUDI)",
    "添加 mempool": "Add mempool",
    "补齐缺失 SOA": "Append missing SOA",
    "不可删除 host": "Cannot delete host",
    "补齐": "Fill gaps",
    "无法保存": "Cannot save",
    "工程非法，已拒绝打开": "Invalid project — open refused",
    "磁盘配置未通过校验（不会自动修补）。请用 gf-config 修正后重开。": (
        "On-disk config failed validation (no auto-repair). "
        "Fix with gf-config and reopen."
    ),
    "校验未通过，未写入磁盘（更改仍在内存）。": (
        "Validation failed — nothing written (edits remain in memory)."
    ),
    "校验未通过，未写入磁盘。可丢弃更改后退出，或取消继续编辑。": (
        "Validation failed — nothing written. Discard to quit, or Cancel to keep editing."
    ),
    "校验未通过 — 未写盘": "Validation failed — not saved",
    "保存（Verify 通过后写盘）": "Save (write after validation passes)",
    "已打开（异常：加载后出现未保存标记，请报告）": (
        "Opened (bug: dirty after load — please report)"
    ),
    "已打开（已自动迁移旧格式，请保存）": (
        "Opened (legacy format migrated — please save)"
    ),
    "有未保存的 SKU / 连线 / ARA cfg 更改，是否保存？": (
        "Unsaved SKU / wiring / ARA cfg changes. Save?"
    ),
    "Verify": "Verify",
    "Generate": "Generate",
    "成功。请查看右侧「Lineage」。\n\n"
    "拓扑图见页 1 画布；评审附件可用「文件 → 导出 Graphviz」。\n"
    "运行时序/回放请用 GMT GUI。\n\n"
    "若要生成 Proxy/Skeleton：文件 → Generate 或 Ctrl+G。": (
        "OK. See Lineage on the right.\n\n"
        "Topology is on tab-1 canvas; use File → Export Graphviz for review attachments.\n"
        "Use GMT GUI for runtime timeline / replay.\n\n"
        "For Proxy/Skeleton: File → Generate or Ctrl+G."
    ),
    "em_launch.yaml：EM Spawn 表（binary / args / max_restarts）。"
    "进程名来自 wiring（及能力允许的 host.*）；与 exec.yaml 只共享名字，"
    "成员集合互不强制对齐。binary 相对 $GF_BUILD_DIR。": (
        "em_launch.yaml: EM Spawn table (binary / args / max_restarts). "
        "Names from wiring (and capability-gated host.*); shares only names with "
        "exec.yaml — membership sets need not match. binary relative to $GF_BUILD_DIR."
    ),
    "exec / wiring 中没有可同步的 SOA 进程名。": (
        "No SOA process names available from exec / wiring."
    ),
    "没有缺失项：EM 表已覆盖 exec SOA 进程。": (
        "Nothing missing: EM table already covers exec SOA processes."
    ),
    "尚未勾选可选平台模块（exec / phm / diag / log / ucm / sm / collector …）。\n"
    "core / com / osal 常开；勾选后对应清单出现在左侧（有界内存因 com 常显）。": (
        "No optional platform modules checked (exec / phm / diag / log / ucm / sm / collector …).\n"
        "core / com / osal stay on; checked modules appear in the left nav "
        "(Memory bounds stays visible because com is always on)."
    ),
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
    "从 wiring 选择": "Pick from wiring",
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
    "em_launch.yaml：EM 入口拉起的进程表（可选 daemons + SOA apps）。"
    "binary 相对 $GF_BUILD_DIR；与 exec.yaml 进程名对齐。"
    "args / max_restarts 不留空（默认 args=0、max_restarts=3）。"
    "args=POSIX argv（非 AP 字段，但 EM Spawn 需要；gateway 15=收满 Trajectory 退出）。"
    "PHM on_failure=restart + GF_EM_MANAGED → exit 75 后按 max_restarts relaunch。": (
        "em_launch.yaml: processes spawned by EM entry (optional daemons + SOA apps). "
        "binary is relative to $GF_BUILD_DIR; names align with exec.yaml. "
        "args / max_restarts are never blank (defaults args=0, max_restarts=3). "
        "args = POSIX argv (not an AP field, but EM Spawn needs it; "
        "gateway 15 = exit after N Trajectory). "
        "PHM on_failure=restart + GF_EM_MANAGED → exit 75 then relaunch up to max_restarts."
    ),
    "添加行": "Add row",
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
    "编辑列表": "Edit list",
    "逐项添加态名；不要用逗号拼写。双击可改名。": (
        "Add state names one by one; do not join with commas. Double-click to rename."
    ),
    "新态名，例如 DrivingActive": "New state name, e.g. DrivingActive",
    "添加": "Add",
    "改名": "Rename",
    "态名": "State name",
    "（点击编辑 states）": "(click to edit states)",
    "编辑 ModeDeclaration states": "Edit ModeDeclaration states",
    "信号与应用": "Signals & apps",
    "dataflows / channel_flows": "dataflows / channel_flows",
    "Lineage": "Lineage",
    "linked": "linked",
    "unlinked": "unlinked",
    "拖拽调整路径（Ctrl+S 保存）": "Drag to adjust route (Ctrl+S to save)",
    "Verify 后显示 lineage 检查结果": "Lineage checks appear here after Verify",
    "原始 signal_lineage_report.yaml …": "Raw signal_lineage_report.yaml …",
    "（无报告内容）": "(empty report)",
    "报告不是合法 YAML，见下方原文": "Report is not valid YAML; see raw text below",
    "报告格式异常": "Unexpected report format",
    "Lineage PASS · {n} 项检查通过": "Lineage PASS · {n} checks ok",
    "Lineage FAIL · {e} 个错误 · {w} 个警告": "Lineage FAIL · {e} errors · {w} warnings",
    "错误\n": "Errors\n",
    "警告\n": "Warnings\n",
    "检查项\n": "Checks\n",
    "require ProgrammingSession": "require ProgrammingSession",
    "require SecurityAccess": "require SecurityAccess",
    "service": "service",
    "源": "from",
    "目的": "to",
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
    "切换语言将刷新界面。有未保存的更改，是否保存？": (
        "Switching language refreshes the UI. Save unsaved changes?"
    ),
    "切换语言将重启应用。有未保存的更改，是否保存？": (
        "Switching language refreshes the UI. Save unsaved changes?"
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
    "发布策略": "Publish policy",
    "触发": "Trigger",
    "周期": "Period",
    "变化时": "On change",
    "语义服务": "Semantic services",
    "通道": "Channels",
    "ms / fps": "ms / fps",
    "周期填 ms；变化时填 expect_fps（期望/告警带，不是发报钟）。须 ≤ 相机 fps。": (
        "Period uses ms; on-change uses expect_fps (budget/warn band, not a send clock). Must be ≤ camera fps."
    ),
    "Out expect_fps 须 ≤ 相机 fps（{cam}）": (
        "Out expect_fps must be ≤ camera fps ({cam})"
    ),
    "请在 frame_ingest 通道填写相机 fps": (
        "Set camera fps on the frame_ingest lane"
    ),
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
    "量产发布：Live/录制灰调；不编 iox_obs_tap；"
    "run_sil 不起 Foxglove。通信绑定仍保留。": (
        "Production release: Live/record greyed; no iox_obs_tap; "
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
    "有未保存更改 — Ctrl+S 保存（须校验通过）": (
        "Unsaved changes — Ctrl+S to save (validation required)"
    ),
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
    "Verify OK — 作者态完成（见右侧 Lineage）。需要 C++ API 时再 Generate (Ctrl+G)；然后 compile_sil": (
        "Verify OK — authoring done (see Lineage). Generate (Ctrl+G) for C++ APIs if needed; then compile_sil"
    ),
    "Verify OK — 右侧 Lineage。需要 C++ API 时点 Generate (Ctrl+G)": (
        "Verify OK — see Lineage on the right. Generate (Ctrl+G) for C++ APIs."
    ),
    "Verify 退出码 {rc} — 见右侧 Lineage 红项": (
        "Verify exit {rc} — see red items in Lineage"
    ),
    "Generate OK → {out}/include/gf_gen/": "Generate OK → {out}/include/gf_gen/",
    # Memory bounds / SHM (BL-MEM-ROUDI) — keep in sync with ara_cfg_editor
    "SHM 实测：未载入（roudi_mgmt 用近似值，非精确）": (
        "SHM measured: not loaded (roudi_mgmt uses approximate value, not exact)"
    ),
    "SHM 合计 = roudi_payload（mempool 用户数据）+ roudi_mgmt（iceoryx_mgmt 端口表）。"
    "未载入实测时 mgmt 用 SIL 拟合近似值（非精确，以实测为准）。"
    "改 mgmt.* → 保存/compose → 重编 iceoryx → 跑 SIL →「载入实测 SHM」。": (
        "SHM total = roudi_payload (mempool user data) + roudi_mgmt (iceoryx_mgmt port tables). "
        "Without a measurement, mgmt uses a SIL-fitted approx (not exact — prefer measure). "
        "After mgmt.* change: save/compose → rebuild iceoryx → run SIL → Load measured SHM."
    ),
    "弹出文件选择；默认指向 reports/iox_shm_report.json。"
    "报告内 mgmt 与当前 bounds 一致则用实测；不一致则用模型+偏移近似。"
    "打开工程时不自动读盘。": (
        "Opens a file picker; default is reports/iox_shm_report.json. "
        "If report mgmt matches current bounds, use measured; else model+offset approx. "
        "Opening a project never auto-loads from disk."
    ),
    "回到未载入状态；roudi_mgmt 改回模型近似。": (
        "Back to unloaded; roudi_mgmt falls back to the model approx."
    ),
    "SHM 实测：已载入 {path} · mgmt={mgmt} · payload={payload}（与当前 IOX 一致）": (
        "SHM measured: loaded {path} · mgmt={mgmt} · payload={payload} (matches current IOX)"
    ),
    "SHM：已载入 {path}，但 IOX 与报告不一致 → mgmt≈{mgmt}（近似，以重编实测为准）": (
        "SHM: loaded {path}, but IOX differs from report → mgmt≈{mgmt} "
        "(approx; rebuild + re-measure for truth)"
    ),
    "SHM 实测：未载入 · roudi_mgmt≈{mgmt}（近似，缺依据，以实测为准）": (
        "SHM measured: not loaded · roudi_mgmt≈{mgmt} (approx; prefer SIL measure)"
    ),
    "payload+mgmt 实测": "payload+mgmt measured",
    "mgmt 近似 — 非精确，以 SIL 实测为准": (
        "mgmt approx — not exact; prefer SIL measure"
    ),
    "说明：roudi_mgmt 为近似值（非精确）。"
    "改 mgmt.* → compose → 重编 iceoryx（如 compile_sil）→ "
    "跑 SIL → 载入 iox_shm_report.json。"
    "仅改 mempool → compose + 重启 RouDi。": (
        "Note: roudi_mgmt is approximate (not exact). "
        "After mgmt.*: compose → rebuild iceoryx (e.g. compile_sil) → "
        "run SIL → load iox_shm_report.json. "
        "Mempools only: compose + restart RouDi."
    ),
    "说明：roudi_mgmt 来自实测报告（与当前 IOX 配置一致）。"
    "仅改 mempool → compose + 重启 RouDi（无需重编 iceoryx）。": (
        "Note: roudi_mgmt from measured report (matches current IOX). "
        "Mempools only: compose + restart RouDi (no iceoryx rebuild)."
    ),
    "保存": "Save",
    "Verify 失败": "Verify failed",
    "Generate 失败": "Generate failed",
    "导出": "Export",
    "导出失败": "Export failed",
    "退出码 {rc}。请查看右侧 Lineage 红项。": (
        "Exit code {rc}. See red items in the Lineage panel."
    ),
    "已写入：\n{path}": "Wrote:\n{path}",
    # frame_ingest UI labels (zh source → en)
    "帧摄入 frame_ingest": "Frame ingest (frame_ingest)",
    "帧源": "Frame source",
    "感知后端": "Perception backend",
    "none（无帧）": "none (no frame)",
    "none（无帧 SIL）": "none (no-frame SIL)",
    "isp（camera）": "isp (camera)",
    "inject（GMT 回灌）": "inject (GMT replay)",
    "启动 carla_bridge": "Start carla_bridge",
    "dry_run（无 CARLA UE）": "dry_run (no CARLA UE)",
    "demo 强制变道": "demo force lane-change",
    "demo 秒": "demo seconds",
    "帧路径": "Frame path",
    "cmd 路径": "Cmd path",
    "pixel_format": "pixel_format",
    "ego_source": "ego_source",
    "改帧源/ego → Save/Verify → compile_sil → run_sil（冻结进二进制；与 carla_scenarios 无关）": (
        "Edit frame source/ego → Save/Verify → compile_sil → run_sil "
        "(frozen into binaries; unrelated to carla_scenarios)"
    ),
    "图像主路径=GfChannel；replay/file 才用 runtime_ipc 帧路径。改帧源/ego → Save/Verify → compile_sil → run_sil": (
        "Image path=GfChannel; runtime_ipc frame path only for replay/file. "
        "Edit frame source/ego → Save/Verify → compile_sil → run_sil"
    ),
    "改此处 → Save/Verify → compile → run_sil（行为编译冻结，勿手改相机 JSON）": (
        "Edit here → Save/Verify → compile → run_sil "
        "(behavior is compile-frozen; do not hand-edit camera JSON)"
    ),
    # Canvas / port / frame_ingest (wiring_dialogs + wiring_graph)
    "编辑端口 — {process}": "Edit ports — {process}",
    "Out（服务）": "Out (service)",
    "触发": "Trigger",
    "ms / fps": "ms / fps",
    "In（requires）": "In (requires)",
    "Out（provides）— 触发写在发布话题上（多订阅共享一份）": (
        "Out (provides) — trigger is on the publish topic (shared by subscribers)"
    ),
    "＋ Out": "+ Out",
    "＋ In": "+ In",
    "删除选中": "Delete selected",
    "切换方向": "Swap direction",
    "一发多收：多模块 In 同名正常（DDS/SOME/IP 多订阅）。"
    "透传时可两模块 Out 同名；publish_policy 按短名一份，属发布话题而非边。"
    "\n手输短名 → services.semantic.*；In/Out 同模块可同名（gateway）。": (
        "Fan-out: same In name on many modules is OK (DDS/SOME/IP). "
        "Passthrough may Out the same short on two modules; "
        "publish_policy is one entry per short (topic, not edge).\n"
        "Typed shorts → services.semantic.*; same module may In/Out same name (gateway)."
    ),
    "添加端口": "Add ports",
    "勾选要加入的名称（作为 service 短名）：": (
        "Check names to add (as service short names):"
    ),
    "仅粗端口 / 整包对接（推荐，隐藏 Item 碎片）": (
        "Fat ports / whole-package only (hide Item fragments)"
    ),
    "目标模块": "Target module",
    "Out（provides）": "Out (provides)",
    "In（requires）": "In (requires)",
    "方向": "Direction",
    "frame_ingest · 视频契约": "frame_ingest · video contract",
    "每路 = 一个 Out（gf.channel.{id}）→ 拖到消费方。\n"
    "SOP 默认帧源=isp；SIL 用 GF_FRAME_SOURCE=carla|replay|colorbar|none（run_sil）。\n"
    "无外参/内参/ego；buffers=AB 固定 2。": (
        "Each lane = one Out (gf.channel.{id}) → drag to consumer.\n"
        "SOP default source=isp; SIL uses GF_FRAME_SOURCE=carla|replay|colorbar|none (run_sil).\n"
        "No extrinsics/intrinsics/ego; buffers=AB fixed at 2."
    ),
    "相机路（每路一条 GfChannel Out）": "Camera lanes (one GfChannel Out each)",
    "相机物理帧率。0=未填。Out expect_fps 须 ≤ 此值。": (
        "Camera physical fps. 0=unset. Out expect_fps must be ≤ this."
    ),
    "槽名": "Slot",
    "宽": "Width",
    "高": "Height",
    "添加一路": "Add lane",
    "删除当前路": "Delete current lane",
    "通道发布策略": "Channel publish policy",
    "添加通道": "Add channel",
    "删除选中通道": "Delete selected channel",
    "请先选中一行通道。": "Select a channel row first.",
    "通道名必填。": "Channel name is required.",
    "通道名必须唯一。": "Channel names must be unique.",
    "通道发布策略（publish_policy.channels）": (
        "Channel publish policy (publish_policy.channels)"
    ),
    "通道": "Channel",
    "至少保留一路。": "Keep at least one lane.",
    "每路 id 必填且唯一。": "Each lane id is required and unique.",
    "添加模块": "Add module",
    "ap_linux — AP Linux（默认）": "ap_linux — AP Linux (default)",
    "host — 桌面 / 仿真 PC": "host — desktop / sim PC",
    "compute_domain：进程运行位置。\n"
    "写入 wiring.yaml → Verify → gf.sor.json deployments[]。": (
        "compute_domain: where the process runs.\n"
        "Written to wiring.yaml → Verify → gf.sor.json deployments[]."
    ),
    "compute_domain 是 wiring 字段（进 SOR）。\n"
    "外部 MCU：空白画布右键 → 添加外部 MCU。\n"
    "视频契约：空白处右键 → 添加 frame_ingest（不进 deployments）。": (
        "compute_domain is a wiring field (into SOR).\n"
        "External MCU: blank canvas → right-click → Add external MCU.\n"
        "Video contract: blank → right-click → Add frame_ingest (not a deployment)."
    ),
    "进程名": "Process name",
    "计算域": "Compute domain",
    "搜索信号（模糊匹配名 / 进程）…": "Search signals (fuzzy name / process)…",
    "Out=绿 · In=橙 · !=未连\n"
    "线色=源模块（同卡扇出同色）· 蓝点划线=GfChannel\n"
    "拖拽连线 · Ctrl+拖改边/同边调序 · Ctrl+Z/Y 撤销": (
        "Out=green · In=orange · !=unwired\n"
        "Edge color=source module (fan-out same color) · blue dots=GfChannel\n"
        "Drag to wire · Ctrl+drag move/reorder · Ctrl+Z/Y undo"
    ),
    "尚无 lineage。菜单：文件 → Verify（Ctrl+R）": (
        "No lineage yet. Menu: File → Verify (Ctrl+R)"
    ),
    "连线": "Wires",
    "折叠 / 展开右侧面板（连线 + Lineage）": (
        "Collapse / expand right panel (wires + Lineage)"
    ),
    "添加模块…": "Add module…",
    "添加 frame_ingest…": "Add frame_ingest…",
    "添加外部 MCU…": "Add external MCU…",
    "导入 hpp/h…": "Import hpp/h…",
    "从头文件添加端口": "Add ports from header",
    "勾选要加入的类型（作为 service 短名）：": (
        "Check types to add (as service short names):"
    ),
    "从 FIDL 添加端口": "Add ports from FIDL",
    "勾选要加入的名称（struct / broadcast / method / interface）：": (
        "Check names to add (struct / broadcast / method / interface):"
    ),
    "语义话题：画布双击模块 → Out 表改触发。"
    "通道话题：双击 frame_ingest 改触发。"
    "一发多收共享同一话题策略；Signals 页不再编辑发布表。": (
        "Semantic topics: canvas double-click → Out table. "
        "Channel topics: double-click frame_ingest. "
        "Fan-out shares one topic policy; Signals page no longer edits the table."
    ),
    "周期": "Period",
    "变化时": "On change",
    "编辑信号": "Edit signal",
    "编辑信号名…": "Edit signal name…",
    "重置连线路径": "Reset wire path",
    "删除信号线": "Delete signal wire",
    "删除 GfChannel 边": "Delete GfChannel edge",
    "补上连线（写入 dataflow）": "Add wire (write dataflow)",
    "忽略此建议（不再显示）": "Ignore suggestion (hide)",
    "移除目标 In 端口（不再需要该输入）": "Remove target In port",
    "补线": "Wire",
    "该 dataflow 已存在": "This dataflow already exists",
    "该 GfChannel 边已存在": "This GfChannel edge already exists",
    "编辑 frame_ingest…": "Edit frame_ingest…",
    "删除 frame_ingest": "Delete frame_ingest",
    "编辑端口…": "Edit ports…",
    "从此模块导入 hpp…": "Import hpp from this module…",
    "删除模块": "Delete module",
    "已存在：{name}": "Already exists: {name}",
    "frame_ingest": "frame_ingest",
    "已存在视频契约节点。请双击 {name} 编辑。": (
        "Video contract node already exists. Double-click {name} to edit."
    ),
    "外部 MCU": "External MCU",
    "当前拓扑为「仅 AP（无 MCU）」，不显示 MCU 节点。\n"
    "请先在 SKU 将拓扑改为「AP + MCU CP」。\n"
    "对外控制信号（如 VehicleBus / Trajectory）可直接挂在 gateway 等模块端口上。": (
        "Topology is AP-only (no MCU); MCU node is hidden.\n"
        "Switch SKU topology to「AP + MCU CP」first.\n"
        "Outbound control (e.g. VehicleBus / Trajectory) can hang on gateway ports."
    ),
    "当前拓扑为仅 AP。请先改为「AP + MCU CP」；"
    "对外控制信号可挂在 gateway 端口上。": (
        "Topology is AP-only. Switch to「AP + MCU CP」first; "
        "outbound control can hang on gateway ports."
    ),
    "外部节点": "External node",
    "external MCU": "external MCU",
    "已添加 {name}": "Added {name}",
    "删除视频契约节点？\n"
    "将清空 camera_slots / channel_flows，并把 active_source 设为 none。": (
        "Delete video contract node?\n"
        "Clears camera_slots / channel_flows and sets active_source to none."
    ),
    "删除 {name} 及其相关 dataflows？": "Delete {name} and related dataflows?",
    "画布上无端口可编辑（边界节点仅连 gateway）。": (
        "No editable ports on canvas (boundary links to gateway only)."
    ),
    "选择头文件": "Select header",
    "选择 FIDL": "Select FIDL",
    "解析失败": "Parse failed",
    "导入": "Import",
    "未解析到 struct，请检查头文件格式": (
        "No struct parsed; check header format"
    ),
    "未解析到 interface/struct/method/broadcast，请检查 .fidl 格式": (
        "No interface/struct/method/broadcast parsed; check .fidl format"
    ),
    "请先添加至少一个模块": "Add at least one module first",
    "导入完成": "Import done",
    "已关联 {rel}\n向 {process} 添加了 {n} 个{direction} 端口。\n"
    "可双击模块继续调整，再从 Out 拖到 In 连线。": (
        "Linked {rel}\nAdded {n} {direction} ports to {process}.\n"
        "Double-click the module to adjust, then drag Out→In to wire."
    ),
    "拖拽连线 · Ctrl+拖：改边或同边调序 · 右键选边": (
        "Drag to wire · Ctrl+drag: move/reorder · right-click for side"
    ),
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


def clear_stale_pending_open() -> None:
    """Drop leftover session/pending_open from older process-restart language switch."""
    try:
        from PySide6.QtCore import QSettings

        QSettings(_ORG, _APP).remove("session/pending_open")
    except Exception:
        pass


def t(zh: str) -> str:
    if _LANG == "en":
        return _EN.get(zh, zh)
    return zh
