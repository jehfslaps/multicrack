"""Loop & section options for drum / percussion stems (hardware skin)."""
from __future__ import annotations

from PySide6.QtCore import QRectF, Qt
from PySide6.QtGui import QColor, QPainter, QPen
from PySide6.QtWidgets import (QAbstractItemView, QAbstractSpinBox, QButtonGroup, QCheckBox,
                               QDoubleSpinBox, QFrame, QHBoxLayout, QHeaderView, QLineEdit,
                               QRadioButton, QTableWidget, QTableWidgetItem, QVBoxLayout, QWidget)

from ..core.naming import chop_key
from .common import fmt_time
from .skin import core as K
from .skin import widgets as W
from .skin.dialogs import HwDialog
from .waveform import WAVE, StemView


def _field(caption, widget):
    box = QVBoxLayout()
    box.setSpacing(6)
    box.addWidget(W.cap(caption, "on_dark", 11.5, 600, 1.6))
    box.addWidget(widget)
    return box


class SpanCard(QFrame):
    def __init__(self, color, name, where, hits):
        super().__init__()
        self.color = color
        self.setMinimumHeight(64)
        lay = QVBoxLayout(self)
        lay.setContentsMargins(14, 8, 14, 8)
        lay.setSpacing(4)
        top = W.mono(name, "on_dark", 13, 600, 0.5)
        top.setStyleSheet(f"color: {QColor(color).lighter(150).name()}; background: transparent;")
        top.setProperty("skincolor", None)
        lay.addWidget(top)
        row = QHBoxLayout()
        row.addWidget(W.mono(where, "on_dark", 13, 500, 0.3))
        row.addStretch(1)
        row.addWidget(W.cap(f"{hits} hits", "on_dark_muted", 11.5, 600, 1.2))
        lay.addLayout(row)

    def paintEvent(self, _e):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        r = QRectF(self.rect()).adjusted(0.5, 0.5, -0.5, -0.5)
        c = QColor(self.color)
        fill = QColor(c)
        fill.setAlpha(46)
        p.setBrush(fill)
        p.setPen(QPen(c.lighter(115), 1.3))
        p.drawRoundedRect(r, 4, 4)


