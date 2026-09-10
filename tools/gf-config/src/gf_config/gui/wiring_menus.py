"""Context menus, search, and edge focus for the wiring canvas."""

from __future__ import annotations

from typing import Any

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QGraphicsItem,
    QLabel,
    QLineEdit,
    QListWidgetItem,
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
    """Mixin: canvas/card/edge menus, fuzzy search, focus helpers."""

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
        act_reset = menu.addAction(t("重置连线路径"))
        act_del = menu.addAction(t("删除信号线"))
        chosen = menu.exec(global_pos)
        if chosen is act_edit:
            self.edit_edge(edge)
        elif chosen is act_reset:
            if self._session:
                self._session.set_flow_route(edge.flow, None)
            else:
                edge.flow.pop("route", None)
            edge.update_path()
            self.changed.emit()
        elif chosen is act_del:
            self._remove_edge(edge)

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
        if edge in self._edges:
            idx = self._edges.index(edge)
            self._flow_list.blockSignals(True)
            self._flow_list.setCurrentRow(idx)
            self._flow_list.blockSignals(False)
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
        if edge in self._channel_edges:
            idx = len(self._edges) + self._channel_edges.index(edge)
            self._flow_list.blockSignals(True)
            self._flow_list.setCurrentRow(idx)
            self._flow_list.blockSignals(False)
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
        if miss in self._missing:
            for i in range(self._flow_list.count()):
                it = self._flow_list.item(i)
                if it is None:
                    continue
                data = it.data(Qt.ItemDataRole.UserRole)
                if data and data[0] == "missing" and data[1] == self._missing.index(miss):
                    self._flow_list.blockSignals(True)
                    self._flow_list.setCurrentRow(i)
                    self._flow_list.blockSignals(False)
                    break
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

    @staticmethod
    def _fuzzy_match(query: str, *parts: str) -> bool:
        hay = " ".join(parts).lower()
        q = query.lower().strip()
        if not q:
            return True
        if q in hay:
            return True
        # subsequence fuzzy: characters of query appear in order
        i = 0
        for ch in hay:
            if i < len(q) and ch == q[i]:
                i += 1
        if i == len(q):
            return True
        return all(tok in hay for tok in q.split())

    def _on_search_text(self, text: str) -> None:
        self._search_hits.clear()
        q = text.strip()
        if not q:
            self._search_hits.setVisible(False)
            return
        hits: list[tuple[str, str, int]] = []  # label, kind, index
        for i, e in enumerate(self._edges):
            if self._fuzzy_match(
                q, short_service(e.service), e.src.process_name, e.dst.process_name, e.service
            ):
                hits.append(
                    (
                        f"{short_service(e.service)}:  {e.src.process_name}  →  {e.dst.process_name}",
                        "edge",
                        i,
                    )
                )
        for i, e in enumerate(self._channel_edges):
            if self._fuzzy_match(
                q, e.slot, e.src.process_name, e.dst.process_name
            ):
                hits.append(
                    (
                        f"[GfChannel] {e.slot}:  {e.src.process_name}  →  {e.dst.process_name}",
                        "channel",
                        i,
                    )
                )
        for i, m in enumerate(self._missing):
            if self._fuzzy_match(
                q, short_service(m.service), m.src.process_name, m.dst.process_name, m.service
            ):
                hits.append(
                    (
                        f"[缺失] {short_service(m.service)}:  {m.src.process_name}  →  {m.dst.process_name}",
                        "missing",
                        i,
                    )
                )
        if not hits:
            item = QListWidgetItem("（无匹配）")
            item.setFlags(Qt.ItemFlag.NoItemFlags)
            self._search_hits.addItem(item)
        else:
            for label, kind, idx in hits[:50]:
                item = QListWidgetItem(label)
                item.setData(Qt.ItemDataRole.UserRole, (kind, idx))
                self._search_hits.addItem(item)
        self._search_hits.setVisible(True)

    def _on_search_hit_clicked(self, item: QListWidgetItem) -> None:
        data = item.data(Qt.ItemDataRole.UserRole)
        if not data:
            return
        kind, idx = data
        if kind == "edge" and 0 <= idx < len(self._edges):
            self._focus_edge(self._edges[idx])
        elif kind == "channel" and 0 <= idx < len(self._channel_edges):
            self._focus_channel_edge(self._channel_edges[idx])
        elif kind == "missing" and 0 <= idx < len(self._missing):
            self._focus_missing(self._missing[idx])
        elif kind == "peer" and 0 <= idx < len(self._peers):
            self._focus_peer(self._peers[idx])

    def edit_edge(self, edge: EdgeCurve) -> None:
        if not self._session:
            return
        dlg = QDialog(self)
        dlg.setWindowTitle(t("编辑信号"))
        form = QFormLayout(dlg)
        form.addRow(t("源"), QLabel(edge.src.process_name))
        form.addRow(t("目的"), QLabel(edge.dst.process_name))
        svc = QLineEdit(edge.service)
        form.addRow("service", svc)
        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(dlg.accept)
        buttons.rejected.connect(dlg.reject)
        form.addRow(buttons)
        if dlg.exec() != QDialog.DialogCode.Accepted:
            return
        new_svc = canon_service(svc.text())
        if not new_svc:
            return
        old_short = short_service(edge.service)
        frm = edge.src.process_name
        to = edge.dst.process_name
        flows = self._session.dataflows()
        for f in flows:
            if (
                str(f.get("from")) == frm
                and str(f.get("to")) == to
                and short_service(str(f.get("service") or "")) == old_short
            ):
                f["service"] = new_svc
        self._session.set_dataflows(flows)
        new_prov = [
            new_svc if short_service(p) == old_short else p for p in edge.src.provides
        ]
        new_req = [
            new_svc if short_service(r) == old_short else r for r in edge.dst.requires
        ]
        self._session.upsert_deployment(
            frm,
            provides=[canon_service(x) for x in new_prov],
            requires=[canon_service(x) for x in edge.src.requires],
        )
        self._session.upsert_deployment(
            to,
            provides=[canon_service(x) for x in edge.dst.provides],
            requires=[canon_service(x) for x in new_req],
        )
        self.rebuild()
        self.changed.emit()

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
            return
        row = self._flow_list.currentRow()
        item = self._flow_list.item(row) if row >= 0 else None
        if item is not None:
            data = item.data(Qt.ItemDataRole.UserRole)
            if data and data[0] == "edge" and 0 <= data[1] < len(self._edges):
                self._remove_edge(self._edges[data[1]])
                return
            if data and data[0] == "channel" and 0 <= data[1] < len(self._channel_edges):
                self._remove_channel_edge(self._channel_edges[data[1]])
                return
            if data and data[0] == "missing" and 0 <= data[1] < len(self._missing):
                self.ignore_missing_edge(self._missing[data[1]])
                return
        if 0 <= row < len(self._edges):
            self._remove_edge(self._edges[row])

    def show_card_menu(self, card: ProcessCard, global_pos) -> None:  # type: ignore[no-untyped-def]
        menu = QMenu(self)
        if card.is_external():
            act_del = menu.addAction(t("Delete external MCU"))
            chosen = menu.exec(global_pos)
            if chosen is act_del:
                self.delete_node(card)
            return
        if card.is_frame_ingest():
            act_edit = menu.addAction(t("编辑 frame_ingest…"))
            act_del = menu.addAction(t("删除 frame_ingest"))
            chosen = menu.exec(global_pos)
            if chosen is act_edit:
                self.edit_frame_ingest(card)
            elif chosen is act_del:
                self.delete_node(card)
            return
        act_edit = menu.addAction(t("编辑端口…"))
        act_import = menu.addAction(t("从此模块导入 hpp…"))
        menu.addSeparator()
        act_del = menu.addAction(t("删除模块"))
        chosen = menu.exec(global_pos)
        if chosen is act_edit:
            self.edit_ports(card)
        elif chosen is act_import:
            self.import_hpp(default_process=card.process_name)
        elif chosen is act_del:
            self.delete_node(card)

