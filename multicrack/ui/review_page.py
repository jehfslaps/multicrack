"""Step 2: hear, trim, relabel and approve every chop."""
from __future__ import annotations

import os
import tempfile

from PySide6.QtCore import QMimeData, QSize, Qt, QTimer, QUrl
from PySide6.QtGui import QDrag
from PySide6.QtWidgets import (QApplication, QCheckBox, QDoubleSpinBox, QFrame, QHBoxLayout,
                               QLayout, QLineEdit, QProgressBar, QPushButton, QScrollArea,
                               QScrollBar, QSizePolicy, QToolButton, QVBoxLayout, QWidget)

from ..core.audio import default_fades_ms, render_chop, write_wav24
from ..core.naming import assign_names
from . import icons
from .common import fmt_len, label, label_combo, magnet_to_hit, panel
from .waveform import MiniWave, TrimEditor

DRAG_DIR = os.path.join(tempfile.gettempdir(), "MultiCrack", "drag")


class ChopRow(QFrame):
    def __init__(self, page, chop, stem):
        super().__init__()
        self.page, self.chop, self.stem = page, chop, stem
        self._press = None
        self.setObjectName("row")
        self.setProperty("selected", "false")
        self.setMinimumHeight(62)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        self.setToolTip("Drag this row into FL Studio (or any folder) to use the sample right away")
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
        self.combo.setFocusPolicy(Qt.ClickFocus)
        self.combo.currentTextChanged.connect(self._label_changed)
        lay.addWidget(self.combo)

        self.wave = MiniWave()
        lay.addWidget(self.wave, 1)

        self.dur = label("", "muted")
        self.dur.setFixedWidth(64)
        lay.addWidget(self.dur)

        self.thumb = QToolButton()
        self.thumb.setObjectName("thumb")
        self.thumb.setCheckable(True)
        self.thumb.setFixedSize(42, 36)
        self.thumb.setIconSize(QSize(18, 18))
        self.thumb.setToolTip("Approve (A approves and moves to the next chop)")
        self.thumb.setChecked(chop.approved)
        self.thumb.clicked.connect(lambda on: page.set_approved(self.chop, on))
        lay.addWidget(self.thumb)

        self.clone_btn = QToolButton()
        self.clone_btn.setFixedSize(34, 36)
        self.clone_btn.setIconSize(QSize(17, 17))
        self.clone_btn.setToolTip("Clone this chop (Ctrl+D): adds a copy right below that you "
                                  "can trim or label differently")
        self.clone_btn.clicked.connect(lambda: page.clone_chop(self.chop))
        lay.addWidget(self.clone_btn)

        self.del_btn = QToolButton()
        self.del_btn.setFixedSize(34, 36)
        self.del_btn.setIconSize(QSize(17, 17))
        self.del_btn.setToolTip("Delete this chop (Delete key)")
        self.del_btn.clicked.connect(lambda: page.delete_chop(self.chop))
        lay.addWidget(self.del_btn)
        self.update_view()

    # ---- mouse: click selects, drag exports the sample
    def mousePressEvent(self, e):
        if e.button() == Qt.LeftButton:
            self._press = e.position().toPoint()
        self.page.select(self.chop, play=False)
        super().mousePressEvent(e)

    def mouseMoveEvent(self, e):
        if (self._press is not None and e.buttons() & Qt.LeftButton and
                (e.position().toPoint() - self._press).manhattanLength()
                >= QApplication.startDragDistance()):
            self._press = None
            self.page.start_drag(self)
            return
        super().mouseMoveEvent(e)

    def mouseReleaseEvent(self, e):
        self._press = None
        super().mouseReleaseEvent(e)

    def _label_changed(self, txt):
        txt = txt.strip()
        if txt and not txt.startswith("—") and txt != self.chop.label:
            self.page.win.history.push(f"label{self.chop.id}")
            self.chop.label = txt
            self.page.names_changed()
            self.page.win.session_changed()
            if not self.combo.lineEdit().hasFocus():
                self.page.setFocus()

    def update_thumb(self):
        t = self.page.win.t
        self.thumb.blockSignals(True)
        self.thumb.setChecked(self.chop.approved)
        self.thumb.blockSignals(False)
        self.thumb.setIcon(icons.thumb(t["on_ok"] if self.chop.approved else t["muted"]))
        self.clone_btn.setIcon(icons.copy(t["muted"]))
        self.del_btn.setIcon(icons.trash(t["muted"]))

    def update_view(self):
        self.name.setText(self.page.names.get(self.chop.id, ""))
        sub = f"from {self.stem.name}"
        extras = []
        if self.chop.reverse:
            extras.append("reversed")
        if self.chop.gain_db:
            extras.append(f"{self.chop.gain_db:+.1f} dB")
        if extras:
            sub += " · " + ", ".join(extras)
        if self.chop.flag:
            sub += f" · {self.chop.flag}"
        fm = self.sub.fontMetrics()
        self.sub.setText(fm.elidedText(sub, Qt.ElideRight, 292))
        self.sub.setToolTip(sub)
        self.sub.setObjectName("warn" if self.chop.flag else "muted")
        self.sub.style().unpolish(self.sub)
        self.sub.style().polish(self.sub)
        self.dur.setText(fmt_len(self.chop.length, self.stem.sr))
        self.wave.set_chop(self.page.win.peaks(self.stem), self.chop.start, self.chop.end,
                           self.chop.reverse)
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
        self._loading_fx = False

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
        self.undo_btn = QPushButton("Undo")
        self.undo_btn.setToolTip("Undo (Ctrl+Z)")
        self.undo_btn.clicked.connect(self.win.undo)
        top.addWidget(self.undo_btn)
        self.redo_btn = QPushButton("Redo")
        self.redo_btn.setToolTip("Redo (Ctrl+Y)")
        self.redo_btn.clicked.connect(self.win.redo)
        top.addWidget(self.redo_btn)
        top.addSpacing(12)
        self.approve_all = QPushButton("Approve all")
        self.approve_all.clicked.connect(self.approve_everything)
        top.addWidget(self.approve_all)
        self.export_btn = QPushButton("Export")
        self.export_btn.setObjectName("primary")
        self.export_btn.clicked.connect(self.win.export_all)
        top.addWidget(self.export_btn)
        outer.addLayout(top)

        # ---------------------------------------------------------- trim editor
        ep, el = panel(spacing=8, margins=(14, 12, 14, 12))
        head = QHBoxLayout()
        self.ed_name = label("", "mono")
        f = self.ed_name.font()
        f.setBold(True)
        self.ed_name.setFont(f)
        head.addWidget(self.ed_name)
        head.addStretch(1)
        head.addWidget(label("Drag the blue handles to trim, or drag across the waveform to pick "
                             "a new section. Scroll to zoom, Shift+scroll to move.", "muted"))
        el.addLayout(head)
        self.editor = TrimEditor()
        self.editor.changed.connect(self._trimmed)
        el.addWidget(self.editor)
        self.ed_scroll = QScrollBar(Qt.Horizontal)
        self.ed_scroll.valueChanged.connect(self._scrolled)
        self.editor.viewChanged.connect(self._view_changed)
        el.addWidget(self.ed_scroll)

        # row 1: transport, snap, zoom
        er = QHBoxLayout()
        self.ed_play = QPushButton("Play")
        self.ed_play.setToolTip("Play / stop (Space)")
        self.ed_play.clicked.connect(self.toggle_play)
        er.addWidget(self.ed_play)
        self.ed_loop = self._toggle("Loop: Off", "Loop playback (L key). Loops always repeat so "
                                    "you can hear the seam; this repeats every other chop too.",
                                    "loop_play", False, self._loop_toggled)
        er.addWidget(self.ed_loop)
        self.ed_reset = QPushButton("Reset trim")
        self.ed_reset.clicked.connect(self.reset_trim)
        er.addWidget(self.ed_reset)
        self.ed_snap = self._toggle("Snap: On", "Snap (S key). On: a start flag dropped within "
                                    "about 12 ms of a hit lines up with its attack. Off: the flags "
                                    "stay exactly where you drop them, no snapping at all.",
                                    "snap_trim", True, self._snap_toggled)
        er.addWidget(self.ed_snap)
        er.addSpacing(12)
        for text, tip, fn in (("−", "Zoom out", lambda: self.editor.zoom(1.6)),
                              ("+", "Zoom in", lambda: self.editor.zoom(0.6)),
                              ("Zoom to chop", "Frame the selected section", self.editor.show_chop),
                              ("Whole stem", "Show the entire stem", self.editor.show_all)):
            b = QPushButton(text)
            b.setToolTip(tip)
            if len(text) == 1:
                b.setFixedWidth(36)
            b.clicked.connect(fn)
            er.addWidget(b)
        self.ed_flag = label("", "warn", wrap=True)
        er.addWidget(self.ed_flag, 1)
        el.addLayout(er)

        # row 2: per-chop sound controls
        fx = QHBoxLayout()
        fx.addWidget(label("Fade in"))
        self.fade_in = self._spin(0, 5000, " ms", 1, "Fade-in length. The default is a tiny "
                                  "automatic de-click.")
        fx.addWidget(self.fade_in)
        fx.addWidget(label("Fade out"))
        self.fade_out = self._spin(0, 10000, " ms", 1, "Fade-out length. The default is a short "
                                   "automatic de-click.")
        fx.addWidget(self.fade_out)
        self.fade_auto = QPushButton("Auto fades")
        self.fade_auto.setToolTip("Back to the automatic de-click fades")
        self.fade_auto.clicked.connect(self._auto_fades)
        fx.addWidget(self.fade_auto)
        fx.addSpacing(12)
        self.ed_reverse = self._toggle("Reverse: Off", "Play and export this chop backwards "
                                       "(R key). The file name gets 'Rev'.", None, False,
                                       self._reverse_toggled)
        fx.addWidget(self.ed_reverse)
        fx.addSpacing(12)
        fx.addWidget(label("Gain"))
        self.gain = self._spin(-48, 0, " dB", 0.5, "Every sample is normalized to full level "
                               "(−0.1 dB). Use this to turn one down from there.")
        self.gain.setDecimals(1)
        fx.addWidget(self.gain)
        fx.addSpacing(12)
        self.ed_seam = self._toggle("Smooth loop seam: On", "Loops only: blends the very end of "
                                    "the loop into what comes just before its start, so it "
                                    "repeats without a click. Length stays exactly on the bars.",
                                    None, True, self._seam_toggled)
        fx.addWidget(self.ed_seam)
        fx.addStretch(1)
        el.addLayout(fx)
        self.fade_in.valueChanged.connect(lambda v: self._fx_changed("fade_in_ms", v))
        self.fade_out.valueChanged.connect(lambda v: self._fx_changed("fade_out_ms", v))
        self.gain.valueChanged.connect(lambda v: self._fx_changed("gain_db", v))
        outer.addWidget(ep)

        # ------------------------------------------------------------- list
        self.scroll = QScrollArea()
        self.scroll.setWidgetResizable(True)
        self.scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.listw = QWidget()
        self.list_lay = QVBoxLayout(self.listw)
        self.list_lay.setSizeConstraint(QLayout.SetMinimumSize)   # never squash the rows
        self.list_lay.setContentsMargins(0, 0, 0, 0)
        self.list_lay.setSpacing(0)
        frame, fl = panel(margins=(0, 0, 0, 0), spacing=0)
        fl.addWidget(self.scroll)
        self.scroll.setWidget(self.listw)
        outer.addWidget(frame, 1)

        self.empty = label("Nothing to review yet. Load stems and press Process all.", "muted")
        self.empty.setAlignment(Qt.AlignCenter)
        outer.addWidget(self.empty)

        self.setFocusPolicy(Qt.StrongFocus)
        self.scroll.setFocusPolicy(Qt.NoFocus)
        # buttons shouldn't steal the keyboard from the list (arrows, Delete, Space)
        for cls in (QPushButton, QCheckBox, QScrollBar, QToolButton):
            for w_ in self.findChildren(cls):
                w_.setFocusPolicy(Qt.NoFocus)
        for sp in (self.fade_in, self.fade_out, self.gain):
            sp.setFocusPolicy(Qt.ClickFocus)

        self._fx_timer = QTimer(self)
        self._fx_timer.setSingleShot(True)
        self._fx_timer.setInterval(350)
        self._fx_timer.timeout.connect(self._fx_settled)
        self._ph_timer = QTimer(self)
        self._ph_timer.setInterval(33)
        self._ph_timer.timeout.connect(self._tick)
        self._ph_timer.start()
        self._ph_row = None

    # ---------------------------------------------------------------- helpers
    def _toggle(self, text, tip, setting, default, slot):
        b = QToolButton()
        b.setObjectName("seg")
        b.setCheckable(True)
        b.setMinimumHeight(34)
        b.setToolTip(tip)
        b.setText(text)
        if setting:
            b.setChecked(self.win.settings.value(setting, "true" if default else "false") == "true")
        else:
            b.setChecked(default)
        b.toggled.connect(slot)
        return b

    def _spin(self, lo, hi, suffix, step, tip):
        s = QDoubleSpinBox()
        s.setRange(lo, hi)
        s.setSuffix(suffix)
        s.setSingleStep(step)
        s.setDecimals(1)
        s.setFixedWidth(104)
        s.setToolTip(tip)
        s.setKeyboardTracking(False)
        return s

    # ------------------------------------------------------------------ build
    def rebuild(self):
        while self.list_lay.count():
            it = self.list_lay.takeAt(0)
            if it.widget():
                it.widget().deleteLater()
        self.rows.clear()
        self._ph_row = None
        self.names = self._compute_names()
        stems = {s.id: s for s in self.win.stems}
        last = None
        for c in self.win.chops:
            st = stems.get(c.stem_id)
            if st is None:
                continue
            if st.id != last:
                self.list_lay.addWidget(self._header(st))
                last = st.id
            row = ChopRow(self, c, st)
            self.rows[c.id] = row
            self.list_lay.addWidget(row)
        self.list_lay.addStretch(1)
        for cls in (QPushButton, QToolButton):
            for w_ in self.listw.findChildren(cls):
                w_.setFocusPolicy(Qt.NoFocus)
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

    def _header(self, st):
        hdr = QFrame()
        hdr.setObjectName("groupHeader")
        hdr.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        hl = QHBoxLayout(hdr)
        hl.setContentsMargins(12, 6, 12, 6)
        mine = [x for x in self.win.chops if x.stem_id == st.id]
        n = len(mine)
        hl.addWidget(label(f"{st.name}", "h2"))
        hl.addWidget(label(f"{st.kind} · {n} chop{'s' if n != 1 else ''}", "muted"))
        hl.addStretch(1)
        for text, tip, fn in (
                ("Approve all", "Approve every chop from this stem", lambda: self.approve_stem(st)),
                ("Remove all", "Remove every chop from this stem (Ctrl+Z brings them back)",
                 lambda: self.remove_stem_chops(st)),
                ("Loop options" if (st.engine == "groove" and st.mode == "auto") else "Edit regions",
                 "", lambda: self.win.open_stem(st))):
            b = QPushButton(text)
            b.setObjectName("link")
            if tip:
                b.setToolTip(tip)
            b.clicked.connect(fn)
            hl.addWidget(b)
        return hdr

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
        self.undo_btn.setEnabled(self.win.history.can_undo())
        self.redo_btn.setEnabled(self.win.history.can_redo())
        self.win.update_steps()

    # ---------------------------------------------------------------- toggles
    def _snap_toggled(self, on):
        self.ed_snap.setText("Snap: On" if on else "Snap: Off")
        self.win.settings.setValue("snap_trim", "true" if on else "false")

    def _loop_toggled(self, on):
        self.ed_loop.setText("Loop: On" if on else "Loop: Off")
        self.win.settings.setValue("loop_play", "true" if on else "false")
        if self.win.player.playing_id is not None:
            self.play_selected()

    def _reverse_toggled(self, on):
        self.ed_reverse.setText("Reverse: On" if on else "Reverse: Off")
        if self._loading_fx or self.selected is None or self.selected.reverse == on:
            return
        self.win.history.push()
        self.selected.reverse = on
        self._after_fx(names=True)
        self.play_selected()

    def _seam_toggled(self, on):
        self.ed_seam.setText("Smooth loop seam: On" if on else "Smooth loop seam: Off")
        if self._loading_fx or self.selected is None or self.selected.seam == on:
            return
        self.win.history.push()
        self.selected.seam = on
        self._after_fx()
        self.play_selected()

    def _fx_changed(self, attr, v):
        if self._loading_fx or self.selected is None:
            return
        c = self.selected
        self.win.history.push(f"{attr}{c.id}")
        setattr(c, attr, float(v))
        self._after_fx()
        self._fx_timer.start()

    def _fx_settled(self):
        if self.selected is not None:
            self.play_selected()

    def _auto_fades(self):
        c = self.selected
        if c is None:
            return
        self.win.history.push()
        c.fade_in_ms = c.fade_out_ms = None
        self._load_fx(c)
        self._after_fx()
        self.play_selected()

    def _after_fx(self, names=False):
        c = self.selected
        row = self.rows.get(c.id)
        if names:
            self.names_changed()
        if row:
            row.update_view()
        self._update_editor_fx(c)
        self.win.session_changed()

    def _load_fx(self, c):
        st = self.win.stem_by_id(c.stem_id)
        din, dout = default_fades_ms(c, st.sr if st else 44100)
        self._loading_fx = True
        self.fade_in.setValue(din if c.fade_in_ms is None else c.fade_in_ms)
        self.fade_out.setValue(dout if c.fade_out_ms is None else c.fade_out_ms)
        self.gain.setValue(float(c.gain_db or 0.0))
        self.ed_reverse.setChecked(c.reverse)
        self.ed_seam.setChecked(c.seam)
        self.ed_seam.setVisible(c.kind == "loop")
        self._loading_fx = False
        self._reverse_toggled(c.reverse)
        self._seam_toggled(c.seam)
        self._update_editor_fx(c)

    def _update_editor_fx(self, c):
        st = self.win.stem_by_id(c.stem_id)
        sr = st.sr if st else 44100
        din, dout = default_fades_ms(c, sr)
        fi = din if c.fade_in_ms is None else c.fade_in_ms
        fo = dout if c.fade_out_ms is None else c.fade_out_ms
        self.editor.set_fx(int(fi / 1000 * sr), int(fo / 1000 * sr), c.reverse)

    # --------------------------------------------------------------- keyboard
    def keyPressEvent(self, e):
        k, mods = e.key(), e.modifiers()
        ctrl = bool(mods & Qt.ControlModifier)
        if k == Qt.Key_Down:
            self.move_selection(1)
        elif k == Qt.Key_Up:
            self.move_selection(-1)
        elif k == Qt.Key_Space:
            self.toggle_play()
        elif k == Qt.Key_A and not ctrl and self.selected is not None:
            self.approve_and_next()
        elif k in (Qt.Key_Delete, Qt.Key_Backspace) and self.selected is not None:
            self.delete_chop(self.selected)
        elif k == Qt.Key_D and ctrl and self.selected is not None:
            self.clone_chop(self.selected)
        elif k == Qt.Key_Z and ctrl and mods & Qt.ShiftModifier:
            self.win.redo()
        elif k == Qt.Key_Z and ctrl:
            self.win.undo()
        elif k == Qt.Key_Y and ctrl:
            self.win.redo()
        elif k == Qt.Key_S and not ctrl:
            self.ed_snap.toggle()
        elif k == Qt.Key_L and not ctrl:
            self.ed_loop.toggle()
        elif k == Qt.Key_R and not ctrl and self.selected is not None:
            self.ed_reverse.toggle()
        elif k in (Qt.Key_Return, Qt.Key_Enter) and self.selected is not None:
            self.set_approved(self.selected, not self.selected.approved)
        else:
            super().keyPressEvent(e)

    def move_selection(self, delta, play=True):
        chops = self.win.chops
        if not chops:
            return
        ids = [c.id for c in chops]
        i = ids.index(self.selected.id) if self.selected is not None and self.selected.id in ids else -1
        j = max(0, min(len(chops) - 1, i + delta if i >= 0 else 0))
        self.select(chops[j], play=play)
        row = self.rows.get(chops[j].id)
        if row:
            self.scroll.ensureWidgetVisible(row, 0, 40)

    # -------------------------------------------------- approve, delete, clone
    def set_approved(self, chop, on):
        if chop.approved == on:
            self.rows.get(chop.id) and self.rows[chop.id].update_thumb()
            return
        self.win.history.push()
        chop.approved = on
        row = self.rows.get(chop.id)
        if row:
            row.update_thumb()
        self.counts_changed()
        self.win.session_changed()

    def approve_and_next(self):
        c = self.selected
        self.set_approved(c, True)
        ids = [x.id for x in self.win.chops]
        if c.id in ids and ids.index(c.id) < len(ids) - 1:
            self.move_selection(1)
        else:
            self.win.player.stop()

    def approve_everything(self):
        self.win.history.push()
        for c in self.win.chops:
            c.approved = True
        for r in self.rows.values():
            r.update_thumb()
        self.counts_changed()
        self.win.session_changed()

    def approve_stem(self, st):
        self.win.history.push()
        for c in self.win.chops:
            if c.stem_id == st.id:
                c.approved = True
        for r in self.rows.values():
            r.update_thumb()
        self.counts_changed()
        self.win.session_changed()

    def remove_stem_chops(self, st):
        self.win.history.push()
        self.win.player.stop()
        self.win.chops = [c for c in self.win.chops if c.stem_id != st.id]
        if self.selected is not None and self.selected.stem_id == st.id:
            self.selected = None
        self.win.chops_edited(st.id)
        self._rebuild_keep_scroll()
        self.win.session_changed()

    def _rebuild_keep_scroll(self):
        bar = self.scroll.verticalScrollBar()
        pos = bar.value()
        self.rebuild()
        QTimer.singleShot(0, lambda: bar.setValue(pos))

    def delete_chop(self, chop):
        chops = self.win.chops
        if chop not in chops:
            return
        self.win.history.push()
        i = chops.index(chop)
        chops.remove(chop)
        self.win.player.stop()
        self.selected = chops[min(i, len(chops) - 1)] if chops else None
        self.win.chops_edited(chop.stem_id)
        self._rebuild_keep_scroll()
        self.setFocus()
        self.win.session_changed()

    def clone_chop(self, chop):
        chops = self.win.chops
        if chop not in chops:
            return
        self.win.history.push()
        twin = chop.clone()
        chops.insert(chops.index(chop) + 1, twin)
        self.selected = twin
        self.win.chops_edited(chop.stem_id)
        self._rebuild_keep_scroll()
        self.setFocus()
        QTimer.singleShot(0, lambda: twin.id in self.rows and
                          self.scroll.ensureWidgetVisible(self.rows[twin.id], 0, 40))
        self.win.session_changed()

    # -------------------------------------------------------------- drag out
    def start_drag(self, row):
        c, st = row.chop, row.stem
        name = self.names.get(c.id) or "MultiCrack_sample.wav"
        os.makedirs(DRAG_DIR, exist_ok=True)
        path = os.path.join(DRAG_DIR, name)
        try:
            write_wav24(path, render_chop(st, c), st.sr)
        except OSError as e:
            self.win.status(f"Couldn't prepare the file: {e}")
            return
        mime = QMimeData()
        mime.setUrls([QUrl.fromLocalFile(path)])
        drag = QDrag(row)
        drag.setMimeData(mime)
        pm = row.wave.grab()
        if not pm.isNull():
            drag.setPixmap(pm.scaledToWidth(min(220, pm.width()), Qt.SmoothTransformation))
        drag.exec(Qt.CopyAction)

    # ------------------------------------------------------------- editing
    def select(self, chop, play=False):
        fw = self.focusWidget()
        if fw is None or not isinstance(fw, QLineEdit):
            self.setFocus()
        if self.selected is not None and self.selected.id in self.rows:
            self.rows[self.selected.id].set_selected(False)
        if self.selected is not None and self.selected.id != chop.id:
            if self.win.player.playing_id == self.selected.id and not play:
                self.win.player.stop()
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
        self._load_fx(chop)
        if play:
            self.play_selected()

    def _load_editor(self, chop, st):
        def snap(s, st=st, chop=chop):
            if not self.ed_snap.isChecked() or chop.kind == "loop":
                return s           # loops stay where you put them (bar lines are yours to move)
            return magnet_to_hit(st, s)
        self.editor.set_chop(self.win.peaks(st), st.frames, st.sr, chop.start, chop.end, snap,
                             keep_view=self.editor.is_whole())
        self._view_changed(self.editor.view_a, self.editor.view_b)

    def _view_changed(self, a, b):
        span = max(1, b - a)
        self.ed_scroll.blockSignals(True)
        self.ed_scroll.setRange(0, max(0, self.editor.n - span))
        self.ed_scroll.setPageStep(span)
        self.ed_scroll.setSingleStep(max(1, span // 20))
        self.ed_scroll.setValue(a)
        self.ed_scroll.setVisible(span < self.editor.n)
        self.ed_scroll.blockSignals(False)

    def _scrolled(self, v):
        span = self.editor.view_b - self.editor.view_a
        self.editor.set_view(v, v + span)

    # ------------------------------------------------------------ playback
    def toggle_play(self):
        if self.selected is not None and self.win.player.playing_id == self.selected.id:
            self.win.player.stop()
        else:
            self.play_selected()

    def play_selected(self):
        c = self.selected
        if c is None:
            return
        st = self.win.stem_by_id(c.stem_id)
        loop = self.ed_loop.isChecked() or c.kind == "loop"
        if not self.win.player.play(render_chop(st, c), st.sr, c.id, loop=loop):
            self.win.status(self.win.player.error or "")

    def _tick(self):
        p = self.win.player
        pos = p.position()
        playing = pos is not None
        self.ed_play.setText("Stop" if playing and self.selected is not None
                             and p.playing_id == self.selected.id else "Play")
        row = self.rows.get(p.playing_id) if playing else None
        if self._ph_row is not None and self._ph_row is not row:
            try:
                self._ph_row.wave.set_playhead(None)
            except RuntimeError:
                pass
        self._ph_row = row
        if row is not None:
            c = row.chop
            frac = pos / max(1, c.length)
            row.wave.set_playhead(min(1.0, frac))
        if playing and self.selected is not None and p.playing_id == self.selected.id:
            c = self.selected
            s = (c.end - pos) if c.reverse else (c.start + pos)
            self.editor.set_playhead(s)
        else:
            self.editor.set_playhead(None)

    def _trimmed(self, s, e):
        c = self.selected
        if c is None:
            return
        self.win.history.push()
        c.start, c.end = int(s), int(e)
        c.cut_at_next = False
        row = self.rows.get(c.id)
        if row:
            row.update_view()
        self.win.session_changed()
        self.play_selected()

    def reset_trim(self):
        c = self.selected
        if c is None or c.id not in self._orig:
            return
        self.win.history.push()
        c.start, c.end = self._orig[c.id]
        self.select(c, play=False)
        row = self.rows.get(c.id)
        if row:
            row.update_view()
        self.win.session_changed()

    def retheme(self):
        t = self.win.t
        for r in self.rows.values():
            r.play.setIcon(icons.play(t["text"]))
            r.update_thumb()
