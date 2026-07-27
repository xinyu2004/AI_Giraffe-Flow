"""Editable tag catalog UI → session.tags.json (markers + ranges) + optional clip."""

from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QComboBox,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMessageBox,
    QPushButton,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from gf_gmt.gui.wall_time import SessionClock
from gf_gmt.measure_tag import (
    TagRecord,
    clip_by_tag,
    delete_tag,
    load_tags,
    new_tag,
    save_tags,
    tags_path_for_session,
    upsert_tag,
)


class TagPanel(QWidget):
    """CRUD tags for the open session; markers jump; ranges can export clip."""

    request_load_clip = Signal(str)  # clip jsonl path
    seek_ns_requested = Signal(object)  # ns may exceed 32-bit Signal(int)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._session: Path | None = None
        self._tags: list[TagRecord] = []
        self._current_id: str | None = None
        self._playhead_ns: int | None = None
        self._clock: SessionClock = SessionClock()

        hint = QLabel(
            "标记点 ●：热键 M 在 playhead 钉一下，方便回头找；"
            "片段 ▬：热键 [ / ] 定 from/to，可导出 clip。列表显示墙钟（方案 1）。"
        )
        hint.setWordWrap(True)
        hint.setStyleSheet("color:#555;")

        self._list = QListWidget()
        self._list.currentItemChanged.connect(self._on_select)
        self._list.itemDoubleClicked.connect(self._on_double_click)

        self._label = QLineEdit()
        self._kind = QComboBox()
        self._kind.addItem("标记点 (marker)", "marker")
        self._kind.addItem("片段 (range)", "range")
        self._from = QLineEdit()
        self._from.setPlaceholderText("from_ns / at_ns")
        self._to = QLineEdit()
        self._to.setPlaceholderText("to_ns（标记点可留空或同 from）")
        self._topics = QLineEdit()
        self._topics.setPlaceholderText("逗号分隔 topic，可选")
        self._notes = QTextEdit()
        self._notes.setMaximumHeight(80)

        form = QFormLayout()
        form.addRow("标签", self._label)
        form.addRow("类型", self._kind)
        form.addRow("from / at", self._from)
        form.addRow("to_ns", self._to)
        form.addRow("topics", self._topics)
        form.addRow("备注", self._notes)

        self._play_lbl = QLabel("playhead=—")
        self._play_lbl.setStyleSheet("color:#333;")

        btn_row = QHBoxLayout()
        self._btn_mark = QPushButton("钉标记 ●")
        self._btn_mark.setToolTip("在 playhead 打一个标记点（热键 M）")
        self._btn_mark.clicked.connect(self._on_drop_marker)
        self._btn_new = QPushButton("新建")
        self._btn_new.clicked.connect(self._on_new)
        self._btn_save = QPushButton("保存")
        self._btn_save.clicked.connect(self._on_save)
        self._btn_del = QPushButton("删除")
        self._btn_del.clicked.connect(self._on_delete)
        self._btn_jump = QPushButton("跳转")
        self._btn_jump.clicked.connect(self._on_jump)
        self._btn_from = QPushButton("from←playhead")
        self._btn_from.clicked.connect(lambda: self._fill_bound("from"))
        self._btn_to = QPushButton("to←playhead")
        self._btn_to.clicked.connect(lambda: self._fill_bound("to"))
        self._btn_clip = QPushButton("导出 clip…")
        self._btn_clip.clicked.connect(self._on_clip)
        for b in (
            self._btn_mark,
            self._btn_new,
            self._btn_save,
            self._btn_del,
            self._btn_jump,
            self._btn_from,
            self._btn_to,
            self._btn_clip,
        ):
            btn_row.addWidget(b)
        btn_row.addStretch(1)

        lay = QVBoxLayout(self)
        lay.addWidget(hint)
        lay.addWidget(self._play_lbl)
        lay.addWidget(self._list, stretch=1)
        lay.addLayout(form)
        lay.addLayout(btn_row)

    def set_session(
        self, path: Path | None, *, clock: SessionClock | None = None
    ) -> None:
        self._session = path
        if clock is not None:
            self._clock = clock
        self._tags = []
        self._current_id = None
        self._clear_form()
        self._list.clear()
        if path is None:
            return
        tp = tags_path_for_session(path)
        self._tags = load_tags(tp)
        self._refresh_list()

    def set_clock(self, clock: SessionClock | None) -> None:
        self._clock = clock or SessionClock()
        self._refresh_list()
        if self._playhead_ns is not None:
            self.set_playhead_ns(self._playhead_ns)

    def set_playhead_ns(self, t_ns: int | None) -> None:
        self._playhead_ns = t_ns
        if t_ns is None:
            self._play_lbl.setText("playhead=—")
        else:
            wall = self._clock.format(t_ns)
            self._play_lbl.setText(f"playhead={t_ns}  墙钟={wall}")

    def live_drop_marker(self, t_ns: int | None = None, *, label: str = "") -> str:
        """One-shot bookmark at playhead (primary live Tag action)."""
        if self._session is None:
            return "无 session（先打开或跟随 live）"
        t = self._playhead_ns if t_ns is None else t_ns
        if t is None:
            return "无 playhead"
        n = sum(1 for x in self._tags if x.is_marker)
        tag = new_tag(
            label=label or f"mark_{n + 1}",
            from_ns=t,
            to_ns=t,
            notes="marker",
            kind="marker",
        )
        self._tags = upsert_tag(self._tags, tag)
        self._current_id = tag.id
        self._persist()
        self._refresh_list()
        self._fill_form(tag)
        return f"● 标记 {tag.label} @ {t} → {self._tags_path()}"

    def live_mark_from(self, t_ns: int | None = None) -> str:
        """Start a range tag at from_ns."""
        if self._session is None:
            return "无 session（先打开或跟随 live）"
        t = self._playhead_ns if t_ns is None else t_ns
        if t is None:
            return "无 playhead"
        n = sum(1 for x in self._tags if (x.label or "").startswith("range_"))
        tag = new_tag(
            label=f"range_{n + 1}",
            from_ns=t,
            to_ns=None,
            notes="range",
            kind="range",
        )
        self._tags = upsert_tag(self._tags, tag)
        self._current_id = tag.id
        self._persist()
        self._refresh_list()
        self._fill_form(tag)
        return f"▬ from={t} → {tag.label}"

    def live_mark_to(self, t_ns: int | None = None) -> str:
        """Close current / newest open range at to_ns and persist."""
        if self._session is None:
            return "无 session"
        t = self._playhead_ns if t_ns is None else t_ns
        if t is None:
            return "无 playhead"
        tag = None
        if self._current_id:
            tag = next((x for x in self._tags if x.id == self._current_id), None)
        if tag is None or tag.is_marker:
            for x in reversed(self._tags):
                if x.kind == "range" and x.from_ns is not None and (
                    x.to_ns is None or x.to_ns == x.from_ns
                ):
                    tag = x
                    break
        if tag is None:
            # no open range → drop marker instead
            return self.live_drop_marker(t)
        tag.kind = "range"
        tag.to_ns = t
        if tag.from_ns is None:
            tag.from_ns = t
        if tag.to_ns is not None and tag.from_ns is not None and tag.to_ns < tag.from_ns:
            tag.from_ns, tag.to_ns = tag.to_ns, tag.from_ns
        self._tags = upsert_tag(self._tags, tag)
        self._current_id = tag.id
        self._persist()
        self._refresh_list()
        self._fill_form(tag)
        return f"▬ 片段 {tag.label} [{tag.from_ns}…{tag.to_ns}] → {self._tags_path()}"

    def _tags_path(self) -> Path | None:
        if self._session is None:
            return None
        return tags_path_for_session(self._session)

    def _fmt_ns(self, t_ns: int | None) -> str:
        if t_ns is None:
            return "—"
        wall = self._clock.format(t_ns, compact=True)
        if wall != "—":
            return f"{wall} ({t_ns})"
        return str(t_ns)

    def _list_text(self, t: TagRecord) -> str:
        if t.is_marker:
            at = t.at_ns()
            return f"● {t.label or '(unnamed)'}  @{self._fmt_ns(at)}"
        return (
            f"▬ {t.label or '(unnamed)'}  "
            f"[{self._fmt_ns(t.from_ns)}…{self._fmt_ns(t.to_ns)}]"
        )

    def _refresh_list(self) -> None:
        self._list.blockSignals(True)
        self._list.clear()
        for t in self._tags:
            item = QListWidgetItem(self._list_text(t))
            item.setData(Qt.ItemDataRole.UserRole, t.id)
            self._list.addItem(item)
            if t.id == self._current_id:
                self._list.setCurrentItem(item)
        self._list.blockSignals(False)

    def _clear_form(self) -> None:
        self._label.clear()
        self._kind.setCurrentIndex(0)
        self._from.clear()
        self._to.clear()
        self._topics.clear()
        self._notes.clear()

    def _fill_form(self, tag: TagRecord) -> None:
        self._label.setText(tag.label)
        idx = self._kind.findData(tag.kind if tag.kind in {"marker", "range"} else "marker")
        self._kind.setCurrentIndex(max(0, idx))
        self._from.setText("" if tag.from_ns is None else str(tag.from_ns))
        self._to.setText("" if tag.to_ns is None else str(tag.to_ns))
        self._topics.setText(", ".join(tag.topics))
        self._notes.setPlainText(tag.notes)

    def _on_select(
        self, cur: QListWidgetItem | None, _prev: QListWidgetItem | None
    ) -> None:
        if cur is None:
            self._current_id = None
            self._clear_form()
            return
        tid = str(cur.data(Qt.ItemDataRole.UserRole) or "")
        self._current_id = tid
        tag = next((t for t in self._tags if t.id == tid), None)
        if tag is None:
            return
        self._fill_form(tag)

    def _on_double_click(self, item: QListWidgetItem) -> None:
        tid = str(item.data(Qt.ItemDataRole.UserRole) or "")
        tag = next((t for t in self._tags if t.id == tid), None)
        if tag is None:
            return
        at = tag.at_ns()
        if at is not None:
            self.seek_ns_requested.emit(at)

    def _on_jump(self) -> None:
        tag = next((t for t in self._tags if t.id == self._current_id), None)
        if tag is None:
            QMessageBox.information(self, "Tag", "先选中一个标记/片段")
            return
        at = tag.at_ns()
        if at is None:
            QMessageBox.information(self, "Tag", "该条目没有时间点")
            return
        self.seek_ns_requested.emit(at)

    def _on_drop_marker(self) -> None:
        msg = self.live_drop_marker()
        if msg.startswith("无"):
            QMessageBox.information(self, "标记", msg)

    def _parse_opt_int(self, text: str) -> int | None:
        s = text.strip()
        if not s:
            return None
        return int(s)

    def _form_to_tag(self) -> TagRecord | None:
        if self._session is None:
            QMessageBox.information(self, "Tag", "请先打开 session")
            return None
        label = self._label.text().strip() or "untagged"
        kind = str(self._kind.currentData() or "marker")
        try:
            from_ns = self._parse_opt_int(self._from.text())
            to_ns = self._parse_opt_int(self._to.text())
        except ValueError:
            QMessageBox.warning(self, "Tag", "from_ns / to_ns 必须是整数")
            return None
        if kind == "marker" and from_ns is not None and to_ns is None:
            to_ns = from_ns
        if kind == "range" and from_ns is not None and to_ns is None:
            # open-ended range ok
            pass
        topics = [t.strip() for t in self._topics.text().split(",") if t.strip()]
        notes = self._notes.toPlainText().strip()
        if self._current_id:
            existing = next((t for t in self._tags if t.id == self._current_id), None)
            if existing is not None:
                existing.label = label
                existing.from_ns = from_ns
                existing.to_ns = to_ns
                existing.topics = topics
                existing.notes = notes
                existing.kind = kind
                return existing
        return new_tag(
            label=label,
            from_ns=from_ns,
            to_ns=to_ns,
            topics=topics,
            notes=notes,
            kind=kind,
        )

    def _persist(self) -> bool:
        tp = self._tags_path()
        if tp is None:
            QMessageBox.information(self, "Tag", "请先打开 session")
            return False
        save_tags(tp, self._tags)
        return True

    def _on_new(self) -> None:
        if self._session is None:
            QMessageBox.information(self, "Tag", "请先打开 session")
            return
        tag = new_tag(
            label="mark",
            from_ns=self._playhead_ns,
            to_ns=self._playhead_ns,
            kind="marker",
        )
        self._tags = upsert_tag(self._tags, tag)
        self._current_id = tag.id
        self._persist()
        self._refresh_list()
        self._fill_form(tag)

    def _on_save(self) -> None:
        tag = self._form_to_tag()
        if tag is None:
            return
        self._tags = upsert_tag(self._tags, tag)
        self._current_id = tag.id
        if self._persist():
            self._refresh_list()
            QMessageBox.information(
                self,
                "Tag",
                f"已保存 {self._tags_path()}",
            )

    def _on_delete(self) -> None:
        if not self._current_id:
            return
        self._tags = delete_tag(self._tags, self._current_id)
        self._current_id = None
        self._clear_form()
        self._persist()
        self._refresh_list()

    def _fill_bound(self, which: str) -> None:
        if self._playhead_ns is None:
            QMessageBox.information(self, "Tag", "无 playhead（先加载并 scrub session）")
            return
        if which == "from":
            self._from.setText(str(self._playhead_ns))
        else:
            self._to.setText(str(self._playhead_ns))
            if self._kind.currentData() == "marker":
                self._kind.setCurrentIndex(self._kind.findData("range"))

    def _on_clip(self) -> None:
        if self._session is None or not self._session.is_file():
            QMessageBox.information(self, "clip", "请先打开 session")
            return
        tag = self._form_to_tag()
        if tag is None:
            return
        if tag.is_marker:
            QMessageBox.information(
                self,
                "clip",
                "当前是标记点 ●，不是时间窗。\n"
                "请把类型改成「片段」并填 from/to，或用 [ / ] 定窗后再导出。",
            )
            return
        if tag.from_ns is None or tag.to_ns is None:
            QMessageBox.information(self, "clip", "片段需要 from_ns 与 to_ns")
            return
        self._tags = upsert_tag(self._tags, tag)
        self._current_id = tag.id
        self._persist()
        self._refresh_list()

        out = self._session.parent / f"{self._session.stem}.clip_{tag.id[:8]}.jsonl"
        try:
            path, kept, total = clip_by_tag(self._session, out, tag)
        except Exception as exc:  # noqa: BLE001
            QMessageBox.critical(self, "clip", str(exc))
            return
        reply = QMessageBox.question(
            self,
            "clip",
            f"已写入 {path}\nkept={kept}/{total}\n是否加载到时间轴？",
        )
        if reply == QMessageBox.StandardButton.Yes:
            self.request_load_clip.emit(str(path))
