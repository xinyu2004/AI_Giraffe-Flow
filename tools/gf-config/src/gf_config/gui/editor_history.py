"""Shared document-history hooks for req / wiring / platform editors."""

from __future__ import annotations

from collections.abc import Callable


class HistoryHooksMixin:
    """Checkpoint / end-edit (/ optional clear) callbacks bound by MainWindow DocHistory."""

    _checkpoint_fn: Callable[..., None] | None
    _end_edit_fn: Callable[[], None] | None
    _clear_history_fn: Callable[[], None] | None

    def _init_history_hooks(self) -> None:
        self._checkpoint_fn = None
        self._end_edit_fn = None
        self._clear_history_fn = None

    def set_history_hooks(
        self,
        checkpoint: Callable[..., None] | None = None,
        end_edit: Callable[[], None] | None = None,
        clear: Callable[[], None] | None = None,
    ) -> None:
        self._checkpoint_fn = checkpoint
        self._end_edit_fn = end_edit
        self._clear_history_fn = clear

    def _checkpoint(self, *, coalesce: bool = False) -> None:
        if self._checkpoint_fn is not None:
            self._checkpoint_fn(coalesce=coalesce)

    def _end_doc_edit(self) -> None:
        if self._end_edit_fn is not None:
            self._end_edit_fn()

    def _clear_doc_history(self) -> None:
        if self._clear_history_fn is not None:
            self._clear_history_fn()
