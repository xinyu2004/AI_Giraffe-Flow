"""Authoritative Chinese tip strings for gf-config (passed through i18n.t).

Tips explain purpose / effect — not restating the field name or enum token.
"""

from __future__ import annotations

# ── runtime_modules ─────────────────────────────────────────
MODULE: dict[str, str] = {
    "core": (
        "基础类型库（Result / ErrorCode）。CMake 强制编入；"
        "几乎所有 middleware 都依赖它，不要试图裁掉。"
    ),
    "com": (
        "通信底座（Proxy/Skeleton、ServicePath）。CMake 强制编入；"
        "页 1 画布的 dataflow 最终走这里。具体传输在 bindings 里选。"
    ),
    "osal": (
        "OS 抽象（时钟、线程、进程 Spawn）。CMake 强制编入；"
        "EM 拉起进程、PHM 计时都依赖它。"
    ),
    "log": (
        "日志 lite：默认级别与 per-context 过滤写在 log.yaml；"
        "页 1 的 live/record 是观测通道，和这里的级别是两件事。"
    ),
    "exec": (
        "执行管理：进程↔功能组拓扑（exec.yaml）+ OS EM 启动表（em_launch.yaml）。"
        "勾选后解锁「执行/FG」与「EM 启动表」。"
    ),
    "phm": (
        "健康监督：按 Alive/Deadline 检查进程是否还在喂狗；"
        "失败可只记日志、通知 SM，或要求 EM 重启。解锁「健康 PHM」。"
    ),
    "sm": (
        "状态管理：功能组 Off / Running / Updating。"
        "与 exec 共用「执行/FG」页；OTA 时会切到 Updating。"
    ),
    "collector": (
        "事件收集（DEM-lite）：防抖/FDC/老化 + DTC；勾选后自动带上 per 做跨重启持久化。"
        "解锁「事件收集」；有 phm/diag 时也会出现入口。"
    ),
    "per": (
        "持久化 lite（双槽文件 KV，无 SQLite）。"
        "collector/ucm 需要跨重启 DTC 或版本时会自动勾选。"
    ),
    "ucm": (
        "OTA 编排：DoIP/GMT 触发后切 Updating → 跑包状态机 → 记结果；"
        "真板 RAUC 刷写仍是 stub。解锁「OTA ucm」。"
    ),
    "diag": (
        "诊断：ISO 14229 UDS（含 NRC）为基础，可选 ISO 13400 DoIP 作以太网传输；"
        "无 DoIP 时 CAN PDU 交 MCU。解锁「诊断」。"
    ),
    "tsync": (
        "时间同步 lite：platform/tsync.yaml；SIL 用 osal mock，"
        "板上配 linuxptp/ptp4l，本模块用 pmc 读状态。"
    ),
}

# ── exec / SM ───────────────────────────────────────────────
FG_ID = "功能组名字，供 SM StateClient 注册；进程通过 function_group 挂到这个组。"
FG_INITIAL = (
    "开机后该功能组进入的状态。\n"
    "• Off：关闭，不应跑业务\n"
    "• Running：正常业务，进程可提供服务\n"
    "• Updating：更新/OTA 窗；PHM 可暂停监督，失败可回滚\n"
    "非法转移：Off→Updating。"
)
FG_INITIAL_ITEMS: dict[str, str] = {
    "Off": "关闭态：组内进程不应处于业务运行；从 Off 不能直接进 Updating。",
    "Running": "正常运行态：组内进程可提供/消费服务；SIL 默认初始多为 Running。",
    "Updating": "更新窗：OTA/刷写期间使用；会配合 PHM pause，失败时可 Rollback。",
}

