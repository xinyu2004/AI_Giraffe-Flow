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
    "时间同步 lite：cfg/gf_ara_cfg/tsync.yaml；SIL 用 osal mock，"
    "板上配 linuxptp/ptp4l，本模块用 pmc 读状态。": (
        "Time-sync lite: cfg/gf_ara_cfg/tsync.yaml; SIL uses osal mock; "
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
    "要由 OS EM（gf_em_daemon）Spawn 的进程，须与 exec/wiring 中的名字一致。\n"
    "host.* 由能力勾选同步插入（置顶锁定），禁止在本表删除。": (
        "Process Spawned by OS EM (gf_em_daemon); name must match exec/wiring.\n"
        "host.* are inserted by capability checkboxes (pinned, locked); do not delete here."
    ),
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
    "开启后 compose 会加入 gmt_board/iox_obs_tap，run_sil 可接 Foxglove WebSocket。": (
        "Live tap: mirror canvas services to observability tools. "
        "On → compose adds gmt_board/iox_obs_tap; run_sil can attach Foxglove WS."
    ),
    "帧摄入（frame_ingest）：CARLA / 文件 / 未来 ISP·摄像头的相机入口。"
    "与 live_tap 白名单不同——这里是行为轨迹，经 compose 冻结为 "
    "frame_ingest_config.hpp（apps + run_sil）。改完请 Verify + compile_sil，再 run_sil。"
    "功能场景（ACC/AEB）不在此配置，见仓库 carla_scenarios/。": (
        "Frame ingest: pick frame source + ego_source; compose freezes "
        "frame_ingest_config.hpp (C++ ingest / FCM / gateway). "
        "After edits: Verify + compile_sil, then run_sil. "
        "carla_scenarios/ is an independent scenario machine — not configured here."
    ),
    "视频源：freeze 默认 isp；SIL 用 GF_FRAME_SOURCE=carla|replay|colorbar|none。": (
        "Video source: freeze SOP default isp; SIL overrides via "
        "GF_FRAME_SOURCE=carla|replay|colorbar|none (synth→colorbar)."
    ),
    "帧从哪来：none=无帧 SIL stub；synth=进程内彩条；"
    "file/carla_file=读相机平面（stream 协商 format/w/h + 每帧 meta）。": (
        "Frame source: none=no frame; carla=CARLA module; isp=board/ISP; "
        "colorbar=bars (alias synth); replay=volume replay."
    ),
    "像素怎么用：stub=帧驱动计数；onnx=检测路径（需 -DGF_WITH_ONNX）。": (
        "How pixels are used: stub=frame-driven counts; onnx=detector path "
        "(needs -DGF_WITH_ONNX)."
    ),
    "像素格式枚举（可配）：nv12 默认；预留 nv21/yuv422/yuv444/rgb8。"
    "路径不含格式语义；以冻结字段 + stream.json 为准。": (
        "Configurable pixel_format enum: nv12 default; nv21/yuv422/yuv444/rgb8 reserved. "
        "Path has no format meaning — freeze field + stream.json win."
    ),
    "Ego 源互斥：gateway=网关自造；carla=bridge→gateway 发布；"
    "inject=回灌独占（gateway 不发 Ego）。运行时三选一。": (
        "Ego source mutex: gateway=fabricated; carla=bridge→gateway; "
        "inject=GMT replay owns Ego. Independent of frame source."
    ),
    "完整前视产品路径下相机写端：run_sil 是否启动 carla_bridge"
    "（相机→YUV 帧、ego、执行 cmd）。世界/变道/ACC 由 carla_scenarios/ 脚本定义，不在此。": (
        "Derived from frame source — whether ingest runs; no manual toggle. "
        "carla_scenarios/ remains a separate scenario machine."
    ),
    "中性帧路径（如 .yuv）；格式不靠后缀。"
    "旁路 .stream.json（协商）+ .meta.json（每帧 timestamp/seq）。"
    "金样在 SKU samples/；用 stage 脚本拷到此运行路径。": (
        "Neutral frame path (e.g. .yuv); format is not in the suffix. "
        "Sidecars: .stream.json (negotiate) + .meta.json (per-frame timestamp/seq). "
        "Goldens live under SKU samples/; use stage to copy onto this runtime path."
    ),
    "gateway→bridge 控车 cmd JSON（throttle/brake/steer/lane_change）。": (
        "gateway→bridge vehicle cmd JSON (throttle/brake/steer/lane_change)."
    ),
    # New hover strings (primary UI)
    "帧摄入（frame_ingest）：选帧源与 ego_source，经 compose 冻结为 "
    "frame_ingest_config.hpp（C++ ingest / FCM / gateway）。"
    "改完请 Verify + compile_sil，再 run_sil。"
    "carla_scenarios/ 是独立场景机，不在此配置、不进入 compose。": (
        "Frame ingest: pick frame source + ego_source; compose freezes "
        "frame_ingest_config.hpp (C++ ingest / FCM / gateway). "
        "After edits: Verify + compile_sil, then run_sil. "
        "carla_scenarios/ is an independent scenario machine — not configured here."
    ),
    "帧源（active_source）：none=无帧；carla=CARLA 相机模块；"
    "isp=板端/ISP（占位）；synth=彩条；replay=卷回灌。": (
        "Frame source: freeze default isp; SIL GF_FRAME_SOURCE="
        "carla|replay|colorbar|isp|none (synth→colorbar)."
    ),
    "Ego 源互斥：gateway=网关自造；carla=bridge→gateway 发布；"
    "inject=GMT 回灌独占（gateway 不发 Ego）。与帧源独立选型。": (
        "Ego source mutex: gateway=fabricated; carla=bridge→gateway; "
        "inject=GMT replay owns Ego. Independent of frame source."
    ),
    "（已由帧源推导）ingest 是否启用；勿再手勾。": (
        "Derived from frame source — whether ingest runs; no manual toggle."
    ),
    # Legacy hover keys (kept so older tipify caches still translate)
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
    "语义话题：画布双击模块 → Out 表改触发。"
    "通道话题：双击 frame_ingest 改触发。"
    "写入 req.publish_policy；compose → SOR / publish_policy.hpp。"
    "一发多收共享同一话题策略。Signals 页不编辑发布表。": (
        "Semantic topics: canvas double-click module → Out table for trigger. "
        "Channel topics: double-click frame_ingest. "
        "Written to req.publish_policy; compose → SOR / publish_policy.hpp. "
        "Fan-out shares one topic policy. Signals page no longer edits the table."
    ),
    "period=按点发；on_change=有新样本才发（无冻帧）。": (
        "period=cyclic; on_change=send only when a new sample exists (no freeze)."
    ),
    "周期：period_ms。变化时：expect_fps（预算/告警带，不是发报钟）。"
    "0 fps=未填。须 ≤ frame_ingest 相机 fps。": (
        "Period: period_ms. On-change: expect_fps (budget/warn band, "
        "not a send clock). 0 fps=unset. Must be ≤ frame_ingest camera fps."
    ),
    # buttons
    "新增一个功能组行，随后在 initial 里选开机状态。": (
        "Add a function-group row; then pick boot state under initial."
    ),
    "删除当前选中的配置行（不可撤销，保存前可重开项目恢复）。": (
        "Delete the selected config row (no undo; reopen project before save to restore)."
    ),
    "删除选中的 SOA 进程行。host.* 不可删——"
    "取消对应能力勾选（DLT / iceoryx / frame_ingest）才会移除。": (
        "Delete selected SOA process rows. host.* cannot be deleted here — "
        "uncheck the capability (DLT / iceoryx / frame_ingest) to remove them."
    ),
    "删除选中的 EM 启动行。host.* 禁止删除——"
    "与能力勾选强绑定：勾选即加、取消勾选即删。": (
        "Delete selected EM launch rows. host.* cannot be deleted — "
        "bound to capability checkboxes: check to add, uncheck to remove."
    ),
    "新增一行空白成员；在 name 列从 wiring 下拉选进程，再配 FG / depends_on / active_in。"
    "host.* 勿手加，勾选能力即可。": (
        "Add a blank membership row; pick a wiring process, then FG / depends_on / active_in. "
        "Do not add host.* by hand — toggle the capability instead."
    ),
    "新增一条空白 EM 启动项；先选进程，再填 binary/args/重启次数。host.* 由能力勾选同步。": (
        "Add a blank EM launch row; pick process, then binary/args/restarts. "
        "host.* sync from capability checkboxes."
    ),
    "仅补齐缺失的 SOA 进程（不碰 host.*）。"
    "已有 binary/args/max_restarts 按进程名保留；host 由能力勾选强同步。": (
        "Append missing SOA processes only (never host.*). "
        "Keep existing binary/args/max_restarts by name; hosts sync from capability checkboxes."
    ),
    "file sink 单文件软上限（字节）；轮转保留 path + path.1，"
    "计入有界内存 DISK 预估 ×2。在「日志」页编辑，不在有界内存页重复。": (
        "File-sink soft rotate cap (bytes); keeps path + path.1; "
        "DISK estimate ×2. Edit on the Log page — not duplicated on Memory bounds."
    ),
    "本地最多保留多少条事件；超出按策略丢弃最旧条目。"
    "计入有界内存 RAM（collector_ring）；在「事件收集」页编辑。": (
        "Max local event records; oldest dropped when full. "
        "Counted in memory-bound RAM (collector_ring); edit on Event collector."
    ),
    "防抖 map 最大键数；RAM ≈ keys × C_DEBOUNCE_ENTRY。"
    "在「事件收集」页编辑，有界内存预估会自动计入。": (
        "Debounce map max keys; RAM ≈ keys × C_DEBOUNCE_ENTRY. "
        "Edit on Event collector; memory-bound estimate picks it up."
    ),
    "共享 NDJSON 文件软上限；保留 ×2，计入 DISK 预估。"
    "在「事件收集」页编辑。": (
        "Shared NDJSON soft cap; ×2 retained; DISK estimate. Edit on Event collector."
    ),
    "不可删除 host.dlt_daemon。\n"
    "它由 Log → sinks 勾选 dlt 产生；请取消勾选 dlt，行会自动从 exec/EM 移除。": (
        "Cannot delete host.dlt_daemon.\n"
        "It comes from Log→sinks checking dlt; uncheck dlt and the row is removed from exec/EM."
    ),
    "不可删除 host.iox_roudi。\n"
    "它由 SKU bindings 勾选 iceoryx 产生；请取消勾选 iceoryx，行会自动移除。": (
        "Cannot delete host.iox_roudi.\n"
        "It comes from SKU bindings checking iceoryx; uncheck iceoryx and the row is removed."
    ),
    "不可删除 host.frame_ingest。\n"
    "它由页 1 frame_ingest 开启产生；请关闭 frame_ingest，行会自动移除。": (
        "Cannot delete host.frame_ingest.\n"
        "It comes from enabling tab-1 frame_ingest; disable frame_ingest and the row is removed."
    ),
    "不可删除该 platform daemon（host.*）。\n"
    "请取消对应能力勾选以移除；禁止在本表删除。": (
        "Cannot delete this platform daemon (host.*).\n"
        "Uncheck its capability to remove it; do not delete the row here."
    ),
    "新增一条健康监督实体，绑定某个 wiring 进程。": (
        "Add a health supervision entity bound to a wiring process."
    ),
    "host.dlt_daemon：由 Log → sinks 勾选 dlt 产生（置顶锁定）。\n"
    "取消勾选 dlt 即从 exec/EM 删除；禁止在本表点删除。": (
        "host.dlt_daemon: created when Log→sinks checks dlt (pinned/locked).\n"
        "Uncheck dlt to remove from exec/EM; do not delete the row here."
    ),
    "host.iox_roudi：由 SKU bindings 勾选 iceoryx 产生（置顶锁定）。\n"
    "取消勾选 iceoryx 即删除；禁止在本表点删除。\n"
    "运行时 RouDi 异常退出 → EM 记日志并有序析构整栈。": (
        "host.iox_roudi: created when SKU bindings checks iceoryx (pinned/locked).\n"
        "Uncheck iceoryx to remove; do not delete the row here.\n"
        "At runtime, abnormal RouDi exit → EM logs and orderly tears down the stack."
    ),
    "host.frame_ingest：由页 1 frame_ingest 开启产生（置顶锁定）。\n"
    "关闭 frame_ingest 即删除；禁止在本表点删除。": (
        "host.frame_ingest: created when tab-1 frame_ingest is enabled (pinned/locked).\n"
        "Disable frame_ingest to remove; do not delete the row here."
    ),
    "platform daemon（host.*）：由对应能力勾选产生；取消勾选即删，禁止在本表删除。": (
        "platform daemon (host.*): created by its capability checkbox; "
        "uncheck to remove; do not delete the row here."
    ),
    "进程名真源在页 1 wiring（画布上的模块）。\n"
    "本列从 wiring 下拉选择；空白行表示尚未选定。\n"
    "不要在此手发明新进程名——应先在 wiring 添加模块。\n"
    "host.* 不在此下拉：由能力勾选自动插入（置顶、灰底锁定）。": (
        "Process name truth is tab-1 wiring.\n"
        "Pick from the wiring dropdown; blank means not chosen yet.\n"
        "Do not invent names here — add the module on the wiring canvas first.\n"
        "host.* are not in this dropdown: capability checkboxes insert them (pinned, locked)."
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
    # ModeDeclaration FG / active_in
    '功能组类型：\n• machine：固定 Off|Running|Updating（平台/OTA）\n• mode：ModeDeclaration，态名任意（行泊/底盘/EMB 等产品词只写在 App）': 'FG kind:\n• machine: fixed Off|Running|Updating (platform/OTA)\n• mode: ModeDeclaration; arbitrary state names (product words stay in Apps)',
    'MachineFG 三态；bring-up EnsureGroup(Running)；不可写 active_in。': 'Machine three-state; bring-up EnsureGroup(Running); no active_in.',
    '任意态名；EM 按进程 active_in 做 set-diff；Mode App 调 RequestTransitionNamed。': 'Arbitrary states; EM set-diff via process active_in; Mode App uses RequestTransitionNamed.',
    '开机后该功能组进入的状态。\n• machine：仅 Off / Running / Updating\n• mode：任意字符串，须属于 states[]\n禁止把 DrivingActive 等 mode 态塞进 machine 的 Off/Running/Updating。': 'Initial FG state after boot.\n• machine: only Off / Running / Updating\n• mode: any string that is in states[]\nDo not put DrivingActive into machine Off/Running/Updating.',
    'ModeDeclaration 的初始态名（须出现在 states）。': 'ModeDeclaration initial state (must be in states).',
    'mode FG 的合法态名列表，逗号分隔。\n进程 active_in 只能从这里选；machine FG 留空。': 'Legal mode FG state names, comma-separated.\nProcess active_in is chosen from this list; leave empty for machine FG.',
    'machine FG 无自由 states（固定 Off|Running|Updating）。': 'machine FG has no free-form states (fixed Off|Running|Updating).',
    '该进程隶属的功能组。\nmachine：常驻（Running 语义）；mode：仅当当前 FG 态 ∈ active_in 时由 EM 拉起。': 'Process membership FG.\nmachine: always-on (Running); mode: EM runs only when FgState ∈ active_in.',
    'ModeDeclaration 成员态：当前 FgState ∈ 勾选集合时进程应运行。\n差集成员 = active_in，不是进程名硬编码。': 'ModeDeclaration membership: process should run when current FgState is in the set.\nSet-diff members = active_in, not hardcoded process names.',
    'machine FG 进程不写 active_in（常驻）。': 'machine FG processes omit active_in (always-on).',

    # Current FG / active_in / SKU tips (exact tips.py keys)
    "ModeDeclaration 的初始态：只能从上方 states 列表里选，先编辑 states。": (
        "ModeDeclaration initial: pick only from the states list above; edit states first."
    ),
    "请先在 states 列弹出对话框添加至少一个态名，再选 initial。": (
        "Add at least one state via the states-cell dialog before choosing initial."
    ),
    "ModeDeclaration 合法态名列表。点击单元格弹出编辑器逐项添加/删除/改名。\n"
    "不要用逗号手写；initial 与进程 active_in 都从这里选。": (
        "Legal ModeDeclaration state names. Click the cell to add/remove/rename one by one.\n"
        "Do not type commas; initial and process active_in are chosen from this list."
    ),
    "machine FG 无自由 states（固定 Off|Running|Updating）；本列灰显不可编辑。": (
        "machine FG has no free-form states (fixed Off|Running|Updating); this column is locked."
    ),
    "该进程隶属的功能组。\n"
    "machine：常驻（Running 语义）；mode：仅当当前 FG 态 = active_in 时由 EM 拉起。": (
        "Owning function group.\n"
        "machine: always-on (Running); mode: EM runs only when current FG state equals active_in."
    ),
    "ModeDeclaration 成员态（单选）：该进程只在所选态下运行。\n"
    "差集场景通常一行一态（如 driving→DrivingActive）；勿多选。": (
        "ModeDeclaration membership (single-select): process runs only in that state.\n"
        "Set-diff rows are usually one state each (e.g. driving→DrivingActive); do not multi-select."
    ),
    "machine FG：无 active_in（常驻），本列灰显不可编辑。": (
        "machine FG: no active_in (always-on); this column is locked."
    ),
    "可选视频契约：B 页添加/双击 host.frame_ingest。"
    "每路 = GfChannel Out（含该路 pixel）；无外参/内参/ego/感知后端。"
    "compose → hpp + camera_contract.json。": (
        "Optional video contract: tab-1 add/double-click host.frame_ingest. "
        "Each lane = GfChannel Out (with that lane's pixel); no extrinsics/intrinsics/ego/backend. "
        "compose → hpp + camera_contract.json."
    ),
    "仅 replay/file 旁路帧路径（可选）；联仿主链走 GfChannel，无 front.yuv / carla_*.json。": (
        "Optional replay/file bypass frame path; cosim main path is GfChannel "
        "(no front.yuv / carla_*.json)."
    ),
    "已删除：控车不走 JSON。SIL egress = GfChannel vehicle_cmd → cosim → giraffe_client。": (
        "Removed: vehicle control is not JSON. SIL egress = "
        "GfChannel vehicle_cmd → cosim → giraffe_client."
    ),
}
