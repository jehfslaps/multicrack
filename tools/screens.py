"""Developer check: render every window with real stems to PNGs."""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
from PySide6.QtWidgets import QApplication
from multicrack.ui.main_window import MainWindow
from multicrack.ui.loop_dialog import LoopDialog
from multicrack.ui.manual_dialog import ManualDialog
from multicrack.ui import workers

out = sys.argv[1]; files = sys.argv[2:]
app = QApplication([]); app.setStyle("Fusion")
w = MainWindow(); w.resize(1440, 900); w.show()
w.load_page.artist.setText("Taylor Swift"); w.load_page.song.setText("Style")
w._files_loaded(workers.load_and_detect(files))
def snap(name, widget=None):
    app.processEvents(); (widget or w).grab().save(os.path.join(out, name))
for theme in ("light", "dark"):
    if w.theme_name != theme: w.toggle_theme()
    w.go(0); snap(f"{theme}_1_load.png")
chops, song = workers.process(w.stems)
w._processed((chops, song))
for theme in ("light", "dark"):
    if w.theme_name != theme: w.toggle_theme()
    w.go(1); snap(f"{theme}_2_review.png")
loops = [s for s in w.stems if s.kind == "Drum loops"][0]
d = LoopDialog(w, loops); d.show(); snap("dark_3_loop.png", d); d.close()
vox = [s for s in w.stems if s.kind == "Vocals"][0]
d = ManualDialog(w, vox); d.show(); snap("dark_4_manual.png", d); d.close()
for c in w.chops: c.approved = True
w.review_page.rebuild()
import tempfile
w.base_dir = tempfile.mkdtemp()
w.load_page._names_changed()
files_out = workers.export({s.id: s for s in w.stems}, list(w.chops), w.output_folder(), w.prefix())
w._exported(files_out, w.output_folder())
w.toggle_theme(); snap("light_5_export.png")
print("ok", len(w.chops), "chops;", len(files_out), "exported to", w.output_folder())
