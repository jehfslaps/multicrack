"""Step 1: song details and stems (hardware skin)."""
from __future__ import annotations

import os

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (QAbstractItemView, QComboBox, QFileDialog, QHBoxLayout,
                               QHeaderView, QLineEdit, QSizePolicy, QTableWidget,
                               QTableWidgetItem, QVBoxLayout, QWidget)

from ..core.audio import AUDIO_EXTS
from ..core.model import KIND_NAMES
from ..core.naming import folder_name, make_prefix
from .common import fmt_len
from .skin import core as K
from .skin import widgets as W


def _table(columns, widths, stretch_col):
    t = QTableWidget(0, len(columns))
    t.setHorizontalHeaderLabels([c.upper() for c in columns])
    hh = t.horizontalHeader()
    for c, w in enumerate(widths):
        if c == stretch_col:
            hh.setSectionResizeMode(c, QHeaderView.Stretch)
        else:
            hh.setSectionResizeMode(c, QHeaderView.Fixed)
            t.setColumnWidth(c, w)
    hh.setDefaultAlignment(Qt.AlignLeft | Qt.AlignVCenter)
    hh.setFont(K.font(11, 600, 1.4))
    hh.setFixedHeight(38)
    t.verticalHeader().setVisible(False)
    t.setShowGrid(False)
    t.setSelectionMode(QAbstractItemView.NoSelection)
    t.setFocusPolicy(Qt.NoFocus)
    t.verticalHeader().setDefaultSectionSize(46)
    t.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
    t.setFont(K.font(13.5, 400, 0.3))
    return t


def _cell(w, align=Qt.AlignLeft, margins=(6, 6, 8, 6)):
    holder = QWidget()
    lay = QHBoxLayout(holder)
    lay.setContentsMargins(*margins)
    if align == Qt.AlignCenter:
        lay.addStretch(1)
    lay.addWidget(w)
    if align != Qt.AlignRight:
        lay.addStretch(1)
    return holder


