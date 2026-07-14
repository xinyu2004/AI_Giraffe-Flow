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
            "  pip install -e tools/codegen -e tools/config",
            file=sys.stderr,
        )
        return 2

    from gf_config.gui.main_window import MainWindow

    app = QApplication(sys.argv)
    app.setApplicationName("gf-config")
    app.setOrganizationName("GiraffeFlow")

    win = MainWindow()
    if args.project:
        try:
            win.open_project(args.project.resolve())
        except Exception as exc:  # noqa: BLE001 — show in UI
            from PySide6.QtWidgets import QMessageBox

            QMessageBox.critical(win, "Open failed", str(exc))
    win.show()
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
