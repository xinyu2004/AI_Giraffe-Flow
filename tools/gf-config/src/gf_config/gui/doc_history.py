"""Document-wide undo/redo for gf-config (req + wiring + platform)."""

from __future__ import annotations

import copy
from typing import Any, Callable

from gf_config.core import ProjectSession

_Snapshot = dict[str, Any]


class DocHistory:
    """Full-session checkpoints. Does not switch UI tabs — caller reloads editors."""

    def __init__(self, *, limit: int = 40) -> None:
        self._undo: list[_Snapshot] = []
        self._redo: list[_Snapshot] = []
        self._limit = limit
        self._armed = False
        self._suppress = False
        self._session_fn: Callable[[], ProjectSession | None] | None = None
        self._flush_fn: Callable[[], None] | None = None

    def bind(
        self,
        session_fn: Callable[[], ProjectSession | None],
        flush_fn: Callable[[], None],
    ) -> None:
        self._session_fn = session_fn
        self._flush_fn = flush_fn

    def clear(self) -> None:
        self._undo.clear()
        self._redo.clear()
        self._armed = False

    def end_edit(self) -> None:
        """Allow the next checkpoint() to take a new snapshot."""
        self._armed = False

    @property
    def suppress(self) -> bool:
        return self._suppress

    @suppress.setter
    def suppress(self, value: bool) -> None:
        self._suppress = bool(value)

    def can_undo(self) -> bool:
        return bool(self._undo)

    def can_redo(self) -> bool:
        return bool(self._redo)

    def checkpoint(self, *, coalesce: bool = False) -> None:
        """Snapshot current session *before* a mutation.

        coalesce=True: skip if already armed (typing / multi-signal bursts).
        coalesce=False: always push a new step (discrete graph actions).
        """
        if self._suppress:
            return
        if coalesce and self._armed:
            return
        sess = self._session_fn() if self._session_fn else None
        if sess is None:
            return
        if self._flush_fn is not None:
            self._flush_fn()
        self._undo.append(_capture(sess))
        if len(self._undo) > self._limit:
            self._undo.pop(0)
        self._redo.clear()
        self._armed = True

    def undo(self) -> _Snapshot | None:
        sess = self._session_fn() if self._session_fn else None
        if not self._undo or sess is None:
            return None
        if self._flush_fn is not None:
            self._flush_fn()
        self._redo.append(_capture(sess))
        snap = self._undo.pop()
        self._armed = False
        return snap

    def redo(self) -> _Snapshot | None:
        sess = self._session_fn() if self._session_fn else None
        if not self._redo or sess is None:
            return None
        if self._flush_fn is not None:
            self._flush_fn()
        self._undo.append(_capture(sess))
        snap = self._redo.pop()
        self._armed = False
        return snap


def _capture(sess: ProjectSession) -> _Snapshot:
    dirty_plat = set(sess.dirty_platform or set())
    return {
        "req": copy.deepcopy(sess.req),
        "wiring": copy.deepcopy(sess.wiring),
        "platform": copy.deepcopy(sess.platform),
        "dirty_req": bool(sess.dirty_req),
        "dirty_wiring": bool(sess.dirty_wiring),
        "dirty_platform": dirty_plat,
    }


def apply_snapshot(sess: ProjectSession, snap: _Snapshot) -> None:
    sess.req = copy.deepcopy(snap["req"])
    sess.wiring = copy.deepcopy(snap["wiring"])
    sess.platform = copy.deepcopy(snap["platform"])
    sess.dirty_req = bool(snap.get("dirty_req"))
    sess.dirty_wiring = bool(snap.get("dirty_wiring"))
    sess.dirty_platform = set(snap.get("dirty_platform") or set())
