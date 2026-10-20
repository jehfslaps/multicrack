"""The MultiCrack window: holds the session and moves between Load, Review and Export."""
from __future__ import annotations

import os

from PySide6.QtCore import QSettings, QSize, Qt
from PySide6.QtWidgets import (QApplication, QButtonGroup, QFrame, QHBoxLayout, QLabel,
                               QMainWindow, QMessageBox, QPushButton, QStackedWidget,
                               QVBoxLayout, QWidget)

from .. import APP_NAME, __version__
from ..core.audio import desktop_dir
from . import icons, theme
from .export_page import ExportPage
from .load_page import LoadPage
from .loop_dialog import LoopDialog
from .manual_dialog import ManualDialog
from .player import Player
from .review_page import ReviewPage
from .waveform import PeakCache
from .workers import Job, export, load_and_detect, process, rechop


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.settings = QSettings(APP_NAME, APP_NAME)
        self.theme_name = self.settings.value("theme", "light")
        self.t = theme.DARK if self.theme_name == "dark" else theme.LIGHT
        base = self.settings.value("base_dir", "")
        self.base_dir = base if base and os.path.isdir(base) else desktop_dir()
        self.stems = []
        self.chops = []
        self.song = None
        self.busy = False
        self.jobs = []
        self._peaks = {}
        self.player = Player()

        self.setWindowTitle(APP_NAME)
        self.setWindowIcon(icons.app_icon())
        self.resize(1360, 880)
        self.setMinimumSize(QSize(1040, 680))

        central = QWidget()
        central.setObjectName("page")
        v = QVBoxLayout(central)
        v.setContentsMargins(0, 0, 0, 0)
        v.setSpacing(0)

        top = QFrame()
        top.setObjectName("topbar")
        tl = QHBoxLayout(top)
        tl.setContentsMargins(12, 6, 12, 0)
        tl.setSpacing(4)
        self.steps = QButtonGroup(self)
        self.step_btns = []
        for i, name in enumerate(["1   Load", "2   Review", "3   Export"]):
            b = QPushButton(name)
            b.setObjectName("step")
            b.setCheckable(True)
            b.clicked.connect(lambda _c=False, i=i: self.go(i))
            self.steps.addButton(b, i)
            self.step_btns.append(b)
            tl.addWidget(b)
        tl.addStretch(1)
        self.status_lbl = QLabel("")
        self.status_lbl.setObjectName("muted")
        tl.addWidget(self.status_lbl)
        tl.addSpacing(12)
        self.theme_btn = QPushButton()
        self.theme_btn.clicked.connect(self.toggle_theme)
        tl.addWidget(self.theme_btn, 0, Qt.AlignVCenter)
        tl.setContentsMargins(12, 6, 12, 0)
        v.addWidget(top)

        self.stack = QStackedWidget()
        self.load_page = LoadPage(self)
        self.review_page = ReviewPage(self)
        self.export_page = ExportPage(self)
        for p in (self.load_page, self.review_page, self.export_page):
            self.stack.addWidget(p)
        v.addWidget(self.stack, 1)
        self.setCentralWidget(central)

        self.apply_theme()
        self.go(0)
        self.load_page.refresh()

    # ------------------------------------------------------------ helpers
    def stem_by_id(self, sid):
        for s in self.stems:
            if s.id == sid:
                return s
        return None

    def peaks(self, stem) -> PeakCache:
        pc = self._peaks.get(stem.id)
        if pc is None:
            pc = PeakCache(stem.mono())
            self._peaks[stem.id] = pc
        return pc

    def prefix(self) -> str:
        return self.load_page.get_prefix()

    def output_folder(self) -> str:
        return self.load_page.output_folder()

    def set_base_dir(self, d):
        self.base_dir = d
        self.settings.setValue("base_dir", d)

    def status(self, msg):
        self.status_lbl.setText(msg)

    def names_changed(self):
        if hasattr(self, "review_page"):
            self.review_page.names_changed()

    def update_steps(self):
        self.step_btns[1].setEnabled(bool(self.chops) or bool(self.stems))
        self.step_btns[2].setEnabled(bool(self.export_page.folder) if hasattr(self, "export_page")
                                     else False)

    def go(self, i):
        self.stack.setCurrentIndex(i)
        self.step_btns[i].setChecked(True)
        if i == 1:
            self.review_page.counts_changed()

    # -------------------------------------------------------------- theme
    def apply_theme(self):
        app = QApplication.instance()
        app.setPalette(theme.palette(self.t))
        app.setStyleSheet(theme.stylesheet(self.t))
        dark = self.theme_name == "dark"
        self.theme_btn.setText("Light mode" if dark else "Dark mode")
        self.theme_btn.setIcon(icons.sun(self.t["text"]) if dark else icons.moon(self.t["text"]))
        if hasattr(self, "review_page"):
            self.review_page.retheme()
            self.load_page.refresh()
            self.export_page.icon.setPixmap(icons.check(self.t["ok"]).pixmap(34, 34))
        self._dark_title_bar(dark)

    def _dark_title_bar(self, dark):
        try:
            import ctypes
            import sys
            if sys.platform != "win32":
                return
            hwnd = int(self.winId())
            val = ctypes.c_int(1 if dark else 0)
            for attr in (20, 19):   # DWMWA_USE_IMMERSIVE_DARK_MODE (new / old builds)
                if ctypes.windll.dwmapi.DwmSetWindowAttribute(hwnd, attr, ctypes.byref(val),
                                                              ctypes.sizeof(val)) == 0:
                    break
        except Exception:
            pass

    def toggle_theme(self):
        self.theme_name = "light" if self.theme_name == "dark" else "dark"
        self.t = theme.DARK if self.theme_name == "dark" else theme.LIGHT
        self.settings.setValue("theme", self.theme_name)
        self.apply_theme()

    # --------------------------------------------------------------- jobs
    def _run(self, job: Job, on_done, msg):
        self.busy = True
        self.load_page.set_busy(True, msg)
        self.status(msg)
        job.progress.connect(lambda m, i, n: (self.load_page.set_busy(True, m, i, n), self.status(m)))
        job.done.connect(lambda res: self._finish(job, on_done, res))
        job.failed.connect(lambda err: self._failed(job, err))
        self.jobs.append(job)
        job.start()

    def _finish(self, job, on_done, res):
        self.busy = False
        self.load_page.set_busy(False)
        self.status("")
        if job in self.jobs:
            self.jobs.remove(job)
        on_done(res)

    def _failed(self, job, err):
        self.busy = False
        self.load_page.set_busy(False)
        self.status("")
        if job in self.jobs:
            self.jobs.remove(job)
        QMessageBox.warning(self, APP_NAME, "Something went wrong:\n\n" + err.splitlines()[-1])

    # ------------------------------------------------------------- stems
    def add_files(self, paths):
        if self.busy:
            return
        self._run(Job(load_and_detect, paths), self._files_loaded, "Loading files…")

    def _files_loaded(self, stems):
        have = {os.path.normcase(p) for s in self.stems for p in s.sources}
        added = [s for s in stems if not any(os.path.normcase(p) in have for p in s.sources)]
        self.stems.extend(added)
        self.load_page.refresh()
        skipped = [s for s in added if s.mode == "skip"]
        if skipped:
            self.status(f"{len(skipped)} file(s) couldn't be read.")
        self.update_steps()

    def set_kind(self, stem, kind):
        if stem.kind == kind:
            return
        stem.kind = kind
        stem.options = {}
        stem.analysis.pop("sections", None)
        if any(c.stem_id == stem.id for c in self.chops):
            stem.status = "Type changed: process again"
        self.load_page.refresh()

    def set_mode(self, stem, mode):
        if stem.mode == mode:
            return
        stem.mode = mode
        stem.status = "Mark regions by hand" if mode == "manual" else "Ready"
        self.load_page.refresh()

    def remove_stem(self, stem):
        self.stems = [s for s in self.stems if s.id != stem.id]
        self.chops = [c for c in self.chops if c.stem_id != stem.id]
        self._peaks.pop(stem.id, None)
        self.load_page.refresh()
        self.review_page.rebuild()

    def open_stem(self, stem):
        if stem.mode == "auto" and stem.engine == "groove":
            if stem.analysis.get("sections") is None or not any(c.stem_id == stem.id for c in self.chops):
                self._run(Job(rechop, stem, self.song),
                          lambda chops: (self.replace_chops(stem, chops, go_review=False),
                                         LoopDialog(self, stem).exec()),
                          f"Analysing {stem.name}…")
                return
            LoopDialog(self, stem).exec()
        else:
            ManualDialog(self, stem).exec()

    def rechop(self, stem):
        self._run(Job(rechop, stem, self.song),
                  lambda chops: self.replace_chops(stem, chops), f"Re-chopping {stem.name}…")

    def replace_chops(self, stem, chops, status=None, go_review=True):
        order = {s.id: i for i, s in enumerate(self.stems)}
        self.chops = [c for c in self.chops if c.stem_id != stem.id] + list(chops)
        self.chops.sort(key=lambda c: (order.get(c.stem_id, 0), c.start))
        stem.status = status or (f"{len(chops)} chops" if chops else "Nothing found")
        self.load_page.refresh()
        self.review_page.rebuild()
        if go_review:
            self.go(1)

    # ----------------------------------------------------------- process
    def process_all(self):
        if self.busy:
            return
        if not self.load_page.artist.text().strip() or not self.load_page.song.text().strip():
            QMessageBox.information(self, APP_NAME, "Enter the artist and song first. They name "
                                    "the output folder and every file.")
            return
        self._run(Job(process, self.stems), self._processed, "Chopping…")

    def _processed(self, result):
        chops, song = result
        self.song = song
        manual_ids = {s.id for s in self.stems if s.mode != "auto"}
        kept = [c for c in self.chops if c.stem_id in manual_ids]
        order = {s.id: i for i, s in enumerate(self.stems)}
        self.chops = sorted(kept + chops, key=lambda c: (order.get(c.stem_id, 0), c.start))
        if song:
            self.status(f"Song tempo: {song['bpm']:g} BPM")
        self.load_page.refresh()
        self.review_page.rebuild()
        self.go(1)

    # ------------------------------------------------------------ export
    def export_all(self):
        if self.busy or not self.chops:
            return
        if not all(c.approved for c in self.chops):
            return
        folder = self.output_folder()
        stems = {s.id: s for s in self.stems}
        self._run(Job(export, stems, list(self.chops), folder, self.prefix()),
                  lambda files: self._exported(files, folder), "Exporting…")

    def _exported(self, files, folder):
        self.export_page.show_result(files, folder)
        self.update_steps()
        self.go(2)

    def start_over(self):
        self.player.stop()
        self.stems, self.chops, self.song = [], [], None
        self._peaks.clear()
        self.load_page.artist.clear()
        self.load_page.song.clear()
        self.load_page.prefix_edited = False
        self.load_page.refresh()
        self.review_page.rebuild()
        self.export_page.show_result([], "")
        self.update_steps()
        self.go(0)

    def closeEvent(self, e):
        self.player.stop()
        for j in self.jobs:
            j.wait(3000)
        super().closeEvent(e)


def about() -> str:
    return f"{APP_NAME} {__version__}"
