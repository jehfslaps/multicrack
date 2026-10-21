"""Entry point."""
import os
import sys

from . import APP_NAME

# UI size (menu › UI size). Applied as Qt's global scale factor, so text, buttons, knobs,
# screws and spacing all shrink together and stay sharp.
UI_SIZES = {"small": 0.75, "medium": 0.85, "large": 1.0}
DEFAULT_UI_SIZE = "medium"


def ui_size() -> str:
    from PySide6.QtCore import QSettings
    v = str(QSettings(APP_NAME, APP_NAME).value("ui_size", DEFAULT_UI_SIZE))
    return v if v in UI_SIZES else DEFAULT_UI_SIZE


def make_app(scale: float):
    """(Re)create the QApplication at a given UI scale."""
    os.environ["QT_SCALE_FACTOR"] = f"{scale:g}"
    from PySide6.QtWidgets import QApplication
    app = QApplication(sys.argv[:1])
    app.setApplicationName(APP_NAME)
    app.setStyle("Fusion")
    return app


def teardown(app, win):
    """Destroy the window and the QApplication so a new one can start at another scale."""
    from PySide6.QtCore import QCoreApplication, QEvent
    from .ui import skin
    win.hide()
    win.shutdown_threads()
    win.deleteLater()
    QCoreApplication.sendPostedEvents(None, QEvent.DeferredDelete)
    app.processEvents()
    skin.reset_caches()
    app.shutdown()


def main(argv=None):
    argv = list(sys.argv[1:] if argv is None else argv)
    if "--selftest" in argv:
        from .core.selftest import run
        return run(gui="--no-gui" not in argv)
    if sys.platform == "win32":
        try:  # own taskbar icon instead of the Python one
            import ctypes
            ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID("Xenakis.App")
        except Exception:
            pass
    from .ui.main_window import MainWindow
    files = [a for a in argv if os.path.exists(a)]
    handoff = None
    while True:
        app = make_app(UI_SIZES[ui_size()])
        win = MainWindow(handoff=handoff)
        win.show_initial(handoff)
        if files and handoff is None:
            win.add_files(files)
        rc = app.exec()
        handoff = win.handoff          # set when the UI size was changed
        if handoff is None:
            return rc
        teardown(app, win)
        del win, app


if __name__ == "__main__":
    sys.exit(main())
