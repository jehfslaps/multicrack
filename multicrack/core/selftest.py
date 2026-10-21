"""Built-in check used by the build: chops synthetic drums and writes WAVs.
Exit code 0 means everything works."""
from __future__ import annotations

import os
import struct
import sys
import tempfile
import traceback

import numpy as np


def _synth(sr=44100, bpm=120.0, bars=8):
    beat = 60.0 / bpm
    n = int(sr * beat * 4 * bars) + sr
    t = np.arange(int(0.4 * sr)) / sr
    kick = (np.sin(2 * np.pi * (50 + 120 * np.exp(-t * 30)) * t) * np.exp(-t * 9)).astype(np.float32)
    rng = np.random.default_rng(1)
    th = np.arange(int(0.06 * sr)) / sr
    hat = (rng.standard_normal(len(th)) * np.exp(-th * 70)).astype(np.float32) * 0.4
    kick_track = np.zeros(n, np.float32)
    hat_track = np.zeros(n, np.float32)
    for b in range(bars * 4):
        s = int(b * beat * sr) + 2000
        kick_track[s:s + len(kick)] += kick * (0.9 if b % 2 else 1.0)
        for h in (0, 0.5):
            hs = int((b + h) * beat * sr) + 2000
            hat_track[hs:hs + len(hat)] += hat
    return sr, kick_track, hat_track


def run(gui=True) -> int:
    try:
        from .audio import write_wav24
        from .model import Stem
        from . import pipeline
        from .naming import make_prefix

        sr, k, h = _synth()
        stems = [Stem(path="Kick.wav", name="Kick.wav", clean_name="Kick",
                      audio=np.stack([k, k], 1), sr=sr),
                 Stem(path="Hats.wav", name="Hats.wav", clean_name="Hats",
                      audio=h[:, None].copy(), sr=sr),
                 Stem(path="Drums.wav", name="Drums.wav", clean_name="Drums",
                      audio=np.stack([k + h, k + h], 1), sr=sr)]
        for s in stems:
            s.kind = pipeline.detect_kind(s)
        assert stems[0].kind == "Kick", stems[0].kind
        assert stems[1].kind == "Hats", stems[1].kind
        chops, song = pipeline.process(stems)
        assert song and abs(song["bpm"] - 120) < 0.6, song
        assert any(c.label == "Kick" for c in chops), [c.label for c in chops]
        assert any(c.kind == "loop" for c in chops), [c.kind for c in chops]
        out = tempfile.mkdtemp(prefix="xenakis_selftest_")
        files = pipeline.export({s.id: s for s in stems}, chops, out, make_prefix("Self", "Test"))
        assert files and all(os.path.getsize(f) > 44 for f in files)
        with open(files[0], "rb") as f:
            data = f.read()
        assert data[:4] == b"RIFF" and data[8:12] == b"WAVE"
        chunks, pos = [], 12
        while pos + 8 <= len(data):
            cid, size = data[pos:pos + 4], struct.unpack("<I", data[pos + 4:pos + 8])[0]
            chunks.append(cid)
            pos += 8 + size + (size & 1)
        assert chunks == [b"fmt ", b"data"], chunks
        _ = write_wav24
        # per-chop edits: reverse, gain, fades, loop seam
        from .audio import render_chop
        loop = next(c for c in chops if c.kind == "loop")
        st = next(s for s in stems if s.id == loop.stem_id)
        loop.reverse, loop.gain_db, loop.fade_out_ms = True, -6.0, 20.0
        y = render_chop(st, loop)
        assert abs(20 * np.log10(np.abs(y).max()) + 6.1) < 0.05
        loop.reverse, loop.gain_db, loop.fade_out_ms = False, 0.0, None
        # sessions round-trip
        from . import session
        meta = {"artist": "Self", "song": "Test"}
        data = session.to_dict(meta, stems, chops)
        assert len(data["chops"]) == len(chops) and data["stems"][0]["kind"] == "Kick"
        # sound-recognition model (bundled with the app)
        from . import ai
        if ai._model_dir():
            assert ai.available(), "AI model failed to load"
            tg = ai.tags(k[: sr], sr)
            assert tg, "AI model returned nothing"
        if gui:
            os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
            from PySide6.QtWidgets import QApplication
            from ..ui.main_window import MainWindow
            app = QApplication.instance() or QApplication([])
            w = MainWindow()
            w.stems = stems
            w.chops = chops
            w.load_page.refresh()
            w.review_page.rebuild()
            n0 = len(w.chops)
            w.review_page.delete_chop(w.chops[0])
            assert len(w.chops) == n0 - 1
            w.undo()
            assert len(w.chops) == n0
            w.redo()
            assert len(w.chops) == n0 - 1
            w.review_page.clone_chop(w.chops[0])
            w.review_page.approve_and_next()
            w.theme_btn.setChecked(True)
            w.toggle_theme()
            w.theme_btn.setChecked(False)
            w.toggle_theme()
            from ..ui.skin import core as SK
            assert SK.FAMILY == "IBM Plex Mono", f"bundled font missing ({SK.FAMILY})"
            # layout: the window measures the room it needs once shown
            w.show()
            app.processEvents()
            assert hasattr(w, "_full_w") and w.minimumWidth() >= 800, "layout not measured"
            # divider between the editor and the list
            w.go(1)
            app.processEvents()
            sp = w.review_page.split
            sp.set_top_fraction(0)
            assert sp.editor_hidden(), "editor did not collapse"
            sp.reset_split()
            assert not sp.editor_hidden(), "editor did not come back"
            # UI size: rebuild the whole app at another scale, keeping the session
            from ..app import make_app, teardown
            n1, dpr0 = len(w.chops), w.devicePixelRatioF()
            h = w._handoff_state()
            teardown(app, w)
            del w, app
            app = make_app(0.75)
            w = MainWindow(handoff=h)
            w.show_initial(h)
            app.processEvents()
            assert len(w.chops) == n1, "chops lost on UI size change"
            assert w.devicePixelRatioF() < dpr0, "UI size did not change"
            w.autosave_path = os.path.join(out, "autosave.xenakis")
            w.autosave()
            assert os.path.exists(w.autosave_path)
            w.close()
            _ = app
        print(f"selftest ok: {len(chops)} chops, {len(files)} files")
        return 0
    except Exception:
        traceback.print_exc()
        try:
            log = os.path.join(tempfile.gettempdir(), "xenakis_selftest.log")
            with open(log, "w") as f:
                traceback.print_exc(file=f)
        except Exception:
            pass
        return 1


if __name__ == "__main__":
    sys.exit(run())
