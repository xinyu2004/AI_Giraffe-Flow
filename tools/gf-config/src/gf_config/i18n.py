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
    "正在切换语言并重启应用…": "Switching language and restarting…",
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
    "已撤销（信号图）": "Undone (graph)",
    "没有可重做的操作": "Nothing to redo",
    "已重做（信号图）": "Redone (graph)",
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
}


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


def t(zh: str) -> str:
    if _LANG == "en":
        return _EN.get(zh, zh)
    return zh


def switch_language_and_restart(lang: str) -> None:
    """Persist language and relaunch this process (sys.argv)."""
    from PySide6.QtCore import QProcess
    from PySide6.QtWidgets import QApplication, QMessageBox

    save_language(lang)
    QMessageBox.information(
        None,
        t("语言"),
        t("正在切换语言并重启应用…"),
    )
    QProcess.startDetached(sys.executable, sys.argv)
    app = QApplication.instance()
    if app is not None:
        app.quit()
