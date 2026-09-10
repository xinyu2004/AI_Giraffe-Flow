"""Platform tab YAML → UI loaders."""

from __future__ import annotations

from typing import Any

from PySide6.QtWidgets import QCheckBox, QComboBox, QSpinBox

from gf_codegen.compose.merge_platform import is_host_platform_process
from gf_config.gui import tips as T
from gf_config.gui.ara_constants import (
    KNOWN_MODULES,
    _COLLECTOR_SOURCES,
    _DEFAULT_ALIVE_PERIOD_MS,
    _DEFAULT_ALIVE_TIMEOUT_MS,
    _DEFAULT_DEADLINE_MS,
    _DEFAULT_EM_ARGS,
    _DEFAULT_MAX_RESTARTS,
    _DID_ACCESS,
    _FG_INITIAL,
    _FORWARD_MODES,
    _LOG_LEVELS,
    _OTA_MODE_ITEMS,
)
from gf_config.gui.ara_widgets import _set_cell, _set_combo
from gf_config.gui.field_ux import (
    COLORS_DID_ACCESS,
    COLORS_LOG_LEVEL,
    apply_spin_value,
    refresh_enum_combo_style,
    set_spin_baseline,
)
from gf_config.i18n import t
from gf_config.validate import ALWAYS_ON_MODULES