PROC_NAME = "要纳入 exec 拓扑的进程（来自页 1 wiring，不含 external.*）。"
PROC_FG = "该进程隶属的功能组：随 FG 的 Off/Running/Updating 一起被 SM 管理。"
PROC_DEPS = (
    "启动依赖：EM 会先拉起勾选的进程，成功后再 Spawn 本进程。"
    "用来保证例如 gateway 先于感知/规划就绪。"
)
PROC_EC = (
    "ExecutionClient：进程是否主动向 EM 汇报 Running/Terminating。\n"
    "• true：期望进程内 ExecutionClient 握手（规范路径）\n"
    "• false：EM 只按 Spawn/退出码管理，不期待客户端状态上报"
)
PROC_EC_ITEMS: dict[str, str] = {
    "true": "进程会通过 ExecutionClient 向 EM 汇报状态（推荐，贴近 ara::exec）。",
    "false": "不要求客户端上报；EM 仅根据进程存活/退出码管理（适合极简 stub）。",
}

# ── EM launch ───────────────────────────────────────────────
EM_NAME = "要由 OS EM（gf_em_daemon）Spawn 的进程，须与 exec/wiring 中的名字一致。"
EM_BINARY = (
    "可执行文件路径，相对 $GF_BUILD_DIR（compose/编译产物目录）。"
    "例如 apps/planning/driving/gf_planning_driving。"
)
EM_ARGS = (
    "传给进程的 POSIX argv（不是 AUTOSAR 字段，但是 Spawn 需要）。\n"
    "本工程 gateway：第一个参数=最多收几条 Trajectory 后退出；"
    "0=一直跑；SIL 冒烟常用 15。其它应用目前可忽略参数内容。"
)
EM_MAX_RESTARTS = (
    "当 PHM on_failure=restart 且进程以 exit 75 请求重启时，"
    "EM 最多 relaunch 的次数；超过则进入 terminal_exit，不再拉起。"
)

# ── PHM ─────────────────────────────────────────────────────
PHM_ID = "监督实体名，仅作配置/日志标识（如 gateway_alive）。"
PHM_PROCESS = "被监督的进程：须与 wiring 中的 AP 进程一致；该进程应周期性 ReportAlive。"
PHM_PERIOD = (
    "期望的 Alive 喂狗周期（ms）。进程应按大约这个间隔调用 ReportAlive；"
    "过慢会触发 AliveMissed。"
)
PHM_TIMEOUT = (
    "Alive 超时（ms）：超过该时间未喂狗则判健康故障。"
    "SIL 路径里也用作 SupervisedEntity 的 deadline 参数。"
)
PHM_DEADLINE = (
    "独立 Deadline 监督（ms）。0=关闭（只用 Alive）。"
    "非 0 时表示关键操作不得超过这么久，超时 → DeadlineMissed。"
)
PHM_ON_FAILURE = (
    "健康故障后的处置：\n"
    "• log：只记日志/Collector\n"
    "• notify_sm：通知 SM（可进 Updating）\n"
    "• restart：要求重启——托管进程 exit 75 由 EM relaunch"
)
PHM_ON_FAILURE_ITEMS: dict[str, str] = {
    "log": "仅记录事件（日志 + Collector），不改 SM 状态、不重启进程。",
    "notify_sm": "上报 Collector，并 NotifyHealthFault；可选让功能组进入 Updating。",
    "restart": (
        "请求恢复：GF_EM_MANAGED 时进程 exit 75，由 gf_em_daemon 按 max_restarts relaunch；"
        "未托管则走进程内 soft relaunch。"
    ),
}

