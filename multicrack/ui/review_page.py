"""Step 2: hear, trim, relabel and approve every chop."""
from __future__ import annotations

from PySide6.QtCore import QSize, Qt
from PySide6.QtGui import QKeySequence, QShortcut
from PySide6.QtWidgets import (QCheckBox, QFrame, QHBoxLayout, QLabel, QProgressBar, QPushButton,
                               QScrollArea, QToolButton, QVBoxLayout, QWidget)

from ..core.audio import render_chop
from ..core.naming import assign_names
from . import icons
from .common import fmt_len, label, label_combo, magnet_to_hit, panel
from .waveform import MiniWave, TrimEditor


class ChopRow(QFrame):
    def __init__(self, page, chop, stem):
        super().__init__()
        self.page, self.chop, self.stem = page, chop, stem
        self.setObjectName("row")
        self.setProperty("selected", "false")
        lay = QHBoxLayout(self)
        lay.setContentsMargins(12, 6, 12, 6)
        lay.setSpacing(12)
        t = page.win.t

        self.play = QToolButton()
        self.play.setFixedSize(36, 36)
        self.play.setIcon(icons.play(t["text"]))
        self.play.setIconSize(QSize(14, 14))
        self.play.setToolTip("Play and load into the trim editor (Space)")
        self.play.setStyleSheet("border-radius: 18px;")
        self.play.clicked.connect(lambda: page.select(self.chop, play=True))
        lay.addWidget(self.play)

        names = QVBoxLayout()
        names.setSpacing(1)
        self.name = label("", "mono")
        self.name.setMinimumWidth(240)
        names.addWidget(self.name)
        self.sub = label("", "muted")
        names.addWidget(self.sub)
        holder = QWidget()
        holder.setLayout(names)
        holder.setFixedWidth(300)
        lay.addWidget(holder)

        self.combo = label_combo(chop.label)
        self.combo.setFixedWidth(170)
        self.combo.currentTextChanged.connect(self._label_changed)
        lay.addWidget(self.combo)

        self.wave = MiniWave()
        self.wave.set_chop(page.win.peaks(stem), chop.start, chop.end)
        lay.addWidget(self.wave, 1)

        self.dur = label("", "muted")
        self.dur.setFixedWidth(64)
        lay.addWidget(self.dur)

        self.thumb = QToolButton()
        self.thumb.setObjectName("thumb")
        self.thumb.setCheckable(True)
        self.thumb.setFixedSize(42, 36)
        self.thumb.setIconSize(QSize(18, 18))
        self.thumb.setToolTip("Approve")
        self.thumb.setChecked(chop.approved)
        self.thumb.toggled.connect(self._approved)
        lay.addWidget(self.thumb)
        self.update_view()

    def mousePressEvent(self, e):
        self.page.select(self.chop, play=False)
        super().mousePressEvent(e)

    def _label_changed(self, txt):
        txt = txt.strip()
        if txt and not txt.startswith("—"):
            self.chop.label = txt
            self.page.names_changed()

    def _approved(self, on):
        self.chop.approved = on
        self.update_thumb()
        self.page.counts_changed()

    def update_thumb(self):
        t = self.page.win.t
        self.thumb.setIcon(icons.thumb(t["on_ok"] if self.chop.approved else t["muted"]))

    def update_view(self):
        self.name.setText(self.page.names.get(self.chop.id, ""))
        sub = f"from {self.stem.name}"
        if self.chop.flag:
            sub += f" · {self.chop.flag}"
        fm = self.sub.fontMetrics()
        self.sub.setText(fm.elidedText(sub, Qt.ElideRight, 292))
        self.sub.setToolTip(sub)
        self.sub.setObjectName("warn" if self.chop.flag else "muted")
        self.sub.style().unpolish(self.sub)
        self.sub.style().polish(self.sub)
        self.dur.setText(fmt_len(self.chop.length, self.stem.sr))
        self.wave.set_chop(self.page.win.peaks(self.stem), self.chop.start, self.chop.end)
        self.update_thumb()

    def set_selected(self, on):
        self.setProperty("selected", "true" if on else "false")
        self.style().unpolish(self)
        self.style().polish(self)


