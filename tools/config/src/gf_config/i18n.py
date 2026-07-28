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
    "gf-config — Giraffe Flow（A/B/C）": "gf-config — Giraffe Flow (A/B/C)",
    "未打开项目": "No project open",
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
    "删除选中边": "Delete selected edge",
    "没有可撤销的操作": "Nothing to undo",
    "已撤销（信号图）": "Undone (graph)",
    "没有可重做的操作": "Nothing to redo",
    "已重做（信号图）": "Redone (graph)",
    "请先打开项目": "Open a project first",
    "打开失败": "Open failed",
    "保存失败": "Save failed",
    "有未保存的更改，是否保存？": "Unsaved changes. Save?",
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