class LoadPage(QWidget):
    def __init__(self, win):
        super().__init__()
        self.win = win
        self.prefix_edited = False
        self.setAcceptDrops(True)

        page = QVBoxLayout(self)
        page.setContentsMargins(0, 4, 0, 0)
        page.setSpacing(12)
        content = QHBoxLayout()
        content.setSpacing(30)
        page.addLayout(content, 1)

        # ================================================================ SONG
        self.song_mod = W.Module("SONG", outline=True, margins=(14, 10, 14, 14))
        self.song_mod.setFixedWidth(340)
        sl = self.song_mod.lay
        sl.setSpacing(7)
        self.artist = QLineEdit()
        self.artist.setPlaceholderText("e.g. Taylor Swift")
        self.song = QLineEdit()
        self.song.setPlaceholderText("e.g. Style")
        sl.addWidget(W.cap("Artist"))
        sl.addWidget(self.artist)
        sl.addSpacing(4)
        sl.addWidget(W.cap("Song"))
        sl.addWidget(self.song)
        sl.addSpacing(10)
        sl.addWidget(W.cap("Prefix"))
        pr = QHBoxLayout()
        pr.setSpacing(0)
        self.prefix = QLineEdit()
        self.prefix.setToolTip("Every file name starts with this. Filled in from the artist and "
                               "song; type to change it.")
        pr.addWidget(self.prefix, 1)
        self.prefix_btn = W.HwButton("", "icon", icon="pencil", min_h=36)
        self.prefix_btn.setToolTip("Edit the prefix")
        self.prefix_btn.clicked.connect(lambda: (self.prefix.setFocus(), self.prefix.selectAll()))
        pr.addSpacing(6)
        pr.addWidget(self.prefix_btn)
        sl.addLayout(pr)
        sl.addSpacing(10)
        sl.addWidget(W.cap("Output path"))
        orow = QHBoxLayout()
        self.folder_edit = QLineEdit()
        self.folder_edit.setReadOnly(True)
        self.folder_edit.setFont(K.font(12.5, 400, 0.2))
        orow.addWidget(self.folder_edit, 1)
        self.folder_btn = W.HwButton("", "icon", icon="folder", min_h=36)
        self.folder_btn.setToolTip("Choose where song folders go")
        self.folder_btn.clicked.connect(self.pick_base)
        orow.addSpacing(6)
        orow.addWidget(self.folder_btn)
        sl.addLayout(orow)
        crow = QHBoxLayout()
        self.change_folder = W.HwButton("Change location", "dark", min_h=32, px=11.5)
        self.change_folder.clicked.connect(self.pick_base)
        crow.addWidget(self.change_folder)
        crow.addStretch(1)
        sl.addLayout(crow)
        erow = QHBoxLayout()
        erow.setSpacing(8)
        self.exists_icon = W.Lamp("led_green", 12)
        erow.addWidget(self.exists_icon, 0, Qt.AlignTop)
        self.exists_lbl = W.mono("", "ok", 12.5, 400, 0.2)
        self.exists_lbl.setWordWrap(True)
        erow.addWidget(self.exists_lbl, 1)
        sl.addLayout(erow)
        self.specs = QWidget()
        spl = QVBoxLayout(self.specs)
        spl.setContentsMargins(0, 0, 0, 0)
        spl.setSpacing(7)
        spl.addWidget(W.Separator())
        spl.addWidget(W.cap("Output specs"))
        for t in ("24-bit WAV", "Original sample rate", "Normalized −0.1 dB", "Light de-click",
                  "Up to 3 variations", "No tags embedded"):
            spl.addWidget(W.mono("•  " + t, "on_dark_muted", 12.5, 400, 0.2))
        sl.addWidget(self.specs)
        sl.addStretch(1)
        content.addWidget(self.song_mod)

        # ============================================================== RIGHT
        right = QVBoxLayout()
        right.setSpacing(12)
        content.addLayout(right, 1)

        self.drop_mod = W.Module("", margins=(16, 14, 16, 14))
        dl = QHBoxLayout()
        dl.setSpacing(18)
        self.drop = W.DropBay()
        dl.addWidget(self.drop, 1)
        bcol = QVBoxLayout()
        bcol.setSpacing(12)
        self.browse_files_btn = W.HwButton("Browse files", "dark", icon="file", min_h=46, px=12.5)
        self.browse_folder_btn = W.HwButton("Browse folder", "dark", icon="folder", min_h=46, px=12.5)
        for b in (self.browse_files_btn, self.browse_folder_btn):
            b.setMinimumWidth(236)
            bcol.addWidget(b)
        bcol.addStretch(1)
        dl.addLayout(bcol)
        self.drop_mod.lay.addLayout(dl)
        right.addWidget(self.drop_mod)

        self.stems_mod = W.Module("STEM LIST", margins=(14, 8, 14, 14))
        self.stems_outline = W.Outline(margins=(4, 2, 4, 4))
        self.table = _table(["#", "File name", "Length", "AI detected", "Auto / Manual", "Status",
                             "Edit", "Remove"], [40, 0, 72, 176, 158, 118, 150, 76], 1)
        self.stems_outline.lay.addWidget(self.table)
        self.empty = W.mono("NO FILES YET  ·  DROP A STEM FOLDER ABOVE TO GET STARTED",
                            "on_dark_dim", 12.5, 500, 2.0)
        self.empty.setAlignment(Qt.AlignCenter)
        self.empty.setMinimumHeight(120)
        self.stems_outline.lay.addWidget(self.empty)
        self.stems_mod.lay.addWidget(self.stems_outline, 1)
        right.addWidget(self.stems_mod, 1)

        self.queue_mod = W.Module("SONG QUEUE", margins=(14, 8, 14, 14))
        qo = W.Outline(margins=(4, 2, 4, 4))
        self.queue_table = _table(["#", "Artist - Song", "Status", "Actions"], [44, 0, 160, 300], 1)
        self.queue_table.setMaximumHeight(38 + 46 * 3 + 4)
        qo.lay.addWidget(self.queue_table)
        self.queue_mod.lay.addWidget(qo)
        self.queue_mod.hide()
        self.queue_mod.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Maximum)
        right.addWidget(self.queue_mod)

        # ============================================================== FOOTER
        foot = QHBoxLayout()
        foot.setContentsMargins(6, 0, 0, 0)
        foot.setSpacing(14)
        foot.addWidget(W.IconLabel("bulb", "chassis_text", 22))
        self.hint = W.mono("TIP: DRAG AND DROP STEMS OR A FOLDER, CHECK THE AI DETECTION, THEN "
                           "PROCESS.", "chassis_text", 11.5, 500, 1.2)
        self.hint.setWordWrap(True)
        self.hint.setMinimumWidth(200)
        self.hint.setSizePolicy(QSizePolicy.Ignored, QSizePolicy.Preferred)
        foot.addWidget(self.hint, 3)
        foot.addWidget(W.Separator(vertical=True))
        self.progress = W.Trough()
        self.progress.setMaximumWidth(520)
        foot.addWidget(self.progress, 2)
        housing = W.Recess(screws=True, margins=(16, 10, 16, 10))
        self.process_btn = W.HwButton("Process all", "red", led=True, min_h=54, px=17)
        self.process_btn.setMinimumWidth(300)
        housing.lay.addWidget(self.process_btn)
        foot.addWidget(housing)
        page.addLayout(foot)

        # ============================================================== wiring
        self.drop.dropped.connect(self.win.add_files)
        self.browse_files_btn.clicked.connect(self.browse_files)
        self.browse_folder_btn.clicked.connect(self.browse_folder)
        self.artist.textChanged.connect(self._names_changed)
        self.song.textChanged.connect(self._names_changed)
        self.prefix.textEdited.connect(self._prefix_edited)
        self.process_btn.clicked.connect(self.win.process_all)
        self._names_changed()

    WIDE = [40, 0, 72, 176, 158, 118, 150, 76]
    NARROW = [30, 0, 0, 132, 108, 92, 84, 48]

    def set_compact(self, narrow, short):
        if getattr(self, "_compact", None) == (narrow, short):
            return
        self._compact = (narrow, short)
        self.song_mod.setFixedWidth(270 if narrow else 340)
        self.specs.setVisible(not short)
        widths = self.NARROW if narrow else self.WIDE
        for c, w in enumerate(widths):
            if c == 1:
                continue
            self.table.setColumnHidden(c, w == 0)
            if w:
                self.table.setColumnWidth(c, w)
        from PySide6.QtWidgets import QTableWidgetItem as _I
        self.table.setHorizontalHeaderItem(7, _I("" if narrow else "REMOVE"))
        for b in (self.browse_files_btn, self.browse_folder_btn):
            b.setMinimumWidth(180 if narrow else 236)
        self.process_btn.setMinimumWidth(230 if narrow else 300)
        self.refresh()

    def install_wires(self, chassis: W.Chassis):
        chassis.add_bus(self.song_mod, [self.drop_mod, self.stems_mod, self.stems_mod,
                                        self.queue_mod], [0.5, 0.25, 0.7, 0.5])

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
        self.folder_edit.setText(folder)
        self.folder_edit.setToolTip(folder)
        self.folder_edit.setCursorPosition(0)
        exists = os.path.isdir(folder) and bool(self.artist.text().strip() or self.song.text().strip())
        self.exists_lbl.setText("Folder exists.\nNumbering continues from the last file."
                                if exists else "")
        self.exists_icon.setVisible(exists)
        self.win.names_changed()

    def set_song(self, artist, song):
        self.prefix_edited = False
        self.artist.setText(artist or "")
        self.song.setText(song or "")
        self._names_changed()

    def refresh_queue(self):
        q = self.win.queue
        t = self.queue_table
        t.setRowCount(len(q))
        for i, item in enumerate(q):
            name = " - ".join(p for p in (item.get("artist"), item.get("song")) if p) or "Untitled"
            t.setItem(i, 0, QTableWidgetItem(str(i + 1)))
            t.setItem(i, 1, QTableWidgetItem(name))
            st = W.StatusText()
            st.set("Next up" if i == 0 else "Waiting", "ok" if i == 0 else "info")
            t.setCellWidget(i, 2, _cell(st))
            acts = QWidget()
            al = QHBoxLayout(acts)
            al.setContentsMargins(4, 5, 4, 5)
            al.setSpacing(10)
            b1 = W.HwButton("Start this song", "dark", icon="play", min_h=34, px=11.5, icon_size=13)
            b1.clicked.connect(lambda _c=False, i=i: self.win.next_song(i))
            b2 = W.HwButton("Remove", "dark", icon="x", min_h=34, px=11.5, icon_size=13)
            b2.clicked.connect(lambda _c=False, i=i: self.win.remove_from_queue(i))
            al.addWidget(b1)
            al.addWidget(b2)
            al.addStretch(1)
            t.setCellWidget(i, 3, acts)
        rows = min(3, max(1, len(q)))
        t.setFixedHeight(38 + 46 * rows + 4)
        self.queue_mod.setVisible(bool(q))
        self.queue_mod.set_title(f"SONG QUEUE  ·  {len(q)} WAITING" if q else "SONG QUEUE")

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
        t = self.table
        t.setRowCount(len(stems))
        for r, st in enumerate(stems):
            t.setItem(r, 0, QTableWidgetItem(str(r + 1)))
            it = QTableWidgetItem(st.name)
            it.setToolTip("\n".join(st.sources) if st.sources else st.path)
            t.setItem(r, 1, it)
            t.setItem(r, 2, QTableWidgetItem(fmt_len(st.frames, st.sr)))

            kind = QComboBox()
            kind.addItems(KIND_NAMES)
            kind.setCurrentText(st.kind)
            kind.setEnabled(st.mode != "skip")
            kind.setFixedWidth(self.table.columnWidth(3) - 14)
            kind.currentTextChanged.connect(lambda txt, s=st: self.win.set_kind(s, txt))
            t.setCellWidget(r, 3, _cell(kind, margins=(0, 6, 6, 6)))

            mode = W.ModeSwitch()
            mode.setFixedWidth(min(150, self.table.columnWidth(4) - 4))
            mode.setChecked(st.mode == "manual")
            mode.setEnabled(st.mode != "skip")
            mode.toggled.connect(lambda on, s=st: self.win.set_mode(s, "manual" if on else "auto"))
            t.setCellWidget(r, 4, _cell(mode, margins=(0, 6, 4, 6)))

            status = W.StatusText()
            s = st.status
            kind_ = ("warn" if "can't" in s.lower() or "couldn't" in s.lower()
                     else "amber" if "process again" in s.lower() or st.analysis.get("tempo_warning")
                     else "ok" if s.lower() in ("ready", "mark regions by hand") else "info")
            status.set(s, kind_)
            if st.analysis.get("tempo_warning"):
                status.setToolTip(st.analysis["tempo_warning"])
            t.setCellWidget(r, 5, _cell(status))

            if st.mode != "skip":
                is_groove = st.engine == "groove" and st.mode == "auto"
                narrow = getattr(self, "_compact", (False, False))[0]
                text = ("Loops" if is_groove else "Edit") if narrow else \
                    ("Loop options" if is_groove else "Edit regions")
                b = W.HwButton(text, "dark", min_h=32, px=11)
                b.setToolTip("Loop options" if is_groove else "Edit regions")
                b.setFixedWidth(self.table.columnWidth(6) - 12)
                b.clicked.connect(lambda _c=False, s=st: self.win.open_stem(s))
                t.setCellWidget(r, 6, _cell(b, margins=(0, 6, 6, 6)))
            else:
                t.setCellWidget(r, 6, QWidget())

            x = W.HwButton("", "danger", min_h=30)
            x.setToolTip("Remove this file")
            x.clicked.connect(lambda _c=False, s=st: self.win.remove_stem(s))
            t.setCellWidget(r, 7, _cell(x, Qt.AlignCenter, (0, 7, 0, 7)))
        t.setVisible(bool(stems))
        self.empty.setVisible(not stems)
        n_auto = sum(1 for s in stems if s.mode == "auto")
        self.process_btn.setEnabled(n_auto > 0 and not self.win.busy)
        if stems and not self.win.busy:
            self.hint.setText(f"{len(stems)} FILE{'S' if len(stems) != 1 else ''} LOADED · CHECK THE "
                              "AI DETECTION, THEN PROCESS.")

    def set_busy(self, on, msg="", i=0, n=0):
        if on:
            self.progress.set(i, max(1, n))
            self.hint.setText(msg.upper())
        else:
            self.progress.set(0, 1)
        self.process_btn.setEnabled(not on and any(s.mode == "auto" for s in self.win.stems))
        self.drop.setEnabled(not on)