class AraLoadMixin:
    """Mixin: ``_load_*`` from ara_cfg docs into widgets."""

    def _load_exec(self, data: dict[str, Any]) -> None:
        self._fg_table.blockSignals(True)
        self._proc_table.blockSignals(True)
        self._fg_table.setRowCount(0)
        for fg in data.get("function_groups") or []:
            if not isinstance(fg, dict):
                continue
            r = self._fg_table.rowCount()
            self._fg_table.insertRow(r)
            states = fg.get("states") or []
            if not isinstance(states, list):
                states = []
            kind = str(fg.get("kind") or "").strip().lower()
            initial = str(fg.get("initial") or "")
            if not kind:
                kind = (
                    "machine"
                    if initial in _FG_INITIAL and not states
                    else ("mode" if states or (initial and initial not in _FG_INITIAL) else "machine")
                )
            self._fill_fg_row(
                r,
                fid=str(fg.get("id") or ""),
                kind=kind,
                initial=initial or ("Running" if kind == "machine" else ""),
                states=[str(x) for x in states],
            )
        self._proc_table.setRowCount(0)
        for p in data.get("processes") or []:
            if not isinstance(p, dict):
                continue
            r = self._proc_table.rowCount()
            self._proc_table.insertRow(r)
            deps = p.get("depends_on") or []
            if not isinstance(deps, list):
                deps = []
            pname = str(p.get("name") or "")
            active = p.get("active_in") or []
            if not isinstance(active, list):
                active = [active] if active else []
            legacy = p.get("drive_park_state")
            if not active and legacy is not None:
                active = [legacy] if not isinstance(legacy, list) else legacy
            self._fill_proc_row(
                r,
                name=pname,
                fg=str(p.get("function_group") or ""),
                deps=[str(x) for x in deps],
                execution_client=(
                    False
                    if is_host_platform_process(pname)
                    else bool(p.get("execution_client", True))
                ),
                active_in=[str(x) for x in active],
            )
        self._fg_table.blockSignals(False)
        self._proc_table.blockSignals(False)
        self._refresh_ucm_fg_combo()

    def _load_em_launch(self, data: dict[str, Any]) -> None:
        self._em_table.blockSignals(True)
        self._em_table.setRowCount(0)
        for p in data.get("processes") or []:
            if not isinstance(p, dict):
                continue
            r = self._em_table.rowCount()
            self._em_table.insertRow(r)
            args = p.get("args")
            if isinstance(args, list):
                args_s = ", ".join(str(x) for x in args)
            elif args is None:
                args_s = ""
            else:
                args_s = str(args)
            if not args_s.strip():
                args_s = _DEFAULT_EM_ARGS
            mr = p.get("max_restarts")
            if mr is None or mr == "":
                mr_s = str(_DEFAULT_MAX_RESTARTS)
            else:
                mr_s = str(mr)
            self._fill_em_row(
                r,
                name=str(p.get("name") or ""),
                binary=str(p.get("binary") or ""),
                args_s=args_s,
                mr_s=mr_s,
            )
        self._em_table.blockSignals(False)

    def _load_phm(self, data: dict[str, Any]) -> None:
        self._phm_table.blockSignals(True)
        self._phm_table.setRowCount(0)
        for e in data.get("entities") or []:
            if not isinstance(e, dict):
                continue
            r = self._phm_table.rowCount()
            self._phm_table.insertRow(r)
            dl = e.get("deadline_ms")
            if dl is None or dl == "":
                dl_s = str(_DEFAULT_DEADLINE_MS)
            else:
                dl_s = str(dl)
            self._fill_phm_row(
                r,
                eid=str(e.get("id") or ""),
                process=str(e.get("process") or ""),
                period=str(e.get("alive_period_ms", _DEFAULT_ALIVE_PERIOD_MS)),
                timeout=str(e.get("alive_timeout_ms", _DEFAULT_ALIVE_TIMEOUT_MS)),
                deadline=dl_s,
                on_failure=str(e.get("on_failure") or "log"),
            )
        self._phm_table.blockSignals(False)

    def _load_diag(self, data: dict[str, Any]) -> None:
        doip = data.get("doip") if isinstance(data.get("doip"), dict) else {}
        standards = data.get("standards") if isinstance(data.get("standards"), dict) else {}
        security = data.get("security") if isinstance(data.get("security"), dict) else {}
        iso14229 = bool(standards.get("iso_14229_uds", True))
        iso13400 = bool(standards.get("iso_13400_doip", doip.get("enabled", False)))
        if iso13400 and not iso14229:
            iso14229 = True
        self._iso_14229.blockSignals(True)
        self._iso_13400.blockSignals(True)
        self._doip_enabled.blockSignals(True)
        self._doip_addr.blockSignals(True)
        self._doip_tester.blockSignals(True)
        self._doip_port.blockSignals(True)
        self._s3_ms.blockSignals(True)
        self._tp_ms.blockSignals(True)
        self._p2_ms.blockSignals(True)
        self._p2star_ms.blockSignals(True)
        self._sec_delay_ms.blockSignals(True)
        self._ota_mode.blockSignals(True)
        self._ota_prog.blockSignals(True)
        self._ota_sec.blockSignals(True)
        self._ota_block.blockSignals(True)
        self._iso_14229.setChecked(iso14229)
        self._iso_13400.setChecked(iso13400 and iso14229)
        self._iso_13400.setEnabled(iso14229)
        self._doip_enabled.setChecked(iso13400 and iso14229)
        self._sec_plugin_path = str(security.get("plugin") or "")
        addr = doip.get("logical_address", "0x0E00")
        if isinstance(addr, int):
            self._doip_addr.setText(hex(addr))
        else:
            self._doip_addr.setText(str(addr or "0x0E00"))
        tester = doip.get("tester_address", "0x0E80")
        if isinstance(tester, int):
            self._doip_tester.setText(hex(tester))
        else:
            self._doip_tester.setText(str(tester or "0x0E80"))
        try:
            doip_port = int(doip.get("tcp_port") or 13400)
        except (TypeError, ValueError):
            doip_port = 13400
        apply_spin_value(self._doip_port, doip_port, as_baseline=True)
        timing = data.get("timing") if isinstance(data.get("timing"), dict) else {}
        xfer = data.get("ota_transfer") if isinstance(data.get("ota_transfer"), dict) else {}
        try:
            apply_spin_value(
                self._s3_ms, int(timing.get("s3_server_ms") or 5000), as_baseline=True
            )
            apply_spin_value(
                self._tp_ms,
                int(timing.get("tester_present_period_ms") or 2000),
                as_baseline=True,
            )
            apply_spin_value(
                self._p2_ms, int(timing.get("p2_server_ms") or 50), as_baseline=True
            )
            apply_spin_value(
                self._p2star_ms,
                int(timing.get("p2_star_server_ms") or 5000),
                as_baseline=True,
            )
            apply_spin_value(
                self._sec_delay_ms,
                int(timing.get("security_delay_ms") or 10000),
                as_baseline=True,
            )
        except (TypeError, ValueError):
            pass
        mode = str(xfer.get("mode") or "request_file_transfer")
        idx = self._ota_mode.findData(mode)
        if idx < 0:
            idx = self._ota_mode.findText(mode)
        self._ota_mode.setCurrentIndex(idx if idx >= 0 else 0)
        self._ota_prog.setChecked(bool(xfer.get("require_programming_session", True)))
        self._ota_sec.setChecked(bool(xfer.get("require_security", True)))
        try:
            ota_block = int(xfer.get("max_block_length") or 1024)
        except (TypeError, ValueError):
            ota_block = 1024
        apply_spin_value(self._ota_block, ota_block, as_baseline=True)
        self._iso_14229.blockSignals(False)
        self._iso_13400.blockSignals(False)
        self._doip_enabled.blockSignals(False)
        self._doip_addr.blockSignals(False)
        self._doip_tester.blockSignals(False)
        self._doip_port.blockSignals(False)
        self._s3_ms.blockSignals(False)
        self._tp_ms.blockSignals(False)
        self._p2_ms.blockSignals(False)
        self._p2star_ms.blockSignals(False)
        self._sec_delay_ms.blockSignals(False)
        self._ota_mode.blockSignals(False)
        self._ota_prog.blockSignals(False)
        self._ota_sec.blockSignals(False)
        self._ota_block.blockSignals(False)
        refresh_enum_combo_style(self._ota_mode)

        self._did_table.blockSignals(True)
        self._did_table.setRowCount(0)
        for d in data.get("dids") or []:
            if not isinstance(d, dict):
                continue
            r = self._did_table.rowCount()
            self._did_table.insertRow(r)
            did = d.get("id", "")
            _set_cell(
                self._did_table,
                r,
                0,
                hex(did) if isinstance(did, int) else str(did),
                T.DID_ID,
            )
            _set_cell(self._did_table, r, 1, str(d.get("name") or ""), T.DID_NAME)
            access = str(d.get("access") or "read")
            if access not in _DID_ACCESS:
                access = "read"
            _set_combo(
                self._did_table,
                r,
                2,
                _DID_ACCESS,
                access,
                self._on_diag_changed,
                tip=T.DID_ACCESS,
                enum_colors=COLORS_DID_ACCESS,
                item_tips=T.DID_ACCESS_ITEMS,
            )
            _set_cell(
                self._did_table,
                r,
                3,
                str(d.get("size") if d.get("size") is not None else "0"),
                T.DID_SIZE,
            )
        self._did_table.blockSignals(False)

        self._rid_table.blockSignals(True)
        self._rid_table.setRowCount(0)
        for d in data.get("rids") or []:
            if not isinstance(d, dict):
                continue
            r = self._rid_table.rowCount()
            self._rid_table.insertRow(r)
            rid = d.get("id", "")
            _set_cell(self._rid_table, r, 0, hex(rid) if isinstance(rid, int) else str(rid))
            _set_cell(self._rid_table, r, 1, str(d.get("name") or ""))
        self._rid_table.blockSignals(False)

    def _load_log(self, data: dict[str, Any]) -> None:
        self._log_level.blockSignals(True)
        self._log_level.setCurrentText(str(data.get("default_level") or "INFO"))
        self._log_level.blockSignals(False)
        refresh_enum_combo_style(self._log_level)

        sinks = data.get("sinks") or []
        if not isinstance(sinks, list):
            sinks = []
        sink_set = {str(s).strip().lower() for s in sinks}
        # Legacy: stdout/stderr ⇒ console
        if "stdout" in sink_set or "stderr" in sink_set:
            sink_set.add("console")
        for cb, name in (
            (self._log_sink_console, "console"),
            (self._log_sink_file, "file"),
            (self._log_sink_dlt, "dlt"),
        ):
            cb.blockSignals(True)
            cb.setChecked(name in sink_set if sink_set else name in ("console", "dlt"))
            cb.blockSignals(False)
        dlt = data.get("dlt") if isinstance(data.get("dlt"), dict) else {}
        app_id = str(dlt.get("app_id") or data.get("dlt_app_id") or "GFAP")[:4]
        self._log_dlt_app.blockSignals(True)
        self._log_dlt_app.setText(app_id or "GFAP")
        self._log_dlt_app.blockSignals(False)
        try:
            fmax = int(data.get("file_max_bytes") or 1_048_576)
        except (TypeError, ValueError):
            fmax = 1_048_576
        apply_spin_value(self._log_file_max, max(4096, fmax), as_baseline=True)

        self._ctx_table.blockSignals(True)
        self._ctx_table.setRowCount(0)
        mods = [m for m in KNOWN_MODULES if m not in ALWAYS_ON_MODULES] + ["app"]
        for c in data.get("contexts") or []:
            if not isinstance(c, dict):
                continue
            r = self._ctx_table.rowCount()
            self._ctx_table.insertRow(r)
            cid = str(c.get("id") or "").strip()
            if not cid:
                continue
            if cid not in mods:
                mods = mods + [cid]
            _set_combo(
                self._ctx_table,
                r,
                0,
                mods,
                cid,
                self._on_log_changed,
                tip=T.LOG_CTX_ID,
            )
            level = str(c.get("level") or "INFO")
            if level not in _LOG_LEVELS:
                level = "INFO"
            _set_combo(
                self._ctx_table,
                r,
                1,
                _LOG_LEVELS,
                level,
                self._on_log_changed,
                tip=T.LOG_CTX_LEVEL,
                enum_colors=COLORS_LOG_LEVEL,
                item_tips=T.LOG_LEVEL_ITEMS,
            )
        self._ctx_table.blockSignals(False)
        if self._ctx_table.rowCount():
            self._ctx_table.selectRow(0)

    def _load_ucm(self, data: dict[str, Any]) -> None:
        self._ucm_enabled.blockSignals(True)
        self._ucm_source.blockSignals(True)
        self._ucm_rollback.blockSignals(True)
        self._ucm_enabled.setChecked(bool(data.get("enabled", False)))
        self._ucm_source.setText(str(data.get("package_source") or ""))
        self._refresh_ucm_fg_combo(str(data.get("function_group") or "MachineFG"))
        self._ucm_rollback.setChecked(bool(data.get("allow_rollback", True)))
        self._ucm_enabled.blockSignals(False)
        self._ucm_source.blockSignals(False)
        self._ucm_rollback.blockSignals(False)

    def _load_collector(self, data: dict[str, Any]) -> None:
        fwd = str(data.get("forward") or "local_store")
        idx = self._col_forward.findText(fwd)
        self._col_forward.blockSignals(True)
        self._col_forward.setCurrentIndex(idx if idx >= 0 else 0)
        self._col_forward.blockSignals(False)
        refresh_enum_combo_style(self._col_forward)
        srcs = {str(x) for x in (data.get("sources") or [])}
        for name, cb in self._src_boxes.items():
            cb.blockSignals(True)
            cb.setChecked(name in srcs if srcs else name in ("phm", "process", "com"))
            cb.blockSignals(False)
        local = data.get("local") if isinstance(data.get("local"), dict) else {}
        self._col_local_en.blockSignals(True)
        self._col_local_en.setChecked(bool(local.get("enabled", True)))
        self._col_local_en.blockSignals(False)
        try:
            col_max = int(local.get("max_entries") or 256)
        except (TypeError, ValueError):
            col_max = 256
        try:
            col_deb = int(local.get("debounce_max_keys") or 64)
        except (TypeError, ValueError):
            col_deb = 64
        try:
            col_store = int(local.get("store_max_bytes") or 1_048_576)
        except (TypeError, ValueError):
            col_store = 1_048_576
        apply_spin_value(self._col_max, col_max, as_baseline=True)
        apply_spin_value(self._col_deb_keys, col_deb, as_baseline=True)
        apply_spin_value(self._col_store_max, col_store, as_baseline=True)

    def _load_bounds(self, data: dict[str, Any]) -> None:
        dlt = data.get("dlt") if isinstance(data.get("dlt"), dict) else {}
        com = data.get("com") if isinstance(data.get("com"), dict) else {}
        per = data.get("per") if isinstance(data.get("per"), dict) else {}
        diag = data.get("diag") if isinstance(data.get("diag"), dict) else {}
        dids = diag.get("dids") if isinstance(diag.get("dids"), dict) else {}
        budget = data.get("budget") if isinstance(data.get("budget"), dict) else {}

        def _set(spin: QSpinBox, val: object, default: int) -> None:
            try:
                v = int(val if val is not None else default)
            except (TypeError, ValueError):
                v = default
            apply_spin_value(spin, v, as_baseline=True)

        _set(self._bnd_dlt_ctx, dlt.get("max_contexts"), 64)
        _set(self._bnd_com_depth, com.get("queue_depth"), 16)
        _set(self._bnd_com_keys, com.get("max_topic_keys"), 64)
        _set(self._bnd_com_avg, com.get("avg_payload_bytes"), 256)
        _set(self._bnd_per_keys, per.get("max_keys"), 1024)
        _set(self._bnd_per_val, per.get("max_value_bytes"), 65536)
        _set(self._bnd_rx, diag.get("rx_max_bytes"), 65536)
        _set(self._bnd_did_n, dids.get("max_entries"), 256)
        _set(self._bnd_did_pay, dids.get("max_payload"), 4096)
        _set(self._bnd_bud_ram, budget.get("ram_bytes"), 0)
        _set(self._bnd_bud_disk, budget.get("disk_bytes"), 0)

        diag_plat = self._session.get_ara_doc("diag") if self._session else {}
        doip = diag_plat.get("doip") if isinstance(diag_plat.get("doip"), dict) else {}
        if doip.get("rx_max_bytes") is not None:
            _set(self._bnd_rx, doip.get("rx_max_bytes"), 65536)

        iox = data.get("iceoryx") if isinstance(data.get("iceoryx"), dict) else {}
        mgmt = iox.get("mgmt") if isinstance(iox.get("mgmt"), dict) else {}
        _set(self._iox_pub, mgmt.get("max_publishers"), 32)
        _set(self._iox_sub, mgmt.get("max_subscribers"), 64)
        _set(self._iox_sub_per_pub, mgmt.get("max_subscribers_per_publisher"), 8)
        _set(self._iox_hist, mgmt.get("max_publisher_history"), 4)
        _set(self._iox_chunk_pub, mgmt.get("max_chunks_allocated_per_publisher"), 2)
        _set(self._iox_chunk_sub, mgmt.get("max_chunks_held_per_subscriber"), 16)
        _set(self._iox_iface, mgmt.get("max_interface_number"), 2)
        _set(self._iox_bud_shm, iox.get("budget_shm_bytes"), 0)
        pools = iox.get("mempools") if isinstance(iox.get("mempools"), list) else []
        self._iox_pool_table.blockSignals(True)
        self._iox_pool_table.setRowCount(0)
        if not pools:
            pools = [
                {"size": 256, "count": 128},
                {"size": 1024, "count": 64},
                {"size": 4096, "count": 32},
            ]
        for p in pools:
            if not isinstance(p, dict):
                continue
            r = self._iox_pool_table.rowCount()
            self._iox_pool_table.insertRow(r)
            _set_cell(self._iox_pool_table, r, 0, str(p.get("size") or 256))
            _set_cell(self._iox_pool_table, r, 1, str(p.get("count") or 1))
        self._iox_pool_table.blockSignals(False)

