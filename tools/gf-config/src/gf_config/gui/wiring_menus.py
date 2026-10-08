"""Context menus and edge focus for the wiring canvas."""

from __future__ import annotations

from typing import Any

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QGraphicsItem,
    QInputDialog,
    QLabel,
    QMenu,
    QMessageBox,
)

from gf_config.core import canon_service, is_channel_svc, short_service
from gf_config.gui.wiring_graph_items import (
    ChannelEdge,
    EdgeCurve,
    MissingEdge,
    McuPeerLink,
    ProcessCard,
    _qt_alive,
)
from gf_config.i18n import t


class WiringMenusMixin:
    """Mixin: canvas/card/edge menus and focus helpers."""

    def _on_view_context_menu(self, pos) -> None:  # type: ignore[no-untyped-def]
        scene_pos = self._view.mapToScene(pos)
        item = self._scene.itemAt(scene_pos, self._view.transform())
        cur: QGraphicsItem | None = item
        while cur is not None:
            if isinstance(cur, EdgeCurve):
                self.show_edge_menu(cur, self._view.mapToGlobal(pos))
                return
            if isinstance(cur, ChannelEdge):
                self.show_channel_edge_menu(cur, self._view.mapToGlobal(pos))
                return
            if isinstance(cur, MissingEdge):
                self.show_missing_menu(cur, self._view.mapToGlobal(pos))
                return
            if isinstance(cur, ProcessCard):
                self.show_card_menu(cur, self._view.mapToGlobal(pos))
                return
            cur = cur.parentItem()

        menu = QMenu(self)
        act_add = menu.addAction(t("添加模块…"))
        act_cam = menu.addAction(t("添加 frame_ingest…"))
        act_ext = menu.addAction(t("添加外部 MCU…"))
        act_ext.setEnabled(self._show_external_mcu())
        if not self._show_external_mcu():
            act_ext.setToolTip(
                t(
                    "当前拓扑为仅 AP。请先改为「AP + MCU CP」；"
                    "对外控制信号可挂在 gateway 端口上。"
                )
            )
        act_import = menu.addAction(t("导入 hpp/h…"))
        chosen = menu.exec(self._view.mapToGlobal(pos))
        if chosen is act_add:
            self.add_node()
        elif chosen is act_cam:
            self.add_frame_ingest()
        elif chosen is act_ext:
            self.add_external_mcu_node()
        elif chosen is act_import:
            self.import_hpp()

    def show_edge_menu(self, edge: EdgeCurve, global_pos) -> None:  # type: ignore[no-untyped-def]
        edge.setSelected(True)
        menu = QMenu(self)
        act_edit = menu.addAction(t("编辑信号名…"))
        act_fields = menu.addAction(t("查看类型…"))
        act_reset = menu.addAction(t("重置连线路径"))
        act_del = menu.addAction(t("删除信号线"))
        chosen = menu.exec(global_pos)
        if chosen is act_edit:
            self.edit_edge(edge)
        elif chosen is act_fields:
            self.inspect_type(edge.service)
        elif chosen is act_reset:
            if self._session:
                self._session.set_flow_route(edge.flow, None)
            else:
                edge.flow.pop("route", None)
            edge.update_path()
            self.changed.emit()
        elif chosen is act_del:
            self._remove_edge(edge)

    def edit_edge(self, edge: EdgeCurve) -> None:
        """Rename the dataflow service (canvas mid-label)."""
        if not self._session:
            return
        old = short_service(edge.service)
        text, ok = QInputDialog.getText(
            self, t("编辑信号名…"), t("信号名"), text=old
        )
        if not ok:
            return
        new = str(text).strip()
        if not new:
            QMessageBox.warning(self, t("编辑信号名…"), t("信号名不能为空"))
            return
        if short_service(new) == old:
            return
        new_short = short_service(canon_service(new))
        for f in self._session.dataflows():
            if (
                str(f.get("from") or "") == edge.src.process_name
                and str(f.get("to") or "") == edge.dst.process_name
                and short_service(str(f.get("service") or "")) == new_short
            ):
                QMessageBox.information(self, t("编辑信号名…"), t("该 dataflow 已存在"))
                return
        self._session.rename_dataflow_service(edge.flow, new)
        self.rebuild()
        self.changed.emit()

    def inspect_type(self, service: str) -> None:
        from gf_config.gui.wiring_dialogs import show_type_tree

        fields: list[Any] = []
        if self._session:
            fields = self._session.lookup_type_fields(service)
        show_type_tree(short_service(service), fields, self)

    def show_channel_edge_menu(self, edge: ChannelEdge, global_pos) -> None:  # type: ignore[no-untyped-def]
        edge.setSelected(True)
        menu = QMenu(self)
        act_del = menu.addAction(t("删除 GfChannel 边"))
        chosen = menu.exec(global_pos)
        if chosen is act_del:
            self._remove_channel_edge(edge)

    def show_missing_menu(self, miss: MissingEdge, global_pos) -> None:  # type: ignore[no-untyped-def]
        miss.setSelected(True)
        menu = QMenu(self)
        act_fix = menu.addAction(t("补上连线（写入 dataflow）"))
        act_ignore = menu.addAction(t("忽略此建议（不再显示）"))
        act_drop = menu.addAction(t("移除目标 In 端口（不再需要该输入）"))
        chosen = menu.exec(global_pos)
        if chosen is act_fix:
            self.fix_missing_edge(miss)
        elif chosen is act_ignore:
            self.ignore_missing_edge(miss)
        elif chosen is act_drop:
            self.drop_missing_require(miss)

    def fix_missing_edge(self, miss: MissingEdge) -> None:
        if not self._session:
            return
        ok = self._session.add_dataflow(
            miss.src.process_name,
            miss.service,
            miss.dst.process_name,
        )
        if not ok:
            QMessageBox.information(self, t("补线"), t("该 dataflow 已存在"))
            return
        self.rebuild()
        self.changed.emit()

    def ignore_missing_edge(self, miss: MissingEdge) -> None:
        """Suppress a suggested provider→consumer pair (require may already be met via another hop)."""
        if not self._session:
            return
        key = (
            f"{miss.src.process_name}|{short_service(miss.service)}|{miss.dst.process_name}"
        )
        ui = self._session.node_ui(miss.dst.process_name)
        ignored = list(ui.get("ignore_missing") or [])
        if key not in ignored:
            ignored.append(key)
        self._session.set_node_ui(miss.dst.process_name, ignore_missing=ignored)
        self.rebuild()
        self.changed.emit()

    def drop_missing_require(self, miss: MissingEdge) -> None:
        """Remove the In port that caused the unsatisfied/suggested missing edge."""
        if not self._session:
            return
        dst = miss.dst.process_name
        svc = short_service(miss.service)
        card = self._nodes.get(dst)
        if not card:
            return
        new_req = [r for r in card.requires if short_service(r) != svc]
        self._session.set_ports(dst, list(card.provides), new_req)
        self.rebuild()
        self.changed.emit()

    def _focus_edge(self, edge: EdgeCurve, *, select: bool = True, center: bool = True) -> None:
        if select:
            self._scene.blockSignals(True)
            self._scene.clearSelection()
            edge.setSelected(True)
            self._scene.blockSignals(False)
        for e in self._edges:
            e.set_visual_state(
                highlight=(e is edge),
                dimmed=(e is not edge),
                role="",
            )
        for e in self._channel_edges:
            e.set_visual_state(highlight=False, dimmed=True, role="")
        for m in self._missing:
            m.set_visual_state(highlight=False, dimmed=True)
        for card in self._nodes.values():
            hit = card is edge.src or card is edge.dst
            card.set_visual_state(emphasis=hit, dimmed=not hit)
        # 确保品红路径点出现（选中态 + 已入 scene）
        if _qt_alive(edge):
            edge.update_path()
        self.relayout_edge_labels()
        if center:
            self._view.centerOn(edge)

    def _focus_channel_edge(
        self, edge: ChannelEdge, *, select: bool = True, center: bool = True
    ) -> None:
        if select:
            self._scene.blockSignals(True)
            self._scene.clearSelection()
            edge.setSelected(True)
            self._scene.blockSignals(False)
        for e in self._edges:
            e.set_visual_state(highlight=False, dimmed=True, role="")
        for e in self._channel_edges:
            e.set_visual_state(
                highlight=(e is edge),
                dimmed=(e is not edge),
                role="",
            )
        for m in self._missing:
            m.set_visual_state(highlight=False, dimmed=True)
        for card in self._nodes.values():
            hit = card is edge.src or card is edge.dst
            card.set_visual_state(emphasis=hit, dimmed=not hit)
        self.relayout_edge_labels()
        if center:
            self._view.centerOn(edge)

    def _focus_missing(self, miss: MissingEdge, *, select: bool = True, center: bool = True) -> None:
        if select:
            self._scene.blockSignals(True)
            self._scene.clearSelection()
            miss.setSelected(True)
            self._scene.blockSignals(False)
        for e in self._edges:
            e.set_visual_state(highlight=False, dimmed=True)
        for e in self._channel_edges:
            e.set_visual_state(highlight=False, dimmed=True, role="")
        for m in self._missing:
            m.set_visual_state(highlight=(m is miss), dimmed=(m is not miss))
        for card in self._nodes.values():
            hit = card is miss.src or card is miss.dst
            card.set_visual_state(emphasis=hit, dimmed=not hit)
        if center:
            self._view.centerOn(miss)

    def _focus_peer(self, peer: McuPeerLink, *, select: bool = True, center: bool = True) -> None:
        if select:
            self._scene.blockSignals(True)
            self._scene.clearSelection()
            peer.setSelected(True)
            self._scene.blockSignals(False)
        for e in self._edges:
            e.set_visual_state(highlight=False, dimmed=True, role="")
        for e in self._channel_edges:
            e.set_visual_state(highlight=False, dimmed=True, role="")
        for m in self._missing:
            m.set_visual_state(highlight=False, dimmed=True)
        for p in self._peers:
            p.set_visual_state(highlight=(p is peer), dimmed=(p is not peer))
        for card in self._nodes.values():
            hit = card is peer.mcu or card is peer.gateway
            card.set_visual_state(emphasis=hit, dimmed=not hit)
        if center:
            self._view.centerOn(peer)

    def show_peer_menu(self, peer: McuPeerLink, global_pos) -> None:  # type: ignore[no-untyped-def]
        menu = QMenu(self)
        act_focus_mcu = menu.addAction(t("Select MCU"))
        act_focus_gw = menu.addAction(t("Select gateway"))
        chosen = menu.exec(global_pos)
        if chosen is act_focus_mcu:
            self._scene.clearSelection()
            peer.mcu.setSelected(True)
        elif chosen is act_focus_gw:
            self._scene.clearSelection()
            peer.gateway.setSelected(True)

    def _remove_edge(self, edge: EdgeCurve) -> None:
        if not self._session:
            return
        self._push_undo()
        target = edge.flow
        flows = self._session.dataflows()
        new_flows = [f for f in flows if f is not target]
        if len(new_flows) == len(flows):
            new_flows = [f for f in flows if f != target]
        self._session.set_dataflows(new_flows)
        self.rebuild()
        self.changed.emit()

    def _remove_channel_edge(self, edge: ChannelEdge) -> None:
        if not self._session:
            return
        self._push_undo()
        self._session.remove_channel_flow_match(
            edge.src.process_name,
            edge.dst.process_name,
            slot=edge.slot,
        )
        self.rebuild()
        self.changed.emit()

    def _delete_selection(self) -> None:
        channels = [i for i in self._scene.selectedItems() if isinstance(i, ChannelEdge)]
        if channels:
            self._remove_channel_edge(channels[0])
            return
        edges = [i for i in self._scene.selectedItems() if isinstance(i, EdgeCurve)]
        if edges:
            self._remove_edge(edges[0])
            return
        missing = [i for i in self._scene.selectedItems() if isinstance(i, MissingEdge)]
        if missing:
            self.ignore_missing_edge(missing[0])
            return
        cards = [i for i in self._scene.selectedItems() if isinstance(i, ProcessCard)]
        if cards:
            self.delete_node(cards[0])

    def show_card_menu(self, card: ProcessCard, global_pos) -> None:  # type: ignore[no-untyped-def]
        menu = QMenu(self)
        if card.is_external():
            act_color = menu.addAction(t("节点颜色…"))
            act_del = menu.addAction(t("Delete external MCU"))
            chosen = menu.exec(global_pos)
            if chosen is act_color:
                self.edit_node_color(card)
            elif chosen is act_del:
                self.delete_node(card)
            return
        if card.is_frame_ingest():
            act_color = menu.addAction(t("节点颜色…"))
            act_edit = menu.addAction(t("编辑 frame_ingest…"))
            act_del = menu.addAction(t("删除 frame_ingest"))
            chosen = menu.exec(global_pos)
            if chosen is act_color:
                self.edit_node_color(card)
            elif chosen is act_edit:
                self.edit_frame_ingest(card)
            elif chosen is act_del:
                self.delete_node(card)
            return
        act_color = menu.addAction(t("节点颜色…"))
        act_edit = menu.addAction(t("编辑端口…"))
        act_import = menu.addAction(t("从此模块导入 hpp…"))
        menu.addSeparator()
        act_del = menu.addAction(t("删除模块"))
        chosen = menu.exec(global_pos)
        if chosen is act_color:
            self.edit_node_color(card)
        elif chosen is act_edit:
            self.edit_ports(card)
        elif chosen is act_import:
            self.import_hpp(default_process=card.process_name)
        elif chosen is act_del:
            self.delete_node(card)

