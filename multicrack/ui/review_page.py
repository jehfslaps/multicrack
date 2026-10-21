"""Step 2: hear, trim, relabel and approve every chop (hardware skin)."""
from __future__ import annotations

import math
import os
import tempfile

from PySide6.QtCore import QMimeData, QPointF, QRectF, Qt, QTimer, QUrl
from PySide6.QtGui import QColor, QDrag, QPainter, QPen
from PySide6.QtWidgets import (QApplication, QFrame, QHBoxLayout, QLabel, QLayout, QLineEdit,
                               QScrollArea, QScrollBar, QSizePolicy, QSlider, QVBoxLayout,
                               QWidget)

from ..core.audio import default_fades_ms, render_chop, write_wav24
from ..core.naming import assign_names
from .common import label_combo, magnet_to_hit
from .skin import core as K
from .skin import widgets as W
from .waveform import MiniWave, TrimEditor

DRAG_DIR = os.path.join(tempfile.gettempdir(), "Xenakis", "drag")

# list columns (fixed widths; the waveform column stretches)
COL_WIDE = dict(grip=18, num=30, play=40, name=292, dur=92, type=164, approve=142, clone=36,
                delete=36)
COL_NARROW = dict(grip=16, num=26, play=40, name=206, dur=80, type=132, approve=116, clone=34,
                  delete=34)
COL = dict(COL_WIDE)
ROW_MARGINS = (12, 6, 16, 6)
ROW_SPACING = 12


def is_warning(flag: str) -> bool:
    """AI suggestions are information; cut tails / tempo problems are warnings."""
    return bool(flag) and not flag.startswith("AI suggestion")