# ── diag ────────────────────────────────────────────────────
DIAG_14229 = (
    "启用 ISO 14229 UDS（含否定响应 NRC）。这是诊断父能力；"
    "DoIP 只是它的一种传输，不能单独存在。"
)
DIAG_13400 = (
    "启用 ISO 13400 DoIP（以太网诊断传输）。必须同时开 14229；"
    "关掉 DoIP 时 AP 不跑 ISO-TP，CAN 侧 PDU 交给 MCU。"
)
DIAG_PLUGIN = (
    "UDS 0x27/0x29 安全访问算法插件（.so/.dll）。"
    "留空则用内置 SIL stub，仅供仿真，不能当量产密钥。"
)
DIAG_PLUGIN_BROWSE = "从磁盘选择安全访问插件动态库。"
DIAG_DOIP_EN = "DoIP 服务开关，与上面的 ISO 13400 勾选同步。"
DIAG_DOIP_ADDR = (
    "本 ECU 的 DoIP 逻辑地址（十六进制，如 0x0E00）。"
    "测试仪用该地址路由诊断请求。"
)
DIAG_DOIP_TESTER = (
    "期望的测试仪逻辑地址（如 0x0E80）。"
    "RoutingActivation 时与诊断仪对齐。"
)
DIAG_DOIP_PORT = "DoIP TCP 监听端口（默认 13400；GMT OTA / run_sil 须一致）。"
DIAG_S3 = (
    "ISO 14229 S3Server（ms）：非默认会话下若超过此时长无测试仪活动，"
    "会话回落 Default 并清除安全解锁。须大于诊断仪 0x3E 周期。"
)
DIAG_TP_PERIOD = (
    "测试仪 0x3E TesterPresent 发送周期（ms）。"
    "须小于 S3Server（建议 ≤ S3/2），与其它诊断仪维持时间对齐。"
)
DIAG_P2 = "P2Server（ms）：服务端最大响应时间（文档/对齐用；SIL 暂不强制掐断）。"
DIAG_P2STAR = "P2*Server（ms）：增强/刷写会话下的扩展响应窗口；GMT 用它作收包超时。"
DIAG_SEC_DELAY = (
    "0x27 密钥错误后的强制等待（ms）。期间再请求返回 NRC 0x37 "
    "RequiredTimeDelayNotExpired，与其它诊断仪对齐。"
)
DIAG_OTA_MODE = (
    "选择 OTA 下载 SID（写入 diag.yaml → ota_transfer.mode；GMT 只读跟从）：\n"
    "• 0x38 RequestFileTransfer：0x38→0x36→0x37（DoIP/以太网推荐）\n"
    "• 0x34 RequestDownload：0x34→0x36→0x37（经典内存下载）\n"
    "• 0x31 RoutineControl (SIL)：仅 F100 捷径，无字节管道"
)
DIAG_OTA_MODE_ITEMS: dict[str, str] = {
    "request_file_transfer": (
        "0x38 RequestFileTransfer → 0x36 TransferData → 0x37 RequestTransferExit。"
        "DoIP / 以太网默认路径；yaml 键 request_file_transfer。"
    ),
    "request_download": (
        "0x34 RequestDownload → 0x36 → 0x37。经典按内存地址下载；"
        "yaml 键 request_download。"
    ),
    "routine_sil": (
        "0x31 RoutineControl（RID F100）SIL 捷径：直接点 UCM，不传文件块。"
        "仅仿真；yaml 键 routine_sil。"
    ),
}
DIAG_OTA_PROG = (
    "传输前是否先发 DiagnosticSessionControl（0x10 02 Programming）。"
    "量产刷写通常必开；关掉仅便于 SIL 捷径调试。"
)
DIAG_OTA_SEC = (
    "传输前是否走 SecurityAccess（0x27 seed/key）。"
    "密钥算法在 GMT→OTA 记本地插件路径，或板端 GF_DIAG_SEC_PLUGIN；本页不存路径。"
)
DIAG_OTA_BLOCK = (
    "0x36 TransferData 单块最大字节数（maxNumberOfBlockLength）。"
    "过大占 RAM，过小拖慢；须与服务端协商值一致（SIL 默认 1024）。"
)
DID_ID = "数据标识符 DID（UDS 读/写用的 id，常用十六进制）。"
DID_NAME = "给人看的 DID 名称，便于在工具里辨认。"
DID_ACCESS = (
    "该 DID 允许的访问：\n"
    "• read：只读\n"
    "• write：只写\n"
    "• read_write：可读可写"
)
DID_ACCESS_ITEMS: dict[str, str] = {
    "read": "诊断仪可以读，不能写。",
    "write": "诊断仪可以写，不能读（少见，按标定策略使用）。",
    "read_write": "可读可写。",
}
DID_SIZE = "该 DID 载荷字节长度；生成/校验侧用来约束数据大小。"

