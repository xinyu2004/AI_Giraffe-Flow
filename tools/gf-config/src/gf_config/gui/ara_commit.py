"""Platform tab UI → session commits (update_ara_doc)."""

from __future__ import annotations

from typing import Any

from PySide6.QtWidgets import QComboBox, QLineEdit, QSpinBox

from gf_codegen.compose.mem_budget import mem_section_gates
from gf_codegen.compose.merge_platform import is_host_platform_process
from gf_config.gui.ara_constants import (
    _DEFAULT_ALIVE_PERIOD_MS,
    _DEFAULT_ALIVE_TIMEOUT_MS,
    _DEFAULT_DEADLINE_MS,
    _DEFAULT_EM_ARGS,
    _DEFAULT_MAX_RESTARTS,
    _DID_ACCESS,
    _FG_INITIAL,
    _LOG_LEVELS,
    _PHM_ON_FAILURE,
)
from gf_config.gui.ara_widgets import _cell, _combo_text, _int_or_default, _int_or_none
from gf_config.gui.field_ux import multi_selected, string_list_values


class AraCommitMixin:
    """Mixin: ``_on_*_changed`` writers for AraCfgEditor."""

    def _mark(self, key: str) -> None:
        """Notify UI after an ara write. Dirty flags come from ``update_ara_doc``."""
        if self._loading or not self._session:
            return
        self.changed.emit()

    def _on_exec_changed(self, *_a: object) -> None:
        if self._loading or not self._session:
            return
        if getattr(self, "_exec_change_guard", False):
            return
        self._exec_change_guard = True
        try:
            self._on_exec_changed_body()
        finally:
            self._exec_change_guard = False

    def _on_exec_changed_body(self) -> None:
        coalesce = self._coalesce_sender()
        self._checkpoint(coalesce=coalesce)
        fgs: list[dict[str, Any]] = []
        for r in range(self._fg_table.rowCount()):
            fid = _cell(self._fg_table, r, 0)
            if not fid:
                continue
            kind = (_combo_text(self._fg_table, r, 1) or "machine").strip().lower()
            if kind not in ("machine", "mode"):
                kind = "machine"
            if kind == "machine":
                initial = _combo_text(self._fg_table, r, 2) or "Running"
                if initial not in _FG_INITIAL:
                    initial = "Running"
                fgs.append({"id": fid, "kind": kind, "initial": initial})
            else:
                states = string_list_values(self._fg_table, r, 3)
                initial = (_combo_text(self._fg_table, r, 2) or _cell(self._fg_table, r, 2) or "").strip()
                if initial and initial not in states and states:
                    initial = states[0]
                if not initial and states:
                    initial = states[0]
                entry: dict[str, Any] = {
                    "id": fid,
                    "kind": kind,
                    "initial": initial or (states[0] if states else "ModeActive"),
                }
                if states:
                    entry["states"] = states
                fgs.append(entry)
        # Keep EC column in sync when process name flips to/from host.*
        self._proc_table.blockSignals(True)
        try:
            for r in range(self._proc_table.rowCount()):
                name = _combo_text(self._proc_table, r, 0)
                if not name:
                    continue
                is_daemon = is_host_platform_process(name)
                has_combo = self._proc_table.cellWidget(r, 4) is not None
                if is_daemon and has_combo:
                    self._set_proc_execution_client_cell(r, name, False)
                elif (not is_daemon) and (not has_combo):
                    self._set_proc_execution_client_cell(r, name, True)
        finally:
            self._proc_table.blockSignals(False)

        procs: list[dict[str, Any]] = []
        for r in range(self._proc_table.rowCount()):
            name = _combo_text(self._proc_table, r, 0)
            if not name:
                continue
            deps = multi_selected(self._proc_table, r, 2)
            fg_id = _combo_text(self._proc_table, r, 1) or self._default_fg()
            aw = self._proc_table.cellWidget(r, 3)
            active_one = _combo_text(self._proc_table, r, 3) if isinstance(aw, QComboBox) else ""
            if is_host_platform_process(name):
                ec = False
            else:
                ec_s = (_combo_text(self._proc_table, r, 4) or "true").lower()
                ec = ec_s not in ("false", "0", "no")
            row: dict[str, Any] = {
                "name": name,
                "function_group": fg_id,
                "depends_on": deps,
                "execution_client": ec,
            }
            if (
                self._fg_kind_for_id(fg_id) == "mode"
                and active_one
                and not active_one.startswith("n/a")
            ):
                row["active_in"] = [active_one]
            procs.append(row)
        self._session.update_ara_doc(
            "exec", function_groups=fgs, processes=procs
        )
        self._refresh_proc_fg_options()
        self._refresh_ucm_fg_combo()
        self._mark("exec")
        if not coalesce:
            self._end_doc_edit()

    def _on_em_launch_changed(self, *_a: object) -> None:
        if self._loading or not self._session:
            return
        coalesce = self._coalesce_sender()
        self._checkpoint(coalesce=coalesce)
        procs: list[dict[str, Any]] = []
        for r in range(self._em_table.rowCount()):
            name = _combo_text(self._em_table, r, 0)
            binary = _cell(self._em_table, r, 1)
            if not name:
                continue
            args_raw = _cell(self._em_table, r, 2).replace(",", " ")
            args = [x for x in args_raw.split() if x]
            if not args:
                args = [_DEFAULT_EM_ARGS]
            entry: dict[str, Any] = {
                "name": name,
                "binary": binary,
                "args": args,
            }
            mr_s = _cell(self._em_table, r, 3)
            try:
                entry["max_restarts"] = int(mr_s, 0) if mr_s else _DEFAULT_MAX_RESTARTS
            except ValueError:
                entry["max_restarts"] = _DEFAULT_MAX_RESTARTS
            procs.append(entry)
        self._session.update_ara_doc("em_launch", processes=procs)
        self._mark("em_launch")
        if not coalesce:
            self._end_doc_edit()

    def _on_phm_changed(self, *_a: object) -> None:
        if self._loading or not self._session:
            return
        coalesce = self._coalesce_sender()
        self._checkpoint(coalesce=coalesce)
        entities: list[dict[str, Any]] = []
        for r in range(self._phm_table.rowCount()):
            eid = _cell(self._phm_table, r, 0)
            if not eid:
                continue
            period = _int_or_default(
                _cell(self._phm_table, r, 2), _DEFAULT_ALIVE_PERIOD_MS
            )
            timeout = _int_or_default(
                _cell(self._phm_table, r, 3), _DEFAULT_ALIVE_TIMEOUT_MS
            )
            deadline = _int_or_default(
                _cell(self._phm_table, r, 4), _DEFAULT_DEADLINE_MS
            )
            onf = _combo_text(self._phm_table, r, 5) or "log"
            if onf not in _PHM_ON_FAILURE:
                onf = "log"
            entities.append(
                {
                    "id": eid,
                    "process": _combo_text(self._phm_table, r, 1),
                    "alive_period_ms": period,
                    "alive_timeout_ms": timeout,
                    "deadline_ms": deadline,
                    "on_failure": onf,
                }
            )
        self._session.update_ara_doc("phm", entities=entities)
        self._mark("phm")
        if not coalesce:
            self._end_doc_edit()

    def _on_iso_14229_toggled(self, checked: bool) -> None:
        if self._loading:
            return
        if not checked:
            self._iso_13400.blockSignals(True)
            self._doip_enabled.blockSignals(True)
            self._iso_13400.setChecked(False)
            self._doip_enabled.setChecked(False)
            self._iso_13400.blockSignals(False)
            self._doip_enabled.blockSignals(False)
        self._iso_13400.setEnabled(checked)
        self._on_diag_changed()

    def _on_iso_13400_toggled(self, checked: bool) -> None:
        if self._loading:
            return
        if checked and not self._iso_14229.isChecked():
            self._iso_14229.blockSignals(True)
            self._iso_14229.setChecked(True)
            self._iso_14229.blockSignals(False)
            self._iso_13400.setEnabled(True)
        self._doip_enabled.blockSignals(True)
        self._doip_enabled.setChecked(checked)
        self._doip_enabled.blockSignals(False)
        self._on_diag_changed()

    def _on_doip_enabled_toggled(self, checked: bool) -> None:
        if self._loading:
            return
        if checked and not self._iso_14229.isChecked():
            self._iso_14229.blockSignals(True)
            self._iso_14229.setChecked(True)
            self._iso_14229.blockSignals(False)
        self._iso_13400.blockSignals(True)
        self._iso_13400.setChecked(checked)
        self._iso_13400.blockSignals(False)
        self._iso_13400.setEnabled(self._iso_14229.isChecked())
        self._on_diag_changed()

    def _on_diag_changed(self, *_a: object) -> None:
        if self._loading or not self._session:
            return
        coalesce = self._coalesce_sender()
        self._checkpoint(coalesce=coalesce)
        try:
            addr = _int_or_none(self._doip_addr.text())
            if addr is None:
                addr = 0x0E00
        except ValueError:
            addr = 0x0E00
        try:
            tester = _int_or_none(self._doip_tester.text())
            if tester is None:
                tester = 0x0E80
        except ValueError:
            tester = 0x0E80
        dids: list[dict[str, Any]] = []
        for r in range(self._did_table.rowCount()):
            did = _cell(self._did_table, r, 0)
            if not did:
                continue
            access = _combo_text(self._did_table, r, 2) or "read"
            if access not in _DID_ACCESS:
                access = "read"
            entry: dict[str, Any] = {
                "id": did,
                "name": _cell(self._did_table, r, 1),
                "access": access,
            }
            size_s = _cell(self._did_table, r, 3) or "0"
            if size_s:
                try:
                    entry["size"] = int(size_s, 0)
                except ValueError:
                    entry["size"] = size_s
            dids.append(entry)
        rids: list[dict[str, Any]] = []
        for r in range(self._rid_table.rowCount()):
            rid = _cell(self._rid_table, r, 0)
            if not rid:
                continue
            rids.append({"id": rid, "name": _cell(self._rid_table, r, 1)})
        iso14229 = self._iso_14229.isChecked()
        iso13400 = self._iso_13400.isChecked() and iso14229
        prev = self._session.get_ara_doc("diag")
        prev_doip = prev.get("doip") if isinstance(prev.get("doip"), dict) else {}
        rx_max = prev_doip.get("rx_max_bytes", 65536)
        if hasattr(self, "_bnd_rx"):
            rx_max = int(self._bnd_rx.value())
        self._session.update_ara_doc(
            "diag",
            standards={
                "iso_14229_uds": iso14229,
                "iso_13400_doip": iso13400,
            },
            # 保留 GMT OTA 写入的 plugin 路径，本页不编辑
            security={"plugin": getattr(self, "_sec_plugin_path", "") or ""},
            doip={
                "enabled": iso13400,
                "logical_address": addr,
                "tester_address": tester,
                "tcp_port": int(self._doip_port.value()),
                "rx_max_bytes": int(rx_max),
            },
            timing={
                "s3_server_ms": int(self._s3_ms.value()),
                "tester_present_period_ms": int(self._tp_ms.value()),
                "p2_server_ms": int(self._p2_ms.value()),
                "p2_star_server_ms": int(self._p2star_ms.value()),
                "security_delay_ms": int(self._sec_delay_ms.value()),
            },
            ota_transfer={
                "mode": str(
                    self._ota_mode.currentData() or "request_file_transfer"
                ),
                "require_programming_session": self._ota_prog.isChecked(),
                "require_security": self._ota_sec.isChecked(),
                "max_block_length": int(self._ota_block.value()),
            },
            dids=dids,
            rids=rids,
        )
        self._mark("diag")
        self._refresh_mem_estimate()
        if not coalesce:
            self._end_doc_edit()

    def _on_log_changed(self, *_a: object) -> None:
        if self._loading or not self._session:
            return
        coalesce = self._coalesce_sender()
        self._checkpoint(coalesce=coalesce)
        contexts: list[dict[str, Any]] = []
        for r in range(self._ctx_table.rowCount()):
            cid = _combo_text(self._ctx_table, r, 0) or _cell(self._ctx_table, r, 0)
            if not cid:
                continue
            level = _combo_text(self._ctx_table, r, 1) or "INFO"
            if level not in _LOG_LEVELS:
                level = "INFO"
            contexts.append({"id": cid, "level": level})
        sinks: list[str] = []
        if self._log_sink_console.isChecked():
            sinks.append("console")
        if self._log_sink_file.isChecked():
            sinks.append("file")
        if self._log_sink_dlt.isChecked():
            sinks.append("dlt")
        if not sinks:
            sinks = ["console"]
        app_id = (self._log_dlt_app.text().strip() or "GFAP")[:4]
        self._session.update_ara_doc(
            "log",
            default_level=self._log_level.currentText().strip() or "INFO",
            contexts=contexts,
            sinks=sinks,
            dlt={"app_id": app_id},
            file_max_bytes=int(self._log_file_max.value()),
        )
        self._mark("log")
        self._refresh_mem_estimate()
        # DLT sink changes host catalog in pickers; tables are not auto-mutated.
        self.sync_capability_hosts()
        if not coalesce:
            self._end_doc_edit()

    def _refresh_process_name_combos(self) -> None:
        """Reload name dropdowns when wiring / capability catalog changes."""
        for table, col, on_change in (
            (self._proc_table, 0, self._on_exec_changed),
            (self._em_table, 0, self._on_em_launch_changed),
            (self._phm_table, 1, self._on_phm_changed),
        ):
            for r in range(table.rowCount()):
                w = table.cellWidget(r, col)
                if not isinstance(w, QComboBox):
                    continue
                cur = w.currentText()
                if table is self._phm_table:
                    opts = list(self._process_names())
                    if cur and cur not in opts:
                        opts = [cur] + opts
                else:
                    opts = self._name_picker_options(cur)
                existing = [w.itemText(i) for i in range(w.count())]
                if existing == opts and w.currentText() == cur:
                    continue
                w.blockSignals(True)
                w.clear()
                w.addItems(opts)
                if cur in opts:
                    w.setCurrentText(cur)
                elif opts:
                    w.setCurrentIndex(0)
                w.blockSignals(False)

    def _on_ucm_changed(self, *_a: object) -> None:
        if self._loading or not self._session:
            return
        coalesce = self._coalesce_sender()
        self._checkpoint(coalesce=coalesce)
        self._session.update_ara_doc(
            "ucm",
            enabled=self._ucm_enabled.isChecked(),
            package_source=self._ucm_source.text().strip(),
            function_group=self._ucm_fg.currentText().strip() or "MachineFG",
            allow_rollback=self._ucm_rollback.isChecked(),
        )
        self._mark("ucm")
        if not coalesce:
            self._end_doc_edit()

    def _on_collector_changed(self, *_a: object) -> None:
        if self._loading or not self._session:
            return
        coalesce = self._coalesce_sender()
        self._checkpoint(coalesce=coalesce)
        self._session.update_ara_doc(
            "collector",
            forward=self._col_forward.currentText().strip() or "local_store",
            sources=[n for n, cb in self._src_boxes.items() if cb.isChecked()],
            local={
                "enabled": self._col_local_en.isChecked(),
                "max_entries": int(self._col_max.value()),
                "debounce_max_keys": int(self._col_deb_keys.value()),
                "store_max_bytes": int(self._col_store_max.value()),
            },
        )
        self._mark("collector")
        self._refresh_mem_estimate()
        if not coalesce:
            self._end_doc_edit()

    def _on_bounds_changed(self, *_a: object) -> None:
        if self._loading or not self._session:
            return
        coalesce = self._coalesce_sender()
        self._checkpoint(coalesce=coalesce)
        fields: dict[str, Any] = {
            "dlt": {"max_contexts": int(self._bnd_dlt_ctx.value())},
            "com": {
                "queue_depth": int(self._bnd_com_depth.value()),
                "max_topic_keys": int(self._bnd_com_keys.value()),
                "avg_payload_bytes": int(self._bnd_com_avg.value()),
            },
            "per": {
                "max_keys": int(self._bnd_per_keys.value()),
                "max_value_bytes": int(self._bnd_per_val.value()),
            },
            "diag": {
                "rx_max_bytes": int(self._bnd_rx.value()),
                "dids": {
                    "max_entries": int(self._bnd_did_n.value()),
                    "max_payload": int(self._bnd_did_pay.value()),
                },
            },
            "budget": {
                "ram_bytes": int(self._bnd_bud_ram.value()),
                "disk_bytes": int(self._bnd_bud_disk.value()),
            },
        }
        pools: list[dict[str, Any]] = []
        for r in range(self._iox_pool_table.rowCount()):
            try:
                size = int(_cell(self._iox_pool_table, r, 0) or "0")
                count = int(_cell(self._iox_pool_table, r, 1) or "0")
            except ValueError:
                continue
            if size > 0 and count > 0:
                pools.append({"size": size, "count": count})
        # Persist iceoryx only while binding is on; keep last yaml when gated off.
        req = self._session.req if isinstance(self._session.req, dict) else {}
        if mem_section_gates(req).get("iceoryx"):
            fields["iceoryx"] = {
                "mgmt": {
                    "max_publishers": int(self._iox_pub.value()),
                    "max_subscribers": int(self._iox_sub.value()),
                    "max_subscribers_per_publisher": int(self._iox_sub_per_pub.value()),
                    "max_publisher_history": int(self._iox_hist.value()),
                    "max_chunks_allocated_per_publisher": int(self._iox_chunk_pub.value()),
                    "max_chunks_held_per_subscriber": int(self._iox_chunk_sub.value()),
                    "max_interface_number": int(self._iox_iface.value()),
                },
                "mempools": pools
                or [
                    {"size": 256, "count": 128},
                    {"size": 1024, "count": 64},
                    {"size": 4096, "count": 32},
                ],
                "budget_shm_bytes": int(self._iox_bud_shm.value()),
            }
        self._session.update_ara_doc("bounds", **fields)
        self._mark("bounds")

        # diag.rx lives on bounds page when diag module is on (same cap as DoIP).
        if mem_section_gates(req).get("diag"):
            prev_diag = self._session.get_ara_doc("diag")
            doip = dict(prev_diag.get("doip") or {}) if isinstance(prev_diag.get("doip"), dict) else {}
            doip["rx_max_bytes"] = int(self._bnd_rx.value())
            self._session.update_ara_doc("diag", doip=doip)
            self._mark("diag")

        self._refresh_mem_estimate()
        if not coalesce:
            self._end_doc_edit()

