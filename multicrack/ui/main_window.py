"""The Xenakis window: holds the session and moves between Load, Review and Export."""
from __future__ import annotations

import os
import shutil
import time
from dataclasses import replace

from PySide6.QtCore import QPoint, QSettings, QSize, QStandardPaths, Qt, QThread, QTimer, Signal
from PySide6.QtGui import QAction, QColor, QDesktopServices, QKeySequence
from PySide6.QtCore import QUrl
from PySide6.QtWidgets import (QApplication, QButtonGroup, QFileDialog, QFrame, QHBoxLayout,
                               QLabel, QMainWindow, QMenu, QMessageBox, QPushButton,
                               QStackedWidget, QToolButton, QVBoxLayout, QWidget)

from .. import APP_NAME, LEGACY_NAME
from ..core import session, updater
from ..core.audio import desktop_dir
from ..core.songs import guess_names, split_songs
from . import logo, skin, theme
from .skin import core as K
from .skin import dialogs
from .skin import widgets as W
from .export_page import ExportPage
from .load_page import LoadPage
from .loop_dialog import LoopDialog
from .manual_dialog import ManualDialog
from .player import Player
from .review_page import DRAG_DIR, ReviewPage
from .waveform import PeakCache
from .workers import Job, export, load_and_detect, process, rechop


class History:
    """Undo / redo of everything on the Review page (snapshots of the chop list)."""

    def __init__(self, win, limit=300):
        self.win = win
        self.limit = limit
        self.undo_stack: list = []
        self.redo_stack: list = []
        self._key = None
        self._t = 0.0

    def _snap(self):
        sel = self.win.review_page.selected if hasattr(self.win, "review_page") else None
        return [replace(c) for c in self.win.chops], (sel.id if sel is not None else None)

    def push(self, key=None):
        now = time.monotonic()
        if key is not None and key == self._key and now - self._t < 1.5:
            self._t = now          # one undo step for a burst of the same edit
            return
        self.undo_stack.append(self._snap())
        del self.undo_stack[:-self.limit]
        self.redo_stack.clear()
        self._key, self._t = key, now

    def can_undo(self):
        return bool(self.undo_stack)

    def can_redo(self):
        return bool(self.redo_stack)

    def undo(self):
        if not self.undo_stack:
            return False
        self.redo_stack.append(self._snap())
        self._restore(self.undo_stack.pop())
        return True

    def redo(self):
        if not self.redo_stack:
            return False
        self.undo_stack.append(self._snap())
        self._restore(self.redo_stack.pop())
        return True

    def clear(self):
        self.undo_stack.clear()
        self.redo_stack.clear()
        self._key = None

    def _restore(self, snap):
        chops, sel = snap
        self._key = None
        w = self.win
        w.chops = [replace(c) for c in chops]
        rp = w.review_page
        rp.selected = next((c for c in w.chops if c.id == sel), None)
        for st in w.stems:
            n = sum(1 for c in w.chops if c.stem_id == st.id)
            if n or st.status.endswith("chops") or st.status == "Nothing kept":
                st.status = f"{n} chops" if n else "Nothing kept"
        w.player.stop()
        w.load_page.refresh()
        rp._rebuild_keep_scroll()
        w.session_changed()


