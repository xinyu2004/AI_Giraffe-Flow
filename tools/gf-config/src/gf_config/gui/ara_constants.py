"""Platform tab constants (modules, deps, table enums, nav)."""

from __future__ import annotations

KNOWN_MODULES = [
    "core",
    "com",
    "osal",
    "log",
    "exec",
    "phm",
    "sm",
    "collector",
    "ucm",
    "diag",
    "per",
    "tsync",
]

# Soft deps: checking a module auto-checks these (with status tip).
# ALWAYS_ON_MODULES imported from gf_config.validate (single source).
MODULE_DEPS: dict[str, tuple[str, ...]] = {
    "collector": ("per",),
    "ucm": ("per", "sm"),
    "diag": ("log",),
    "phm": ("log",),
    "exec": ("sm",),
}

MODULE_DEP_HINTS: dict[str, str] = {
    "collector": "已自动勾选 per：DTC/事件跨重启需要持久化（gf_ara::per）",
    "ucm": "已自动勾选 per（记版本）、sm（Updating 功能组）",
    "diag": "已自动勾选 log：诊断/OTA 步骤需要可观测日志",
    "phm": "已自动勾选 log：健康失败默认 on_failure=log",
    "exec": "已自动勾选 sm：进程功能组状态需要 sm",
}

DEFAULT_MAX_RESTARTS = 3
# Explicit default argv token so the EM table never leaves args blank.
# Gateway: argv[1] = max Trajectory count (0 = forever). Other apps ignore argv today.
DEFAULT_EM_ARGS = "0"
DEFAULT_ALIVE_PERIOD_MS = 100
DEFAULT_ALIVE_TIMEOUT_MS = 300
# 0 = no separate deadline supervision in our SIL path (explicit, not null).
DEFAULT_DEADLINE_MS = 0

FG_INITIAL = ["Off", "Running", "Updating"]
FG_KIND = ["machine", "mode"]
BOOL_TF = ["true", "false"]
PHM_ON_FAILURE = ["log", "notify_sm", "restart"]
DID_ACCESS = ["read", "write", "read_write"]

OTA_MODE_ITEMS: list[tuple[str, str]] = [
    ("request_file_transfer", "0x38 · RequestFileTransfer"),
    ("request_download", "0x34 · RequestDownload"),
    ("routine_sil", "0x31 · RoutineControl (SIL)"),
]

MODULE_COLS = 5

# (platform yaml key, nav title, runtime_modules that unlock this page)
NAV = [
    ("exec", "执行 / 功能组", frozenset({"exec", "sm"})),
    ("em_launch", "EM 启动表", frozenset({"exec"})),
    ("phm", "健康 PHM", frozenset({"phm"})),
    ("diag", "诊断 diag", frozenset({"diag"})),
    ("log", "日志", frozenset({"log"})),
    ("ucm", "OTA ucm", frozenset({"ucm"})),
    ("collector", "事件收集", frozenset({"collector"})),
    ("bounds", "有界内存", frozenset({"com", "per", "log", "collector", "diag"})),
]

LOG_LEVELS = ["FATAL", "ERROR", "WARN", "INFO", "DEBUG", "VERBOSE"]
FORWARD_MODES = ["local_store", "cp_dem", "both"]
COLLECTOR_SOURCES = ["phm", "process", "com", "ucm"]

# Compat aliases (private names used throughout ara_cfg_editor historically).
_DEFAULT_MAX_RESTARTS = DEFAULT_MAX_RESTARTS
_DEFAULT_EM_ARGS = DEFAULT_EM_ARGS
_DEFAULT_ALIVE_PERIOD_MS = DEFAULT_ALIVE_PERIOD_MS
_DEFAULT_ALIVE_TIMEOUT_MS = DEFAULT_ALIVE_TIMEOUT_MS
_DEFAULT_DEADLINE_MS = DEFAULT_DEADLINE_MS
_FG_INITIAL = FG_INITIAL
_FG_KIND = FG_KIND
_BOOL_TF = BOOL_TF
_PHM_ON_FAILURE = PHM_ON_FAILURE
_DID_ACCESS = DID_ACCESS
_OTA_MODE_ITEMS = OTA_MODE_ITEMS
_MODULE_COLS = MODULE_COLS
_NAV = NAV
_LOG_LEVELS = LOG_LEVELS
_FORWARD_MODES = FORWARD_MODES
_COLLECTOR_SOURCES = COLLECTOR_SOURCES
