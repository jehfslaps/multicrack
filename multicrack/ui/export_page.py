"""Step 3: what was exported, and where."""
from __future__ import annotations

import os
import subprocess
import sys

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (QHBoxLayout, QLabel, QListWidget, QPushButton, QVBoxLayout,
                               QWidget)

from . import icons
from .common import label, panel


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
        self.setObjectName("page")
        self.folder = ""
        outer = QHBoxLayout(self)
        outer.setContentsMargins(16, 24, 16, 16)
        outer.addStretch(1)
        box, bl = panel(spacing=14, margins=(24, 22, 24, 22))
        box.setMinimumWidth(640)
        box.setMaximumWidth(760)
        head = QHBoxLayout()
        self.icon = QLabel()
        head.addWidget(self.icon)
        col = QVBoxLayout()
        col.setSpacing(2)
        self.title = label("Nothing exported yet", "h1")
        col.addWidget(self.title)
        self.path = label("", "mono", wrap=True)
        self.path.setTextInteractionFlags(Qt.TextSelectableByMouse)
        col.addWidget(self.path)
        head.addLayout(col, 1)
        bl.addLayout(head)
        self.list = QListWidget()
        self.list.setMinimumHeight(320)
        f = self.list.font()
        f.setFamily("Consolas")
        self.list.setFont(f)
        bl.addWidget(self.list, 1)
        bl.addWidget(label("24-bit WAV · original sample rate · each sample normalized to −0.1 dB · "
                           "light de-click applied · no tags embedded", "muted", wrap=True))
        row = QHBoxLayout()
        row.addStretch(1)
        self.again = QPushButton("Chop another song")
        self.again.clicked.connect(self.win.start_over)
        row.addWidget(self.again)
        self.open = QPushButton("Open folder")
        self.open.setObjectName("primary")
        self.open.clicked.connect(lambda: self.folder and open_folder(self.folder))
        row.addWidget(self.open)
        bl.addLayout(row)
        wrap = QVBoxLayout()
        wrap.addWidget(box)
        wrap.addStretch(1)
        outer.addLayout(wrap)
        outer.addStretch(1)
        self.show_result([], "")

    def show_result(self, files, folder):
        self.folder = folder
        t = self.win.t
        self.icon.setPixmap(icons.check(t["ok"]).pixmap(34, 34))
        self.icon.setVisible(bool(files))
        self.title.setText(f"Exported {len(files)} file{'s' if len(files) != 1 else ''}"
                           if files else "Nothing exported yet")
        self.path.setText(folder)
        self.list.clear()
        for p in files:
            try:
                size = os.path.getsize(p)
                s = f"{size / 1e6:.1f} MB" if size > 1e6 else f"{size // 1000} KB"
            except OSError:
                s = ""
            self.list.addItem(f"{os.path.basename(p)}    {s}")
        self.open.setEnabled(bool(files))
