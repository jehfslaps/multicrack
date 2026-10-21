"""Manual mode: mark regions by hand (vocals, melodic parts, anything)."""
from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (QAbstractItemView, QCheckBox, QDialog, QHBoxLayout, QHeaderView,
                               QPushButton, QTableWidget, QTableWidgetItem, QVBoxLayout, QWidget)

from ..core.audio import render_chop
from ..core.model import Chop
from .common import (fmt_time, label, label_combo, magnet_to_hit, panel, snap_to_sound,
                     trim_tail)
from .waveform import StemView

DEFAULT_LABEL = {"vocal": "Vocal Chop", "guitar": "Guitar Stab", "fx": "FX", "synth": "Synth Stab",
                 "bass": "Bass", "keys": "Keys", "strings": "Strings", "brass": "Brass",
                 "kick": "Kick", "snare": "Snare", "clap": "Clap", "hats": "Closed Hat",
                 "cymbals": "Crash", "toms": "Tom"}


class ManualDialog(QDialog):
    def __init__(self, win, stem):
        super().__init__(win)
        self.win, self.stem = win, stem
        self.setWindowTitle(f"Edit regions · {stem.name}")
        self.resize(1180, 760)
        self.regions = []
        for c in win.chops:
            if c.stem_id == stem.id:
                self.regions.append(dict(start=c.start, end=c.end, label=c.label, kind=c.kind,
                                         bars=c.bars, origin=c.origin, flag=c.flag,
                                         approved=c.approved,
                                         style="ai" if c.origin in ("ai", "auto") else "user"))

        lay = QVBoxLayout(self)
        lay.setContentsMargins(16, 14, 16, 14)
        lay.setSpacing(12)

        head = QHBoxLayout()
        head.addWidget(label(stem.name, "h2"))
        head.addWidget(label("Manual mode" if stem.mode == "manual" else f"AI detected: {stem.kind}",
                             "muted"))
        head.addStretch(1)
        self.play_btn = QPushButton("Play selected")
        self.play_btn.clicked.connect(self.play_selected)
        head.addWidget(self.play_btn)
        stop = QPushButton("Stop")
        stop.clicked.connect(win.player.stop)
        head.addWidget(stop)
        zo = QPushButton("−")
        zo.setToolTip("Zoom out")
        zo.setFixedWidth(36)
        zi = QPushButton("+")
        zi.setToolTip("Zoom in")
        zi.setFixedWidth(36)
        fit = QPushButton("Whole file")
        head.addWidget(zo)
        head.addWidget(zi)
        head.addWidget(fit)
        self.snap = QCheckBox("Snap to start of sound")
        self.snap.setChecked(True)
        head.addWidget(self.snap)
        lay.addLayout(head)

        vp, vl = panel(spacing=6, margins=(10, 10, 10, 8))
        vl.addWidget(label("Click and drag across the waveform to mark a region. Drag a region's "
                           "edge to resize it. Dashed boxes came from the AI. Scroll to zoom, "
                           "Shift+scroll to move.", "muted", wrap=True))
        self.view = StemView(editable=True)
        self.view.setMinimumHeight(220)
        self.view.set_stem(win.peaks(stem), stem.frames, stem.sr)
        self.view.snap = lambda s: snap_to_sound(stem, s) if self.snap.isChecked() else s
        self.view.snap_edge = lambda s: magnet_to_hit(stem, s) if self.snap.isChecked() else s
        self.view.regionAdded.connect(self.add_region)
        self.view.regionChanged.connect(self.region_changed)
        self.view.regionSelected.connect(self.select_row)
        vl.addWidget(self.view)
        lay.addWidget(vp)
        zo.clicked.connect(lambda: self.view.zoom(1.5))
        zi.clicked.connect(lambda: self.view.zoom(0.66))
        fit.clicked.connect(lambda: self.view.set_stem(win.peaks(stem), stem.frames, stem.sr))

        self.table = QTableWidget(0, 7)
        self.table.setHorizontalHeaderLabels(["#", "Start", "End", "Label", "From", "", ""])
        hh = self.table.horizontalHeader()
        for c, w in ((0, 50), (1, 110), (2, 110), (3, 200), (4, 80), (5, 70), (6, 90)):
            hh.setSectionResizeMode(c, QHeaderView.Fixed)
            self.table.setColumnWidth(c, w)
        hh.setStretchLastSection(True)
        hh.setDefaultAlignment(Qt.AlignLeft | Qt.AlignVCenter)
        self.table.verticalHeader().setVisible(False)
        self.table.setShowGrid(False)
        self.table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.table.setSelectionMode(QAbstractItemView.SingleSelection)
        self.table.verticalHeader().setDefaultSectionSize(42)
        self.table.itemSelectionChanged.connect(self._table_selected)
        lay.addWidget(self.table, 1)

        bottom = QHBoxLayout()
        bottom.addWidget(label("Each region is trimmed of silence, de-clicked and normalized "
                               "automatically.", "muted"), 1)
        cancel = QPushButton("Cancel")
        cancel.clicked.connect(self.reject)
        bottom.addWidget(cancel)
        self.apply_btn = QPushButton("")
        self.apply_btn.setObjectName("primary")
        self.apply_btn.clicked.connect(self.apply)
        bottom.addWidget(self.apply_btn)
        lay.addLayout(bottom)
        self.refresh()

    # ------------------------------------------------------------------
    def refresh(self, select=-1):
        self.regions.sort(key=lambda r: r["start"])
        n_user = 0
        for i, r in enumerate(self.regions):
            if r["style"] == "user":
                n_user += 1
            r["tag"] = "AI" if r["style"] == "ai" else str(i + 1)
        self.view.set_regions(self.regions, select)
        sr = self.stem.sr
        self.table.blockSignals(True)
        self.table.setRowCount(len(self.regions))
        for i, r in enumerate(self.regions):
            self.table.setItem(i, 0, QTableWidgetItem(str(i + 1)))
            self.table.setItem(i, 1, QTableWidgetItem(fmt_time(r["start"], sr)))
            self.table.setItem(i, 2, QTableWidgetItem(fmt_time(r["end"], sr)))
            cb = label_combo(r["label"])
            cb.currentTextChanged.connect(lambda txt, r=r: self._relabel(r, txt))
            self.table.setCellWidget(i, 3, self._pad(cb))
            self.table.setItem(i, 4, QTableWidgetItem("AI" if r["style"] == "ai" else "You"))
            pb = QPushButton("Play")
            pb.setObjectName("link")
            pb.clicked.connect(lambda _c=False, i=i: self.play(i))
            self.table.setCellWidget(i, 5, pb)
            rm = QPushButton("Remove")
            rm.setObjectName("link")
            rm.clicked.connect(lambda _c=False, i=i: self.remove(i))
            self.table.setCellWidget(i, 6, rm)
        self.table.blockSignals(False)
        if 0 <= select < len(self.regions):
            self.table.selectRow(select)
        n = len(self.regions)
        self.apply_btn.setText(f"Send {n} region{'s' if n != 1 else ''} to Review")
        self.apply_btn.setEnabled(True)

    @staticmethod
    def _pad(w):
        holder = QWidget()
        lay = QHBoxLayout(holder)
        lay.setContentsMargins(4, 4, 8, 4)
        lay.addWidget(w)
        return holder

    def _relabel(self, r, txt):
        txt = txt.strip()
        if txt and not txt.startswith("—"):
            r["label"] = txt

    def add_region(self, a, b):
        b = trim_tail(self.stem, a, b)
        lab = DEFAULT_LABEL.get(self.stem.context, "Synth Stab")
        self.regions.append(dict(start=a, end=b, label=lab, kind="region", bars=None,
                                 origin="manual", flag="", approved=False, style="user"))
        self.refresh()
        idx = next(i for i, r in enumerate(self.regions) if r["start"] == a and r["end"] == b)
        self.refresh(idx)
        self.play(idx)

    def region_changed(self, i, a, b):
        r = self.regions[i]
        r["start"], r["end"] = a, b
        r["style"], r["origin"] = "user", "manual"
        self.refresh(i)

    def select_row(self, i):
        self.table.blockSignals(True)
        self.table.selectRow(i)
        self.table.blockSignals(False)

    def _table_selected(self):
        rows = self.table.selectionModel().selectedRows()
        if rows:
            i = rows[0].row()
            self.view.selected = i
            r = self.regions[i]
            if not (self.view.view_a <= r["start"] and r["end"] <= self.view.view_b):
                self.view.show_range(r["start"], r["end"])
            self.view.update()

    def remove(self, i):
        if 0 <= i < len(self.regions):
            self.regions.pop(i)
            self.refresh()

    def play(self, i):
        if not (0 <= i < len(self.regions)):
            return
        r = self.regions[i]
        c = Chop(stem_id=self.stem.id, start=r["start"], end=r["end"], label=r["label"],
                 kind=r["kind"] if r["kind"] != "region" else "event")
        self.win.player.play(render_chop(self.stem, c), self.stem.sr)

    def play_selected(self):
        rows = self.table.selectionModel().selectedRows()
        if rows:
            self.play(rows[0].row())

    def apply(self):
        new = []
        for r in self.regions:
            new.append(Chop(stem_id=self.stem.id, start=int(r["start"]), end=int(r["end"]),
                            label=r["label"], kind=r["kind"] if r["kind"] != "region" else "event",
                            bars=r["bars"], origin=r["origin"],
                            flag="" if r["style"] == "user" else r["flag"],
                            approved=r["approved"] and r["style"] != "user"))
        self.accept()
        self.win.replace_chops(self.stem, new, status=f"{len(new)} chops")
