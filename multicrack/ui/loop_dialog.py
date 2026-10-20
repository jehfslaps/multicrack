"""Loop & section options for drum / percussion stems."""
from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (QCheckBox, QComboBox, QDialog, QDoubleSpinBox, QGridLayout,
                               QHBoxLayout, QPushButton, QVBoxLayout, QWidget)

from ..core.naming import chop_key
from .common import Segmented, fmt_time, hline, label, panel
from .theme import WAVE
from .waveform import StemView


class LoopDialog(QDialog):
    def __init__(self, win, stem):
        super().__init__(win)
        self.win, self.stem = win, stem
        self.setWindowTitle(f"Loop options · {stem.name}")
        self.resize(1080, 720)
        opts = stem.options
        sec = stem.analysis.get("sections") or {}
        grid = stem.analysis.get("grid") or {}

        lay = QVBoxLayout(self)
        lay.setContentsMargins(16, 14, 16, 14)
        lay.setSpacing(12)

        head = QHBoxLayout()
        head.addWidget(label(stem.name, "h2"))
        head.addWidget(label(f"AI detected: {stem.kind}", "muted"))
        head.addStretch(1)
        head.addWidget(label("Tempo"))
        self.bpm = QDoubleSpinBox()
        self.bpm.setRange(40, 250)
        self.bpm.setDecimals(2)
        self.bpm.setSuffix(" BPM")
        self.bpm.setValue(float(opts.get("bpm") or sec.get("bpm") or grid.get("bpm") or 120))
        head.addWidget(self.bpm)
        lay.addLayout(head)

        row = QHBoxLayout()
        row.addWidget(label("Loop length"))
        self.bars = Segmented(["2 bars", "4 bars", "8 bars", "16 bars"],
                              f"{int(opts.get('bars', 4))} bars")
        row.addWidget(self.bars)
        row.addWidget(label("Cuts land exactly on bar lines. Tempo is locked for the whole song.",
                            "muted"))
        row.addStretch(1)
        lay.addLayout(row)

        vp, vl = panel(spacing=6, margins=(10, 10, 10, 8))
        self.view = StemView(editable=False)
        self.view.setMinimumHeight(170)
        self.view.set_stem(win.peaks(stem), stem.frames, stem.sr)
        bands, regions = [], []
        bpm = float(sec.get("bpm") or 120)
        bar = 240.0 * stem.sr / bpm
        d0 = float(grid.get("downbeat", 0)) % bar if grid else 0.0
        for i, g in enumerate(sec.get("grooves", [])):
            color = WAVE["groove"][i % len(WAVE["groove"])]
            for part in g["where"].split(", "):
                try:
                    a, b = part.replace("bars ", "").split("–")
                    bands.append(dict(start=d0 + (int(a) - 1) * bar, end=d0 + int(b) * bar,
                                      color=color, name=g["name"]))
                except ValueError:
                    pass
            regions.append(dict(start=g["start"], end=g["end"], style="loop",
                                tag=g["name"].split()[-1]))
        for c in win.chops:
            if c.stem_id == stem.id and c.kind == "roll":
                regions.append(dict(start=c.start, end=c.end, style="roll", tag="R"))
        self.view.bands = bands
        self.view.set_regions(regions)
        vl.addWidget(self.view)
        vl.addWidget(label(f"Coloured strips: grooves the AI found. Blue boxes: the loop it "
                           f"picked from each groove. Yellow: rolls. Scroll to zoom.", "muted"))
        lay.addWidget(vp)

        tp, tl = panel(spacing=0, margins=(0, 0, 0, 0))
        g = QGridLayout()
        g.setContentsMargins(14, 10, 14, 10)
        g.setHorizontalSpacing(18)
        g.setVerticalSpacing(10)
        for c, h in enumerate(["Section (AI)", "Where", "Loop file", "Loop", "Chop into hits"]):
            g.addWidget(label(h, "muted"), 0, c)
        self.groove_boxes = {}
        r = 1
        gopts = opts.setdefault("grooves", {})
        for gr in sec.get("grooves", []):
            go = gopts.setdefault(gr["name"], {"loop": True, "chop": True})
            g.addWidget(label(gr["name"]), r, 0)
            g.addWidget(label(gr["where"] + f"  ·  starts {fmt_time(gr['start'], stem.sr)}",
                              "muted", wrap=True), r, 1)
            fname = chop_key(gr["label"], gr["bars"])
            note = "  (section is shorter)" if gr.get("short") else ""
            g.addWidget(label(f"{win.prefix()}{fname}_##{note}", "mono"), r, 2)
            lb = QCheckBox("Include")
            lb.setChecked(go["loop"])
            cb = QCheckBox(f"Also chop ({gr['hits']} hits)")
            cb.setChecked(go["chop"])
            g.addWidget(lb, r, 3)
            g.addWidget(cb, r, 4)
            self.groove_boxes[gr["name"]] = (lb, cb)
            r += 1
        if not sec.get("grooves"):
            g.addWidget(label("No repeating groove found in this file. Rolls and single hits "
                              "are still chopped.", "muted", wrap=True), r, 0, 1, 5)
            r += 1
        g.addWidget(hline(), r, 0, 1, 5)
        r += 1
        g.addWidget(label("Rolls / fills"), r, 0)
        g.addWidget(label(f"{sec.get('rolls', 0)} found, up to 6 distinct kept · not loopable",
                          "muted"), r, 1, 1, 2)
        self.roll_mode = QComboBox()
        self.roll_mode.addItems(["One-shot", "Loop", "Skip"])
        self.roll_mode.setCurrentText(opts.get("roll_mode", "One-shot"))
        g.addWidget(self.roll_mode, r, 3, 1, 2)
        r += 1
        g.addWidget(label("Single hits"), r, 0)
        g.addWidget(label(f"{sec.get('hits', 0)} outside the grooves", "muted"), r, 1, 1, 2)
        self.hits = QCheckBox("Include")
        self.hits.setChecked(opts.get("include_hits", True))
        g.addWidget(self.hits, r, 3, 1, 2)
        g.setRowStretch(r + 1, 1)
        g.setColumnStretch(1, 1)
        holder = QWidget()
        holder.setLayout(g)
        tl.addWidget(holder)
        lay.addWidget(tp)
        lay.addStretch(1)

        bottom = QHBoxLayout()
        bottom.addWidget(label("Hits from loops and single hits are pooled: up to 3 of each sound. "
                               "Anything the AI can't name confidently is called Perc.", "muted",
                               wrap=True), 1)
        cancel = QPushButton("Cancel")
        cancel.clicked.connect(self.reject)
        bottom.addWidget(cancel)
        apply = QPushButton("Apply and send to Review")
        apply.setObjectName("primary")
        apply.clicked.connect(self.apply)
        bottom.addWidget(apply)
        lay.addLayout(bottom)

    def apply(self):
        st = self.stem
        opts = st.options
        grid = st.analysis.get("grid") or {}
        bpm = round(self.bpm.value(), 2)
        opts["bpm"] = None if grid and abs(bpm - float(grid.get("bpm", 0))) < 0.005 else bpm
        opts["bars"] = int(self.bars.value.split()[0])
        opts["roll_mode"] = self.roll_mode.currentText()
        opts["include_hits"] = self.hits.isChecked()
        for name, (lb, cb) in self.groove_boxes.items():
            opts["grooves"][name] = {"loop": lb.isChecked(), "chop": cb.isChecked()}
        self.accept()
        self.win.rechop(st)
