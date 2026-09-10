"""Wire-drag and Ctrl+port relocate for the wiring canvas."""

from __future__ import annotations

from typing import Any

from PySide6.QtCore import QPointF, QRectF, Qt
from PySide6.QtGui import QBrush, QColor, QCursor, QFont, QPen
from PySide6.QtWidgets import (
    QApplication,
    QGraphicsItem,
    QGraphicsLineItem,
    QGraphicsSimpleTextItem,
    QGraphicsView,
    QMessageBox,
)

from gf_config.core import (
    ProjectSession,
    canon_service,
    is_channel_svc,
    normalize_channel_slot,
    short_service,
)
from gf_config.gui.cursors import port_move_cursor, wire_link_cursor
from gf_config.gui.wiring_graph_items import (
    PortItem,
    ProcessCard,
    _norm_side,
    _qt_alive,
    port_label,
    port_link_key,
)
from gf_config.i18n import t


class WiringInteractionMixin:
    """Mixin: begin/finish wire + port side/order relocate."""

    def refresh_port_hover_cursor(self) -> None:
        """Ctrl press/release while hovering a port → swap link vs move cursor."""
        if self._wire_src is not None or self._reloc_port is not None:
            return
        gp = QCursor.pos()
        vp = self._view.viewport().mapFromGlobal(gp)
        if not self._view.viewport().rect().contains(vp):
            return
        item = self._view.itemAt(vp)
        cur: QGraphicsItem | None = item
        while cur is not None:
            if isinstance(cur, PortItem) and _qt_alive(cur):
                mods = QApplication.queryKeyboardModifiers()
                cur.setCursor(
                    port_move_cursor()
                    if mods & Qt.KeyboardModifier.ControlModifier
                    else wire_link_cursor()
                )
                return
            cur = cur.parentItem()

    def _set_wire_forbid_mark(self, scene_pos: QPointF | None) -> None:
        """Illegal drop: red ✕ near apex (keep hand cursor — no ForbiddenCursor)."""
        mark = self._wire_forbid_mark
        if scene_pos is None:
            if mark is not None and _qt_alive(mark):
                mark.hide()
            return
        if mark is None or not _qt_alive(mark):
            mark = QGraphicsSimpleTextItem("✕")
            font = QFont()
            font.setPointSize(22)
            font.setBold(True)
            mark.setFont(font)
            mark.setBrush(QBrush(QColor("#c0392b")))
            mark.setZValue(200)
            mark.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIgnoresTransformations, True)
            self._scene.addItem(mark)
            self._wire_forbid_mark = mark
        mark.setPos(scene_pos.x() + 10, scene_pos.y() - 28)
        mark.show()

    def _clear_wire_forbid_mark(self) -> None:
        mark = self._wire_forbid_mark
        self._wire_forbid_mark = None
        if mark is not None and _qt_alive(mark) and mark.scene():
            self._scene.removeItem(mark)

    def _port_at(self, scene_pos: QPointF) -> PortItem | None:
        """Nearest PortItem near scene_pos (fat pick), skipping wire preview."""
        r = float(PortItem.HIT)
        rect = QRectF(scene_pos.x() - r, scene_pos.y() - r, 2 * r, 2 * r)
        best: PortItem | None = None
        best_d = 1e18
        for item in self._scene.items(rect):
            if item is self._wire_line:
                continue
            cur: QGraphicsItem | None = item
            port: PortItem | None = None
            while cur is not None:
                if isinstance(cur, PortItem):
                    port = cur
                    break
                cur = cur.parentItem()
            if port is None or not _qt_alive(port):
                continue
            c = port.scene_center()
            d = (c.x() - scene_pos.x()) ** 2 + (c.y() - scene_pos.y()) ** 2
            if d < best_d:
                best_d = d
                best = port
        return best

    def begin_wire(self, src_port: PortItem) -> None:
        self.cancel_port_relocate()
        self.cancel_wire()
        self._wire_src = src_port
        self._view.setDragMode(QGraphicsView.DragMode.NoDrag)
        # Override beats PortItem hover cursors for the whole drag.
        self._push_app_cursor(wire_link_cursor())
        line = QGraphicsLineItem()
        line.setPen(QPen(QColor("#f7dc6f"), 2.0, Qt.PenStyle.DashLine))
        line.setZValue(100)
        line.setAcceptedMouseButtons(Qt.MouseButton.NoButton)
        c = src_port.scene_center()
        line.setLine(c.x(), c.y(), c.x(), c.y())
        self._scene.addItem(line)
        self._wire_line = line

    def update_wire_preview(self, scene_pos: QPointF) -> None:
        if self._wire_src is None or self._wire_line is None:
            return
        c = self._wire_src.scene_center()
        self._wire_line.setLine(c.x(), c.y(), scene_pos.x(), scene_pos.y())
        target = self._port_at(scene_pos)
        src = self._wire_src
        if target is None:
            ok: bool | None = None  # blank = searching
        else:
            ok = self._wire_pair_ok(src, target)
        # Legal → green; illegal → red dash + ✕; searching → yellow dash. Cursor stays hand.
        if ok is True:
            pen = QPen(QColor("#2ecc71"), 2.5, Qt.PenStyle.SolidLine)
        elif ok is False:
            pen = QPen(QColor("#c0392b"), 2.8, Qt.PenStyle.DashLine)
        else:
            pen = QPen(QColor("#f7dc6f"), 2.0, Qt.PenStyle.DashLine)
        self._wire_line.setPen(pen)
        self._set_wire_forbid_mark(scene_pos if ok is False else None)

    def _wire_pair_ok(self, src: PortItem, target: PortItem) -> bool:
        if target is src or target.card is src.card:
            return False
        if target.direction == src.direction:
            return False
        out_port = src if src.direction == "out" else target
        in_port = target if src.direction == "out" else src
        out_cam = out_port.card.is_frame_ingest()
        in_cam = in_port.card.is_frame_ingest()
        if out_cam and in_cam:
            return False
        if in_cam:
            return False  # frame_ingest 只出不进
        if out_cam:
            return not in_port.card.is_external()
        if out_port.card.is_external() or in_port.card.is_external():
            return True
        # SOA: Out→In；禁止把 GfChannel 口当普通服务边混连
        if is_channel_svc(out_port.service) or is_channel_svc(in_port.service):
            return out_cam  # only frame_ingest Out owns channel svc
        return True

    def finish_wire(self, scene_pos: QPointF) -> None:
        src = self._wire_src
        # hit-test before cancel clears the preview line
        target = self._port_at(scene_pos)
        self.cancel_wire()
        if src is None or not self._session:
            return
        if target is None or not self._wire_pair_ok(src, target):
            return

        out_port = src if src.direction == "out" else target
        in_port = target if src.direction == "out" else src

        # GfChannel: frame_ingest Out → consumer（不写 dataflows / deployments）
        if out_port.card.is_frame_ingest():
            slot = (out_port.service or "").strip()
            if not is_channel_svc(slot):
                sid = ProjectSession.slot_id_from_camera_process(
                    out_port.card.process_name
                )
                slot = ProjectSession.gf_channel_slot_name(sid)
            self._push_undo()
            ok = self._session.add_channel_flow(
                out_port.card.process_name,
                in_port.card.process_name,
                slot=slot,
            )
            if not ok:
                QMessageBox.information(self, t("连线"), t("该 GfChannel 边已存在"))
                return
            self.rebuild()
            self.changed.emit()
            return

        self._push_undo()
        out_svc = canon_service(out_port.service)
        in_svc = (in_port.service or "").strip()
        # Simulink-like: connection carries the Out signal; In port name follows Out.
        if not in_svc:
            new_req = list(in_port.card.requires) + [out_svc]
            # 保留画布上的 GfChannel In
            new_req = self._merge_channel_requires(
                in_port.card.process_name, new_req
            )
            soa_req = [r for r in new_req if not is_channel_svc(r)]
            self._session.set_ports(
                in_port.card.process_name,
                [p for p in in_port.card.provides if not is_channel_svc(p)],
                soa_req,
            )
        elif short_service(in_svc) != short_service(out_svc) and not is_channel_svc(
            in_svc
        ):
            new_req = [
                out_svc if short_service(r) == short_service(in_svc) else r
                for r in in_port.card.requires
                if not is_channel_svc(r)
            ]
            self._session.set_ports(
                in_port.card.process_name,
                [p for p in in_port.card.provides if not is_channel_svc(p)],
                new_req,
            )

        ok = self._session.add_dataflow(
            out_port.card.process_name,
            out_svc,
            in_port.card.process_name,
        )
        if not ok:
            QMessageBox.information(self, t("连线"), t("该 dataflow 已存在"))
            return
        self.rebuild()
        self.changed.emit()

    def _merge_channel_requires(self, process: str, requires: list[str]) -> list[str]:
        """Keep existing channel In slots from channel_flows when editing SOA ports."""
        if not self._session:
            return requires
        extra: list[str] = []
        for fl in self._session.channel_flows():
            if str(fl.get("to")) != process:
                continue
            slot = str(fl.get("slot") or "").strip()
            if not slot and str(fl.get("from") or "").startswith("camera."):
                slot = ProjectSession.gf_channel_slot_name(
                    ProjectSession.slot_id_from_camera_process(str(fl.get("from")))
                )
            if slot and slot not in requires and slot not in extra:
                extra.append(slot)
        return list(requires) + extra

    def cancel_wire(self) -> None:
        self._wire_src = None
        if self._wire_line is not None:
            if self._wire_line.scene():
                self._scene.removeItem(self._wire_line)
            self._wire_line = None
        self._clear_wire_forbid_mark()
        self._pop_app_cursor()
        for card in self._nodes.values():
            for p in card._out_ports + card._in_ports:
                if _qt_alive(p):
                    p.setCursor(wire_link_cursor())
        if self._reloc_port is None:
            self._view.setDragMode(QGraphicsView.DragMode.ScrollHandDrag)

    def _push_app_cursor(self, cursor: QCursor) -> None:
        self._pop_app_cursor()
        QApplication.setOverrideCursor(cursor)
        self._app_cursor_pushed = True

    def _pop_app_cursor(self) -> None:
        if self._app_cursor_pushed:
            QApplication.restoreOverrideCursor()
            self._app_cursor_pushed = False

    # --- port side relocate + same-side reorder (Ctrl+drag) ---

    def begin_port_relocate(self, port: PortItem) -> None:
        self.cancel_wire()
        self.cancel_port_relocate()
        self._reloc_port = port
        port._home_pos = QPointF(port.pos())
        port._origin_side = port.side
        peers = self._ports_on_side_unified(port.card, port.side, exclude=None)
        try:
            port._origin_index = peers.index(port)
        except ValueError:
            port._origin_index = 0
        port._pending_side = port.side
        port._pending_index = port._origin_index
        self._reloc_card_was_movable = bool(
            port.card.flags() & QGraphicsItem.GraphicsItemFlag.ItemIsMovable
        )
        port.card.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIsMovable, False)
        self._view.setDragMode(QGraphicsView.DragMode.NoDrag)
        # Snapshot once at gesture start (finish must stay cheap for cursor restore).
        if not self._drag_undo_armed:
            self._push_undo()
            self._drag_undo_armed = True
        self._push_app_cursor(port_move_cursor())

    def _services_list(self, card: ProcessCard, direction: str) -> list[str]:
        return list(card.provides if direction == "out" else card.requires)

    def _ports_on_side_unified(
        self,
        card: ProcessCard,
        side: str,
        *,
        exclude: PortItem | None = None,
    ) -> list[PortItem]:
        """Same-side Out+In peers in current slot order (allows interleave)."""
        side_n = _norm_side(side, "left")
        by_key = {
            ProcessCard.slot_key(p.direction, p.service): p
            for p in (card._out_ports + card._in_ports)
            if p.side == side_n
        }
        ex_key = (
            ProcessCard.slot_key(exclude.direction, exclude.service)
            if exclude is not None
            else ""
        )
        out: list[PortItem] = []
        for raw in card.port_slot_order.get(side_n, []):
            if ex_key and raw == ex_key:
                continue
            p = by_key.pop(raw, None)
            if p is not None:
                out.append(p)
        for key, p in list(by_key.items()):
            if ex_key and key == ex_key:
                continue
            out.append(p)
        return out

    def _insert_index_on_side(
        self, port: PortItem, side: str, scene_pos: QPointF
    ) -> int:
        """Insert index among same-side Out+In peers."""
        card = port.card
        local = card.mapFromScene(scene_pos)
        peers = self._ports_on_side_unified(card, side, exclude=port)
        if side in ("left", "right"):
            coord = local.y()
            for i, p in enumerate(peers):
                if coord < p.pos().y():
                    return i
            return len(peers)
        coord = local.x()
        for i, p in enumerate(peers):
            if coord < p.pos().x():
                return i
        return len(peers)

    def _preview_port_layout(
        self, moving: PortItem, new_side: str, new_index: int
    ) -> None:
        """Live-preview side + order without mutating YAML yet."""
        from collections import defaultdict

        card = moving.card
        new_side = _norm_side(new_side, moving.side)
        groups: dict[str, list[PortItem]] = defaultdict(list)
        for p in card._out_ports + card._in_ports:
            if p is moving:
                continue
            groups[p.side].append(p)
        # Keep each side's relative order from current slot list when possible.
        for side in list(groups.keys()):
            ordered = self._ports_on_side_unified(card, side, exclude=moving)
            groups[side] = [p for p in ordered if p in groups[side]] + [
                p for p in groups[side] if p not in ordered
            ]
        dest = list(groups.get(new_side, []))
        new_index = max(0, min(int(new_index), len(dest)))
        dest.insert(new_index, moving)
        groups[new_side] = dest
        for side, plist in groups.items():
            n = len(plist)
            for i, p in enumerate(plist):
                p.side = side
                p.index = i
                p.setPos(card._place_on_side(side, i, n))
        moving._pending_side = new_side
        moving._pending_index = new_index
        for e in list(card._edges):
            if hasattr(e, "update_path"):
                e.update_path()

    @staticmethod
    def _reorder_services_on_side(
        services: list[str],
        moved: str,
        new_side: str,
        new_index: int,
        side_of,
    ) -> list[str]:
        """Reorder `moved` among services that share `new_side`; keep others stable."""
        key = short_service(moved)
        moved_c = next((s for s in services if short_service(s) == key), moved)
        rest = [s for s in services if short_service(s) != key]
        same = [s for s in rest if side_of(s) == new_side]
        new_index = max(0, min(int(new_index), len(same)))
        same.insert(new_index, moved_c)
        result: list[str] = []
        emitted = False
        for s in rest:
            if side_of(s) == new_side:
                if not emitted:
                    result.extend(same)
                    emitted = True
            else:
                result.append(s)
        if not emitted:
            result.extend(same)
        return result

    def update_port_relocate(self, scene_pos: QPointF) -> None:
        port = self._reloc_port
        if port is None or not _qt_alive(port):
            return
        side = port.nearest_card_side(scene_pos)
        idx = self._insert_index_on_side(port, side, scene_pos)
        self._preview_port_layout(port, side, idx)

    def finish_port_relocate(self) -> None:
        port = self._reloc_port
        if port is None:
            self.cancel_port_relocate()
            return
        pending = port._pending_side
        pending_idx = port._pending_index
        origin = port._origin_side
        origin_idx = port._origin_index
        card = port.card
        # Clear reloc mode first so mouse/view stop treating this as a drag.
        self._reloc_port = None
        if self._reloc_card_was_movable and _qt_alive(card):
            card.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIsMovable, True)
        # Keep override until persist/rebuild finishes — otherwise PortItem's
        # Ctrl move cursor flashes during deepcopy and feels "stuck".
        try:
            if not _qt_alive(port) or not _qt_alive(card):
                return
            side_changed = bool(pending and pending != origin)
            order_changed = (
                pending_idx is not None and int(pending_idx) != int(origin_idx)
            )
            if pending and (side_changed or order_changed):
                self.apply_port_side_and_order(
                    port, pending, int(pending_idx or 0), card=card
                )
            else:
                port._pending_side = None
                port._pending_index = None
                card._rebuild_ports()
                for e in list(card._edges):
                    if hasattr(e, "update_path"):
                        e.update_path()
        finally:
            self._pop_app_cursor()
            self._view.setDragMode(QGraphicsView.DragMode.ScrollHandDrag)
            self._drag_undo_armed = False
            self._end_doc_edit()
            self.refresh_port_hover_cursor()

    def cancel_port_relocate(self) -> None:
        port = self._reloc_port
        self._reloc_port = None
        card = port.card if port is not None and _qt_alive(port) else None
        try:
            if port is not None and _qt_alive(port):
                port._pending_side = None
                port._pending_index = None
                if self._reloc_card_was_movable and card is not None and _qt_alive(card):
                    card.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIsMovable, True)
                if card is not None and _qt_alive(card):
                    card._rebuild_ports()
                    for e in list(card._edges):
                        if hasattr(e, "update_path"):
                            e.update_path()
        finally:
            self._pop_app_cursor()
            if self._wire_src is None:
                self._view.setDragMode(QGraphicsView.DragMode.ScrollHandDrag)
            # Cancelled gesture: drop the armed undo snapshot usability by
            # keeping stack as-is (snapshot == current). Clear armed flag.
            self._drag_undo_armed = False
            self._end_doc_edit()
            self.refresh_port_hover_cursor()

    def apply_port_side_and_order(
        self,
        port: PortItem,
        new_side: str,
        new_index: int,
        *,
        card: ProcessCard | None = None,
    ) -> None:
        """Persist port edge + same-side Out/In slot order (may interleave)."""
        from collections import defaultdict

        if not self._session:
            return
        card = card if card is not None else port.card
        if not _qt_alive(card):
            return
        # Capture identity before any rebuild destroys PortItem
        direction = port.direction
        moved_svc = port.service
        key = short_service(moved_svc)
        moved_slot = ProcessCard.slot_key(direction, moved_svc)
        side_n = _norm_side(new_side, "right" if direction == "out" else "left")
        dir_key = ProcessCard.port_side_key(direction, moved_svc)
        card.port_sides[dir_key] = side_n
        # 去掉旧版无方向键，避免同名 In/Out 再被绑在一起
        card.port_sides.pop(key, None)

        # Drop moved from all side orders, then insert on destination side.
        for s, keys in list(card.port_slot_order.items()):
            card.port_slot_order[s] = [k for k in keys if k != moved_slot]
            if not card.port_slot_order[s]:
                card.port_slot_order.pop(s, None)

        out_by: dict[str, list[str]] = defaultdict(list)
        in_by: dict[str, list[str]] = defaultdict(list)
        for svc in card.provides:
            if direction == "out" and short_service(svc) == key:
                continue
            out_by[card.port_side_for(svc, "out")].append(svc)
        for svc in card.requires:
            if direction == "in" and short_service(svc) == key:
                continue
            in_by[card.port_side_for(svc, "in")].append(svc)

        base = card._slots_for_side(side_n, out_by, in_by)
        idx = max(0, min(int(new_index), len(base)))
        base.insert(idx, (direction, moved_svc))
        card.port_slot_order[side_n] = [
            ProcessCard.slot_key(d, svc) for d, svc in base
        ]
        for s in ("left", "right", "top", "bottom"):
            if s == side_n:
                continue
            rebuilt = card._slots_for_side(s, out_by, in_by)
            if rebuilt:
                card.port_slot_order[s] = [
                    ProcessCard.slot_key(d, svc) for d, svc in rebuilt
                ]
            else:
                card.port_slot_order.pop(s, None)

        new_prov = self._services_from_slot_orders(card, "out", list(card.provides))
        new_req = self._services_from_slot_orders(card, "in", list(card.requires))

        self._session.set_node_ui(
            card.process_name,
            port_sides=dict(card.port_sides),
            port_slot_order={
                s: list(keys) for s, keys in card.port_slot_order.items()
            },
        )
        # frame_ingest Outs are GfChannel slots (canvas only) — never push through
        # set_ports / deployments (that strips channel services).
        if card.is_frame_ingest():
            card.provides = list(new_prov)
            card.requires = list(new_req)
            card._height = card._compute_height()
            card._rebuild_ports()
            card.prepareGeometryChange()
            card.update()
        else:
            self._session.set_ports(
                card.process_name, new_prov, new_req, prune_flows=False
            )
            card.set_ports(new_prov, new_req)
        for e in list(card._edges):
            if hasattr(e, "update_path"):
                e.update_path()
        self._drag_undo_armed = False
        self._end_doc_edit()
        self.changed.emit()

    @staticmethod
    def _services_from_slot_orders(
        card: ProcessCard, direction: str, services: list[str]
    ) -> list[str]:
        """Order provides/requires to follow interleaved port_slot_order."""
        by_short = {short_service(s): s for s in services}
        seen: set[str] = set()
        result: list[str] = []
        for side in ("left", "right", "top", "bottom"):
            for raw in card.port_slot_order.get(side, []):
                parsed = ProcessCard.parse_slot_key(raw)
                if parsed is None or parsed[0] != direction:
                    continue
                sk = parsed[1]
                full = by_short.get(sk)
                if full is not None and sk not in seen:
                    result.append(full)
                    seen.add(sk)
        for s in services:
            sk = short_service(s)
            if sk not in seen:
                result.append(s)
                seen.add(sk)
        return result

    def set_single_port_side(self, port: PortItem, side: str) -> None:
        """Move one Out/In port (e.g. EgoMotion only) to another card edge."""
        side_n = _norm_side(side, port.side)
        peers = self._ports_on_side_unified(port.card, side_n, exclude=port)
        self.apply_port_side_and_order(port, side_n, len(peers))

    def note_flow_route(
        self, flow: dict[str, Any], route: dict[str, Any] | None
    ) -> None:
        """Persist edge bend; called from EdgeCurve handle (session API only)."""
        if self._session is None:
            return
        self._session.set_flow_route(flow, route)
        self.changed.emit()