def fmt_dur(samples, sr):
    t = samples / float(sr)
    m = int(t // 60)
    return f"{m}:{t - 60 * m:06.3f}"


def _fixed(w, width):
    w.setFixedWidth(width)
    return w


class ColumnHeader(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        lay = QHBoxLayout(self)
        lay.setContentsMargins(*ROW_MARGINS)
        lay.setSpacing(ROW_SPACING)
        self.setFixedHeight(34)

        def h(text, w=None):
            lb = W.cap(text, "header_text", 11, 600, 1.4)
            if w:
                lb.setFixedWidth(w)
            return lb
        lay.addWidget(h("", COL["grip"]))
        lay.addWidget(h("#", COL["num"]))
        lay.addWidget(h("", COL["play"]))
        lay.addWidget(h("File / stem", COL["name"]))
        lay.addWidget(h("Waveform"), 1)
        lay.addWidget(h("Duration", COL["dur"]))
        lay.addWidget(h("Type", COL["type"]))
        lay.addWidget(h("Actions", COL["approve"] + COL["clone"] + COL["delete"] + 2 * ROW_SPACING))

    def paintEvent(self, _e):
        p = QPainter(self)
        p.setPen(QPen(QColor("#3A3D42"), 1))
        p.drawLine(QPointF(8, self.height() - 0.5), QPointF(self.width() - 8, self.height() - 0.5))


class GroupHeader(QFrame):
    def __init__(self, page, st, count):
        super().__init__()
        self.setFixedHeight(44)
        lay = QHBoxLayout(self)
        lay.setContentsMargins(16, 4, 16, 4)
        lay.setSpacing(12)
        name = W.ElidedLabel(st.name, "on_dark", 13.5, 600, 0.4)
        name.setToolTip(st.name)
        name.setMinimumWidth(80)
        lay.addWidget(name)
        lay.addWidget(W.cap(f"{st.kind}  ·  {count} chop{'s' if count != 1 else ''}",
                            "on_dark_muted", 11, 500, 1.4))
        lay.addStretch(1)
        for text, tip, fn in (
                ("Approve all", "Approve every chop from this stem", lambda: page.approve_stem(st)),
                ("Remove all", "Remove every chop from this stem (Ctrl+Z brings them back)",
                 lambda: page.remove_stem_chops(st)),
                ("Loop options" if (st.engine == "groove" and st.mode == "auto") else "Edit regions",
                 "", lambda: page.win.open_stem(st))):
            b = W.HwButton(text, "dark", min_h=K.H_SMALL, px=10.5)
            if tip:
                b.setToolTip(tip)
            b.clicked.connect(fn)
            lay.addWidget(b)

    def paintEvent(self, _e):
        p = QPainter(self)
        r = QRectF(self.rect())
        p.fillRect(r, QColor(0, 0, 0, 70))
        p.setPen(QPen(QColor(0, 0, 0, 160), 1))
        p.drawLine(QPointF(0, 0.5), QPointF(r.width(), 0.5))
        p.setPen(QPen(QColor(255, 255, 255, 12), 1))
        p.drawLine(QPointF(0, r.height() - 0.5), QPointF(r.width(), r.height() - 0.5))
        p.fillRect(QRectF(0, 0, 3, r.height()), K.C("outline", 200))


class ChopRow(QFrame):
    def __init__(self, page, chop, stem, number):
        super().__init__()
        self.page, self.chop, self.stem = page, chop, stem
        self._press = None
        self._hover = False
        self.selected = False
        self.setAttribute(Qt.WA_Hover)
        self.setFixedHeight(60)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        self.setToolTip("Drag this row into FL Studio (or any folder) to use the sample right away")
        lay = QHBoxLayout(self)
        lay.setContentsMargins(*ROW_MARGINS)
        lay.setSpacing(ROW_SPACING)

        lay.addWidget(_fixed(W.IconLabel("grip", "on_dark_dim", COL["grip"]), COL["grip"]))
        self.num = _fixed(W.mono(str(number), "on_dark_muted", 13, 500, 0.4), COL["num"])
        lay.addWidget(self.num)
        self.play = W.HwButton("", "round", icon="play", min_h=COL["play"])
        self.play.setToolTip("Play and load into the editor (Space)")
        self.play.clicked.connect(lambda: page.select(self.chop, play=True))
        lay.addWidget(self.play)

        names = QVBoxLayout()
        names.setSpacing(2)
        names.setContentsMargins(0, 0, 0, 0)
        self.name = W.mono("", "on_dark", 13.5, 500, 0.3)
        names.addWidget(self.name)
        self.sub = W.cap("", "on_dark_muted", 11, 500, 1.1)
        names.addWidget(self.sub)
        holder = QWidget()
        holder.setLayout(names)
        holder.setFixedWidth(COL["name"])
        lay.addWidget(holder)

        self.wave = MiniWave()
        lay.addWidget(self.wave, 1)
        self.dur = _fixed(W.mono("", "on_dark", 13, 400, 0.4), COL["dur"])
        lay.addWidget(self.dur)

        self.combo = label_combo(chop.label)
        self.combo.setObjectName("flat")
        self.combo.setFixedWidth(COL["type"])
        self.combo.setFocusPolicy(Qt.ClickFocus)
        self.combo.setMinimumWidth(COL["type"])
        self.combo.currentTextChanged.connect(self._label_changed)
        lay.addWidget(self.combo)

        self.approve = W.ApprovePill(width=COL["approve"])
        self.approve.setToolTip("Approve (A approves and moves to the next chop)")
        self.approve.setChecked(chop.approved)
        self.approve.clicked.connect(lambda on: page.set_approved(self.chop, on))
        lay.addWidget(self.approve)
        self.clone_btn = W.HwButton("", "icon", icon="copy", min_h=COL["clone"])
        self.clone_btn.setToolTip("Clone this chop (Ctrl+D)")
        self.clone_btn.clicked.connect(lambda: page.clone_chop(self.chop))
        lay.addWidget(self.clone_btn)
        self.del_btn = W.HwButton("", "icon", icon="trash", min_h=COL["delete"])
        self.del_btn.setToolTip("Delete this chop (Delete key)")
        self.del_btn.clicked.connect(lambda: page.delete_chop(self.chop))
        lay.addWidget(self.del_btn)
        self.update_view()

    # ---- painting
    def enterEvent(self, e):
        self._hover = True
        self.update()

    def leaveEvent(self, e):
        self._hover = False
        self.update()

    def paintEvent(self, _e):
        p = QPainter(self)
        r = QRectF(self.rect())
        if self.selected:
            p.fillRect(r, K.C("row_sel"))
            p.fillRect(QRectF(0, 0, 4, r.height()), K.C("red_hi"))
        elif self._hover:
            p.fillRect(r, K.C("row_hover"))
        p.setPen(QPen(K.C("row_line"), 1))
        p.drawLine(QPointF(8, r.height() - 0.5), QPointF(r.width() - 8, r.height() - 0.5))

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
        self.approve.blockSignals(True)
        self.approve.setChecked(self.chop.approved)
        self.approve.blockSignals(False)
        self.approve.update()

    def update_view(self):
        self.name.setText(self.page.names.get(self.chop.id, ""))
        bits = [f"Stem: {self.stem.kind}"]
        if self.chop.reverse:
            bits.append("reversed")
        if self.chop.gain_db:
            bits.append(f"{self.chop.gain_db:+.1f} dB")
        sub = "  ·  ".join(bits)
        full = sub + (f"  ·  {self.chop.flag}" if self.chop.flag else "")
        fm = self.sub.fontMetrics()
        self.sub.setText(fm.elidedText(full.upper(), Qt.ElideRight, COL["name"] - 4))
        self.sub.setToolTip(f"From {self.stem.name}" + (f"\n{self.chop.flag}" if self.chop.flag else ""))
        W.recolor(self.sub, "warn" if is_warning(self.chop.flag) else "on_dark_muted")
        self.dur.setText(fmt_dur(self.chop.length, self.stem.sr))
        self.wave.set_chop(self.page.win.peaks(self.stem), self.chop.start, self.chop.end,
                           self.chop.reverse)
        self.update_thumb()

    def set_selected(self, on):
        self.selected = on
        self.update()


class ReviewPage(QWidget):
    def __init__(self, win):
        super().__init__()
        self.win = win
        self.rows: dict = {}
        self.names: dict = {}
        self.selected = None
        self._orig = {}
        self._loading_fx = False

        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 4, 0, 0)
        outer.setSpacing(12)

        # ---------------------------------------------------------- header
        head = W.Module("", margins=(20, 10, 20, 10))
        hl = QHBoxLayout()
        hl.setSpacing(10)
        self.count_lbl = W.ElidedLabel("", "on_dark", 21, 600, 2.2)
        self.count_lbl.setMinimumWidth(290)
        hl.addWidget(self.count_lbl)
        self.meter = W.LedMeter(28)
        self.meter.setMaximumWidth(420)
        self.meter.setMinimumWidth(80)
        self.meter.setFixedHeight(30)
        hl.addWidget(self.meter, 1)
        hl.addSpacing(8)
        self.undo_btn = W.HwButton("Undo", "key", icon="undo", min_h=K.H_KEY)
        self.undo_btn.setToolTip("Undo (Ctrl+Z)")
        self.undo_btn.clicked.connect(self.win.undo)
        self.redo_btn = W.HwButton("Redo", "key", icon="redo", min_h=K.H_KEY)
        self.redo_btn.setToolTip("Redo (Ctrl+Y)")
        self.redo_btn.clicked.connect(self.win.redo)
        self.approve_all = W.HwButton("Approve all", "key", icon="check", min_h=K.H_KEY)
        self.approve_all.clicked.connect(self.approve_everything)
        self.export_btn = W.HwButton("Export", "red", icon="export", min_h=K.H_KEY)
        self.export_btn.clicked.connect(self.win.export_all)
        for b in (self.undo_btn, self.redo_btn, self.approve_all):
            hl.addWidget(b)
        hl.addSpacing(4)
        hl.addWidget(self.export_btn)
        head.lay.addLayout(hl)
        outer.addWidget(head)

        # ------------------------------------------------------ trim module
        trim = W.Module("", margins=(16, 10, 16, 12))
        tl = trim.lay
        tl.setSpacing(8)
        th = QHBoxLayout()
        th.setSpacing(12)
        self.ed_name = W.mono("", "on_dark", 15, 500, 0.6)
        th.addWidget(self.ed_name)
        # AI suggestion / warning for the selected chop, next to its name
        self.warn_tile = W.Tile(alert=True, margins=(10, 0, 12, 0))
        self.warn_tile.setFixedHeight(32)
        self.warn_icon = W.IconLabel("warning", "warn", 18)
        self.warn_tile.lay.addWidget(self.warn_icon)
        self.ed_flag = W.ElidedLabel("", "warn", 12.5, 500, 0.3)
        self.warn_tile.lay.addWidget(self.ed_flag, 1)
        self.warn_tile.setMinimumWidth(120)
        th.addWidget(self.warn_tile, 1)
        self.flag_spacer = QWidget()
        self.flag_spacer.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)
        th.addWidget(self.flag_spacer, 1)
        self.sel_readout = W.Lcd("", "", value_px=13.5, min_w=190)
        self.sel_readout.setFixedHeight(32)
        th.addWidget(self.sel_readout)
        tl.addLayout(th)
        self.editor = TrimEditor()
        self.editor.setMinimumHeight(96)
        self.editor.changed.connect(self._trimmed)
        self.editor.seekRequested.connect(self.play_from)
        self.editor.selectionChanged.connect(lambda s, e: self._update_readout(s, e))
        tl.addWidget(self.editor, 1)
        self.ed_scroll = QScrollBar(Qt.Horizontal)
        self.ed_scroll.valueChanged.connect(self._scrolled)
        self.editor.viewChanged.connect(self._view_changed)
        tl.addWidget(self.ed_scroll)

        H = K.H_ROW
        # row 1: transport, loop, reset, snap, zoom, whole stem
        r1 = QHBoxLayout()
        r1.setSpacing(8)
        tp = W.Tile(margins=(5, 5, 5, 5))
        tp.lay.setSpacing(6)
        tp.setFixedHeight(H)
        self.ed_play = W.HwButton("", "key", icon="play", min_h=H - 10, icon_size=17)
        self.ed_play.setFixedWidth(48)
        self.ed_play.setToolTip("Play (Space)")
        self.ed_play.clicked.connect(self.play_selected)
        self.ed_stop = W.HwButton("", "key", icon="stop", min_h=H - 10, icon_size=17)
        self.ed_stop.setFixedWidth(48)
        self.ed_stop.setToolTip("Stop (Space)")
        self.ed_stop.clicked.connect(self.win.player.stop)
        tp.lay.addWidget(self.ed_play)
        tp.lay.addWidget(self.ed_stop)
        r1.addWidget(tp)
        self.ed_loop = W.LedToggle("Loop", "green", icon="loop", min_h=H)
        self.ed_loop.setToolTip("Loop playback (L). Loop chops always repeat so you can hear the seam.")
        self.ed_loop.setChecked(self.win.settings.value("loop_play", "false") == "true")
        self.ed_loop.toggled.connect(self._loop_toggled)
        r1.addWidget(self.ed_loop)
        self.ed_reset = W.HwButton("Reset trim", "dark", icon="reset", min_h=H, px=11.5)
        self.ed_reset.setToolTip("Put the start and end back where the chop was found")
        self.ed_reset.clicked.connect(self.reset_trim)
        r1.addWidget(self.ed_reset)
        self.ed_snap = W.LedToggle("Snap", "green", icon="magnet", min_h=H)
        self.ed_snap.setToolTip("Snap (S). On: a start dropped within about 12 ms of a hit lines "
                                "up with its attack. Off: no snapping at all.")
        self.ed_snap.setChecked(self.win.settings.value("snap_trim", "true") == "true")
        self.ed_snap.toggled.connect(self._snap_toggled)
        r1.addWidget(self.ed_snap)
        zt = W.Tile(margins=(12, 0, 8, 0))
        zt.setFixedHeight(H)
        self.zoom_cap = W.cap("Zoom", "on_dark", 11.5, 600, 1.6)
        zt.lay.addWidget(self.zoom_cap)
        zo = W.HwButton("", "icon", icon="minus", min_h=K.H_SMALL)
        zo.setToolTip("Zoom out")
        zo.clicked.connect(lambda: self.editor.zoom(1.6))
        zt.lay.addWidget(zo)
        self.zoom_slider = QSlider(Qt.Horizontal)
        self.zoom_slider.setRange(0, 1000)
        self.zoom_slider.setMinimumWidth(70)
        self.zoom_slider.valueChanged.connect(self._zoom_slid)
        zt.lay.addWidget(self.zoom_slider, 1)
        zi = W.HwButton("", "icon", icon="plus", min_h=K.H_SMALL)
        zi.setToolTip("Zoom in")
        zi.clicked.connect(lambda: self.editor.zoom(0.6))
        zt.lay.addWidget(zi)
        zc = W.HwButton("Chop", "dark", min_h=K.H_SMALL, px=10.5)
        zc.setToolTip("Zoom to the chop")
        zc.clicked.connect(self.editor.show_chop)
        zt.lay.addWidget(zc)
        r1.addWidget(zt, 1)
        self.whole_btn = W.HwButton("Whole stem", "dark", icon="expand", min_h=H, px=11.5)
        self.whole_btn.setToolTip("Show the entire stem")
        self.whole_btn.clicked.connect(self.editor.show_all)
        r1.addWidget(self.whole_btn)
        tl.addLayout(r1)

        # row 2: per-chop sound controls
        r2 = QHBoxLayout()
        r2.setSpacing(8)
        self.fade_in = W.KnobTile("Fade in", 0, 5000, " ms", 1, step=0.5, decimals=1, curve=3.2,
                                  tip="Fade-in length. Auto = a tiny de-click.")
        self.fade_out = W.KnobTile("Fade out", 0, 10000, " ms", 8, step=0.5, decimals=1, curve=3.2,
                                   tip="Fade-out length. Auto = a short de-click.")
        self.gain = W.KnobTile("Gain", -48, 0, " dB", 0, step=0.5, decimals=1,
                               tip="Every sample is normalized to −0.1 dB. Turn one down from there.")
        self.fade_auto = W.LedToggle("Auto fades", "green", min_h=H)
        self.fade_auto.setToolTip("On: automatic de-click fades. Turn a fade knob to set your own.")
        self.fade_auto.clicked.connect(self._auto_clicked)
        self.ed_reverse = W.LedToggle("Reverse", "red", icon="reverse", min_h=H)
        self.ed_reverse.setToolTip("Play and export this chop backwards (R). The file name gets 'Rev'.")
        self.ed_reverse.toggled.connect(self._reverse_toggled)
        self.ed_seam = W.LedToggle("Smooth loop seam", "red", min_h=H)
        self.ed_seam.setToolTip("Loops: blends the end into what comes just before the start, so "
                                "it repeats without a click. Length stays on the bars.")
        self.ed_seam.toggled.connect(self._seam_toggled)
        for w in (self.fade_in, self.fade_out):
            r2.addWidget(w, 3)
        r2.addWidget(self.fade_auto, 2)
        r2.addWidget(self.ed_reverse, 2)
        r2.addWidget(self.gain, 3)
        r2.addWidget(self.ed_seam, 3)
        tl.addLayout(r2)
        self.fade_in.valueChanged.connect(lambda v: self._fx_changed("fade_in_ms", v))
        self.fade_out.valueChanged.connect(lambda v: self._fx_changed("fade_out_ms", v))
        self.gain.valueChanged.connect(lambda v: self._fx_changed("gain_db", v))
        self.trim_mod = trim

        # ------------------------------------------------------------- list
        lm = W.Module("", margins=(8, 8, 8, 10))
        lm.lay.setSpacing(0)
        self.col_header = ColumnHeader()
        lm.lay.addWidget(self.col_header)
        self.scroll = QScrollArea()
        self.scroll.setWidgetResizable(True)
        self.scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.listw = QWidget()
        self.list_lay = QVBoxLayout(self.listw)
        self.list_lay.setSizeConstraint(QLayout.SetMinimumSize)
        self.list_lay.setContentsMargins(0, 0, 0, 0)
        self.list_lay.setSpacing(0)
        self.scroll.setWidget(self.listw)
        lm.lay.addWidget(self.scroll, 1)
        self.empty = W.mono("NOTHING TO REVIEW YET  ·  LOAD STEMS AND PRESS PROCESS ALL",
                            "on_dark_dim", 12.5, 500, 2.0)
        self.empty.setAlignment(Qt.AlignCenter)
        lm.lay.addWidget(self.empty)
        self.list_mod = lm

        # divider: drag to share the room between the editor and the list
        self.split = W.PanelSplitter(default_top=0.47)
        self.split.addWidget(trim)
        self.split.addWidget(lm)
        self.split.setCollapsible(0, True)
        self.split.setCollapsible(1, False)
        self.split.setStretchFactor(0, 47)
        self.split.setStretchFactor(1, 53)
        self.split.splitterMoved.connect(self._split_moved)
        outer.addWidget(self.split, 1)
        self._split_applied = False

        self.setFocusPolicy(Qt.StrongFocus)
        self.scroll.setFocusPolicy(Qt.NoFocus)
        for cls in (W.HwButton, W.LedToggle, QScrollBar, QSlider):
            for w_ in self.findChildren(cls):
                w_.setFocusPolicy(Qt.NoFocus)

        self._fx_timer = QTimer(self)
        self._fx_timer.setSingleShot(True)
        self._fx_timer.setInterval(350)
        self._fx_timer.timeout.connect(self._fx_settled)
        self._ph_timer = QTimer(self)
        self._ph_timer.setInterval(33)
        self._ph_timer.timeout.connect(self._tick)
        self._ph_timer.start()
        self._ph_row = None

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
        number = 0
        for c in self.win.chops:
            st = stems.get(c.stem_id)
            if st is None:
                continue
            if st.id != last:
                n = sum(1 for x in self.win.chops if x.stem_id == st.id)
                self.list_lay.addWidget(GroupHeader(self, st, n))
                last = st.id
            number += 1
            row = ChopRow(self, c, st, number)
            self.rows[c.id] = row
            self.list_lay.addWidget(row)
        self.list_lay.addStretch(1)
        self._rows_narrow = getattr(self, "_compact", (False, False))[0]
        for cls in (W.HwButton, W.ApprovePill):
            for w_ in self.listw.findChildren(cls):
                w_.setFocusPolicy(Qt.NoFocus)
        has = bool(self.win.chops)
        self.empty.setVisible(not has)
        self.scroll.setVisible(has)
        self.col_header.setVisible(has)
        if self.selected is None or self.selected.id not in self.rows:
            self.selected = None
            if self.win.chops:
                self.select(self.win.chops[0], play=False)
            else:
                self.editor.clear()
                self.ed_name.setText("")
                self._set_flag("")
                self.sel_readout.set(value="")
        else:
            self.select(self.selected, play=False)
        self.counts_changed()
        self.win.request_measure()

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
        narrow = getattr(self, "_compact", (False, False))[0]
        self.count_lbl.setText((f"{a}/{n} APPROVED" if narrow else f"{a} OF {n} APPROVED")
                               if n else "NO CHOPS YET")
        self.meter.set(a / n if n else 0)
        done = n > 0 and a == n
        self.export_btn.setEnabled(done and not self.win.busy)
        self.export_btn.setText(("Export all" if narrow else f"Export {n} files") if done else
                                ("Export" if narrow else "Export (approve all)"))
        self.export_btn.setToolTip(f"Export {n} files" if done else "")
        if not done:
            self.export_btn.setToolTip("Approve every chop to export")
        self.approve_all.setEnabled(n > 0 and not done)
        self.undo_btn.setEnabled(self.win.history.can_undo())
        self.redo_btn.setEnabled(self.win.history.can_redo())
        self.win.update_steps()

    def set_compact(self, narrow, short):
        if getattr(self, "_compact", None) == (narrow, short):
            return
        changed_cols = getattr(self, "_compact", (None, None))[0] != narrow
        self._compact = (narrow, short)
        COL.clear()
        COL.update(COL_NARROW if narrow else COL_WIDE)
        self.count_lbl.setFont(K.font(17 if narrow else 21, 600, 1.6 if narrow else 2.2))
        self.count_lbl.setMinimumWidth(200 if narrow else 290)
        self.meter.setMinimumWidth(70 if narrow else 160)
        for b in (self.undo_btn, self.redo_btn, self.approve_all):
            b.setMinimumWidth(0 if narrow else 122)
        self.export_btn.setMinimumWidth(self.export_btn.width_for("Export all") if narrow else
                                        self.export_btn.width_for("Export (approve all)"))
        for tg in (self.fade_auto, self.ed_reverse, self.ed_seam, self.ed_loop, self.ed_snap):
            tg.show_state = not narrow
            tg.updateGeometry()
            tg.update()
        self.ed_seam.label = "Seam" if narrow else "Smooth loop seam"
        self.fade_auto.label = "Auto" if narrow else "Auto fades"
        for kt in (self.fade_in, self.fade_out, self.gain):
            kt.set_compact(narrow)
        self.ed_reset.setText("Reset" if narrow else "Reset trim")
        self.whole_btn.setText("Whole" if narrow else "Whole stem")
        self.zoom_cap.setVisible(not narrow)
        for b in (self.ed_reset, self.whole_btn):
            b.updateGeometry()
        self.counts_changed()
        if changed_cols:
            old = self.col_header
            self.col_header = ColumnHeader()
            self.list_mod.lay.replaceWidget(old, self.col_header)
            old.deleteLater()
            self.col_header.setVisible(bool(self.win.chops))
        if (self.rows and not getattr(self.win, "_measuring", False)
                and getattr(self, "_rows_narrow", narrow) != narrow):
            self._rebuild_keep_scroll()

    # -------------------------------------------------------------- divider
    def showEvent(self, e):
        super().showEvent(e)
        if not self._split_applied:
            self._split_applied = True
            QTimer.singleShot(0, self._apply_saved_split)

    def _apply_saved_split(self):
        try:
            f = float(self.win.settings.value("review_split", self.split.default_top))
        except (TypeError, ValueError):
            f = self.split.default_top
        self.split.set_top_fraction(max(0.0, min(0.9, f)))
        self.split.handle(1).update()

    def _split_moved(self, *_):
        self.win.settings.setValue("review_split", round(self.split.top_fraction(), 4))
        self.split.handle(1).update()

    def _set_flag(self, text):
        warn = is_warning(text)
        self.ed_flag.setText(text)
        self.warn_tile.set_alert(warn)
        self.warn_icon.icon_name = "warning" if warn else "bulb"
        self.warn_icon.color_key = "warn" if warn else "on_dark_muted"
        self.warn_icon.update()
        W.recolor(self.ed_flag, "warn" if warn else "on_dark_muted")
        self.warn_tile.setToolTip(text)
        self.warn_tile.setVisible(bool(text))
        self.flag_spacer.setVisible(not text)

    def _update_readout(self, s, e):
        st = self.win.stem_by_id(self.selected.stem_id) if self.selected is not None else None
        if st is None:
            self.sel_readout.set(value="")
            return
        extra = "  ·  REV" if self.selected.reverse else ""
        self.sel_readout.set(value=f"{(e - s) / st.sr:.3f} S SELECTED{extra}")

    # ---------------------------------------------------------------- toggles
    def _snap_toggled(self, on):
        self.win.settings.setValue("snap_trim", "true" if on else "false")

    def _loop_toggled(self, on):
        self.win.settings.setValue("loop_play", "true" if on else "false")
        if self.selected is not None and self.win.player.playing_id == self.selected.id:
            self.play_selected()

    def _reverse_toggled(self, on):
        if self._loading_fx or self.selected is None or self.selected.reverse == on:
            return
        self.win.history.push()
        self.selected.reverse = on
        self._after_fx(names=True)
        self.play_selected()

    def _seam_toggled(self, on):
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
        self.fade_auto.setChecked(c.fade_in_ms is None and c.fade_out_ms is None)
        self._after_fx()
        self._fx_timer.start()

    def _fx_settled(self):
        if self.selected is not None:
            self.play_selected()

    def _auto_clicked(self, on):
        c = self.selected
        if c is None:
            self.fade_auto.setChecked(False)
            return
        if on:
            self._auto_fades()
        else:   # can't turn "auto" off directly: turning a knob does that
            self.fade_auto.setChecked(c.fade_in_ms is None and c.fade_out_ms is None)

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
        self._update_readout(c.start, c.end)
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
        self.ed_seam.setEnabled(c.kind == "loop")
        self.ed_seam.setToolTip("" if c.kind == "loop" else "Only for loops")
        self.fade_auto.setChecked(c.fade_in_ms is None and c.fade_out_ms is None)
        self._loading_fx = False
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
        name = self.names.get(c.id) or "Xenakis_sample.wav"
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
            drag.setPixmap(pm.scaledToWidth(min(220, max(1, pm.width())), Qt.SmoothTransformation))
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
        self._set_flag(chop.flag)
        self._load_editor(chop, st)
        self._load_fx(chop)
        self._update_readout(chop.start, chop.end)
        if play:
            self.play_selected()

    def _load_editor(self, chop, st):
        def snap(s, st=st, chop=chop):
            if not self.ed_snap.isChecked() or chop.kind == "loop":
                return s           # loops stay where you put them (bar lines are yours to move)
            return magnet_to_hit(st, s)

        def snap_move(s, st=st, chop=chop):
            """Moving a loop with Snap on keeps it on the bar grid."""
            if not self.ed_snap.isChecked() or chop.kind != "loop":
                return s
            grid = st.analysis.get("grid") or {}
            bpm = float(st.options.get("bpm") or grid.get("bpm") or 0)
            if bpm <= 0:
                return s
            bar = 240.0 * st.sr / bpm
            d0 = float(grid.get("downbeat", 0)) % bar
            return int(round(d0 + round((s - d0) / bar) * bar))
        self.editor.snap_move = snap_move if chop.kind == "loop" else None
        self.editor.set_chop(self.win.peaks(st), st.frames, st.sr, chop.start, chop.end, snap,
                             keep_view=self.editor.is_whole())
        self._view_changed(self.editor.view_a, self.editor.view_b)

    def _view_changed(self, a, b):
        span = max(1, b - a)
        n = max(1, self.editor.n)
        self.ed_scroll.blockSignals(True)
        self.ed_scroll.setRange(0, max(0, n - span))
        self.ed_scroll.setPageStep(span)
        self.ed_scroll.setSingleStep(max(1, span // 20))
        self.ed_scroll.setValue(a)
        self.ed_scroll.setVisible(span < n)
        self.ed_scroll.blockSignals(False)
        lo = max(1.0, 0.01 * self.editor.sr)
        if n > lo:
            v = math.log(span / n) / math.log(lo / n)
            self.zoom_slider.blockSignals(True)
            self.zoom_slider.setValue(int(round(max(0, min(1, v)) * 1000)))
            self.zoom_slider.blockSignals(False)

    def _zoom_slid(self, v):
        n = max(1, self.editor.n)
        lo = max(1.0, 0.01 * self.editor.sr)
        if self.editor.cache is None or n <= lo:
            return
        span = n * (lo / n) ** (v / 1000.0)
        a, b = self.editor.view_a, self.editor.view_b
        sel_c = (self.editor.start + self.editor.end) / 2
        center = sel_c if a <= sel_c <= b else (a + b) / 2
        self.editor.set_view(int(center - span / 2), int(center + span / 2))

    def _scrolled(self, v):
        span = self.editor.view_b - self.editor.view_a
        self.editor.set_view(v, v + span)

    # ------------------------------------------------------------ playback
    def toggle_play(self):
        if self.win.player.playing_id is not None:
            self.win.player.stop()
        else:
            self.play_selected()

    def play_from(self, s):
        """Play the whole stem from a clicked spot (until stopped). The selection is untouched."""
        c = self.selected
        if c is None:
            return
        st = self.win.stem_by_id(c.stem_id)
        s = int(max(0, min(st.frames - 1, s)))
        if not self.win.player.play(st.audio[s:], st.sr, ("seek", st.id, s)):
            self.win.status(self.win.player.error or "")
        self.setFocus()

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
        row = self.rows.get(p.playing_id) if playing else None
        if self._ph_row is not None and self._ph_row is not row:
            try:
                self._ph_row.wave.set_playhead(None)
            except RuntimeError:
                pass
        self._ph_row = row
        if row is not None:
            c = row.chop
            row.wave.set_playhead(min(1.0, pos / max(1, c.length)))
        pid = p.playing_id
        if playing and self.selected is not None and pid == self.selected.id:
            c = self.selected
            s = (c.end - pos) if c.reverse else (c.start + pos)
            self.editor.set_playhead(s)
        elif (playing and self.selected is not None and isinstance(pid, tuple)
              and pid[1] == self.selected.stem_id):
            self.editor.set_playhead(pid[2] + pos)
            if pid[2] + pos > self.editor.view_b and self.editor.drag is None:
                span = self.editor.view_b - self.editor.view_a
                self.editor.set_view(pid[2] + pos - int(span * 0.1),
                                     pid[2] + pos + int(span * 0.9))   # follow the playhead
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
        self._update_readout(c.start, c.end)
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
        self.update()
