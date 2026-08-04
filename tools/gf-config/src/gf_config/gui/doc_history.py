"""Document-wide undo/redo for gf-config (req + wiring + platform)."""

from __future__ import annotations

import copy
from typing import Any, Callable

from gf_config.core import ProjectSession
from gf_config.i18n import t

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


def capture_snapshot(sess: ProjectSession) -> _Snapshot:
    dirty_plat = set(sess.dirty_platform or set())
    return {
        "req": copy.deepcopy(sess.req),
        "wiring": copy.deepcopy(sess.wiring),
        "platform": copy.deepcopy(sess.platform),
        "dirty_req": bool(sess.dirty_req),
        "dirty_wiring": bool(sess.dirty_wiring),
        "dirty_platform": dirty_plat,
    }


def _capture(sess: ProjectSession) -> _Snapshot:
    return capture_snapshot(sess)


def apply_snapshot(sess: ProjectSession, snap: _Snapshot) -> None:
    sess.req = copy.deepcopy(snap["req"])
    sess.wiring = copy.deepcopy(snap["wiring"])
    sess.platform = copy.deepcopy(snap["platform"])
    sess.dirty_req = bool(snap.get("dirty_req"))
    sess.dirty_wiring = bool(snap.get("dirty_wiring"))
    sess.dirty_platform = set(snap.get("dirty_platform") or set())


# platform yaml key → nav title (same strings as platform_editor._NAV; i18n via t())
_PLATFORM_LABELS = {
    "exec": "执行 / 功能组",
    "em_launch": "EM 启动表",
    "phm": "健康 PHM",
    "diag": "诊断 diag",
    "log": "日志",
    "ucm": "OTA ucm",
    "collector": "事件收集",
}


def locate_doc_change(
    before: _Snapshot, after: _Snapshot
) -> tuple[str, str | None, str]:
    """Where *after* differs from *before* (the edit being undone/redone).

    Returns (area, platform_key|None, hint).
    area: 'platform' | 'wiring' | 'req' | 'signals'
    """
    plat_a = before.get("platform") or {}
    plat_b = after.get("platform") or {}
    if plat_a != plat_b:
        keys = sorted(set(plat_a) | set(plat_b))
        changed = [k for k in keys if plat_a.get(k) != plat_b.get(k)]
        if len(changed) == 1:
            key = changed[0]
            label = t(_PLATFORM_LABELS.get(key, key))
            return "platform", key, f"{t('平台')} · {label}"
        if changed:
            labels = "、".join(t(_PLATFORM_LABELS.get(k, k)) for k in changed[:3])
            return "platform", changed[0], f"{t('平台')} · {labels}"
        return "platform", None, t("平台运行时")

    req_diff = (before.get("req") or {}) != (after.get("req") or {})
    wir_diff = (before.get("wiring") or {}) != (after.get("wiring") or {})
    if wir_diff and not req_diff:
        return "wiring", None, t("信号连线 / 部署")
    if req_diff and not wir_diff:
        return "req", None, t("SKU / 需求")
    if wir_diff or req_diff:
        return "signals", None, t("信号与应用")
    return "signals", None, t("文档")
