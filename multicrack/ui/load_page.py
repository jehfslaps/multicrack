"""Step 1: song details and stems."""
from __future__ import annotations

import os

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (QAbstractItemView, QComboBox, QFileDialog, QFrame, QHBoxLayout,
                               QHeaderView, QLabel, QLineEdit, QProgressBar, QPushButton,
                               QSizePolicy, QTableWidget, QTableWidgetItem, QToolButton,
                               QVBoxLayout, QWidget)

from ..core.audio import AUDIO_EXTS
from ..core.model import KIND_NAMES
from ..core.naming import folder_name, make_prefix
from . import icons
from .common import fmt_len, hline, label, panel


class DropZone(QFrame):
    dropped = Signal(list)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("drop")
        self.setAcceptDrops(True)
        self.setMinimumHeight(104)
        lay = QHBoxLayout(self)
        lay.setContentsMargins(16, 14, 16, 14)
        lay.setSpacing(14)
        lay.addStretch(1)
        self.icon = QLabel()
        lay.addWidget(self.icon)
        col = QVBoxLayout()
        col.setSpacing(2)
        col.addWidget(label("Drop stems or a whole stem folder here", "h2"))
        col.addWidget(label("WAV, AIFF, FLAC, MP3, OGG and other audio files", "muted"))
        lay.addLayout(col)
        self.browse_files = QPushButton("Browse files…")
        self.browse_folder = QPushButton("Browse folder…")
        lay.addWidget(self.browse_files)
        lay.addWidget(self.browse_folder)
        lay.addStretch(1)

    def set_icon_color(self, color):
        self.icon.setPixmap(icons.upload(color).pixmap(28, 28))

    def _set_hover(self, on):
        self.setProperty("hover", "true" if on else "false")
        self.style().unpolish(self)
        self.style().polish(self)

    def dragEnterEvent(self, e):
        if e.mimeData().hasUrls():
            e.acceptProposedAction()
            self._set_hover(True)

    def dragLeaveEvent(self, _e):
        self._set_hover(False)

    def dropEvent(self, e):
        self._set_hover(False)
        paths = [u.toLocalFile() for u in e.mimeData().urls() if u.isLocalFile()]
        if paths:
            self.dropped.emit(paths)


