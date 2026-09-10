"""Platform tab table row fillers / FG helpers."""

from __future__ import annotations

from typing import Any

from PySide6.QtCore import Qt
from PySide6.QtGui import QColor
from PySide6.QtWidgets import (
    QComboBox,
    QTableWidget,
    QTableWidgetItem,
    QWidget,
)

from gf_codegen.compose.merge_platform import is_host_platform_process
from gf_config.gui import tips as T
from gf_config.gui.ara_constants import (
    _BOOL_TF,
    _FG_INITIAL,
    _FG_KIND,
    _PHM_ON_FAILURE,
)
from gf_config.gui.ara_widgets import _cell, _combo_text, _set_cell, _set_combo
from gf_config.gui.field_ux import (
    COLORS_FG_INITIAL,
    COLORS_ON_FAILURE,
    multi_selected,
    set_multi_check,
    set_string_list_edit,
    string_list_values,
    tipify_item,
)
from gf_config.i18n import t


class AraTablesMixin:
    """Mixin: FG/process/EM/PHM table row helpers for AraCfgEditor."""

    def _fg_meta(self) -> dict[str, dict[str, object]]:
        """id -> {kind, initial, states} from the FG table."""
        meta: dict[str, dict[str, object]] = {}
        for r in range(self._fg_table.rowCount()):
            fid = _cell(self._fg_table, r, 0)
            if not fid:
                continue
            kind = (_combo_text(self._fg_table, r, 1) or "machine").strip().lower()
            if kind not in ("machine", "mode"):
                kind = "machine"
            initial = _combo_text(self._fg_table, r, 2) or _cell(self._fg_table, r, 2)
            if kind == "machine":
                states: list[str] = []
            else:
                states = string_list_values(self._fg_table, r, 3)
            meta[fid] = {"kind": kind, "initial": initial, "states": states}
        return meta

    def _fg_kind_for_id(self, fg_id: str) -> str:
        return str(self._fg_meta().get(fg_id, {}).get("kind") or "machine")

    def _states_for_fg(self, fg_id: str) -> list[str]:
        return list(self._fg_meta().get(fg_id, {}).get("states") or [])

    def _on_fg_kind_changed(self, row: int) -> None:
        if getattr(self, "_fg_kind_guard", False):
            return
        self._fg_kind_guard = True
        try:
            self._on_fg_kind_changed_body(row)
        finally:
            self._fg_kind_guard = False

    def _on_fg_kind_changed_body(self, row: int) -> None:
        fid = _cell(self._fg_table, row, 0) or f"FG{row + 1}"
        kind = (_combo_text(self._fg_table, row, 1) or "machine").strip().lower()
        if kind not in ("machine", "mode"):
            kind = "machine"
        if kind == "machine":
            initial = _combo_text(self._fg_table, row, 2) or "Running"
            if initial not in _FG_INITIAL:
                initial = "Running"
            states: list[str] = []
        else:
            states = string_list_values(self._fg_table, row, 3)
            initial = _combo_text(self._fg_table, row, 2) or _cell(self._fg_table, row, 2)
            if initial in _FG_INITIAL and initial not in states:
                # switching from machine: drop classic three-state name
                initial = states[0] if states else ""
            if not states and not initial:
                initial = ""
        self._fg_table.blockSignals(True)
        self._fill_fg_row(row, fid=fid, kind=kind, initial=initial, states=states)
        self._fg_table.blockSignals(False)
        self._on_exec_changed()

    def _on_fg_states_changed(self, row: int) -> None:
        states = string_list_values(self._fg_table, row, 3)
        cur = _combo_text(self._fg_table, row, 2) or _cell(self._fg_table, row, 2)
        if cur not in states:
            cur = states[0] if states else ""
        self._fg_table.blockSignals(True)
        self._fg_table.removeCellWidget(row, 2)
        self._fg_table.takeItem(row, 2)
        if states:
            _set_combo(
                self._fg_table,
                row,
                2,
                states,
                cur or states[0],
                self._on_exec_changed,
                tip=T.FG_INITIAL_MODE,
            )
        else:
            _set_cell(self._fg_table, row, 2, "", T.FG_INITIAL_MODE)
            cell = self._fg_table.item(row, 2)
            if cell is not None:
                tipify_item(cell, T.FG_INITIAL_NEED_STATES)
                cell.setFlags(cell.flags() & ~Qt.ItemFlag.ItemIsEditable)
        self._fg_table.blockSignals(False)
        self._on_exec_changed()

    def _fill_fg_row(
        self,
        r: int,
        *,
        fid: str,
        kind: str,
        initial: str,
        states: list[str],
    ) -> None:
        kind = (kind or "machine").strip().lower()
        if kind not in ("machine", "mode"):
            kind = "machine"
        _set_cell(self._fg_table, r, 0, fid, T.FG_ID)
        _set_combo(
            self._fg_table,
            r,
            1,
            _FG_KIND,
            kind,
            lambda *_a, row=r: self._on_fg_kind_changed(row),
            tip=T.FG_KIND,
            item_tips=T.FG_KIND_ITEMS,
        )
        self._fg_table.removeCellWidget(r, 3)
        self._fg_table.takeItem(r, 3)
        if kind == "machine":
            init = initial if initial in _FG_INITIAL else "Running"
            _set_combo(
                self._fg_table,
                r,
                2,
                _FG_INITIAL,
                init,
                self._on_exec_changed,
                tip=T.FG_INITIAL,
                enum_colors=COLORS_FG_INITIAL,
                item_tips=T.FG_INITIAL_ITEMS,
            )
            _set_cell(self._fg_table, r, 3, "n/a · machine", T.FG_STATES_MACHINE)
            cell = self._fg_table.item(r, 3)
            if cell is not None:
                tipify_item(cell, T.FG_STATES_MACHINE)
                cell.setFlags(cell.flags() & ~Qt.ItemFlag.ItemIsEditable)
                cell.setForeground(QColor("#37474f"))
                cell.setBackground(QColor("#cfd8dc"))
        else:
            set_string_list_edit(
                self._fg_table,
                r,
                3,
                states,
                lambda *_a, row=r: self._on_fg_states_changed(row),
                tip=T.FG_STATES,
                empty_label=t("（点击编辑 states）"),
                title=t("编辑 ModeDeclaration states"),
            )
            self._fg_table.removeCellWidget(r, 2)
            self._fg_table.takeItem(r, 2)
            if states:
                init = initial if initial in states else states[0]
                _set_combo(
                    self._fg_table,
                    r,
                    2,
                    states,
                    init,
                    self._on_exec_changed,
                    tip=T.FG_INITIAL_MODE,
                )
            else:
                _set_cell(self._fg_table, r, 2, "", T.FG_INITIAL_NEED_STATES)
                cell = self._fg_table.item(r, 2)
                if cell is not None:
                    tipify_item(cell, T.FG_INITIAL_NEED_STATES)
                    cell.setFlags(cell.flags() & ~Qt.ItemFlag.ItemIsEditable)

    def _fg_ids(self) -> list[str]:
        ids = [
            _cell(self._fg_table, r, 0)
            for r in range(self._fg_table.rowCount())
            if _cell(self._fg_table, r, 0)
        ]
        return ids or ["MachineFG"]

    def _default_fg(self) -> str:
        ids = self._fg_ids()
        return ids[0] if ids else "MachineFG"

    def _proc_names_in_table(self) -> list[str]:
        out: list[str] = []
        for r in range(self._proc_table.rowCount()):
            n = _combo_text(self._proc_table, r, 0)
            if n:
                out.append(n)
        return out

    def _deps_candidates_for_row(self, row: int) -> list[str]:
        self_name = _combo_text(self._proc_table, row, 0)
        names = self._proc_names_in_table() or self._process_names()
        return [n for n in names if n and n != self_name]

    def _fill_proc_row(
        self,
        r: int,
        *,
        name: str,
        fg: str,
        deps: list[str],
        execution_client: bool,
        active_in: list[str] | None = None,
    ) -> None:
        fg_id = fg or self._default_fg()
        tip = self._host_row_tip(name) if is_host_platform_process(name) else T.PROC_NAME
        _set_combo(
            self._proc_table,
            r,
            0,
            self._name_picker_options(name),
            name,
            self._on_exec_changed,
            tip=tip,
        )
        _set_combo(
            self._proc_table,
            r,
            1,
            self._fg_ids(),
            fg_id,
            self._on_exec_changed,
            tip=T.PROC_FG,
        )
        set_multi_check(
            self._proc_table,
            r,
            2,
            [str(x) for x in deps],
            lambda row=r: self._deps_candidates_for_row(row),
            self._on_exec_changed,
            tip=T.PROC_DEPS,
            empty_label=t("（无依赖）"),
            title=t("选择 depends_on"),
        )
        self._set_proc_active_in_cell(r, fg_id, active_in)
        self._set_proc_execution_client_cell(r, name, execution_client)

    def _set_proc_execution_client_cell(
        self, r: int, name: str, execution_client: bool
    ) -> None:
        """SOA apps: true/false combo. Platform daemons: locked n/a (always false)."""
        self._proc_table.removeCellWidget(r, 4)
        if is_host_platform_process(name):
            _set_cell(self._proc_table, r, 4, "n/a · daemon", T.PROC_EC_DAEMON)
            cell = self._proc_table.item(r, 4)
            if cell is not None:
                tipify_item(cell, T.PROC_EC_DAEMON)
                cell.setFlags(cell.flags() & ~Qt.ItemFlag.ItemIsEditable)
                cell.setForeground(QColor("#37474f"))
                cell.setBackground(QColor("#cfd8dc"))
            return
        # Drop stale item so combo owns the cell
        self._proc_table.takeItem(r, 4)
        _set_combo(
            self._proc_table,
            r,
            4,
            _BOOL_TF,
            "true" if execution_client else "false",
            self._on_exec_changed,
            tip=T.PROC_EC,
            bool_style=True,
            item_tips=T.PROC_EC_ITEMS,
        )

    def _fill_em_row(
        self, r: int, *, name: str, binary: str, args_s: str, mr_s: str
    ) -> None:
        tip = self._host_row_tip(name) if is_host_platform_process(name) else T.EM_NAME
        _set_combo(
            self._em_table,
            r,
            0,
            self._name_picker_options(name),
            name,
            self._on_em_launch_changed,
            tip=tip,
        )
        _set_cell(self._em_table, r, 1, binary, T.EM_BINARY)
        _set_cell(self._em_table, r, 2, args_s, T.EM_ARGS)
        _set_cell(self._em_table, r, 3, mr_s, T.EM_MAX_RESTARTS)

    def _fill_phm_row(
        self,
        r: int,
        *,
        eid: str,
        process: str,
        period: str,
        timeout: str,
        deadline: str,
        on_failure: str,
    ) -> None:
        names = list(self._process_names())
        if process and process not in names:
            names = [process] + names
        _set_cell(self._phm_table, r, 0, eid, T.PHM_ID)
        _set_combo(
            self._phm_table,
            r,
            1,
            names,
            process,
            self._on_phm_changed,
            tip=T.PHM_PROCESS,
        )
        _set_cell(self._phm_table, r, 2, period, T.PHM_PERIOD)
        _set_cell(self._phm_table, r, 3, timeout, T.PHM_TIMEOUT)
        _set_cell(self._phm_table, r, 4, deadline, T.PHM_DEADLINE)
        onf = on_failure if on_failure in _PHM_ON_FAILURE else "log"
        _set_combo(
            self._phm_table,
            r,
            5,
            _PHM_ON_FAILURE,
            onf,
            self._on_phm_changed,
            tip=T.PHM_ON_FAILURE,
            enum_colors=COLORS_ON_FAILURE,
            item_tips=T.PHM_ON_FAILURE_ITEMS,
        )

    def _refresh_ucm_fg_combo(self, current: str | None = None) -> None:
        want = current if current is not None else self._ucm_fg.currentText()
        ids = self._fg_ids()
        self._ucm_fg.blockSignals(True)
        self._ucm_fg.clear()
        self._ucm_fg.addItems(ids)
        if want in ids:
            self._ucm_fg.setCurrentText(want)
        elif ids:
            self._ucm_fg.setCurrentIndex(0)
        self._ucm_fg.blockSignals(False)

    def _set_proc_active_in_cell(
        self, r: int, fg_id: str, active_in: list[str] | None = None
    ) -> None:
        """Update only the active_in column (no full-row rebuild / signal storms)."""
        states = self._states_for_fg(fg_id)
        self._proc_table.removeCellWidget(r, 3)
        self._proc_table.takeItem(r, 3)
        if self._fg_kind_for_id(fg_id) == "mode" and states:
            cur_list = [str(x) for x in (active_in or []) if str(x).strip()]
            cur = cur_list[0] if cur_list else ""
            if cur not in states:
                cur = states[0]
            _set_combo(
                self._proc_table,
                r,
                3,
                states,
                cur,
                self._on_exec_changed,
                tip=T.PROC_ACTIVE_IN,
            )
        else:
            _set_cell(self._proc_table, r, 3, "n/a · machine", T.PROC_ACTIVE_IN_MACHINE)
            cell = self._proc_table.item(r, 3)
            if cell is not None:
                tipify_item(cell, T.PROC_ACTIVE_IN_MACHINE)
                cell.setFlags(cell.flags() & ~Qt.ItemFlag.ItemIsEditable)
                cell.setForeground(QColor("#37474f"))
                cell.setBackground(QColor("#cfd8dc"))

    def _refresh_proc_fg_options(self) -> None:
        """Refresh FG id lists + active_in options without rebuilding whole rows.

        Rebuilding via _fill_proc_row re-enters _on_exec_changed (combo signals) and
        blows DocHistory deepcopy (RecursionError).
        """
        ids = self._fg_ids()
        for r in range(self._proc_table.rowCount()):
            w = self._proc_table.cellWidget(r, 1)
            if isinstance(w, QComboBox):
                cur = w.currentText()
                w.blockSignals(True)
                w.clear()
                w.addItems(ids)
                if cur in ids:
                    w.setCurrentText(cur)
                elif ids:
                    w.setCurrentIndex(0)
                w.blockSignals(False)
            fg_id = _combo_text(self._proc_table, r, 1) or self._default_fg()
            aw = self._proc_table.cellWidget(r, 3)
            prev = (
                [_combo_text(self._proc_table, r, 3)]
                if isinstance(aw, QComboBox)
                else []
            )
            self._set_proc_active_in_cell(r, fg_id, prev)