class LoopDialog(HwDialog):
    def __init__(self, win, stem):
        super().__init__(win, "Loop options", (1100, 880))
        self.win, self.stem = win, stem
        opts = stem.options
        sec = stem.analysis.get("sections") or {}
        grid = stem.analysis.get("grid") or {}
        body = self.body
        body.setSpacing(14)

        # ---- stem / ai / tempo
        top = QHBoxLayout()
        top.setSpacing(18)
        name = QLineEdit(stem.name)
        name.setReadOnly(True)
        name.setFocusPolicy(Qt.NoFocus)
        kind = QLineEdit(stem.kind)
        kind.setReadOnly(True)
        kind.setFocusPolicy(Qt.NoFocus)
        self.bpm = QDoubleSpinBox()
        self.bpm.setRange(40, 250)
        self.bpm.setDecimals(2)
        self.bpm.setSuffix(" BPM")
        self.bpm.setButtonSymbols(QAbstractSpinBox.NoButtons)
        self.bpm.setValue(float(opts.get("bpm") or sec.get("bpm") or grid.get("bpm") or 120))
        self.bpm.setToolTip("The song tempo. Change it only if the loops land off the beat.")
        self.bpm.setFocusPolicy(Qt.ClickFocus)
        top.addLayout(_field("Stem", name), 3)
        top.addLayout(_field("AI detected", kind), 3)
        top.addLayout(_field("Tempo", self.bpm), 2)
        body.addLayout(top)

        # ---- loop length
        lg = W.GroupFrame("Loop length", layout="h", margins=(18, 24, 18, 14))
        lg.lay.setSpacing(18)
        self.bar_group = QButtonGroup(self)
        cur = int(opts.get("bars", 4))
        for n in (2, 4, 8, 16):
            b = W.HwButton(f"{n} bars", "seg", checkable=True, min_h=K.H_KEY, px=14)
            b.setChecked(n == cur)
            self.bar_group.addButton(b, n)
            lg.lay.addWidget(b, 1)
        self.bar_group.setExclusive(True)
        body.addWidget(lg)

        # ---- overview
        ov = W.GroupFrame("", margins=(14, 18, 14, 10))
        self.view = StemView(editable=False)
        self.view.setMinimumHeight(190)
        self.view.set_stem(win.peaks(stem), stem.frames, stem.sr)
        bands, regions, labels = [], [], []
        bpm = float(sec.get("bpm") or 120)
        bar = 240.0 * stem.sr / bpm
        d0 = float(grid.get("downbeat", 0)) % bar if grid else 0.0
        grooves = sec.get("grooves", [])
        for i, g in enumerate(grooves):
            color = WAVE["groove"][i % len(WAVE["groove"])]
            for part in g["where"].split(", "):
                try:
                    a, b = part.replace("bars ", "").split("–")
                    s0, s1 = d0 + (int(a) - 1) * bar, d0 + int(b) * bar
                    bands.append(dict(start=s0, end=s1, color=color, name=g["name"]))
                    labels.append((s0, a))
                    labels.append((s1, b))
                except ValueError:
                    pass
            regions.append(dict(start=g["start"], end=g["end"], style="loop", color=color,
                                tag=g["name"].split()[-1]))
        self.view.bands = bands
        self.view.bar_labels = labels
        self.view.ticks = [c.start for c in win.chops
                           if c.stem_id == stem.id and c.kind in ("roll", "hit")]
        self.view.set_regions(regions)
        ov.lay.addWidget(self.view)
        body.addWidget(ov, 3)

        # ---- selected loop spans
        if grooves:
            sp = W.GroupFrame("Selected loop spans", layout="h", margins=(16, 24, 16, 14))
            sp.lay.setSpacing(14)
            for i, g in enumerate(grooves):
                where = "Bars " + ", ".join(p.replace("bars ", "") for p in g["where"].split(", "))
                sp.lay.addWidget(SpanCard(WAVE["groove"][i % len(WAVE["groove"])], g["name"],
                                          where, g["hits"]), 1)
            body.addWidget(sp)

        # ---- loop settings table
        st_g = W.GroupFrame("Loop settings", margins=(10, 22, 10, 8))
        self.table = QTableWidget(0, 5)
        self.table.setHorizontalHeaderLabels(["SECTION", "WHERE", "LOOP FILE NAME", "INCLUDE",
                                              "ALSO CHOP"])
        hh = self.table.horizontalHeader()
        for c, w in enumerate((170, 220, 0, 110, 210)):
            hh.setSectionResizeMode(c, QHeaderView.Stretch if w == 0 else QHeaderView.Fixed)
            if w:
                self.table.setColumnWidth(c, w)
        hh.setDefaultAlignment(Qt.AlignLeft | Qt.AlignVCenter)
        hh.setFont(K.font(11, 600, 1.4))
        hh.setFixedHeight(34)
        self.table.verticalHeader().setVisible(False)
        self.table.verticalHeader().setDefaultSectionSize(42)
        self.table.setShowGrid(False)
        self.table.setSelectionMode(QAbstractItemView.NoSelection)
        self.table.setFocusPolicy(Qt.NoFocus)
        self.table.setFont(K.font(13, 400, 0.3))
        self.groove_boxes = {}
        gopts = opts.setdefault("grooves", {})
        self.table.setRowCount(max(1, len(grooves)))
        for r, gr in enumerate(grooves):
            go = gopts.setdefault(gr["name"], {"loop": True, "chop": True})
            cell = QWidget()
            cl = QHBoxLayout(cell)
            cl.setContentsMargins(8, 0, 4, 0)
            cl.setSpacing(10)
            cl.addWidget(W.Swatch(WAVE["groove"][r % len(WAVE["groove"])]))
            cl.addWidget(W.mono(gr["name"], "on_dark", 13, 500, 0.3))
            cl.addStretch(1)
            self.table.setCellWidget(r, 0, cell)
            where = "Bars " + ", ".join(p.replace("bars ", "") for p in gr["where"].split(", "))
            it = QTableWidgetItem(where)
            it.setToolTip(where + f"  ·  starts {fmt_time(gr['start'], stem.sr)}")
            self.table.setItem(r, 1, it)
            fname = chop_key(gr["label"], gr["bars"])
            note = "  (section is shorter)" if gr.get("short") else ""
            self.table.setItem(r, 2, QTableWidgetItem(f"{win.prefix()}{fname}_##.wav{note}"))
            lb = QCheckBox()
            lb.setChecked(go["loop"])
            cb = QCheckBox(f"Also chop ({gr['hits']} hits)")
            cb.setChecked(go["chop"])
            self.table.setCellWidget(r, 3, self._pad(lb))
            self.table.setCellWidget(r, 4, self._pad(cb))
            self.groove_boxes[gr["name"]] = (lb, cb)
        if not grooves:
            self.table.setSpan(0, 0, 1, 5)
            msg = W.mono("No repeating groove found in this file. Rolls and single hits are still "
                         "chopped.", "on_dark_muted", 13, 400, 0.3)
            self.table.setCellWidget(0, 0, self._pad(msg))
        self.table.setFixedHeight(34 + 42 * max(1, len(grooves)) + 4)
        st_g.lay.addWidget(self.table)
        body.addWidget(st_g)

        # ---- rolls / single hits
        bottom = QHBoxLayout()
        bottom.setSpacing(16)
        rg = W.GroupFrame("Rolls / fills", layout="h", margins=(18, 24, 18, 12))
        rg.lay.setSpacing(28)
        self.roll_group = QButtonGroup(self)
        mode = opts.get("roll_mode", "One-shot")
        for i, text in enumerate(("One-shot", "Loop", "Skip")):
            rb = QRadioButton(text)
            rb.setChecked(text == mode)
            self.roll_group.addButton(rb, i)
            rg.lay.addWidget(rb)
        rg.lay.addStretch(1)
        rg.lay.addWidget(W.cap(f"{sec.get('rolls', 0)} found · up to 6 kept", "on_dark_muted",
                               11, 500, 1.2))
        bottom.addWidget(rg, 3)
        hg = W.GroupFrame("Single hits", layout="h", margins=(18, 24, 18, 12))
        self.hits = QCheckBox("Include")
        self.hits.setChecked(opts.get("include_hits", True))
        hg.lay.addWidget(self.hits)
        hg.lay.addStretch(1)
        hg.lay.addWidget(W.cap(f"{sec.get('hits', 0)} outside the grooves", "on_dark_muted",
                               11, 500, 1.2))
        bottom.addWidget(hg, 2)
        body.addLayout(bottom)

        # ---- buttons
        btns = QHBoxLayout()
        note = W.cap("Hits are pooled: up to 3 of each sound. Anything the AI can't name is "
                     "called Perc.", "on_dark_muted", 11, 500, 1.0)
        note.setWordWrap(True)
        btns.addWidget(note, 1)
        cancel = W.HwButton("Cancel", "dark", min_h=K.H_KEY)
        cancel.setMinimumWidth(170)
        cancel.clicked.connect(self.reject)
        apply = W.HwButton("Apply and send to review", "red", min_h=K.H_KEY)
        apply.setMinimumWidth(300)
        apply.clicked.connect(self.apply)
        btns.addWidget(cancel)
        btns.addSpacing(10)
        btns.addWidget(apply)
        body.addLayout(btns)

    @staticmethod
    def _pad(w):
        holder = QWidget()
        lay = QHBoxLayout(holder)
        lay.setContentsMargins(8, 0, 4, 0)
        lay.addWidget(w)
        lay.addStretch(1)
        return holder

    def apply(self):
        st = self.stem
        opts = st.options
        grid = st.analysis.get("grid") or {}
        bpm = round(self.bpm.value(), 2)
        opts["bpm"] = None if grid and abs(bpm - float(grid.get("bpm", 0))) < 0.005 else bpm
        opts["bars"] = int(self.bar_group.checkedId()) if self.bar_group.checkedId() > 0 else 4
        opts["roll_mode"] = ("One-shot", "Loop", "Skip")[max(0, self.roll_group.checkedId())]
        opts["include_hits"] = self.hits.isChecked()
        for name, (lb, cb) in self.groove_boxes.items():
            opts["grooves"][name] = {"loop": lb.isChecked(), "chop": cb.isChecked()}
        self.accept()
        self.win.rechop(st)
