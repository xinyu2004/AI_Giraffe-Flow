"""Node CRUD, frame_ingest, ports dialog, hpp/fidl import."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from PySide6.QtWidgets import QDialog, QFileDialog, QMessageBox

from gf_config.core import ProjectSession, canon_service, is_channel_svc, short_service
from gf_config.gui.wiring_dialogs import (
    AddNodeDialog,
    FrameIngestDialog,
    ImportPortsDialog,
    NodeColorDialog,
    PortEditDialog,
)
from gf_config.gui.wiring_graph_items import ProcessCard, _qt_alive
from gf_config.i18n import t


class WiringNodesMixin:
    """Mixin: add/edit/delete processes, frame_ingest, import ports."""

    def add_node(self) -> None:
        if not self._session:
            return
        dlg = AddNodeDialog(self)
        if dlg.exec() != QDialog.DialogCode.Accepted:
            return
        name, domain = dlg.values()
        if not name:
            return
        if name in self._nodes:
            QMessageBox.warning(self, t("添加模块"), t("已存在：{name}").format(name=name))
            return
        self._push_undo()
        self._session.upsert_deployment(name, compute_domain=domain, provides=[], requires=[])
        self.rebuild(fit_view=True)
        self._persist_authored_node_paint(name)
        self.changed.emit()

    def add_frame_ingest(self) -> None:
        """Add optional host.frame_ingest canvas node (not a deployment)."""
        if not self._session:
            return
        name = ProjectSession.FRAME_INGEST_PROCESS
        if name in self._nodes or any(
            c.is_frame_ingest() for c in self._nodes.values() if _qt_alive(c)
        ):
            QMessageBox.information(
                self,
                t("frame_ingest"),
                t("已存在视频契约节点。请双击 {name} 编辑。").format(name=name),
            )
            self.edit_frame_ingest(self._nodes.get(name))
            return
        fi = dict(self._session.frame_ingest_cfg())
        slots = list(self._session.camera_slots())
        if not slots:
            slots = [{"id": "front", "w": 640, "h": 480}]
        if str(fi.get("active_source") or "none") == "none":
            fi = {**fi, "active_source": "isp"}
        dlg = FrameIngestDialog(
            fi,
            slots,
            parent=self,
            channel_policies=self._session.publish_policy_channels(),
            channel_names=self._session.channel_policy_names(),
        )
        if dlg.exec() != QDialog.DialogCode.Accepted:
            return
        self._push_undo()
        fields, new_slots = dlg.result_config()
        self._apply_frame_ingest(fields, new_slots, seed_fcm=True)
        self._session.apply_channel_publish_policies(dlg.result_channel_policies())
        self.rebuild(fit_view=True)
        self._persist_authored_node_paint(name)
        self.changed.emit()

    def edit_frame_ingest(self, card: ProcessCard | None = None) -> None:
        if not self._session:
            return
        fi = dict(self._session.frame_ingest_cfg())
        slots = list(self._session.camera_slots())
        name = ProjectSession.FRAME_INGEST_PROCESS
        ui = self._session.get_node_ui(name)
        dlg = FrameIngestDialog(
            fi,
            slots,
            parent=self,
            channel_policies=self._session.publish_policy_channels(),
            channel_names=self._session.channel_policy_names(),
            color_hex=str(ui.get("color") or ""),
            color_user=bool(ui.get("color_user")),
        )
        if dlg.exec() != QDialog.DialogCode.Accepted:
            return
        self._push_undo()
        fields, new_slots = dlg.result_config()
        self._apply_frame_ingest(fields, new_slots, seed_fcm=False)
        self._session.apply_channel_publish_policies(dlg.result_channel_policies())
        action, hex_c = dlg.result_color_action()
        if action == "auto":
            self._session.clear_node_ui_keys(name, "color", "color_user")
        elif action == "user":
            self._session.set_node_ui(name, color=hex_c, color_user=True)
        self.rebuild()
        self.changed.emit()

    def _apply_frame_ingest(
        self,
        fields: dict[str, Any],
        slots: list[dict[str, Any]],
        *,
        seed_fcm: bool,
    ) -> None:
        assert self._session is not None
        self._session.migrate_legacy_camera_channel_flows()
        old_ids = {str(s.get("id")) for s in self._session.camera_slots()}
        new_ids = {str(s.get("id")) for s in slots if str(s.get("id") or "").strip()}
        # Preserve SIL paths / camera_transport from prior req
        prev = self._session.frame_ingest_cfg()
        merged = dict(prev)
        merged.update(fields)
        if isinstance(prev.get("paths"), dict) and "paths" not in fields:
            merged["paths"] = prev["paths"]
        legacy_transport = prev.get("camera_transport")
        if legacy_transport and "camera_transport" not in fields:
            merged["camera_transport"] = legacy_transport
        for k, v in merged.items():
            if k == "camera_slots":
                continue
            self._session.update_frame_ingest(**{k: v})
        self._session.set_camera_slots(slots)
        # Drop channel_flows for removed lane ids
        for sid in old_ids - new_ids:
            slot = ProjectSession.gf_channel_slot_name(sid)
            for fl in list(self._session.channel_flows()):
                if str(fl.get("slot") or "") == slot:
                    self._session.remove_channel_flow_match(
                        str(fl.get("from") or ""),
                        str(fl.get("to") or ""),
                        slot=slot,
                    )
        name = ProjectSession.FRAME_INGEST_PROCESS
        ui = self._session.node_ui(name)
        x = float(ui["x"]) if "x" in ui else -80.0
        y = float(ui["y"]) if "y" in ui else -320.0
        # Preserve authored out_side / port_sides / slot order when editing slots.
        fields_ui: dict[str, Any] = {
            "kind": "frame_ingest",
            "label": str(ui.get("label") or "frame_ingest"),
            "x": x,
            "y": y,
        }
        if "out_side" not in ui:
            fields_ui["out_side"] = "right"
        if "in_side" not in ui:
            fields_ui["in_side"] = "left"
        self._session.set_node_ui(name, **fields_ui)
        self._layout_pos[name] = (x, y)
        if seed_fcm and not self._session.channel_flows():
            self._session.seed_default_channel_flows()

    def add_external_mcu_node(self) -> None:
        """Add external MCU boundary node (VehicleBus / Trajectory via gateway)."""
        if not self._session:
            return
        if not self._show_external_mcu():
            QMessageBox.information(
                self,
                t("外部 MCU"),
                t(
                    "当前拓扑为「仅 AP（无 MCU）」，不显示 MCU 节点。\n"
                    "请先在 SKU 将拓扑改为「AP + MCU CP」。\n"
                    "对外控制信号（如 VehicleBus / Trajectory）可直接挂在 gateway 等模块端口上。"
                ),
            )
            return
        name = "external.vehicle_mcu"
        if name in self._nodes:
            QMessageBox.information(self, t("外部节点"), t("已存在：{name}").format(name=name))
            return
        self._push_undo()
        self._session.upsert_deployment(
            name,
            compute_domain="external",
            provides=["services.semantic.VehicleBus"],
            requires=["services.semantic.DrivingTrajectory"],
        )
        self._session.set_node_ui(
            name,
            kind="external",
            label="MCU",
            out_side="right",
            in_side="left",
            x=-280.0,
            y=120.0,
        )
        # link to gateway if present
        gw = "adapter.vehicle_can_gateway"
        deps = {str(d.get("process")) for d in self._session.deployments()}
        if gw in deps:
            self._session.add_dataflow(name, "services.semantic.VehicleBus", gw)
            self._session.add_dataflow(gw, "services.semantic.DrivingTrajectory", name)
            # ensure gateway ports
            for d in self._session.deployments():
                if str(d.get("process")) != gw:
                    continue
                prov = [str(x) for x in (d.get("provides") or [])]
                req = [str(x) for x in (d.get("requires") or [])]
                if not any(short_service(x) == "DrivingTrajectory" for x in prov):
                    prov.append("services.semantic.DrivingTrajectory")
                if not any(short_service(x) == "VehicleBus" for x in req):
                    req.append("services.semantic.VehicleBus")
                if not any(short_service(x) == "DrivingTrajectory" for x in req):
                    req.append("services.semantic.DrivingTrajectory")
                self._session.set_ports(gw, prov, req)
                break
        self.rebuild(fit_view=True)
        self._persist_authored_node_paint(name)
        self.changed.emit()
        QMessageBox.information(self, t("external MCU"), t("已添加 {name}").format(name=name))

    def _persist_authored_node_paint(self, name: str) -> None:
        """User added this node: keep this frame's colour/pose as authored UI."""
        if not self._session:
            return
        ui = self._session.get_node_ui(name)
        fields: dict[str, Any] = {}
        qc = getattr(self, "_process_color_map", {}).get(name)
        if qc is not None and not ui.get("color_user") and not ui.get("color"):
            fields["color"] = qc.name()
        card = self._nodes.get(name)
        if card is not None and _qt_alive(card):
            p = card.pos()
            if "x" not in ui:
                fields["x"] = round(p.x(), 1)
            if "y" not in ui:
                fields["y"] = round(p.y(), 1)
        if fields:
            self._session.set_node_ui(name, **fields)

    def flush_canvas(self) -> None:
        """Write back authored canvas fields only. Paint defaults are not authors.

        ``set_node_ui`` skips None (never deletes). Missing keys stay missing.
        """
        if not self._session:
            return
        for name, card in self._nodes.items():
            if not _qt_alive(card):
                continue
            ui = self._session.get_node_ui(name)
            if not ui:
                continue
            p = card.pos()
            fields: dict[str, Any] = {}
            if "x" in ui or "y" in ui:
                nx = round(float(p.x()), 1)
                ny = round(float(p.y()), 1)
                ox = round(float(ui["x"]), 1) if "x" in ui else nx
                oy = round(float(ui["y"]), 1) if "y" in ui else ny
                if nx != ox or ny != oy:
                    fields["x"] = nx
                    fields["y"] = ny
            if "out_side" in ui and card.out_side != ui.get("out_side"):
                fields["out_side"] = card.out_side
            if "in_side" in ui and card.in_side != ui.get("in_side"):
                fields["in_side"] = card.in_side
            # port_sides / port_slot_order are written at relocate time.
            # Paint may infer extra slots — never flush those back.
            if "kind" in ui and card.kind and card.kind != "process":
                if card.kind != ui.get("kind"):
                    fields["kind"] = card.kind
            if "label" in ui and card.label and card.label != ui.get("label"):
                fields["label"] = card.label
            if fields:
                self._session.set_node_ui(name, **fields)

    def delete_node(self, card: ProcessCard) -> None:
        if not self._session:
            return
        if card.is_frame_ingest():
            reply = QMessageBox.question(
                self,
                t("删除 frame_ingest"),
                t(
                    "删除视频契约节点？\n"
                    "将清空 camera_slots / channel_flows，并把 active_source 设为 none。"
                ),
            )
            if reply != QMessageBox.StandardButton.Yes:
                return
            self._push_undo()
            self._session.remove_frame_ingest_node()
            self.rebuild()
            self.changed.emit()
            return
        reply = QMessageBox.question(
            self,
            t("删除模块"),
            t("删除 {name} 及其相关 dataflows？").format(name=card.process_name),
        )
        if reply != QMessageBox.StandardButton.Yes:
            return
        self._push_undo()
        # Also drop GfChannel edges into this process
        for fl in list(self._session.channel_flows()):
            if str(fl.get("to")) == card.process_name or str(fl.get("from")) == card.process_name:
                self._session.remove_channel_flow_match(
                    str(fl.get("from") or ""),
                    str(fl.get("to") or ""),
                    slot=str(fl.get("slot") or ""),
                )
        self._session.remove_deployment(card.process_name)
        self.rebuild()
        self.changed.emit()

    def _port_candidates(self, process: str) -> list[str]:
        if not self._session:
            return []
        names: list[str] = []
        for svc in self._session.wiring_service_names():
            short = short_service(svc)
            if short and short not in names:
                names.append(short)
        for card in self._nodes.values():
            for s in card.provides + card.requires:
                short = short_service(s)
                if short and short not in names:
                    names.append(short)
        return names

    def edit_node_color(self, card: ProcessCard) -> None:
        """Context menu / external double-click: colour only."""
        if not self._session:
            return
        name = card.process_name
        ui = self._session.get_node_ui(name)
        dlg = NodeColorDialog(
            name,
            str(ui.get("color") or ""),
            color_user=bool(ui.get("color_user")),
            parent=self,
        )
        if dlg.exec() != QDialog.DialogCode.Accepted:
            return
        if not self._apply_color_action(name, dlg.result_action()):
            return
        self.rebuild()
        self.changed.emit()

    def _apply_color_action(self, name: str, action_hex: tuple[str, str | None]) -> bool:
        """Apply colour bar result. Returns False if nothing to write (keep)."""
        assert self._session is not None
        action, hex_c = action_hex
        if action == "keep":
            return False
        self._push_undo()
        if action == "auto":
            self._session.clear_node_ui_keys(name, "color", "color_user")
        else:
            self._session.set_node_ui(name, color=hex_c, color_user=True)
        return True

    def edit_ports(self, card: ProcessCard) -> None:
        if not self._session:
            return
        if card.is_external():
            QMessageBox.information(
                self,
                t("external MCU"),
                t("画布上无端口可编辑（边界节点仅连 gateway）。"),
            )
            return
        if card.is_frame_ingest():
            self.edit_frame_ingest(card)
            return
        soa_prov = [p for p in card.provides if not is_channel_svc(p)]
        soa_req = [r for r in card.requires if not is_channel_svc(r)]
        ui = self._session.get_node_ui(card.process_name)
        dlg = PortEditDialog(
            card.process_name,
            soa_prov,
            soa_req,
            self._port_candidates(card.process_name),
            self,
            out_policies=self._session.publish_policy_services(),
            color_hex=str(ui.get("color") or ""),
            color_user=bool(ui.get("color_user")),
            lookup_fields=self._session.lookup_type_fields,
        )
        if dlg.exec() != QDialog.DialogCode.Accepted:
            return
        self._push_undo()
        provides, requires = dlg.result_ports()
        self._session.set_ports(card.process_name, provides, requires)
        self._session.apply_out_publish_policies(dlg.result_out_policies())
        self._session.prune_orphan_publish_policies()
        action, hex_c = dlg.result_color_action()
        if action == "auto":
            self._session.clear_node_ui_keys(
                card.process_name, "color", "color_user"
            )
        elif action == "user":
            self._session.set_node_ui(
                card.process_name, color=hex_c, color_user=True
            )
        self.rebuild()
        self.changed.emit()

    def import_hpp(self, default_process: str = "") -> None:
        if not self._session:
            return
        path, _ = QFileDialog.getOpenFileName(
            self,
            t("选择头文件"),
            str(self._session.paths.project_dir),
            "C/C++ Headers (*.hpp *.h);;All (*)",
        )
        if not path:
            return
        hpp_path = Path(path)
        try:
            structs = self._session.parse_hpp_structs(hpp_path)
        except Exception as exc:  # noqa: BLE001
            QMessageBox.critical(self, t("解析失败"), str(exc))
            return
        candidates = [str(s["name"]) for s in structs if s.get("name")]
        if not candidates:
            QMessageBox.information(self, t("导入"), t("未解析到 struct，请检查头文件格式"))
            return
        self._apply_import_candidates(
            candidates,
            default_process,
            source_path=hpp_path,
            kind="hpp",
            title=t("从头文件添加端口"),
            hint=t("勾选要加入的类型（作为 service 短名）："),
            structs=structs,
        )

    def import_fidl(self, default_process: str = "") -> None:
        if not self._session:
            return
        path, _ = QFileDialog.getOpenFileName(
            self,
            t("选择 FIDL"),
            str(self._session.paths.project_dir),
            "Franca IDL (*.fidl);;All (*)",
        )
        if not path:
            return
        fidl_path = Path(path)
        try:
            candidates = self._session.parse_fidl_candidates(fidl_path)
        except Exception as exc:  # noqa: BLE001
            QMessageBox.critical(self, t("解析失败"), str(exc))
            return
        if not candidates:
            QMessageBox.information(
                self,
                t("导入"),
                t("未解析到 interface/struct/method/broadcast，请检查 .fidl 格式"),
            )
            return
        self._apply_import_candidates(
            candidates,
            default_process,
            source_path=fidl_path,
            kind="fidl",
            title=t("从 FIDL 添加端口"),
            hint=t("勾选要加入的名称（struct / broadcast / method / interface）："),
        )

    def _apply_import_candidates(
        self,
        candidates: list[str],
        default_process: str,
        *,
        source_path: Path,
        kind: str,
        title: str,
        hint: str,
        structs: list[dict[str, Any]] | None = None,
    ) -> None:
        assert self._session is not None
        procs = sorted(self._nodes.keys())
        if not procs:
            QMessageBox.information(self, t("导入"), t("请先添加至少一个模块"))
            return
        default = default_process if default_process in procs else procs[0]
        dlg = ImportPortsDialog(
            candidates,
            procs,
            default,
            self,
            title=title,
            hint=hint,
            structs=structs,
        )
        if dlg.exec() != QDialog.DialogCode.Accepted:
            return
        process, names, direction = dlg.selected()
        if not names:
            return

        rel = self._session.relpath_from_repo(source_path)
        if kind == "fidl":
            n_types = self._session.ingest_fidl_structs(
                self._session.parse_fidl_structs(source_path), source=rel
            )
        else:
            n_types = self._session.ingest_hpp_structs(
                list(structs or []), source=rel
            )

        card = self._nodes.get(process)
        provides = list(card.provides) if card else []
        requires = list(card.requires) if card else []
        for n in names:
            svc = canon_service(n)
            if direction == "out":
                if short_service(svc) not in {short_service(x) for x in provides}:
                    provides.append(svc)
            else:
                if short_service(svc) not in {short_service(x) for x in requires}:
                    requires.append(svc)
        self._session.set_ports(process, provides, requires)
        self.rebuild()
        self.changed.emit()
        QMessageBox.information(
            self,
            t("导入完成"),
            t(
                "已写入 cfg/types.yaml（{n_types} 个类型）\n"
                "向 {process} 添加了 {n} 个{direction} 端口。\n"
                "可双击模块继续调整，再从 Out 拖到 In 连线。"
            ).format(
                n_types=n_types,
                process=process,
                n=len(names),
                direction=direction,
            ),
        )