class UpdateCheck(QThread):
    found = Signal(object)
    failed = Signal(str)

    def run(self):
        try:
            self.found.emit(updater.check())
        except Exception as e:  # network, private project, rate limit ...
            self.failed.emit(str(e))


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.settings = QSettings(APP_NAME, APP_NAME)
        self._migrate_settings()
        self.theme_name = self.settings.value("theme", "light")
        self.t = theme.DARK if self.theme_name == "dark" else theme.LIGHT
        base = self.settings.value("base_dir", "")
        self.base_dir = base if base and os.path.isdir(base) else desktop_dir()
        self.stems = []
        self.chops = []
        self.song = None
        self.queue: list = []
        self.busy = False
        self.jobs = []
        self._peaks = {}
        self._finished = False
        self._update = None
        self._checks = []
        self.player = Player()
        self.history = History(self)
        data_dir = QStandardPaths.writableLocation(QStandardPaths.AppDataLocation) or os.path.join(
            os.path.expanduser("~"), ".xenakis")
        self.autosave_path = os.path.join(data_dir, "autosave" + session.EXT)
        self._migrate_autosave(data_dir)

        self.setWindowTitle(f"{APP_NAME} {updater.current_version()}")
        self.setWindowIcon(logo.app_icon())
        self.resize(1480, 940)
        self.setMinimumSize(QSize(1040, 700))

        skin.apply(self.theme_name)
        central = W.Chassis()
        v = QVBoxLayout(central)
        v.setContentsMargins(22, 20, 22, 18)
        v.setSpacing(14)

        top = QHBoxLayout()
        top.setSpacing(14)
        brand = W.Plate(margins=(26, 4, 22, 4))
        brand.setFixedHeight(70)
        self.brand_mark = W.LogoMark(46)
        brand.lay.addWidget(self.brand_mark)
        brand.lay.addSpacing(12)
        self.brand_lbl = W.mono("XENAKIS", "plate_text", 31, 700, 5.5)
        brand.lay.addWidget(self.brand_lbl)
        brand.lay.addSpacing(6)
        self.version_badge = W.Badge(f"XK-1  [v{updater.current_version()}]")
        brand.lay.addWidget(self.version_badge)
        top.addWidget(brand)
        self.steps_sel = W.StepSelector(["01 LOAD", "02 REVIEW", "03 EXPORT"])
        self.steps_sel.setFixedHeight(64)
        self.steps_sel.clicked.connect(self.go)
        top.addWidget(self.steps_sel)
        self.lcd = W.Lcd("SONG TEMPO", "— BPM", value_px=21, min_w=230)
        self.lcd.setFixedHeight(64)
        top.addWidget(self.lcd, 1)
        self.update_btn = W.HwButton("Update", "red", icon="export", min_h=50, px=12.5)
        self.update_btn.hide()
        self.update_btn.clicked.connect(self.install_update)
        top.addWidget(self.update_btn)
        self.theme_btn = W.LeverSwitch("LIGHT", "DARK")
        self.theme_btn.setFixedSize(140, 64)
        self.theme_btn.setChecked(self.theme_name == "dark")
        self.theme_btn.setToolTip("Light / dark")
        self.theme_btn.clicked.connect(self.toggle_theme)
        top.addWidget(self.theme_btn)
        self.menu_btn = W.HwButton("", "icon", icon="menu", min_h=64)
        self.menu_btn.setToolTip("Menu")
        self._menu = self._build_menu()
        self.menu_btn.clicked.connect(lambda: self._menu.exec(
            self.menu_btn.mapToGlobal(self.menu_btn.rect().bottomRight())
            - QPoint(self._menu.sizeHint().width(), -4)))
        top.addWidget(self.menu_btn)
        v.addLayout(top)

        self.stack = QStackedWidget()
        self.load_page = LoadPage(self)
        self.review_page = ReviewPage(self)
        self.export_page = ExportPage(self)
        for p in (self.load_page, self.review_page, self.export_page):
            self.stack.addWidget(p)
        v.addWidget(self.stack, 1)
        self.setCentralWidget(central)
        self.chassis = central
        self.load_page.install_wires(central)
        self._status_timer = QTimer(self)
        self._status_timer.setSingleShot(True)
        self._status_timer.timeout.connect(self._show_tempo)

        self._autosave_timer = QTimer(self)
        self._autosave_timer.setSingleShot(True)
        self._autosave_timer.setInterval(1500)
        self._autosave_timer.timeout.connect(self.autosave)

        self.apply_theme()
        self.go(0)
        self.load_page.refresh()
        updater.cleanup_old()
        shutil.rmtree(DRAG_DIR, ignore_errors=True)
        QTimer.singleShot(400, self._offer_resume)
        if updater.is_frozen():
            QTimer.singleShot(2500, lambda: self.check_updates(quiet=True))

    def _build_menu(self):
        m = QMenu(self)
        items = [("New session", QKeySequence.New, self.new_session),
                 ("Open session…", QKeySequence.Open, self.open_session),
                 ("Save session as…", QKeySequence("Ctrl+S"), self.save_session_as), None,
                 ("Undo", QKeySequence.Undo, self.undo),
                 ("Redo", QKeySequence("Ctrl+Y"), self.redo), None,
                 ("Check for updates…", None, lambda: self.check_updates(quiet=False)),
                 (f"About {APP_NAME}", None, self.about)]
        for it in items:
            if it is None:
                m.addSeparator()
                continue
            text, key, fn = it
            a = QAction(text, self)
            if key is not None:
                a.setShortcut(key)
                a.setShortcutContext(Qt.ApplicationShortcut)
                self.addAction(a)
            a.triggered.connect(fn)
            m.addAction(a)
        return m

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
        if not msg:
            if not self.busy:
                self._show_tempo()
            return
        self.lcd.set("BUSY" if self.busy else "STATUS", msg.upper())
        self._status_timer.start(1500 if self.busy else 3500)

    def _show_tempo(self):
        if self.busy:
            return
        bpm = self.song.get("bpm") if self.song else None
        self.lcd.set("SONG TEMPO", f"{bpm:g} BPM" if bpm else "— BPM")

    def names_changed(self):
        if hasattr(self, "review_page"):
            self.review_page.names_changed()
            self.session_changed()

    def update_steps(self):
        self.steps_sel.set_enabled(1, bool(self.chops) or bool(self.stems))
        self.steps_sel.set_enabled(2, bool(self.export_page.folder) if hasattr(self, "export_page")
                                   else False)

    def go(self, i):
        self.stack.setCurrentIndex(i)
        self.steps_sel.set_current(i)
        self.chassis.update()
        if i == 1:
            self.review_page.counts_changed()
            self.review_page.setFocus()

    # -------------------------------------------------------------- theme
    def apply_theme(self):
        skin.apply(self.theme_name)
        self.t = theme.DARK if self.theme_name == "dark" else theme.LIGHT
        if hasattr(self, "review_page"):
            self.review_page.retheme()
            self.load_page.refresh()
            self.load_page.refresh_queue()
        self._style_title_bar()

    def _style_title_bar(self):
        """Windows 11: color the native title bar to match the chassis."""
        try:
            import ctypes
            import sys
            if sys.platform != "win32":
                return
            hwnd = int(self.winId())
            dark = self.theme_name == "dark"
            val = ctypes.c_int(1 if dark else 0)
            for attr in (20, 19):   # DWMWA_USE_IMMERSIVE_DARK_MODE (new / old builds)
                if ctypes.windll.dwmapi.DwmSetWindowAttribute(hwnd, attr, ctypes.byref(val),
                                                              ctypes.sizeof(val)) == 0:
                    break

            def colorref(hexs):
                c = QColor(hexs)
                return ctypes.c_uint(c.red() | (c.green() << 8) | (c.blue() << 16))
            P = K.pal()
            for attr, col in ((35, P["chassis"] if not dark else "#1E1F21"),       # caption
                              (36, P["chassis_text"]),                              # caption text
                              (34, P["chassis_lo"])):                               # border
                v = colorref(col)
                ctypes.windll.dwmapi.DwmSetWindowAttribute(hwnd, attr, ctypes.byref(v),
                                                           ctypes.sizeof(v))
        except Exception:
            pass

    def resizeEvent(self, e):
        super().resizeEvent(e)
        narrow = self.width() < 1330
        short = self.height() < 830
        if getattr(self, "_compact", None) != (narrow, short):
            self._compact = (narrow, short)
            self.brand_lbl.setFont(K.font(24 if narrow else 31, 700, 3.5 if narrow else 5.5))
            self.version_badge.setVisible(not narrow)
            self.lcd.setMinimumWidth(150 if narrow else 230)
            self.load_page.set_compact(narrow, short)
            self.review_page.set_compact(narrow, short)

    def showEvent(self, e):
        super().showEvent(e)
        self._style_title_bar()

    def toggle_theme(self):
        self.theme_name = "dark" if self.theme_btn.isChecked() else "light"
        self.settings.setValue("theme", self.theme_name)
        self.apply_theme()
        self.update()

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
        dialogs.warn(self, "Something went wrong:\n\n" + err.strip().splitlines()[-1], "Error")

    # ---------------------------------------------------------- undo / redo
    def undo(self):
        if self.history.undo():
            self.status("Undone")
        self.review_page.counts_changed()

    def redo(self):
        if self.history.redo():
            self.status("Redone")
        self.review_page.counts_changed()

    # ------------------------------------------------------------- stems
    def add_files(self, paths):
        if self.busy:
            return
        songs = split_songs(paths)
        if songs:
            entries = []
            for f in songs:
                a, s = guess_names(f)
                entries.append({"artist": a, "song": s, "paths": [f]})
            if not self.stems:
                first = entries.pop(0)
                self.queue.extend(entries)
                self._begin_song(first)
            else:
                self.queue.extend(entries)
                self.load_page.refresh_queue()
                self.status(f"Added {len(entries)} songs to the queue")
            self.session_changed()
            return
        self._run(Job(load_and_detect, paths), self._files_loaded, "Loading files…")

    def _begin_song(self, item):
        self.load_page.set_song(item.get("artist", ""), item.get("song", ""))
        self.load_page.refresh_queue()
        self._run(Job(load_and_detect, item["paths"]), self._files_loaded, "Loading files…")

    def _files_loaded(self, stems):
        have = {os.path.normcase(p) for s in self.stems for p in s.sources}
        added = [s for s in stems if not any(os.path.normcase(p) in have for p in s.sources)]
        self.stems.extend(added)
        self._finished = False
        self.load_page.refresh()
        skipped = [s for s in added if s.mode == "skip"]
        if skipped:
            self.status(f"{len(skipped)} file(s) couldn't be read.")
        self.update_steps()
        self.session_changed()

    def set_kind(self, stem, kind):
        if stem.kind == kind:
            return
        stem.kind = kind
        stem.options = {}
        stem.analysis.pop("sections", None)
        if any(c.stem_id == stem.id for c in self.chops):
            stem.status = "Type changed: process again"
        self.load_page.refresh()
        self.session_changed()

    def set_mode(self, stem, mode):
        if stem.mode == mode:
            return
        stem.mode = mode
        stem.status = "Mark regions by hand" if mode == "manual" else "Ready"
        self.load_page.refresh()
        self.session_changed()

    def remove_stem(self, stem):
        self.history.push()
        self.stems = [s for s in self.stems if s.id != stem.id]
        self.chops = [c for c in self.chops if c.stem_id != stem.id]
        self._peaks.pop(stem.id, None)
        self.load_page.refresh()
        self.review_page.rebuild()
        self.session_changed()

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

    def chops_edited(self, stem_id):
        st = self.stem_by_id(stem_id)
        if st is not None:
            n = sum(1 for c in self.chops if c.stem_id == stem_id)
            st.status = f"{n} chops" if n else "Nothing kept"
            self.load_page.refresh()

    def replace_chops(self, stem, chops, status=None, go_review=True):
        self.history.push()
        order = {s.id: i for i, s in enumerate(self.stems)}
        self.chops = [c for c in self.chops if c.stem_id != stem.id] + list(chops)
        self.chops.sort(key=lambda c: (order.get(c.stem_id, 0), c.start))
        stem.status = status or (f"{len(chops)} chops" if chops else "Nothing found")
        self.load_page.refresh()
        self.review_page.rebuild()
        self.session_changed()
        if go_review:
            self.go(1)

    # ----------------------------------------------------------- process
    def process_all(self):
        if self.busy:
            return
        if not self.load_page.artist.text().strip() or not self.load_page.song.text().strip():
            dialogs.inform(self, "Enter the artist and song first. They name the output folder "
                           "and every file.", "Song details")
            return
        self._run(Job(process, self.stems), self._processed, "Chopping…")

    def _processed(self, result):
        chops, song = result
        self.history.push()
        self.song = song
        manual_ids = {s.id for s in self.stems if s.mode != "auto"}
        kept = [c for c in self.chops if c.stem_id in manual_ids]
        order = {s.id: i for i, s in enumerate(self.stems)}
        self.chops = sorted(kept + chops, key=lambda c: (order.get(c.stem_id, 0), c.start))
        self._show_tempo()
        self.load_page.refresh()
        self.review_page.rebuild()
        self.session_changed()
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
        self._finished = True
        self.autosave()
        self.export_page.show_result(files, folder)
        self.export_page.set_next(self._queue_label(0) if self.queue else None, len(self.queue))
        self.update_steps()
        self.go(2)

    def _queue_label(self, i):
        q = self.queue[i]
        return " - ".join(p for p in (q.get("artist"), q.get("song")) if p) or "Untitled"

    def _reset(self):
        self.player.stop()
        self.stems, self.chops, self.song = [], [], None
        self._peaks.clear()
        self.history.clear()
        self.load_page.artist.clear()
        self.load_page.song.clear()
        self.load_page.prefix_edited = False
        self.review_page.selected = None
        self.load_page.refresh()
        self.review_page.rebuild()
        self.export_page.show_result([], "")
        self.export_page.set_next(None, 0)
        self.update_steps()
        self.go(0)

    def start_over(self):
        self._reset()
        self._finished = False
        self.load_page.refresh_queue()
        self.session_changed()

    def next_song(self, index=0):
        if not self.queue or self.busy:
            return
        if self.chops and not self._finished:
            if not dialogs.ask(self, "Switch songs? This song's chops haven't been exported yet. "
                               "Use Menu › Save session as… first if you want to keep them.",
                               "Switch song", "Cancel", "Next song"):
                return
        item = self.queue.pop(index)
        self._reset()
        self._finished = False
        self._begin_song(item)

    def remove_from_queue(self, index):
        if 0 <= index < len(self.queue):
            self.queue.pop(index)
            self.load_page.refresh_queue()
            self.session_changed()

    # ----------------------------------------------------------- sessions
    def _meta(self):
        lp = self.load_page
        return {"artist": lp.artist.text(), "song": lp.song.text(), "prefix": lp.prefix.text(),
                "prefix_edited": lp.prefix_edited, "base_dir": self.base_dir,
                "song_grid": ({k: self.song[k] for k in ("bpm", "downbeat", "frames", "sr")}
                              if self.song else None)}

    def session_changed(self):
        if hasattr(self, "_autosave_timer"):
            self._autosave_timer.start()

    def autosave(self):
        try:
            if not self.stems and not self.queue:
                if os.path.exists(self.autosave_path):
                    os.remove(self.autosave_path)
                return
            data = session.to_dict(self._meta(), self.stems, self.chops, self.queue,
                                   finished=self._finished and not self.queue)
            session.save(self.autosave_path, data)
        except Exception:
            pass

    def _offer_resume(self):
        if not os.path.exists(self.autosave_path) or self.stems:
            return
        try:
            data = session.read(self.autosave_path)
        except Exception:
            return
        if data.get("finished") or (not data.get("stems") and not data.get("queue")):
            return
        if dialogs.ask(self, "Pick up where you left off?\n\n" + session.describe(data),
                       "Resume", "Start fresh", "Resume session"):
            self.open_session_data(data)
        else:
            data["finished"] = True
            try:
                session.save(self.autosave_path, data)
            except Exception:
                pass

    def new_session(self):
        if self.chops and not self._finished:
            if not dialogs.ask(self, "Start a new session? Unexported chops will be cleared "
                               "(Save session as… keeps them).", "Start new", "Cancel", "New session"):
                return
        self.queue = []
        self.start_over()

    def open_session(self):
        path, _ = QFileDialog.getOpenFileName(self, "Open session", self.base_dir,
                                              f"{APP_NAME} sessions ("
                                              + " ".join(f"*{e}" for e in session.OPEN_EXTS) + ")")
        if not path:
            return
        try:
            data = session.read(path)
        except Exception as e:
            dialogs.warn(self, f"Couldn't open that file:\n\n{e}")
            return
        self.open_session_data(data)

    def open_session_data(self, data):
        def done(res):
            stems, chops, missing = res
            self._reset()
            m = data.get("meta", {})
            if m.get("base_dir") and os.path.isdir(m["base_dir"]):
                self.base_dir = m["base_dir"]
            self.load_page.set_song(m.get("artist", ""), m.get("song", ""))
            if m.get("prefix_edited"):
                self.load_page.prefix.setText(m.get("prefix", ""))
                self.load_page.prefix_edited = True
            g = m.get("song_grid")
            self.song = dict(g, ref=None) if g else None
            self.stems = stems
            self.chops = chops
            self.queue = data.get("queue", [])
            self._finished = False
            self.load_page.refresh()
            self.load_page.refresh_queue()
            self.review_page.rebuild()
            self.update_steps()
            self.go(1 if chops else 0)
            if missing:
                dialogs.warn(self, "Some audio files couldn't be found (moved "
                                    "or renamed?), so their chops were skipped:\n\n"
                                    + "\n".join(missing[:12]))
            self.session_changed()
        self._run(Job(lambda progress=None: session.restore(data, progress)), done,
                  "Reopening session…")

    def save_session_as(self):
        lp = self.load_page
        name = " - ".join(p for p in (lp.artist.text().strip(), lp.song.text().strip()) if p) or "Session"
        path, _ = QFileDialog.getSaveFileName(self, "Save session",
                                              os.path.join(self.base_dir, name + session.EXT),
                                              f"{APP_NAME} sessions (*{session.EXT})")
        if not path:
            return
        if not path.endswith(session.EXT):
            path += session.EXT
        try:
            session.save(path, session.to_dict(self._meta(), self.stems, self.chops, self.queue))
            self.status(f"Saved {os.path.basename(path)}")
        except Exception as e:
            dialogs.warn(self, f"Couldn't save the session:\n\n{e}")

    # ------------------------------------------------------------ updates
    def check_updates(self, quiet=True):
        if not updater.is_frozen():
            if not quiet:
                dialogs.inform(self, "Updates work in the downloaded "
                                        "Xenakis.exe.")
            return
        th = UpdateCheck(self)
        self._checks.append(th)

        def found(info):
            self._update = info
            if info:
                self.update_btn.setText(f"Update to {info['version']}")
                self.update_btn.show()
                if not quiet:
                    self.install_update()
            elif not quiet:
                dialogs.inform(self, f"You're on the latest version "
                                        f"({updater.current_version()}).")

        def failed(msg):
            if not quiet:
                if dialogs.ask(self, "Couldn't check for updates. The GitHub project needs to be "
                               "public for this to work.\n\nOpen the download page instead?",
                               "Updates", "Open page", "Close"):
                    QDesktopServices.openUrl(QUrl(updater.RELEASES_PAGE))

        th.found.connect(found)
        th.failed.connect(failed)
        th.start()

    def install_update(self):
        info = self._update
        if not info or self.busy:
            return
        if not dialogs.ask(self, f"Update {APP_NAME} to {info['version']}?\n\nIt downloads, "
                           "restarts, and offers to pick up where you left off.", "Update",
                           "Update now", "Later"):
            return
        self.autosave()

        def done(path):
            try:
                self.player.stop()
                updater.install_and_restart(path)
                QApplication.instance().quit()
            except Exception as e:
                dialogs.warn(self, f"Couldn't install the update ({e}). "
                                    "Opening the download page instead.")
                QDesktopServices.openUrl(QUrl(updater.RELEASES_PAGE))
        self._run(Job(lambda progress=None: updater.download(info["url"], progress)), done,
                  "Downloading update…")

    # ------------------------------------------------------------ carried over from MultiCrack
    def _migrate_settings(self):
        """First run after the rename: copy the old app's preferences across."""
        if self.settings.value("migrated_from_legacy", False, type=bool):
            return
        old = QSettings(LEGACY_NAME, LEGACY_NAME)
        for key in old.allKeys():
            if not self.settings.contains(key):
                self.settings.setValue(key, old.value(key))
        self.settings.setValue("migrated_from_legacy", True)
        self.settings.sync()

    def _migrate_autosave(self, data_dir):
        if os.path.exists(self.autosave_path):
            return
        head, tail = os.path.split(os.path.normpath(data_dir))
        if tail != APP_NAME:
            return
        old = os.path.join(head, LEGACY_NAME, "autosave.multicrack")
        if os.path.isfile(old):
            try:
                os.makedirs(data_dir, exist_ok=True)
                shutil.move(old, self.autosave_path)
            except OSError:
                pass

    def about(self):
        dialogs.inform(self, f"{APP_NAME} {updater.current_version()}\n\nChops stems and "
                       "multitracks into clean, labeled samples.\n\nNamed for Iannis Xenakis, who "
                       "built sound and buildings out of straight lines; the X in the logo is woven "
                       "the same way.\n\nSound recognition: CED-mini "
                       "model (Apache 2.0) via sherpa-onnx. Font: IBM Plex Mono (OFL).", "About")

    def closeEvent(self, e):
        self.player.stop()
        self.autosave()
        for j in self.jobs:
            j.wait(3000)
        shutil.rmtree(DRAG_DIR, ignore_errors=True)
        super().closeEvent(e)