class LoadPage(QWidget):
    def __init__(self, win):
        super().__init__()
        self.win = win
        self.setObjectName("page")
        self.prefix_edited = False
        self.setAcceptDrops(True)

        outer = QHBoxLayout(self)
        outer.setContentsMargins(16, 16, 16, 16)
        outer.setSpacing(16)

        # ---- song panel
        sp, sl = panel(spacing=8)
        sp.setFixedWidth(330)
        sl.addWidget(label("Song", "h2"))
        self.artist = QLineEdit()
        self.artist.setPlaceholderText("e.g. Taylor Swift")
        self.song = QLineEdit()
        self.song.setPlaceholderText("e.g. Style")
        self.prefix = QLineEdit()
        for text, w in (("Artist", self.artist), ("Song", self.song),
                        ("File prefix (automatic)", self.prefix)):
            sl.addWidget(label(text, "muted"))
            sl.addWidget(w)
        sl.addSpacing(6)
        sl.addWidget(hline())
        sl.addWidget(label("Output folder", "muted"))
        self.folder_lbl = label("", "mono", wrap=True)
        sl.addWidget(self.folder_lbl)
        row = QHBoxLayout()
        self.change_folder = QPushButton("Change location…")
        self.change_folder.setObjectName("link")
        row.addWidget(self.change_folder)
        row.addStretch(1)
        sl.addLayout(row)
        self.exists_lbl = label("", "muted", wrap=True)
        sl.addWidget(self.exists_lbl)
        sl.addSpacing(6)
        sl.addWidget(hline())
        sl.addWidget(label("Output settings", "muted"))
        for t in ("24-bit WAV · original sample rate", "Each sample normalized to −0.1 dB",
                  "Light de-click on the edges", "Up to 3 variations per sound",
                  "No tempo, key or other tags embedded"):
            sl.addWidget(label(t))
        sl.addStretch(1)
        outer.addWidget(sp)

        # ---- stems
        right = QVBoxLayout()
        right.setSpacing(12)
        self.drop = DropZone()
        right.addWidget(self.drop)

        self.table = QTableWidget(0, 7)
        self.table.setHorizontalHeaderLabels(["File", "Length", "AI detected", "Mode", "Status",
                                              "", ""])
        hh = self.table.horizontalHeader()
        hh.setSectionResizeMode(0, QHeaderView.Stretch)
        for c, w in ((1, 70), (2, 160), (3, 100), (4, 150), (5, 120), (6, 40)):
            hh.setSectionResizeMode(c, QHeaderView.Fixed)
            self.table.setColumnWidth(c, w)
        hh.setDefaultAlignment(Qt.AlignLeft | Qt.AlignVCenter)
        self.table.verticalHeader().setVisible(False)
        self.table.setShowGrid(False)
        self.table.setSelectionMode(QAbstractItemView.NoSelection)
        self.table.setFocusPolicy(Qt.NoFocus)
        self.table.verticalHeader().setDefaultSectionSize(46)
        self.table.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        right.addWidget(self.table, 1)

        self.empty = label("No files yet. Drop a stem folder above to get started.", "muted")
        self.empty.setAlignment(Qt.AlignCenter)
        right.addWidget(self.empty)

        bottom = QHBoxLayout()
        self.hint = label("AI labels every file. Change any type, or switch a file to Manual, "
                          "before processing.", "muted", wrap=True)
        bottom.addWidget(self.hint, 1)
        self.busy = QProgressBar()
        self.busy.setObjectName("busy")
        self.busy.setTextVisible(False)
        self.busy.setFixedWidth(160)
        self.busy.hide()
        bottom.addWidget(self.busy)
        self.process_btn = QPushButton("Process all")
        self.process_btn.setObjectName("primary")
        bottom.addWidget(self.process_btn)
        right.addLayout(bottom)
        outer.addLayout(right, 1)

        # ---- wiring
        self.drop.dropped.connect(self.win.add_files)
        self.drop.browse_files.clicked.connect(self.browse_files)
        self.drop.browse_folder.clicked.connect(self.browse_folder)
        self.artist.textChanged.connect(self._names_changed)
        self.song.textChanged.connect(self._names_changed)
        self.prefix.textEdited.connect(self._prefix_edited)
        self.change_folder.clicked.connect(self.pick_base)
        self.process_btn.clicked.connect(self.win.process_all)
        self._names_changed()

    # ------------------------------------------------------------- song info
    def dragEnterEvent(self, e):
        if e.mimeData().hasUrls():
            e.acceptProposedAction()

    def dropEvent(self, e):
        paths = [u.toLocalFile() for u in e.mimeData().urls() if u.isLocalFile()]
        if paths:
            self.win.add_files(paths)

    def _prefix_edited(self, _t):
        self.prefix_edited = bool(self.prefix.text().strip())
        self.win.names_changed()

    def _names_changed(self):
        if not self.prefix_edited:
            self.prefix.setText(make_prefix(self.artist.text(), self.song.text()))
        folder = self.output_folder()
        self.folder_lbl.setText(folder)
        self.exists_lbl.setText("This folder already exists. New chops are added and the "
                                "numbering continues." if os.path.isdir(folder) else "")
        self.win.names_changed()

    def output_folder(self) -> str:
        return os.path.join(self.win.base_dir, folder_name(self.artist.text(), self.song.text()))

    def get_prefix(self) -> str:
        p = self.prefix.text().strip()
        if p and not p.endswith("_"):
            p += "_"
        return p

    def pick_base(self):
        d = QFileDialog.getExistingDirectory(self, "Where should song folders go?", self.win.base_dir)
        if d:
            self.win.set_base_dir(d)
            self._names_changed()

    def browse_files(self):
        exts = " ".join(f"*{e}" for e in sorted(AUDIO_EXTS))
        files, _ = QFileDialog.getOpenFileNames(self, "Choose stems", "", f"Audio files ({exts})")
        if files:
            self.win.add_files(files)

    def browse_folder(self):
        d = QFileDialog.getExistingDirectory(self, "Choose a stem folder")
        if d:
            self.win.add_files([d])

    # ---------------------------------------------------------------- table
    def refresh(self):
        stems = self.win.stems
        t = self.win.t
        self.table.setRowCount(len(stems))
        for r, st in enumerate(stems):
            it = QTableWidgetItem(st.name)
            it.setToolTip("\n".join(st.sources) if st.sources else st.path)
            f = it.font()
            f.setFamily("Consolas")
            it.setFont(f)
            self.table.setItem(r, 0, it)
            self.table.setItem(r, 1, QTableWidgetItem(fmt_len(st.frames, st.sr)))

            kind = QComboBox()
            kind.addItems(KIND_NAMES)
            kind.setCurrentText(st.kind)
            kind.setEnabled(st.mode != "skip")
            kind.currentTextChanged.connect(lambda txt, s=st: self.win.set_kind(s, txt))
            self.table.setCellWidget(r, 2, self._pad(kind))

            mode = QComboBox()
            mode.addItems(["Auto", "Manual"])
            mode.setCurrentText("Manual" if st.mode == "manual" else "Auto")
            mode.setEnabled(st.mode != "skip")
            mode.currentTextChanged.connect(lambda txt, s=st: self.win.set_mode(s, txt.lower()))
            self.table.setCellWidget(r, 3, self._pad(mode))

            status = QTableWidgetItem(st.status)
            if st.analysis.get("tempo_warning"):
                status.setToolTip(st.analysis["tempo_warning"])
            self.table.setItem(r, 4, status)

            if st.mode != "skip":
                is_groove = st.engine == "groove" and st.mode == "auto"
                b = QPushButton("Loop options" if is_groove else "Edit regions")
                b.setObjectName("link")
                b.clicked.connect(lambda _c=False, s=st: self.win.open_stem(s))
                self.table.setCellWidget(r, 5, b)
            else:
                self.table.setCellWidget(r, 5, QWidget())

            x = QToolButton()
            x.setIcon(icons.close(t["muted"]))
            x.setToolTip("Remove this file")
            x.setAutoRaise(True)
            x.setStyleSheet("border: none; background: transparent;")
            x.clicked.connect(lambda _c=False, s=st: self.win.remove_stem(s))
            self.table.setCellWidget(r, 6, self._pad(x))
        self.table.setVisible(bool(stems))
        self.empty.setVisible(not stems)
        n_auto = sum(1 for s in stems if s.mode == "auto")
        self.process_btn.setEnabled(n_auto > 0 and not self.win.busy)
        self.drop.set_icon_color(t["muted"])
        if stems:
            self.hint.setText(f"{len(stems)} file{'s' if len(stems) != 1 else ''} · AI labels "
                              "every file. Change any type, or switch a file to Manual, before "
                              "processing.")

    @staticmethod
    def _pad(w):
        holder = QWidget()
        lay = QHBoxLayout(holder)
        lay.setContentsMargins(4, 6, 8, 6)
        lay.addWidget(w)
        return holder

    def set_busy(self, on, msg="", i=0, n=0):
        self.busy.setVisible(on)
        if on:
            self.busy.setRange(0, max(1, n))
            self.busy.setValue(i)
            self.hint.setText(msg)
        self.process_btn.setEnabled(not on and any(s.mode == "auto" for s in self.win.stems))
        self.drop.setEnabled(not on)
