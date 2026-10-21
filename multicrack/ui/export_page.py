"""Step 3: what was exported, and where (hardware skin)."""
from __future__ import annotations

import os
import subprocess
import sys

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (QAbstractItemView, QHBoxLayout, QHeaderView, QLineEdit,
                               QTableWidget, QTableWidgetItem, QVBoxLayout, QWidget)

from .skin import core as K
from .skin import widgets as W


def open_folder(path):
    if sys.platform == "win32":
        os.startfile(path)  # noqa: S606 - opening the user's own folder
    elif sys.platform == "darwin":
        subprocess.Popen(["open", path])
    else:
        subprocess.Popen(["xdg-open", path])


class ExportPage(QWidget):
    def __init__(self, win):
        super().__init__()
        self.win = win
        self.folder = ""
        outer = QHBoxLayout(self)
        outer.setContentsMargins(0, 4, 0, 0)
        outer.addStretch(1)
        col = QVBoxLayout()
        col.setSpacing(0)
        box = W.Module("EXPORT", margins=(22, 10, 22, 18))
        box.setMinimumWidth(640)
        self.box = box
        box.setMaximumWidth(980)
        bl = box.lay
        bl.setSpacing(14)

        head = QHBoxLayout()
        head.setSpacing(14)
        self.icon = W.Lamp("led_green", 30)
        head.addWidget(self.icon)
        hc = QVBoxLayout()
        hc.setSpacing(6)
        self.title = W.mono("NOTHING EXPORTED YET", "on_dark", 22, 600, 2.4)
        hc.addWidget(self.title)
        self.path = QLineEdit()
        self.path.setReadOnly(True)
        self.path.setFont(K.font(13, 400, 0.3))
        hc.addWidget(self.path)
        head.addLayout(hc, 1)
        bl.addLayout(head)

        outline = W.Outline(margins=(4, 2, 4, 4))
        self.list = QTableWidget(0, 2)
        self.list.setHorizontalHeaderLabels(["FILE NAME", "SIZE"])
        hh = self.list.horizontalHeader()
        hh.setSectionResizeMode(0, QHeaderView.Stretch)
        hh.setSectionResizeMode(1, QHeaderView.Fixed)
        self.list.setColumnWidth(1, 120)
        hh.setDefaultAlignment(Qt.AlignLeft | Qt.AlignVCenter)
        hh.setFont(K.font(11, 600, 1.4))
        hh.setFixedHeight(36)
        self.list.verticalHeader().setVisible(False)
        self.list.verticalHeader().setDefaultSectionSize(36)
        self.list.setShowGrid(False)
        self.list.setSelectionMode(QAbstractItemView.NoSelection)
        self.list.setFocusPolicy(Qt.NoFocus)
        self.list.setFont(K.font(13, 400, 0.3))
        self.list.setMinimumHeight(220)
        outline.lay.addWidget(self.list)
        bl.addWidget(outline, 1)
        bl.addWidget(W.cap("24-bit WAV  ·  original sample rate  ·  normalized −0.1 dB  ·  "
                           "de-clicked  ·  no tags embedded", "on_dark_muted", 11, 500, 1.3))
        row = QHBoxLayout()
        row.setSpacing(12)
        row.addStretch(1)
        self.again = W.HwButton("Chop another song", "dark", min_h=K.H_KEY)
        self.again.clicked.connect(self.win.start_over)
        row.addWidget(self.again)
        self.open = W.HwButton("Open folder", "key", icon="folder", min_h=K.H_KEY)
        self.open.clicked.connect(lambda: self.folder and open_folder(self.folder))
        row.addWidget(self.open)
        self.next_btn = W.HwButton("", "red", icon="play", min_h=K.H_KEY)
        self.next_btn.clicked.connect(lambda: self.win.next_song(0))
        self.next_btn.hide()
        row.addWidget(self.next_btn)
        bl.addLayout(row)
        col.addWidget(box, 1)
        outer.addLayout(col, 6)
        outer.addStretch(1)
        self.show_result([], "")

    def set_compact(self, narrow, short):
        self.list.setMinimumHeight(140 if short else 220)

    def set_next(self, name, waiting):
        self.last_next = (name, waiting)
        if name:
            short = name if len(name) <= 34 else name[:33] + "…"
            self.next_btn.setText(f"Next song: {short}" + (f"  ({waiting} in queue)" if waiting > 1 else ""))
            self.next_btn.setToolTip(f"Load {name}")
            self.next_btn.show()
            self.again.hide()
        else:
            self.next_btn.hide()
            self.again.show()

    def show_result(self, files, folder):
        self.last_result = (list(files), folder)
        self.folder = folder
        self.icon.setVisible(bool(files))
        self.title.setText(f"EXPORTED {len(files)} FILE{'S' if len(files) != 1 else ''}"
                           if files else "NOTHING EXPORTED YET")
        self.path.setText(folder)
        self.path.setCursorPosition(0)
        self.list.setRowCount(len(files))
        for i, p in enumerate(files):
            try:
                size = os.path.getsize(p)
                s = f"{size / 1e6:.1f} MB" if size > 1e6 else f"{size // 1000} KB"
            except OSError:
                s = ""
            self.list.setItem(i, 0, QTableWidgetItem(os.path.basename(p)))
            self.list.setItem(i, 1, QTableWidgetItem(s))
        self.open.setEnabled(bool(files))
