"""CLI entry for gf-config."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="gf-config",
        description="Giraffe Flow SKU + signal-link config GUI (host-only, PySide6)",
    )
    parser.add_argument(
        "project",
        nargs="?",
        type=Path,
        help="Path to giraffe.yaml (default: pick via dialog)",
    )
    args = parser.parse_args(argv)

    try:
        from PySide6.QtCore import Qt
        from PySide6.QtWidgets import QApplication
    except ImportError:
        print(
            "PySide6 is required. Install with:\n"
            "  pip install -e tools/gf-codegen -e tools/gf-config",
            file=sys.stderr,
        )
        return 2

    app = QApplication(sys.argv)
    app.setApplicationName("gf-config")
    app.setOrganizationName("GiraffeFlow")

    from gf_config.gui.main_window import MainWindow
    from gf_config.i18n import clear_stale_pending_open, load_language, t

    load_language()
    clear_stale_pending_open()

    win = MainWindow()
    win.restore_window_geometry()

    project = args.project.resolve() if args.project else None

    if project is None:
        win.show()
        win.raise_()
        win.activateWindow()
        return app.exec()

    # Fit graph while mapped but not on-screen, then reveal once.
    win._quiet_booting = True
    win.setUpdatesEnabled(False)
    win._graph._view.setUpdatesEnabled(False)
    win.setAttribute(Qt.WidgetAttribute.WA_DontShowOnScreen, True)
    win.show()
    app.processEvents()

    try:
        win.open_project(project)
    except Exception as exc:  # noqa: BLE001
        from PySide6.QtWidgets import QMessageBox

        win.setAttribute(Qt.WidgetAttribute.WA_DontShowOnScreen, False)
        win._quiet_booting = False
        win.setUpdatesEnabled(True)
        win._graph._view.setUpdatesEnabled(True)
        wh = win.windowHandle()
        if wh is not None:
            wh.setVisible(True)
        win.show()
        QMessageBox.critical(win, t("打开失败"), str(exc))
        return app.exec()

    win.finish_quiet_boot()

    win.setAttribute(Qt.WidgetAttribute.WA_DontShowOnScreen, False)
    win._quiet_booting = False
    wh = win.windowHandle()
    if wh is not None:
        wh.setVisible(True)
    win._graph._view.setUpdatesEnabled(True)
    win.setUpdatesEnabled(True)
    win.show()
    win.raise_()
    win.activateWindow()
    app.processEvents()

    if not win.isVisible() or win.testAttribute(
        Qt.WidgetAttribute.WA_DontShowOnScreen
    ):
        win.hide()
        win.setAttribute(Qt.WidgetAttribute.WA_DontShowOnScreen, False)
        win.setUpdatesEnabled(True)
        win._graph._view.setUpdatesEnabled(True)
        win.show()
        win.raise_()
        win.activateWindow()

    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