class ReviewPage(QWidget):
    def __init__(self, win):
        super().__init__()
        self.win = win
        self.setObjectName("page")
        self.rows: dict = {}
        self.names: dict = {}
        self.selected = None
        self._orig = {}

        outer = QVBoxLayout(self)
        outer.setContentsMargins(16, 14, 16, 16)
        outer.setSpacing(12)

        top = QHBoxLayout()
        col = QVBoxLayout()
        col.setSpacing(6)
        self.count_lbl = label("", "h2")
        col.addWidget(self.count_lbl)
        self.progress = QProgressBar()
        self.progress.setTextVisible(False)
        self.progress.setFixedWidth(280)
        col.addWidget(self.progress)
        top.addLayout(col)
        top.addStretch(1)
        self.approve_all = QPushButton("Approve all")
        self.approve_all.clicked.connect(self.approve_everything)
        top.addWidget(self.approve_all)
        self.export_btn = QPushButton("Export")
        self.export_btn.setObjectName("primary")
        self.export_btn.clicked.connect(self.win.export_all)
        top.addWidget(self.export_btn)
        outer.addLayout(top)

        # trim editor
        ep, el = panel(spacing=8, margins=(14, 12, 14, 12))
        head = QHBoxLayout()
        self.ed_name = label("", "mono")
        f = self.ed_name.font()
        f.setBold(True)
        self.ed_name.setFont(f)
        head.addWidget(self.ed_name)
        head.addStretch(1)
        head.addWidget(label("Drag the blue handles to trim. Scroll on the waveform to zoom.",
                             "muted"))
        el.addLayout(head)
        self.editor = TrimEditor()
        self.editor.changed.connect(self._trimmed)
        el.addWidget(self.editor)
        er = QHBoxLayout()
        self.ed_play = QPushButton("Play")
        self.ed_play.clicked.connect(lambda: self.play_selected())
        er.addWidget(self.ed_play)
        self.ed_stop = QPushButton("Stop")
        self.ed_stop.clicked.connect(self.win.player.stop)
        er.addWidget(self.ed_stop)
        self.ed_reset = QPushButton("Reset trim")
        self.ed_reset.clicked.connect(self.reset_trim)
        er.addWidget(self.ed_reset)
        self.ed_snap = QCheckBox("Snap start to the hit")
        self.ed_snap.setToolTip("When on, a start dropped within about 12 ms of a hit lines up "
                                "with its attack. Turn off for completely free trimming.")
        self.ed_snap.setChecked(self.win.settings.value("snap_trim", "true") == "true")
        self.ed_snap.toggled.connect(
            lambda on: self.win.settings.setValue("snap_trim", "true" if on else "false"))
        er.addSpacing(8)
        er.addWidget(self.ed_snap)
        self.ed_flag = label("", "warn", wrap=True)
        er.addWidget(self.ed_flag, 1)
        el.addLayout(er)
        outer.addWidget(ep)

        # list
        self.scroll = QScrollArea()
        self.scroll.setWidgetResizable(True)
        self.listw = QWidget()
        self.list_lay = QVBoxLayout(self.listw)
        self.list_lay.setContentsMargins(0, 0, 0, 0)
        self.list_lay.setSpacing(0)
        frame, fl = panel(margins=(0, 0, 0, 0), spacing=0)
        fl.addWidget(self.scroll)
        self.scroll.setWidget(self.listw)
        outer.addWidget(frame, 1)

        self.empty = label("Nothing to review yet. Load stems and press Process all.", "muted")
        self.empty.setAlignment(Qt.AlignCenter)
        outer.addWidget(self.empty)

        QShortcut(QKeySequence(Qt.Key_Space), self, activated=self.play_selected)

    # ------------------------------------------------------------------ build
    def rebuild(self):
        while self.list_lay.count():
            it = self.list_lay.takeAt(0)
            if it.widget():
                it.widget().deleteLater()
        self.rows.clear()
        self.names = self._compute_names()
        stems = {s.id: s for s in self.win.stems}
        t = self.win.t
        last = None
        for c in self.win.chops:
            st = stems.get(c.stem_id)
            if st is None:
                continue
            if st.id != last:
                hdr = QFrame()
                hdr.setObjectName("groupHeader")
                hl = QHBoxLayout(hdr)
                hl.setContentsMargins(12, 6, 12, 6)
                n = sum(1 for x in self.win.chops if x.stem_id == st.id)
                hl.addWidget(label(f"{st.name}", "h2"))
                hl.addWidget(label(f"{st.kind} · {n} chop{'s' if n != 1 else ''}", "muted"))
                hl.addStretch(1)
                b = QPushButton("Loop options" if (st.engine == "groove" and st.mode == "auto")
                                else "Edit regions")
                b.setObjectName("link")
                b.clicked.connect(lambda _c=False, s=st: self.win.open_stem(s))
                hl.addWidget(b)
                self.list_lay.addWidget(hdr)
                last = st.id
            row = ChopRow(self, c, st)
            self.rows[c.id] = row
            self.list_lay.addWidget(row)
        self.list_lay.addStretch(1)
        has = bool(self.win.chops)
        self.empty.setVisible(not has)
        self.scroll.parentWidget().setVisible(has)
        if self.selected is None or self.selected.id not in self.rows:
            self.selected = None
            if self.win.chops:
                self.select(self.win.chops[0], play=False)
            else:
                self.editor.clear()
                self.ed_name.setText("")
                self.ed_flag.setText("")
        else:
            self.select(self.selected, play=False)
        self.counts_changed()
        _ = t

    def _compute_names(self):
        return assign_names(self.win.chops, self.win.prefix(), self.win.output_folder())

    def names_changed(self):
        self.names = self._compute_names()
        for r in self.rows.values():
            r.name.setText(self.names.get(r.chop.id, ""))
        if self.selected is not None:
            self.ed_name.setText(self.names.get(self.selected.id, ""))

    def counts_changed(self):
        chops = self.win.chops
        n = len(chops)
        a = sum(1 for c in chops if c.approved)
        self.count_lbl.setText(f"{a} of {n} approved" if n else "No chops yet")
        self.progress.setRange(0, max(1, n))
        self.progress.setValue(a)
        done = n > 0 and a == n
        self.export_btn.setEnabled(done and not self.win.busy)
        self.export_btn.setText(f"Export {n} files" if done else "Export (approve all first)")
        self.approve_all.setEnabled(n > 0 and not done)
        self.win.update_steps()

    def approve_everything(self):
        for r in self.rows.values():
            r.thumb.setChecked(True)

    # -------------------------------------------------------------- editing
    def select(self, chop, play=False):
        if self.selected is not None and self.selected.id in self.rows:
            self.rows[self.selected.id].set_selected(False)
        self.selected = chop
        row = self.rows.get(chop.id)
        if row:
            row.set_selected(True)
        st = self.win.stem_by_id(chop.stem_id)
        if chop.id not in self._orig:
            self._orig[chop.id] = (chop.start, chop.end)
        self.ed_name.setText(self.names.get(chop.id, ""))
        self.ed_flag.setText(chop.flag)
        self._load_editor(chop, st)
        if play:
            self.play_selected()

    def _load_editor(self, chop, st):
        def snap(s, st=st, chop=chop):
            if not self.ed_snap.isChecked() or chop.kind == "loop":
                return s           # loops stay where you put them (bar lines are yours to move)
            return magnet_to_hit(st, s)
        self.editor.set_chop(self.win.peaks(st), st.frames, st.sr, chop.start, chop.end, snap)

    def play_selected(self):
        c = self.selected
        if c is None:
            return
        st = self.win.stem_by_id(c.stem_id)
        if not self.win.player.play(render_chop(st, c), st.sr, c.id):
            self.win.status(self.win.player.error or "")

    def _trimmed(self, s, e):
        c = self.selected
        if c is None:
            return
        c.start, c.end = int(s), int(e)
        c.cut_at_next = False
        row = self.rows.get(c.id)
        if row:
            row.update_view()
        st = self.win.stem_by_id(c.stem_id)
        if s <= self.editor.view_a + int(0.02 * st.sr) or e >= self.editor.view_b - int(0.02 * st.sr):
            self._load_editor(c, st)   # handle reached the edge: re-frame so you can keep going
        self.play_selected()

    def reset_trim(self):
        c = self.selected
        if c is None or c.id not in self._orig:
            return
        c.start, c.end = self._orig[c.id]
        self.select(c, play=False)
        row = self.rows.get(c.id)
        if row:
            row.update_view()

    def retheme(self):
        t = self.win.t
        for r in self.rows.values():
            r.play.setIcon(icons.play(t["text"]))
            r.update_thumb()
