"""Manual mode: mark regions by hand (vocals, melodic parts, anything)."""
from __future__ import annotations

from dataclasses import replace

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (QAbstractItemView, QHBoxLayout, QHeaderView, QTableWidget,
                               QTableWidgetItem, QVBoxLayout, QWidget)

from ..core.audio import render_chop
from ..core.model import Chop
from .common import fmt_time, label_combo, magnet_to_hit, snap_to_sound, trim_tail
from .skin import core as K
from .skin import widgets as W
from .skin.dialogs import HwDialog
from .waveform import StemView

DEFAULT_LABEL = {"vocal": "Vocal Chop", "guitar": "Guitar Stab", "fx": "FX", "synth": "Synth Stab",
                 "bass": "Bass", "keys": "Keys", "strings": "Strings", "brass": "Brass",
                 "kick": "Kick", "snare": "Snare", "clap": "Clap", "hats": "Closed Hat",
                 "cymbals": "Crash", "toms": "Tom"}


class ManualDialog(HwDialog):
    def __init__(self, win, stem):
        super().__init__(win, "Edit regions", (1120, 760))
        self.win, self.stem = win, stem
        self.regions = []
        for c in win.chops:
            if c.stem_id == stem.id:
                self.regions.append(dict(start=c.start, end=c.end, label=c.label, kind=c.kind,
                                         bars=c.bars, origin=c.origin, flag=c.flag,
                                         approved=c.approved, src=c,
                                         style="ai" if c.origin in ("ai", "auto") else "user"))
        lay = self.body
        lay.setSpacing(12)

        head = QHBoxLayout()
        head.setSpacing(10)
        info = QVBoxLayout()
        info.setSpacing(3)
        info.addWidget(W.mono(stem.name, "on_dark", 15, 600, 0.4))
        info.addWidget(W.cap("Manual mode" if stem.mode == "manual" else f"AI detected: {stem.kind}",
                             "on_dark_muted", 11, 500, 1.4))
        head.addLayout(info)
        head.addStretch(1)
        self.play_btn = W.HwButton("Play", "key", icon="play", min_h=40)
        self.play_btn.setToolTip("Play the selected region")
        self.play_btn.clicked.connect(self.play_selected)
        head.addWidget(self.play_btn)
        stop = W.HwButton("", "key", icon="stop", min_h=40)
        stop.setFixedWidth(50)
        stop.clicked.connect(win.player.stop)
        head.addWidget(stop)
        head.addSpacing(8)
        zo = W.HwButton("", "icon", icon="minus", min_h=40)
        zo.setToolTip("Zoom out")
        zi = W.HwButton("", "icon", icon="plus", min_h=40)
        zi.setToolTip("Zoom in")
        fit = W.HwButton("Whole file", "dark", icon="expand", min_h=40, px=11.5)
        head.addWidget(zo)
        head.addWidget(zi)
        head.addWidget(fit)
        head.addSpacing(8)
        self.snap = W.LedToggle("Snap", "green", icon="magnet", min_h=40)
        self.snap.setToolTip("Snap new regions to the start of the sound")
        self.snap.setChecked(True)
        head.addWidget(self.snap)
        lay.addLayout(head)

        vg = W.GroupFrame("", margins=(12, 16, 12, 10))
        hint = W.cap("Drag across the waveform to mark a region  ·  drag an edge to resize  ·  "
                     "dashed = AI  ·  scroll to zoom", "on_dark_muted", 11, 500, 1.0)
        hint.setWordWrap(True)
        vg.lay.addWidget(hint)
        self.view = StemView(editable=True)
        self.view.setMinimumHeight(220)
        self.view.set_stem(win.peaks(stem), stem.frames, stem.sr)
        self.view.snap = lambda s: snap_to_sound(stem, s) if self.snap.isChecked() else s
        self.view.snap_edge = lambda s: magnet_to_hit(stem, s) if self.snap.isChecked() else s
        self.view.regionAdded.connect(self.add_region)
        self.view.regionChanged.connect(self.region_changed)
        self.view.regionSelected.connect(self.select_row)
        vg.lay.addWidget(self.view)
        lay.addWidget(vg, 3)
        zo.clicked.connect(lambda: self.view.zoom(1.5))
        zi.clicked.connect(lambda: self.view.zoom(0.66))
        fit.clicked.connect(lambda: self.view.set_stem(win.peaks(stem), stem.frames, stem.sr))

        tg = W.GroupFrame("Regions", margins=(10, 22, 10, 8))
        self.table = QTableWidget(0, 7)
        self.table.setHorizontalHeaderLabels(["#", "START", "END", "LABEL", "FROM", "", ""])
        hh = self.table.horizontalHeader()
        for c, w in ((0, 50), (1, 130), (2, 130), (3, 230), (4, 90), (5, 110), (6, 130)):
            hh.setSectionResizeMode(c, QHeaderView.Fixed)
            self.table.setColumnWidth(c, w)
        hh.setStretchLastSection(True)
        hh.setDefaultAlignment(Qt.AlignLeft | Qt.AlignVCenter)
        hh.setFont(K.font(11, 600, 1.4))
        hh.setFixedHeight(34)
        self.table.verticalHeader().setVisible(False)
        self.table.setShowGrid(False)
        self.table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.table.setSelectionMode(QAbstractItemView.SingleSelection)
        self.table.verticalHeader().setDefaultSectionSize(44)
        self.table.setFont(K.font(13, 400, 0.3))
        self.table.itemSelectionChanged.connect(self._table_selected)
        tg.lay.addWidget(self.table)
        lay.addWidget(tg, 3)

        bottom = QHBoxLayout()
        note = W.cap("Each region is trimmed of silence, de-clicked and normalized "
                     "automatically.", "on_dark_muted", 11, 500, 1.0)
        note.setWordWrap(True)
        bottom.addWidget(note, 1)
        cancel = W.HwButton("Cancel", "dark", min_h=K.H_KEY)
        cancel.setMinimumWidth(170)
        cancel.clicked.connect(self.reject)
        bottom.addWidget(cancel)
        bottom.addSpacing(10)
        self.apply_btn = W.HwButton("", "red", min_h=K.H_KEY)
        self.apply_btn.setMinimumWidth(300)
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
            self.table.setItem(i, 4, QTableWidgetItem("AI" if r["style"] == "ai" else "YOU"))
            pb = W.HwButton("Play", "dark", icon="play", min_h=30, px=10.5, icon_size=12)
            pb.clicked.connect(lambda _c=False, i=i: self.play(i))
            self.table.setCellWidget(i, 5, self._pad(pb))
            rm = W.HwButton("Remove", "dark", icon="x", min_h=30, px=10.5, icon_size=12)
            rm.clicked.connect(lambda _c=False, i=i: self.remove(i))
            self.table.setCellWidget(i, 6, self._pad(rm))
        self.table.blockSignals(False)
        if 0 <= select < len(self.regions):
            self.table.selectRow(select)
        n = len(self.regions)
        self.apply_btn.setText(f"Send {n} region{'s' if n != 1 else ''} to review")
        self.apply_btn.setEnabled(True)

    @staticmethod
    def _pad(w):
        holder = QWidget()
        lay = QHBoxLayout(holder)
        lay.setContentsMargins(4, 5, 8, 5)
        lay.addWidget(w)
        lay.addStretch(1)
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
            fields = dict(start=int(r["start"]), end=int(r["end"]), label=r["label"],
                          kind=r["kind"] if r["kind"] != "region" else "event", bars=r["bars"],
                          origin=r["origin"], flag="" if r["style"] == "user" else r["flag"],
                          approved=r["approved"] and r["style"] != "user")
            src = r.get("src")
            # keep fades / reverse / gain made on the Review page
            new.append(replace(src, **fields) if src is not None
                       else Chop(stem_id=self.stem.id, **fields))
        self.accept()
        self.win.replace_chops(self.stem, new, status=f"{len(new)} chops")
