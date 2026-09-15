"""Paint-only wiring scene rebuild (no session mutations).

Called from WiringGraphView.rebuild — keeps the view class smaller and
makes the read-only contract explicit.
"""

from __future__ import annotations

from typing import Any

from gf_config.core import ProjectSession, is_channel_svc, normalize_channel_slot, short_service
from gf_config.gui.wiring_graph_items import (
    ChannelEdge,
    EdgeCurve,
    McuPeerLink,
    MissingEdge,
    ProcessCard,
    _qt_alive,
    assign_process_colors,
    build_process_color_adjacency,
    deconflict_edge_labels,
    is_external_node,
    parse_canvas_color,
)


def rebuild_wiring_graph(
    view: Any,
    *,
    fit_view: bool = False,
    reset_layout: bool = False,
    keep_layout_pos: bool = False,
) -> None:
    view.cancel_wire()
    # Snapshot positions before C++ items are destroyed — unless caller
    # already filled _layout_pos (undo/redo) or asked to drop layout.
    if reset_layout:
        view._layout_pos.clear()
    elif not keep_layout_pos:
        for name, card in list(view._nodes.items()):
            if _qt_alive(card):
                p = card.pos()
                view._layout_pos[name] = (p.x(), p.y())

    # Block selectionChanged while tearing down — scene.clear() deletes C++ items
    # while Python still briefly holds ProcessCard/EdgeCurve wrappers.
    view._scene.blockSignals(True)
    try:
        for e in view._edges:
            if _qt_alive(e):
                e.remove_label()
        for e in view._channel_edges:
            if _qt_alive(e):
                e.remove_label()
        for m in view._missing:
            if _qt_alive(m):
                m.remove_label()
        for p in view._peers:
            if _qt_alive(p):
                p.remove_label()
        view._nodes.clear()
        view._edges.clear()
        view._channel_edges.clear()
        view._missing.clear()
        view._peers.clear()
        view._scene.clear()
    finally:
        view._scene.blockSignals(False)

    if not view._session:
        return

    # rebuild is paint-only: migrations run in ProjectSession.open / normalize_after_open.
    fi_cfg = view._session.frame_ingest_cfg()
    active = str(fi_cfg.get("active_source") or "none").strip() or "none"
    camera_slots = view._session.camera_slots()
    ch_flows = view._session.channel_flows()
    need_ingest = bool(camera_slots) or active != "none" or bool(ch_flows)
    ingest_name = ProjectSession.FRAME_INGEST_PROCESS

    dep_map: dict[str, dict[str, Any]] = {}
    for d in view._session.deployments():
        p = d.get("process")
        if p:
            dep_map[str(p)] = d

    ordered = list(dep_map.keys())
    for fl in view._session.dataflows():
        for key in ("from", "to"):
            p = fl.get(key)
            if p and str(p) not in dep_map:
                dep_map[str(p)] = {"process": p, "provides": [], "requires": []}
                ordered.append(str(p))

    depths = view._compute_depths(ordered, view._session.dataflows())
    cols: dict[int, list[str]] = {}
    for name in ordered:
        cols.setdefault(depths.get(name, 0), []).append(name)

    # auto-layout slots for nodes without a remembered position
    show_mcu = view._show_external_mcu()
    ap_x0 = 120.0 if show_mcu else 40.0
    auto_slots: dict[str, tuple[float, float]] = {}
    ext_i = 0
    for depth, names in sorted(cols.items()):
        for i, name in enumerate(names):
            if is_external_node(process=name):
                # MCU 默认在最左，避免挤进 AP 列被裁切
                auto_slots[name] = (-280.0, 40.0 + ext_i * 120.0)
                ext_i += 1
            else:
                # 有 MCU 时 AP 列右移留空；仅 AP 拓扑则贴左
                auto_slots[name] = (ap_x0 + depth * 280.0, 40.0 + i * 240.0)

    # Consumer channel Ins derived from channel_flows (never from deployments)
    channel_ins: dict[str, list[str]] = {}
    for fl in view._session.channel_flows():
        dst = str(fl.get("to") or "").strip()
        if not dst:
            continue
        slot = normalize_channel_slot(str(fl.get("slot") or "")) or ""
        frm = str(fl.get("from") or "")
        if not slot and frm.startswith("camera."):
            slot = ProjectSession.gf_channel_slot_name(
                ProjectSession.slot_id_from_camera_process(frm)
            )
        if not slot and frm == ProjectSession.FRAME_INGEST_PROCESS:
            continue
        if slot and slot not in channel_ins.setdefault(dst, []):
            channel_ins[dst].append(slot)

    # Colour map before cards/edges: anti-adjacent hues (dataflow + spatial).
    color_names: list[str] = []
    color_pos: dict[str, tuple[float, float]] = {}
    for name in ordered:
        if ProjectSession.is_frame_ingest_process(process=name):
            continue
        ui0 = view._session.get_node_ui(name)
        kind0 = str(ui0.get("kind") or "")
        if is_external_node(kind=kind0, process=name) and not show_mcu:
            continue
        if name in view._layout_pos:
            cx, cy = view._layout_pos[name]
        elif "x" in ui0 and "y" in ui0:
            cx, cy = float(ui0["x"]), float(ui0["y"])
        else:
            cx, cy = auto_slots.get(name, (40.0, 40.0))
        color_names.append(name)
        color_pos[name] = (cx, cy)
    if need_ingest:
        color_names.append(ingest_name)
        if ingest_name in view._layout_pos:
            color_pos[ingest_name] = view._layout_pos[ingest_name]
        else:
            # ingest card position resolved below; seed near auto slot
            color_pos[ingest_name] = auto_slots.get(ingest_name, (40.0, -80.0))

    locked: dict[str, Any] = {}
    preferred: dict[str, Any] = {}
    for name in color_names:
        ui_c = view._session.get_node_ui(name)
        qc = parse_canvas_color(ui_c.get("color"))
        if qc is None:
            continue
        if ui_c.get("color_user"):
            locked[name] = qc
        else:
            preferred[name] = qc
    view._process_color_map = assign_process_colors(
        color_names,
        build_process_color_adjacency(
            color_names,
            flows=list(view._session.dataflows()),
            positions=color_pos,
        ),
        locked=locked,
        preferred=preferred,
    )
    # Persist auto colours (never overwrite color_user locks).
    for name, qc in view._process_color_map.items():
        if name in locked:
            continue
        hex_c = qc.name()
        ui_c = view._session.get_node_ui(name)
        same = str(ui_c.get("color") or "").lower() == hex_c.lower()
        if same and not ui_c.get("color_user"):
            continue
        view._session.set_node_ui(name, color=hex_c)
        if ui_c.get("color_user"):
            view._session.clear_node_ui_keys(name, "color_user")

    for name in ordered:
        if ProjectSession.is_frame_ingest_process(process=name):
            # Never build ingest from deployments (empty provides); dedicated card below.
            continue
        d = dep_map.get(name) or {}
        provides = [
            str(x) for x in (d.get("provides") or []) if not is_channel_svc(str(x))
        ]
        requires = [
            str(x) for x in (d.get("requires") or []) if not is_channel_svc(str(x))
        ]
        for slot in channel_ins.get(name, []):
            if not any(normalize_channel_slot(str(r)) == slot for r in requires):
                requires.append(slot)
        ui = view._session.get_node_ui(name)
        kind = str(ui.get("kind") or "")
        if is_external_node(kind=kind, process=name) and not kind:
            kind = "external"
        # ap_only：不画 MCU 卡片；YAML/dataflow 仍保留，gateway 对外端口可见
        if is_external_node(kind=kind, process=name) and not show_mcu:
            continue
        if name in view._layout_pos:
            x, y = view._layout_pos[name]
        elif "x" in ui and "y" in ui:
            x, y = float(ui["x"]), float(ui["y"])
            view._layout_pos[name] = (x, y)
        else:
            x, y = auto_slots.get(name, (40.0, 40.0))
            if name not in auto_slots:
                n = len(view._layout_pos)
                x, y = 80.0 + (n % 4) * 40.0, 80.0 + (n // 4) * 40.0
            view._layout_pos[name] = (x, y)
        raw_ps = ui.get("port_sides") if isinstance(ui.get("port_sides"), dict) else {}
        raw_order = (
            ui.get("port_slot_order")
            if isinstance(ui.get("port_slot_order"), dict)
            else {}
        )
        order_map: dict[str, list[str]] = {}
        for sk, keys in raw_order.items():
            if isinstance(keys, list):
                order_map[str(sk)] = [str(x) for x in keys]
        card = ProcessCard(
            name,
            provides,
            requires,
            x,
            y,
            graph=view,
            out_side=str(ui.get("out_side") or "right"),
            in_side=str(ui.get("in_side") or "left"),
            kind=kind or "process",
            label=str(ui.get("label") or ""),
            compute_domain=str(d.get("compute_domain") or "ap_linux"),
            port_sides={str(k): str(v) for k, v in raw_ps.items()},
            port_slot_order=order_map,
        )
        view._scene.addItem(card)
        view._nodes[name] = card

    # Single frame_ingest card: one Out per camera_slot
    if need_ingest and ingest_name not in view._nodes:
        outs = [
            ProjectSession.gf_channel_slot_name(str(s.get("id")))
            for s in camera_slots
            if str(s.get("id") or "").strip()
        ]
        if not outs and active != "none":
            outs = [ProjectSession.gf_channel_slot_name("front")]
        ui = view._session.get_node_ui(ingest_name)
        if ingest_name in view._layout_pos:
            x, y = view._layout_pos[ingest_name]
        elif "x" in ui and "y" in ui:
            x, y = float(ui["x"]), float(ui["y"])
            view._layout_pos[ingest_name] = (x, y)
        else:
            x, y = -80.0, -320.0
            view._layout_pos[ingest_name] = (x, y)
        raw_ps = ui.get("port_sides") if isinstance(ui.get("port_sides"), dict) else {}
        raw_order = (
            ui.get("port_slot_order")
            if isinstance(ui.get("port_slot_order"), dict)
            else {}
        )
        order_map: dict[str, list[str]] = {}
        for sk, keys in raw_order.items():
            if isinstance(keys, list):
                order_map[str(sk)] = [str(x) for x in keys]
        card = ProcessCard(
            ingest_name,
            outs,
            [],
            x,
            y,
            graph=view,
            out_side=str(ui.get("out_side") or "right"),
            in_side=str(ui.get("in_side") or "left"),
            kind="frame_ingest",
            label=str(ui.get("label") or "frame_ingest"),
            compute_domain="host",
            port_sides={str(k): str(v) for k, v in raw_ps.items()},
            port_slot_order=order_map,
        )
        view._scene.addItem(card)
        view._nodes[ingest_name] = card

    # drop positions for deleted processes / cameras
    view._layout_pos = {k: v for k, v in view._layout_pos.items() if k in view._nodes}

    flows = view._session.dataflows()
    peer_svcs: dict[tuple[str, str], list[str]] = {}
    # Fan groups: same out-port (from+service). Index by destination Y so
    # one-to-many curves leave in visual order instead of YAML order.
    fan_groups: dict[tuple[str, str], list[tuple[Any, ...]]] = {}
    for fl in flows:
        src = str(fl.get("from") or "")
        dst = str(fl.get("to") or "")
        svc = str(fl.get("service") or "")
        src_n = view._nodes.get(src)
        dst_n = view._nodes.get(dst)
        if not src_n or not dst_n:
            continue
        # External-MCU flows: one boundary link on canvas; yaml keeps services
        if src_n.is_external() or dst_n.is_external():
            a, b = (src, dst) if src_n.is_external() else (dst, src)
            key = (a, b)
            peer_svcs.setdefault(key, []).append(svc)
            continue
        fan_groups.setdefault((src, svc), []).append((fl, src_n, dst_n, src, dst, svc))

    for _fan_key, group in fan_groups.items():
        group.sort(
            key=lambda it: (
                float(it[2].in_anchor(it[5]).y()),
                float(it[2].in_anchor(it[5]).x()),
                it[4],
            )
        )
        n = len(group)
        for idx, (fl, src_n, dst_n, src, dst, svc) in enumerate(group):
            edge = EdgeCurve(src_n, dst_n, svc, fl, idx, n, graph=view)
            view._scene.addItem(edge)
            edge.update_path()  # 入景后再挂路径控制点
            view._edges.append(edge)

    for fl in view._session.channel_flows():
        src = str(fl.get("from") or "")
        dst = str(fl.get("to") or "")
        slot = str(fl.get("slot") or "").strip()
        if not slot and src.startswith("camera."):
            slot = ProjectSession.gf_channel_slot_name(
                ProjectSession.slot_id_from_camera_process(src)
            )
        src_n = view._nodes.get(src)
        dst_n = view._nodes.get(dst)
        if not src_n or not dst_n or not slot:
            continue
        cedge = ChannelEdge(src_n, dst_n, slot, fl, graph=view)
        view._scene.addItem(cedge)
        cedge.update_path()
        view._channel_edges.append(cedge)

    # gateway 上仅面向 MCU 的端口：画布隐藏（保留 planning→Trajectory In 等）
    hide_out: dict[str, set[str]] = {}
    hide_in: dict[str, set[str]] = {}
    for fl in flows:
        src = str(fl.get("from") or "")
        dst = str(fl.get("to") or "")
        svc = short_service(str(fl.get("service") or ""))
        src_n = view._nodes.get(src)
        dst_n = view._nodes.get(dst)
        if not src_n or not dst_n or not svc:
            continue
        if src_n.is_external() and not dst_n.is_external():
            hide_in.setdefault(dst, set()).add(svc)
        elif dst_n.is_external() and not src_n.is_external():
            hide_out.setdefault(src, set()).add(svc)
    for name, card in view._nodes.items():
        if card.is_external() or card.is_camera():
            continue
        card.set_canvas_hide(out=hide_out.get(name, set()), inn=hide_in.get(name, set()))
    # 隐藏端口后 gateway 高度变化，刷新已有边锚点
    for e in view._edges:
        if _qt_alive(e):
            e.update_path()
    for e in view._channel_edges:
        if _qt_alive(e):
            e.update_path()

    # 有 dataflow / channel_flow 的端口=已连（绿/橙）；否则红
    linked_out: dict[str, set[str]] = {n: set() for n in view._nodes}
    linked_in: dict[str, set[str]] = {n: set() for n in view._nodes}
    for fl in flows:
        src = str(fl.get("from") or "")
        dst = str(fl.get("to") or "")
        svc = short_service(str(fl.get("service") or ""))
        if not svc:
            continue
        if src in linked_out:
            linked_out[src].add(svc)
        if dst in linked_in:
            linked_in[dst].add(svc)
    for fl in view._session.channel_flows():
        src = str(fl.get("from") or "")
        dst = str(fl.get("to") or "")
        slot = str(fl.get("slot") or "").strip()
        if not slot and src.startswith("camera."):
            slot = ProjectSession.gf_channel_slot_name(
                ProjectSession.slot_id_from_camera_process(src)
            )
        if not slot:
            continue
        if src in linked_out:
            linked_out[src].add(slot)
        if dst in linked_in:
            linked_in[dst].add(slot)
    for name, card in view._nodes.items():
        card.set_link_status(
            linked_out=linked_out.get(name, set()),
            linked_in=linked_in.get(name, set()),
        )

    for (mcu_name, gw_name), svcs in peer_svcs.items():
        mcu_n = view._nodes.get(mcu_name)
        gw_n = view._nodes.get(gw_name)
        if not mcu_n or not gw_n:
            continue
        peer = McuPeerLink(mcu_n, gw_n, svcs, graph=view)
        view._scene.addItem(peer)
        peer.update_path()
        view._peers.append(peer)

    provided_by: dict[str, list[str]] = {}
    for name, card in view._nodes.items():
        if card.is_camera():
            continue
        for p in card.provides:
            if is_channel_svc(p):
                continue
            provided_by.setdefault(short_service(p), []).append(name)

    # 仅当某 In 端口「完全没有」入边时才提示缺失；
    # External MCU / CameraSource / GfChannel In：不画缺失虚线
    for cons_name, card in view._nodes.items():
        if card.is_external() or card.is_camera():
            continue
        ignored = set()
        if view._session:
            ignored = {
                str(x)
                for x in (view._session.get_node_ui(cons_name).get("ignore_missing") or [])
            }
        for req in card.requires:
            if is_channel_svc(req):
                continue
            svc_s = short_service(req)
            satisfied = any(
                str(f.get("to")) == cons_name
                and short_service(str(f.get("service") or "")) == svc_s
                for f in flows
            )
            if satisfied:
                continue
            providers = provided_by.get(svc_s) or []
            if not providers:
                # 无提供方：不画到虚构节点（画布不再维护侧栏列表）
                continue
            for prov in providers:
                key = f"{prov}|{svc_s}|{cons_name}"
                if key in ignored:
                    continue
                src_n = view._nodes.get(prov)
                if not src_n or src_n.is_external() or src_n.is_camera():
                    continue
                miss = MissingEdge(src_n, card, req, graph=view)
                view._scene.addItem(miss)
                view._missing.append(miss)

    deconflict_edge_labels([*view._edges, *view._channel_edges])

    view._refresh_scene_rect()
    if fit_view:
        view._fit_and_remember()
    view._last_topo = view._topology()
