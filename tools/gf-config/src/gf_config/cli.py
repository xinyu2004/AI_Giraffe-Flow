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

    from gf_config.gui.main_window import MainWindow
    from gf_config.i18n import load_language, t

    app = QApplication(sys.argv)
    app.setApplicationName("gf-config")
    app.setOrganizationName("GiraffeFlow")
    load_language()

    win = MainWindow()
    if args.project:
        try:
            win.open_project(args.project.resolve())
        except Exception as exc:  # noqa: BLE001 — show in UI
            from PySide6.QtWidgets import QMessageBox

            QMessageBox.critical(win, t("打开失败"), str(exc))
    win.show()
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
