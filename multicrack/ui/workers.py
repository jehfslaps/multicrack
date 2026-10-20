"""Background jobs so the window stays responsive."""
import traceback

from PySide6.QtCore import QThread, Signal

from ..core import audio, pipeline


class Job(QThread):
    progress = Signal(str, int, int)
    done = Signal(object)
    failed = Signal(str)

    def __init__(self, fn, *args):
        super().__init__()
        self.fn, self.args = fn, args

    def run(self):
        try:
            result = self.fn(*self.args, progress=lambda msg, i, n: self.progress.emit(msg, i, n))
            self.done.emit(result)
        except Exception:
            self.failed.emit(traceback.format_exc())


def load_and_detect(paths, progress=None):
    stems = audio.load_stems(paths, progress=progress)
    for i, st in enumerate(stems):
        if st.mode == "skip":
            continue
        if progress:
            progress(f"Listening to {st.name}", i, len(stems))
        try:
            st.kind = pipeline.detect_kind(st)
        except Exception:
            st.kind = "Melodic (other)"
        st.status = "Ready"
    return stems


def process(stems, progress=None):
    return pipeline.process(stems, progress=progress)


def rechop(stem, song, progress=None):
    return pipeline.chop_stem(stem, song)


def export(stems_by_id, chops, folder, prefix, progress=None):
    return pipeline.export(stems_by_id, chops, folder, prefix, progress=progress)