# ── log ─────────────────────────────────────────────────────
LOG_DEFAULT = (
    "进程默认日志级别。比它更啰嗦的级别会被丢掉；"
    "单个 context 可在下表单独加严或放宽。"
)
LOG_CTX_ID = "日志上下文名（代码里 Logger 的 context id），用于分类过滤。"
LOG_CTX_LEVEL = "该 context 的级别覆盖默认值；未列出的 context 仍用 default_level。"
LOG_LEVEL_ITEMS: dict[str, str] = {
    "FATAL": "只保留致命错误。",
    "ERROR": "错误及以上。",
    "WARN": "警告及以上。",
    "INFO": "常规信息（常用默认）。",
    "DEBUG": "调试细节，日志量明显增加。",
    "VERBOSE": "最细，仅短时排障使用。",
}

# ── ucm ─────────────────────────────────────────────────────
UCM_ENABLED = (
    "打开后才跑 OtaOrchestrator：GMT/DoIP 下发更新时会切功能组、跑包状态机并记结果。"
    "关闭则忽略 OTA 编排请求。"
)
UCM_SOURCE = (
    "包/清单 URI，SIL 下交给 PackageManager::Initialize 识别包源。"
    "例如 sil://artifact；不是去编辑刷写镜像本身。"
)
UCM_FG = (
    "OTA 期间要切到 Updating 的功能组（通常 MachineFG）。"
    "须与 exec 里定义的 FG id 一致。"
)
UCM_ROLLBACK = (
    "编排失败时是否走 Rollback。"
    "关掉则失败只记 Collector 事件（如 ota_failed），不自动回滚包状态。"
)

# ── collector ───────────────────────────────────────────────
COL_FORWARD = (
    "事件往哪送：\n"
    "• local_store：本机 DEM-lite 落盘\n"
    "• cp_dem：转到 MCU CP DEM（有跨域时）\n"
    "• both：两边都要"
)
COL_FORWARD_ITEMS: dict[str, str] = {
    "local_store": "只写本地环形缓冲/落盘，适合纯 AP SIL。",
    "cp_dem": "转发到 MCU Classic DEM 路径（需要 CP/gateway）。",
    "both": "本地存一份，同时尝试转 MCU。",
}
COL_SOURCE = (
    "勾选后，该来源会写入 collector.yaml 的 sources。"
    "当前运行时会 ReportEvent 的有：phm（健康）、process（进程退出）、"
    "com（通信超时等）、ucm（OTA）。不是只能这三个；后续还可扩展。"
    "注意：runtime 暂未按 sources 过滤，勾选主要用于配置意图与文档。"
)
COL_LOCAL_EN = "是否启用本地 DEM-lite 存储；关则只转发、不在本机留历史。"
COL_MAX = "本地最多保留多少条事件；超出按策略丢弃最旧条目，防止磁盘涨满。"

