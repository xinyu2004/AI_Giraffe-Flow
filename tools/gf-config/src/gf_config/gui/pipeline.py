"""Editor pipeline façade: flush UI → validate → save / compose.

MainWindow (and tests) should call these instead of duplicating flush+gate logic.

Principle: controls → memory → validate → disk (fail keeps memory, no write).
Each bag flushes independently; harvest must not author display defaults.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import TYPE_CHECKING

from gf_config.validate import ValidationResult

if TYPE_CHECKING:
    from gf_config.core import ProjectSession


def flush_session(
    flush_canvas: Callable[[], None] | None = None,
    flush_platform: Callable[[], None] | None = None,
) -> None:
    """Push visible editor widgets into ProjectSession before gate."""
    if flush_canvas is not None:
        flush_canvas()
    if flush_platform is not None:
        flush_platform()


def save_validated(
    session: ProjectSession,
    *,
    flush_canvas: Callable[[], None] | None = None,
    flush_platform: Callable[[], None] | None = None,
) -> ValidationResult:
    """Flush widgets → session, then validate+persist dirty slices."""
    flush_session(flush_canvas, flush_platform)
    return session.save_all(require_valid=True)


def compose_validated(
    session: ProjectSession,
    *,
    flush_canvas: Callable[[], None] | None = None,
    flush_platform: Callable[[], None] | None = None,
) -> tuple[int, str, ValidationResult]:
    """Flush → validate → persist → compose_project."""
    flush_session(flush_canvas, flush_platform)
    return session.compose()
