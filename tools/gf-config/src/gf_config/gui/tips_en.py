"""English translations for tips.py Chinese source keys (merged into i18n._EN)."""

from __future__ import annotations

TIP_EN: dict[str, str] = {
    # modules
    "基础类型库（Result / ErrorCode）。CMake 强制编入；"
    "几乎所有 middleware 都依赖它，不要试图裁掉。": (
        "Base types (Result / ErrorCode). Forced by CMake; "
        "almost all middleware depends on it — do not try to drop it."
    ),
    "通信底座（Proxy/Skeleton、ServicePath）。CMake 强制编入；"
    "页 1 画布的 dataflow 最终走这里。具体传输在 bindings 里选。": (
        "Communication base (Proxy/Skeleton, ServicePath). Forced by CMake; "
        "tab-1 dataflows end here. Pick transports under bindings."
    ),
    "OS 抽象（时钟、线程、进程 Spawn）。CMake 强制编入；"
    "EM 拉起进程、PHM 计时都依赖它。": (
        "OS abstraction (clock, threads, process Spawn). Forced by CMake; "
        "EM process launch and PHM timing depend on it."
    ),
    "日志 lite：默认级别与 per-context 过滤写在 log.yaml；"
    "页 1 的 live/record 是观测通道，和这里的级别是两件事。": (
        "Log lite: default level and per-context filters live in log.yaml; "
        "tab-1 live/record are observability channels — a separate concern."
    ),
    "执行管理：进程↔功能组拓扑（exec.yaml）+ OS EM 启动表（em_launch.yaml）。"
    "勾选后解锁「执行/FG」与「EM 启动表」。": (
        "Execution mgmt: process↔FG topology (exec.yaml) + OS EM table "
        "(em_launch.yaml). Unlocks Exec/FG and EM launch pages."
    ),
    "健康监督：按 Alive/Deadline 检查进程是否还在喂狗；"
    "失败可只记日志、通知 SM，或要求 EM 重启。解锁「健康 PHM」。": (
        "Health supervision: Alive/Deadline watchdogs; on fault you can log, "
        "notify SM, or ask EM to restart. Unlocks Health PHM."
    ),
    "状态管理：功能组 Off / Running / Updating。"
    "与 exec 共用「执行/FG」页；OTA 时会切到 Updating。": (
        "State management: FG Off / Running / Updating. Shares the Exec/FG "
        "page with exec; OTA switches to Updating."
    ),
    "事件收集（DEM-lite）：防抖/FDC/老化 + DTC；勾选后自动带上 per 做跨重启持久化。"
    "解锁「事件收集」；有 phm/diag 时也会出现入口。": (
        "Event collector (DEM-lite): debounce/FDC/aging + DTC; auto-checks per "
        "for cross-reboot persistency. Unlocks Collector; also with phm/diag."
    ),
    "OTA 编排：DoIP/GMT 触发后切 Updating → 跑包状态机 → 记结果；"
    "真板 RAUC 刷写仍是 stub。解锁「OTA ucm」。": (
        "OTA orchestration: after DoIP/GMT, switch Updating → package SM → "
        "record result; real RAUC flash is still stub. Unlocks OTA ucm."
    ),
    "诊断：ISO 14229 UDS（含 NRC）为基础，可选 ISO 13400 DoIP 作以太网传输；"
    "无 DoIP 时 CAN PDU 交 MCU。解锁「诊断」。": (
        "Diagnostics: ISO 14229 UDS (+NRC) base; optional ISO 13400 DoIP "
        "for Ethernet; without DoIP, CAN PDUs go to MCU. Unlocks Diag."
    ),
    "持久化 lite（双槽文件 KV，无 SQLite）。"
    "collector/ucm 需要跨重启 DTC 或版本时会自动勾选。": (
        "Persistency lite (dual-slot file KV, no SQLite). "
        "Auto-checked when collector/ucm need cross-reboot DTC or version."
    ),
    "时间同步 lite：platform/tsync.yaml；SIL 用 osal mock，"
    "板上配 linuxptp/ptp4l，本模块用 pmc 读状态。": (
        "Time-sync lite: platform/tsync.yaml; SIL uses osal mock; "
        "on-target use linuxptp/ptp4l, this module reads status via pmc."
    ),
    "时序/trace 导出到 VCD / GMT，偏调试路径；"
    "production-release 剖面下通常关掉观测相关能力。": (
        "Timing/trace export to VCD / GMT (debug-oriented); "
        "usually off under production-release."
    ),
    # exec / SM
    "功能组名字，供 SM StateClient 注册；进程通过 function_group 挂到这个组。": (
        "Function-group name for SM StateClient; processes attach via function_group."
    ),
    "开机后该功能组进入的状态。\n"
    "• Off：关闭，不应跑业务\n"
    "• Running：正常业务，进程可提供服务\n"
    "• Updating：更新/OTA 窗；PHM 可暂停监督，失败可回滚\n"
    "非法转移：Off→Updating。": (
        "State entered after boot.\n"
        "• Off: shut down — no business work\n"
        "• Running: normal ops — processes may serve\n"
        "• Updating: OTA window; PHM may pause; failure can roll back\n"
        "Illegal: Off→Updating."
    ),
    "关闭态：组内进程不应处于业务运行；从 Off 不能直接进 Updating。": (
        "Off: processes should not run business; Off cannot go directly to Updating."
    ),
    "正常运行态：组内进程可提供/消费服务；SIL 默认初始多为 Running。": (
        "Running: processes may provide/consume services; SIL usually starts here."
    ),
    "更新窗：OTA/刷写期间使用；会配合 PHM pause，失败时可 Rollback。": (
        "Updating: used during OTA/flash; pairs with PHM pause; failure may Rollback."
    ),
    "要纳入 exec 拓扑的进程（来自页 1 wiring，不含 external.*）。": (
        "Process in the exec topology (from tab-1 wiring; not external.*)."
    ),
    "该进程隶属的功能组：随 FG 的 Off/Running/Updating 一起被 SM 管理。": (
        "Owning FG: managed with that group's Off/Running/Updating by SM."
    ),
    "启动依赖：EM 会先拉起勾选的进程，成功后再 Spawn 本进程。"
    "用来保证例如 gateway 先于感知/规划就绪。": (
        "Start deps: EM launches checked processes first, then Spawns this one "
        "(e.g. gateway before perception/planning)."
    ),
    "ExecutionClient：仅 SOA 应用可选。进程是否主动向 EM 汇报 Running/Terminating。\n"
    "• true：期望进程内 ExecutionClient 握手（规范路径）\n"
    "• false：EM 只按 Spawn/退出码管理，不期待客户端状态上报\n"
    "host.* platform daemons 固定 n/a（不可选 true）。": (
        "ExecutionClient: SOA apps only. Whether the process reports Running/Terminating to EM.\n"
        "• true: expect in-process ExecutionClient handshake (normative)\n"
        "• false: EM manages by Spawn/exit code only — no client state reports\n"
        "host.* platform daemons are fixed n/a (true is not selectable)."
    ),
    "platform daemon（host.*）：外部二进制，无 ExecutionClient。"
    "EM 只按 Spawn/退出码管理；Verify 会拒绝 execution_client=true。": (
        "platform daemon (host.*): external binary — no ExecutionClient. "
        "EM manages by Spawn/exit code; Verify rejects execution_client=true."
    ),
    "n/a · daemon": "n/a · daemon",
    "进程会通过 ExecutionClient 向 EM 汇报状态（推荐，贴近 ara::exec）。": (
        "Process reports state via ExecutionClient (recommended; closer to ara::exec)."
    ),
    "不要求客户端上报；EM 仅根据进程存活/退出码管理（适合极简 stub）。": (
        "No client reports; EM uses liveness/exit code only (minimal stubs)."
    ),
    # EM
    "要由 OS EM（gf_em_daemon）Spawn 的进程，须与 exec/wiring 中的名字一致。": (
        "Process Spawned by OS EM (gf_em_daemon); name must match exec/wiring."
    ),
    "可执行文件路径，相对 $GF_BUILD_DIR（compose/编译产物目录）。"
    "例如 apps/planning/driving/gf_planning_driving。": (
        "Executable path relative to $GF_BUILD_DIR (compose/build output), "
        "e.g. apps/planning/driving/gf_planning_driving."
    ),
    "传给进程的 POSIX argv（不是 AUTOSAR 字段，但是 Spawn 需要）。\n"
    "本工程 gateway：第一个参数=最多收几条 Trajectory 后退出；"
    "0=一直跑；SIL 冒烟常用 15。其它应用目前可忽略参数内容。": (
        "POSIX argv for Spawn (not an AUTOSAR field, but Spawn needs it).\n"
        "This project's gateway: arg0 = max Trajectories then exit; "
        "0 = run forever; SIL smoke often uses 15. Other apps can ignore content."
    ),
    "当 PHM on_failure=restart 且进程以 exit 75 请求重启时，"
    "EM 最多 relaunch 的次数；超过则进入 terminal_exit，不再拉起。": (
        "When PHM on_failure=restart and the process exits 75, EM relaunches "
        "at most this many times; then terminal_exit — no more relaunch."
    ),
    # PHM
    "监督实体名，仅作配置/日志标识（如 gateway_alive）。": (
        "Supervision entity name — config/log id only (e.g. gateway_alive)."
    ),
    "被监督的进程：须与 wiring 中的 AP 进程一致；该进程应周期性 ReportAlive。": (
        "Supervised process: must match an AP process in wiring; it should ReportAlive periodically."
    ),
    "期望的 Alive 喂狗周期（ms）。进程应按大约这个间隔调用 ReportAlive；"
    "过慢会触发 AliveMissed。": (
        "Expected Alive period (ms). Process should ReportAlive roughly this often; "
        "too slow → AliveMissed."
    ),
    "Alive 超时（ms）：超过该时间未喂狗则判健康故障。"
    "SIL 路径里也用作 SupervisedEntity 的 deadline 参数。": (
        "Alive timeout (ms): no kick within this → health fault. "
        "SIL also uses it as SupervisedEntity deadline."
    ),
    "独立 Deadline 监督（ms）。0=关闭（只用 Alive）。"
    "非 0 时表示关键操作不得超过这么久，超时 → DeadlineMissed。": (
        "Separate Deadline supervision (ms). 0=off (Alive only). "
        "Non-zero: critical work must finish within this → else DeadlineMissed."
    ),
    "健康故障后的处置：\n"
    "• log：只记日志/Collector\n"
    "• notify_sm：通知 SM（可进 Updating）\n"
    "• restart：要求重启——托管进程 exit 75 由 EM relaunch": (
        "Action after a health fault:\n"
        "• log: log / Collector only\n"
        "• notify_sm: notify SM (may enter Updating)\n"
        "• restart: request restart — managed process exit 75 → EM relaunch"
    ),
    "仅记录事件（日志 + Collector），不改 SM 状态、不重启进程。": (
        "Record only (log + Collector); no SM change, no process restart."
    ),
    "上报 Collector，并 NotifyHealthFault；可选让功能组进入 Updating。": (
        "Report to Collector and NotifyHealthFault; optionally move FG to Updating."
    ),
    "请求恢复：GF_EM_MANAGED 时进程 exit 75，由 gf_em_daemon 按 max_restarts relaunch；"
    "未托管则走进程内 soft relaunch。": (
        "Recovery: if GF_EM_MANAGED, process exits 75 and gf_em_daemon relaunches "
        "up to max_restarts; else in-process soft relaunch."
    ),
    # diag
    "启用 ISO 14229 UDS（含否定响应 NRC）。这是诊断父能力；"
    "DoIP 只是它的一种传输，不能单独存在。": (
        "Enable ISO 14229 UDS (+NRC). Parent diagnostic capability; "
        "DoIP is only a transport and cannot stand alone."
    ),
    "启用 ISO 13400 DoIP（以太网诊断传输）。必须同时开 14229；"
    "关掉 DoIP 时 AP 不跑 ISO-TP，CAN 侧 PDU 交给 MCU。": (
        "Enable ISO 13400 DoIP (Ethernet diagnostic transport). Requires 14229; "
        "without DoIP, AP skips ISO-TP and CAN PDUs go to MCU."
    ),
    "UDS 0x27/0x29 安全访问算法插件（.so/.dll）。"
    "留空则用内置 SIL stub，仅供仿真，不能当量产密钥。": (
        "UDS 0x27/0x29 security-access plugin (.so/.dll). "
        "Empty = built-in SIL stub for simulation — not production keys."
    ),
    "从磁盘选择安全访问插件动态库。": "Browse for the security-access plugin library.",
    "DoIP 服务开关，与上面的 ISO 13400 勾选同步。": (
        "DoIP service switch; stays in sync with the ISO 13400 checkbox above."
    ),
    "本 ECU 的 DoIP 逻辑地址（十六进制，如 0x0E00）。"
    "测试仪用该地址路由诊断请求。": (
        "This ECU's DoIP logical address (hex, e.g. 0x0E00). "
        "Testers route diagnostic requests to it."
    ),
    "期望的测试仪逻辑地址（如 0x0E80）。"
    "RoutingActivation 时与诊断仪对齐。": (
        "Expected tester logical address (e.g. 0x0E80). "
        "Align with the tool at RoutingActivation."
    ),
    "DoIP TCP 监听端口（默认 13400；GMT OTA / run_sil 须一致）。": (
        "DoIP TCP listen port (default 13400; must match GMT OTA / run_sil)."
    ),
    "ISO 14229 S3Server（ms）：非默认会话下若超过此时长无测试仪活动，"
    "会话回落 Default 并清除安全解锁。须大于诊断仪 0x3E 周期。": (
        "ISO 14229 S3Server (ms): in a non-default session, idle longer than this "
        "falls back to Default and clears security unlock. Must be > tester 0x3E period."
    ),
    "测试仪 0x3E TesterPresent 发送周期（ms）。"
    "须小于 S3Server（建议 ≤ S3/2），与其它诊断仪维持时间对齐。": (
        "Tester 0x3E TesterPresent period (ms). Must be < S3Server "
        "(recommend ≤ S3/2); align with other diagnostic tools."
    ),
    "P2Server（ms）：服务端最大响应时间（文档/对齐用；SIL 暂不强制掐断）。": (
        "P2Server (ms): max server response time (docs/alignment; SIL does not hard-cut)."
    ),
    "P2*Server（ms）：增强/刷写会话下的扩展响应窗口；GMT 用它作收包超时。": (
        "P2*Server (ms): extended response window in programming sessions; "
        "GMT uses it as receive timeout."
    ),
    "0x27 密钥错误后的强制等待（ms）。期间再请求返回 NRC 0x37 "
    "RequiredTimeDelayNotExpired，与其它诊断仪对齐。": (
        "Forced wait (ms) after invalid 0x27 key. Further requests return NRC 0x37 "
        "RequiredTimeDelayNotExpired until the delay elapses."
    ),
    "选择 OTA 下载 SID（写入 diag.yaml → ota_transfer.mode；GMT 只读跟从）：\n"
    "• 0x38 RequestFileTransfer：0x38→0x36→0x37（DoIP/以太网推荐）\n"
    "• 0x34 RequestDownload：0x34→0x36→0x37（经典内存下载）\n"
    "• 0x31 RoutineControl (SIL)：仅 F100 捷径，无字节管道": (
        "Select OTA download SID (diag.yaml → ota_transfer.mode; GMT follows read-only):\n"
        "• 0x38 RequestFileTransfer: 0x38→0x36→0x37 (DoIP/Ethernet default)\n"
        "• 0x34 RequestDownload: 0x34→0x36→0x37 (classic memory download)\n"
        "• 0x31 RoutineControl (SIL): F100 shortcut only, no byte pipe"
    ),
    "0x38 RequestFileTransfer → 0x36 TransferData → 0x37 RequestTransferExit。"
    "DoIP / 以太网默认路径；yaml 键 request_file_transfer。": (
        "0x38 RequestFileTransfer → 0x36 TransferData → 0x37 RequestTransferExit. "
        "Default DoIP/Ethernet path; yaml key request_file_transfer."
    ),
    "0x34 RequestDownload → 0x36 → 0x37。经典按内存地址下载；"
    "yaml 键 request_download。": (
        "0x34 RequestDownload → 0x36 → 0x37. Classic memory-address download; "
        "yaml key request_download."
    ),
    "0x31 RoutineControl（RID F100）SIL 捷径：直接点 UCM，不传文件块。"
    "仅仿真；yaml 键 routine_sil。": (
        "0x31 RoutineControl (RID F100) SIL shortcut: poke UCM with no file blocks. "
        "Simulation only; yaml key routine_sil."
    ),
    "传输前是否先发 DiagnosticSessionControl（0x10 02 Programming）。"
    "量产刷写通常必开；关掉仅便于 SIL 捷径调试。": (
        "Whether to send DiagnosticSessionControl (0x10 02 Programming) first. "
        "Usually required for production flash; off only for SIL shortcut debug."
    ),
    "传输前是否走 SecurityAccess（0x27 seed/key）。"
    "密钥算法在 GMT→OTA 记本地插件路径，或板端 GF_DIAG_SEC_PLUGIN；本页不存路径。": (
        "Whether to run SecurityAccess (0x27 seed/key) before transfer. "
        "Plugin path is remembered in GMT→OTA or board GF_DIAG_SEC_PLUGIN; "
        "this page does not store the path."
    ),
    "0x36 TransferData 单块最大字节数（maxNumberOfBlockLength）。"
    "过大占 RAM，过小拖慢；须与服务端协商值一致（SIL 默认 1024）。": (
        "Max bytes per 0x36 TransferData block (maxNumberOfBlockLength). "
        "Too large uses RAM; too small is slow; must match server negotiation "
        "(SIL default 1024)."
    ),
    "数据标识符 DID（UDS 读/写用的 id，常用十六进制）。": (
        "Data Identifier (DID) for UDS read/write — usually hex."
    ),
    "给人看的 DID 名称，便于在工具里辨认。": "Human-readable DID name for the tool UI.",
    "该 DID 允许的访问：\n"
    "• read：只读\n"
    "• write：只写\n"
    "• read_write：可读可写": (
        "Allowed DID access:\n"
        "• read: read-only\n"
        "• write: write-only\n"
        "• read_write: read and write"
    ),
    "诊断仪可以读，不能写。": "Tester may read, not write.",
    "诊断仪可以写，不能读（少见，按标定策略使用）。": (
        "Tester may write, not read (uncommon; use per calibration policy)."
    ),
    "可读可写。": "Read and write.",
    "该 DID 载荷字节长度；生成/校验侧用来约束数据大小。": (
        "DID payload size in bytes; used by generate/verify to constrain data size."
    ),
    # log
    "进程默认日志级别。比它更啰嗦的级别会被丢掉；"
    "单个 context 可在下表单独加严或放宽。": (
        "Default process log level. More verbose levels are dropped; "
        "a context below can tighten or loosen this."
    ),
    "日志上下文名（代码里 Logger 的 context id），用于分类过滤。": (
        "Log context id (Logger context in code) for category filtering."
    ),
    "该 context 的级别覆盖默认值；未列出的 context 仍用 default_level。": (
        "Level override for this context; unlisted contexts keep default_level."
    ),
    "只保留致命错误。": "Fatal errors only.",
    "错误及以上。": "Error and above.",
    "警告及以上。": "Warning and above.",
    "常规信息（常用默认）。": "Informational (common default).",
    "调试细节，日志量明显增加。": "Debug detail — much more volume.",
    "最细，仅短时排障使用。": "Most verbose — short troubleshooting only.",
    # ucm
    "打开后才跑 OtaOrchestrator：GMT/DoIP 下发更新时会切功能组、跑包状态机并记结果。"
    "关闭则忽略 OTA 编排请求。": (
        "When on, OtaOrchestrator runs: GMT/DoIP updates switch FG, run package SM, "
        "record results. Off ignores OTA orchestration requests."
    ),
    "包/清单 URI，SIL 下交给 PackageManager::Initialize 识别包源。"
    "例如 sil://artifact；不是去编辑刷写镜像本身。": (
        "Package/manifest URI for PackageManager::Initialize under SIL "
        "(e.g. sil://artifact) — not editing the flash image itself."
    ),
    "OTA 期间要切到 Updating 的功能组（通常 MachineFG）。"
    "须与 exec 里定义的 FG id 一致。": (
        "FG switched to Updating during OTA (usually MachineFG). "
        "Must match an FG id defined in exec."
    ),
    "编排失败时是否走 Rollback。"
    "关掉则失败只记 Collector 事件（如 ota_failed），不自动回滚包状态。": (
        "Whether orchestration failure runs Rollback. "
        "Off only records Collector events (e.g. ota_failed) — no auto package rollback."
    ),
    # collector
    "事件往哪送：\n"
    "• local_store：本机 DEM-lite 落盘\n"
    "• cp_dem：转到 MCU CP DEM（有跨域时）\n"
    "• both：两边都要": (
        "Where events go:\n"
        "• local_store: on-host DEM-lite\n"
        "• cp_dem: MCU Classic DEM (when cross-domain)\n"
        "• both: both"
    ),
    "只写本地环形缓冲/落盘，适合纯 AP SIL。": (
        "Local ring buffer / disk only — good for AP-only SIL."
    ),
    "转发到 MCU Classic DEM 路径（需要 CP/gateway）。": (
        "Forward to MCU Classic DEM (needs CP/gateway)."
    ),
    "本地存一份，同时尝试转 MCU。": "Store locally and also try MCU forward.",
    "勾选后，该来源会写入 collector.yaml 的 sources。"
    "当前运行时会 ReportEvent 的有：phm（健康）、process（进程退出）、"
    "com（通信超时等）、ucm（OTA）。不是只能这三个；后续还可扩展。"
    "运行时按 sources 白名单过滤：未勾选的来源在 ReportEvent 时丢弃"
    "（列表为空则不过滤，兼容旧配置）。": (
        "When checked, this source is listed in collector.yaml sources. "
        "Today ReportEvent producers are: phm, process, com, ucm — not only "
        "three; more can be added later. Runtime allowlists by sources: "
        "unchecked sources are dropped in ReportEvent "
        "(empty list = no filter, legacy-compatible)."
    ),
    "是否启用本地 DEM-lite 存储；关则只转发、不在本机留历史。": (
        "Enable local DEM-lite storage; off = forward only, no local history."
    ),
    "本地最多保留多少条事件；超出按策略丢弃最旧条目，防止磁盘涨满。": (
        "Max local events kept; older ones drop to avoid filling disk."
    ),
    # SKU
    "变体名，区分同一产品下的配置分支（写入 req.variant，参与 compose 标识）。": (
        "Variant name for product branches (req.variant; used in compose identity)."
    ),
    "产品名（如 AFC），用于文档/报告与 compose 元数据。": (
        "Product name (e.g. AFC) for docs/reports and compose metadata."
    ),
    "部署拓扑：\n"
    "• ap_only：只有 AP Linux，无 MCU CP\n"
    "• ap_mcu_cp：AP + MCU CP gateway，可走跨域 IPC / cp_dem": (
        "Deployment topology:\n"
        "• ap_only: AP Linux only, no MCU CP\n"
        "• ap_mcu_cp: AP + MCU CP gateway — cross-domain IPC / cp_dem"
    ),
    "单域 AP：无 Classic DEM 转发、无 MCU gateway 进程。": (
        "AP-only: no Classic DEM forward, no MCU gateway process."
    ),
    "异构：存在 MCU CP；bindings 可开 cross_domain_ipc，collector 可 forward=cp_dem。": (
        "Heterogeneous: MCU CP present; bindings may enable cross_domain_ipc; "
        "collector may forward=cp_dem."
    ),
    "工程剖面：\n"
    "• vehicle-debug：允许 live_tap / record / Foxglove\n"
    "• production-release：强制关掉观测注入，不编 iox_obs_tap": (
        "Engineering profile:\n"
        "• vehicle-debug: live_tap / record / Foxglove allowed\n"
        "• production-release: forces obs off; no iox_obs_tap"
    ),
    "调试剖面：可开 live/record/trace，便于 GMT/Foxglove。": (
        "Debug profile: live/record/trace allowed for GMT/Foxglove."
    ),
    "发布剖面：灰掉观测开关，Verify/编译不带 tap，run_sil 不起 Foxglove。": (
        "Release profile: obs controls greyed; Verify/build without tap; "
        "run_sil skips Foxglove."
    ),
    "Live tap：把画布上的服务镜像到观测工具。"
    "开启后 compose 会加入 debug_bridge/iox_obs_tap，run_sil 可接 Foxglove WebSocket。": (
        "Live tap: mirror canvas services to observability tools. "
        "On → compose adds debug_bridge/iox_obs_tap; run_sil can attach Foxglove WS."
    ),
    "帧摄入（frame_ingest）：CARLA / 文件 / 未来 ISP·摄像头的 RGB 入口。"
    "与 live_tap 白名单不同——这里是行为轨迹，经 compose 冻结为 "
    "frame_ingest_config.hpp（apps + run_sil）。改完请 Verify + compile_sil，再 run_sil。": (
        "Frame ingest: RGB ingress for CARLA / file / future ISP·camera. "
        "Unlike live_tap allowlists, this is behavior — frozen as "
        "frame_ingest_config.hpp (apps + run_sil). "
        "After edits: Verify + compile_sil, then run_sil."
    ),
    "帧从哪来：none=无帧 SIL stub；synth=进程内彩条；"
    "file/carla_file=读 GF 路径上的 raw RGB+json（同一协议）。": (
        "Where pixels come from: none=no-frame SIL stub; synth=in-process bars; "
        "file/carla_file=raw RGB+json at the configured path (same protocol)."
    ),
    "像素怎么用：stub=帧驱动计数；onnx=检测路径（需 -DGF_WITH_ONNX）。": (
        "How pixels are used: stub=frame-driven counts; onnx=detector path "
        "(needs -DGF_WITH_ONNX)."
    ),
    "run_sil 是否后台启动 tools/carla_bridge（写帧协议 + 执行变道 cmd）。": (
        "Whether run_sil starts tools/carla_bridge (write frame protocol + apply "
        "lane-change cmd)."
    ),
    "dry_run=无 CARLA UE 时写合成帧（协议自检）。"
    "真车联调请取消勾选并启动 UE。": (
        "dry_run=synth frames without CARLA UE (protocol self-check). "
        "For real CARLA, uncheck and start UE."
    ),
    "gateway 定时强制写一次 lane_change（演示变道；不经规划决策）。": (
        "Gateway forces a lane_change once on a timer (demo; not planner-decided)."
    ),
    "demo 变道触发时刻（秒，自 gateway 启动起算）。": (
        "Seconds after gateway start when demo lane-change fires."
    ),
    "raw RGB 路径（旁路 .json sidecar）；bridge 写、fcm 读。": (
        "Raw RGB path (+ .json sidecar); bridge writes, fcm reads."
    ),
    "gateway→bridge 变道 cmd JSON 路径。": (
        "Path for gateway→bridge lane-change cmd JSON."
    ),
    "live 服务范围：\n"
    "• wiring_all：天花板=页 1 全部 dataflow（推荐）\n"
    "• explicit：只用下面白名单，空名单会导致 Verify 失败": (
        "Live service scope:\n"
        "• wiring_all: ceiling = all tab-1 dataflows (recommended)\n"
        "• explicit: allowlist only — empty → Verify fails"
    ),
    "自动跟随画布连线；GMT 仍可再过滤。": (
        "Follow canvas edges automatically; GMT may filter further."
    ),
    "只镜像白名单服务；必须至少选一项，否则 Verify 失败。": (
        "Mirror allowlisted services only; at least one required or Verify fails."
    ),
    "explicit 模式下要镜像的服务；从 wiring 多选，避免手打拼写错误。": (
        "Services to mirror in explicit mode; multi-select from wiring — avoid typos."
    ),
    "录制策略：控制 measure/record 采多少。\n"
    "off=不录；minimal/sampled/full 依次更全、更重。": (
        "Record policy: how much measure/record captures.\n"
        "off=none; minimal/sampled/full = richer and heavier."
    ),
    "最小集录制，负载低。": "Minimal recording — low load.",
    "抽样录制，平衡体积与可回放性。": "Sampled recording — balance size vs replay.",
    "尽量全量，磁盘与带宽占用高。": "Near-full recording — heavy disk/bandwidth.",
    "关闭录制；下方服务白名单也会灰掉。": (
        "Recording off; service allowlist below is greyed."
    ),
    "参与 record 的服务白名单；从 wiring 多选。": (
        "Record service allowlist; multi-select from wiring."
    ),
    "是否导出时序 trace（供 GMT/VCD）。on=导出；off=不导出。": (
        "Export timing trace for GMT/VCD. on=export; off=no."
    ),
    "打开 trace 导出。": "Enable trace export.",
    "关闭 trace 导出。": "Disable trace export.",
    "本机/进程间零拷贝通信（iceoryx）。SIL 双进程联调几乎总是要开。": (
        "Local/zero-copy IPC (iceoryx). Almost always on for SIL multi-process."
    ),
    "SOME/IP：车载以太网服务发现与序列化（对标量产 SOME/IP 栈时再开）。": (
        "SOME/IP: automotive Ethernet discovery/serialization "
        "(enable when targeting a production SOME/IP stack)."
    ),
    "DDS 绑定（可选中间件路径）；未接真 DDS 前多为占位能力开关。": (
        "DDS binding (optional middleware); mostly a capability flag until real DDS."
    ),
    "跨域 IPC：AP↔MCU CP gateway。topology=ap_mcu_cp 时才有意义。": (
        "Cross-domain IPC: AP↔MCU CP gateway. Meaningful when topology=ap_mcu_cp."
    ),
    "给人看的验收说明（本 SKU 要证明什么），写入 acceptance.description。": (
        "Human acceptance note (what this SKU must prove) → acceptance.description."
    ),
    "Verify 时是否强制 signal lineage 门禁全部通过；"
    "打开后 lineage 失败则 Verify 失败。": (
        "Whether Verify requires all signal-lineage gates to pass; "
        "on → lineage failure fails Verify."
    ),
    "验收必须出现的服务（required_services）；"
    "compose/lineage 会检查画布是否覆盖这些服务。": (
        "Services that must appear (required_services); "
        "compose/lineage checks the canvas covers them."
    ),
    # buttons
    "新增一个功能组行，随后在 initial 里选开机状态。": (
        "Add a function-group row; then pick boot state under initial."
    ),
    "删除当前选中的配置行（不可撤销，保存前可重开项目恢复）。": (
        "Delete the selected config row (no undo; reopen project before save to restore)."
    ),
    "新增进程行；进程名从 wiring 选择，避免手打错名。": (
        "Add a process row; pick the name from wiring to avoid typos."
    ),
    "按页 1 wiring 的进程列表重建本表；"
    "已填的 FG / depends_on / execution_client 会尽量按进程名保留。": (
        "Rebuild this table from tab-1 wiring processes; "
        "keep FG / depends_on / execution_client by process name when possible."
    ),
    "新增一条 EM 启动项（选进程、填 binary/args/重启次数）。": (
        "Add an EM launch row (pick process; fill binary/args/restart count)."
    ),
    "按 exec 进程表重建 EM 启动表；已有 binary/args/max_restarts 按进程名保留。": (
        "Rebuild EM launch from exec processes; keep binary/args/max_restarts by name."
    ),
    "新增一条健康监督实体，绑定某个 wiring 进程。": (
        "Add a health supervision entity bound to a wiring process."
    ),
    "新增一个诊断 DID 定义。": "Add a diagnostic DID definition.",
    "新增一个日志 context 覆盖项。": "Add a log-context level override.",
    # bounds / iceoryx
    "DLT context 表容量上限；log.contexts 条数不能超过此值，否则 Verify 报错。": (
        "Max DLT context table size; log.contexts count must not exceed this "
        "or Verify fails."
    ),
    "LoopbackBus 每个 topic 的队列深度（仅 SIL loopback 路径的 RAM 上界）。": (
        "LoopbackBus queue depth per topic (RAM upper bound for SIL loopback only)."
    ),
    "LoopbackBus 允许的 topic 键数量上限。": (
        "Max number of LoopbackBus topic keys."
    ),
    "仅用于内存预估：假设队列里每条样本的平均字节数，不写进运行时配置。": (
        "Estimate-only: assumed average sample bytes in the queue; not a runtime knob."
    ),
    "per（持久化 KV）最多允许多少个键。": "Max keys in per (persistence KV).",
    "per 单个 value 的最大字节数。": "Max bytes per per-value.",
    "DoIP TCP 接收累加器上限；保存时同步写入 diag.doip.rx_max_bytes。": (
        "DoIP TCP rx accumulator cap; saved also to diag.doip.rx_max_bytes."
    ),
    "UDS DID 表最多条目数。": "Max entries in the UDS DID map.",
    "单个 DID payload 最大字节数。": "Max bytes for one DID payload.",
    "可选门禁：预估 total_ram 超过此值则 Verify 警告；0=不检查。": (
        "Optional gate: Verify warns if estimated total_ram exceeds this; 0=off."
    ),
    "可选门禁：预估 total_disk 超过此值则 Verify 警告；0=不检查。": (
        "Optional gate: Verify warns if estimated total_disk exceeds this; 0=off."
    ),
    "写回 log.file_max_bytes：file sink 单文件软上限；"
    "预估 DISK 按 path + path.1 计 ×2（仅当启用 file sink）。": (
        "Writes log.file_max_bytes: file-sink soft cap; "
        "DISK estimate counts path + path.1 (×2) when file sink is on."
    ),
    "写回 collector.local.max_entries：本地事件环最大条数。": (
        "Writes collector.local.max_entries: max local event-ring entries."
    ),
    "写回 collector.local.debounce_max_keys：防抖 map 最大键数。": (
        "Writes collector.local.debounce_max_keys: max debounce-map keys."
    ),
    "写回 collector.local.store_max_bytes：共享 NDJSON 软上限；"
    "预估 DISK 按双文件计 ×2。": (
        "Writes collector.local.store_max_bytes: shared NDJSON soft cap; "
        "DISK estimate ×2 for the dual files."
    ),
    "两类配置、两套生效方式：\n"
    "• mgmt.*（IOX_MAX_*）：决定 iceoryx_mgmt 端口表大小，必须 "
    "compose → cmake 重配并重编 iceoryx（如 compile_sil）后才生效。\n"
    "• mempools：决定用户数据块共享内存（payload），compose 写出 "
    "iox_roudi.toml 后重启 RouDi 即可，不必重编。\n"
    "req.bindings 含 iceoryx 时由 EM 拉起 RouDi（platform daemon，非与 EM 并列）。": (
        "Two knobs, two apply paths:\n"
        "• mgmt.* (IOX_MAX_*): sizes iceoryx_mgmt port tables — needs "
        "compose → cmake reconfigure + rebuild iceoryx (e.g. compile_sil).\n"
        "• mempools: user payload shared memory — compose writes "
        "iox_roudi.toml, then restart RouDi (no rebuild).\n"
        "When req.bindings includes iceoryx, EM starts RouDi as a platform daemon "
        "(not a peer of EM)."
    ),
    "全局最多同时存在的 Publisher 端口数（编译进 iceoryx，对应 IOX_MAX_PUBLISHERS）。"
    "增大是拉高 iceoryx_mgmt 的主要因素；改后需重编 iceoryx。": (
        "Max concurrent Publisher ports (baked into iceoryx as IOX_MAX_PUBLISHERS). "
        "Main driver of iceoryx_mgmt size; rebuild iceoryx after change."
    ),
    "全局最多同时存在的 Subscriber 端口数（IOX_MAX_SUBSCRIBERS）。"
    "增大也会明显增加 iceoryx_mgmt；改后需重编 iceoryx。": (
        "Max concurrent Subscriber ports (IOX_MAX_SUBSCRIBERS). "
        "Also grows iceoryx_mgmt a lot; rebuild iceoryx after change."
    ),
    "每个 Publisher 最多挂多少个 Subscriber（IOX_MAX_SUBSCRIBERS_PER_PUBLISHER）。"
    "影响分发器表；相对 pub/sub 总数，对 mgmt 体积影响较小。": (
        "Max subscribers per publisher (IOX_MAX_SUBSCRIBERS_PER_PUBLISHER). "
        "Affects distributor tables; smaller mgmt impact than pub/sub totals."
    ),
    "Publisher 历史缓存深度（IOX_MAX_PUBLISHER_HISTORY）："
    "晚订阅者可拿到的最近样本数。对 mgmt 体积影响很小。": (
        "Publisher history depth (IOX_MAX_PUBLISHER_HISTORY): recent samples "
        "for late joiners. Tiny effect on mgmt size."
    ),
    "每个 Publisher 可同时占用的 chunk 数上限"
    "（IOX_MAX_CHUNKS_ALLOCATED_PER_PUBLISHER_*）。对 mgmt 体积影响很小。": (
        "Max chunks a publisher may hold at once "
        "(IOX_MAX_CHUNKS_ALLOCATED_PER_PUBLISHER_*). Tiny mgmt impact."
    ),
    "每个 Subscriber 可同时持有的 chunk 数 / 队列容量"
    "（IOX_MAX_CHUNKS_HELD_PER_SUBSCRIBER_*）。中等影响 mgmt 体积。": (
        "Max chunks held / queue capacity per subscriber "
        "(IOX_MAX_CHUNKS_HELD_PER_SUBSCRIBER_*). Moderate mgmt impact."
    ),
    "Interface 端口数（IOX_MAX_INTERFACE_NUMBER），gateway / 跨进程发现常用。"
    "改后需重编 iceoryx。": (
        "Interface port count (IOX_MAX_INTERFACE_NUMBER); used by gateway / "
        "discovery. Rebuild iceoryx after change."
    ),
    "可选门禁：预估 total_shm 超过则 Verify 警告；0=不检查。": (
        "Optional gate: Verify warns if estimated total_shm exceeds this; 0=off."
    ),
    "用户数据内存池（不是 iceoryx_mgmt）：\n"
    "• size = 单块可放的最大字节（选能装下你最大消息的一档）\n"
    "• count = 该档同时可借出的块数\n"
    "写入 generated/iox_roudi.toml，构成 payload 共享内存（预估里的 roudi_payload）。\n"
    "改完：保存/compose 后重启 RouDi 即可，无需重编 iceoryx。\n"
    "块越多/越大 → payload SHM 越大；与上方 mgmt.* 是两回事。": (
        "User data mempools (not iceoryx_mgmt):\n"
        "• size = max bytes per chunk (pick a tier that fits your largest message)\n"
        "• count = how many chunks of that tier can be loaned at once\n"
        "Written to generated/iox_roudi.toml as payload shared memory "
        "(roudi_payload in the estimate).\n"
        "After change: save/compose then restart RouDi — no iceoryx rebuild.\n"
        "More/larger chunks → larger payload SHM; separate from mgmt.* above."
    ),
    "该档每个 chunk 的字节容量（应 ≥ 该档要传的最大消息）。": (
        "Byte capacity of each chunk in this tier (≥ largest message for the tier)."
    ),
    "该档同时可分配的 chunk 个数（并发 in-flight 样本数）。": (
        "How many chunks of this tier may be allocated at once (in-flight samples)."
    ),
    "新增一档 mempool（size/count）。": "Add a mempool tier (size/count).",
}
