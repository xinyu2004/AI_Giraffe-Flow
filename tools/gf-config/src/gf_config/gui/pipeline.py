"""Editor pipeline façade: flush canvas → validate → save / compose.

MainWindow (and tests) should call these instead of duplicating flush+gate logic.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import TYPE_CHECKING

from gf_config.validate import ValidationResult

if TYPE_CHECKING:
    from gf_config.core import ProjectSession


def flush_session(flush_canvas: Callable[[], None] | None) -> None:
    if flush_canvas is not None:
        flush_canvas()


def save_validated(
    session: ProjectSession,
    *,
    flush_canvas: Callable[[], None] | None = None,
) -> ValidationResult:
    """Flush canvas UI into session, then validate+persist dirty slices."""
    flush_session(flush_canvas)
    return session.save_all(require_valid=True)


def compose_validated(
    session: ProjectSession,
    *,
    flush_canvas: Callable[[], None] | None = None,
) -> tuple[int, str, ValidationResult]:
    """Flush → validate → persist → compose_project."""
    flush_session(flush_canvas)
    return session.compose()
