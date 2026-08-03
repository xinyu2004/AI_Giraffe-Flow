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
        help="Path to project.yaml (default: pick via dialog)",
    )
    args = parser.parse_args(argv)

    try:
        from PySide6.QtWidgets import QApplication
    except ImportError:
        print(
            "PySide6 is required. Install with:\n"
            "  pip install -e tools/gf-codegen -e tools/gf-config",
            file=sys.stderr,
        )
        return 2

    # QApplication before any GUI import (QCursor/QPixmap need a QGuiApplication).
    app = QApplication(sys.argv)
    app.setApplicationName("gf-config")
    app.setOrganizationName("GiraffeFlow")

    from gf_config.gui.main_window import MainWindow
    from gf_config.i18n import load_language, t, take_pending_reopen_project

    load_language()

    win = MainWindow()
    reopen = take_pending_reopen_project()
    project = args.project.resolve() if args.project else None
    if project is None and reopen:
        cand = Path(reopen)
        if cand.is_file():
            project = cand.resolve()
    if project is not None:
        try:
            win.open_project(project)
        except Exception as exc:  # noqa: BLE001 — show in UI
            from PySide6.QtWidgets import QMessageBox

            QMessageBox.critical(win, t("打开失败"), str(exc))
    win.show()
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