# ── SKU / req ───────────────────────────────────────────────
SKU_VARIANT = "变体名，区分同一产品下的配置分支（写入 req.variant，参与 compose 标识）。"
SKU_PRODUCT = "产品名（如 AFC），用于文档/报告与 compose 元数据。"
SKU_TOPOLOGY = (
    "部署拓扑：\n"
    "• ap_only：只有 AP Linux，无 MCU CP\n"
    "• ap_mcu_cp：AP + MCU CP gateway，可走跨域 IPC / cp_dem"
)
SKU_TOPOLOGY_ITEMS: dict[str, str] = {
    "ap_only": "单域 AP：无 Classic DEM 转发、无 MCU gateway 进程。",
    "ap_mcu_cp": "异构：存在 MCU CP；bindings 可开 cross_domain_ipc，collector 可 forward=cp_dem。",
}
SKU_PROFILE = (
    "工程剖面：\n"
    "• vehicle-debug：允许 live_tap / record / Foxglove\n"
    "• production-release：强制关掉观测注入，不编 iox_obs_tap"
)
SKU_PROFILE_ITEMS: dict[str, str] = {
    "vehicle-debug": "调试剖面：可开 live/record/trace，便于 GMT/Foxglove。",
    "production-release": "发布剖面：灰掉观测开关，Verify/编译不带 tap，run_sil 不起 Foxglove。",
}
SKU_LIVE = (
    "Live tap：把画布上的服务镜像到观测工具。"
    "开启后 compose 会加入 debug_bridge/iox_obs_tap，run_sil 可接 Foxglove WebSocket。"
)
SKU_LIVE_MODE = (
    "live 服务范围：\n"
    "• wiring_all：天花板=页 1 全部 dataflow（推荐）\n"
    "• explicit：只用下面白名单，空名单会导致 Verify 失败"
)
SKU_LIVE_MODE_ITEMS: dict[str, str] = {
    "wiring_all": "自动跟随画布连线；GMT 仍可再过滤。",
    "explicit": "只镜像白名单服务；必须至少选一项，否则 Verify 失败。",
}
SKU_LIVE_SVCS = "explicit 模式下要镜像的服务；从 wiring 多选，避免手打拼写错误。"
SKU_RECORD = (
    "录制策略：控制 measure/record 采多少。\n"
    "off=不录；minimal/sampled/full 依次更全、更重。"
)
SKU_RECORD_ITEMS: dict[str, str] = {
    "minimal": "最小集录制，负载低。",
    "sampled": "抽样录制，平衡体积与可回放性。",
    "full": "尽量全量，磁盘与带宽占用高。",
    "off": "关闭录制；下方服务白名单也会灰掉。",
}
SKU_REC_SVCS = "参与 record 的服务白名单；从 wiring 多选。"
SKU_BIND_ICEORYX = "本机/进程间零拷贝通信（iceoryx）。SIL 双进程联调几乎总是要开。"
SKU_BIND_SOMEIP = "SOME/IP：车载以太网服务发现与序列化（对标量产 SOME/IP 栈时再开）。"
SKU_BIND_DDS = "DDS 绑定（可选中间件路径）；未接真 DDS 前多为占位能力开关。"
SKU_BIND_XDOMAIN = "跨域 IPC：AP↔MCU CP gateway。topology=ap_mcu_cp 时才有意义。"
SKU_ACC_DESC = "给人看的验收说明（本 SKU 要证明什么），写入 acceptance.description。"
SKU_ACC_LINEAGE = (
    "Verify 时是否强制 signal lineage 门禁全部通过；"
    "打开后 lineage 失败则 Verify 失败。"
)
SKU_ACC_SVCS = (
    "验收必须出现的服务（required_services）；"
    "compose/lineage 会检查画布是否覆盖这些服务。"
)

# Buttons (short but still purposeful)
BTN_ADD_FG = "新增一个功能组行，随后在 initial 里选开机状态。"
BTN_DEL_ROW = "删除当前选中的配置行（不可撤销，保存前可重开项目恢复）。"
BTN_ADD_PROC = "新增进程行；进程名从 wiring 选择，避免手打错名。"
BTN_SYNC_WIRING = (
    "按页 1 wiring 的进程列表重建本表；"
    "已填的 FG / depends_on / execution_client 会尽量按进程名保留。"
)
BTN_ADD_EM = "新增一条 EM 启动项（选进程、填 binary/args/重启次数）。"
BTN_SYNC_EXEC = "按 exec 进程表重建 EM 启动表；已有 binary/args/max_restarts 按进程名保留。"
BTN_ADD_PHM = "新增一条健康监督实体，绑定某个 wiring 进程。"
BTN_ADD_DID = "新增一个诊断 DID 定义。"
BTN_ADD_CTX = "新增一个日志 context 覆盖项。"
