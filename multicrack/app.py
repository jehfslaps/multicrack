"""Entry point."""
import os
import sys


def main(argv=None):
    argv = list(sys.argv[1:] if argv is None else argv)
    if "--selftest" in argv:
        from .core.selftest import run
        return run(gui="--no-gui" not in argv)
    if sys.platform == "win32":
        try:  # own taskbar icon instead of the Python one
            import ctypes
            ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID("MultiCrack.App")
        except Exception:
            pass
    from PySide6.QtWidgets import QApplication

    from .ui.main_window import MainWindow
    app = QApplication(sys.argv[:1])
    app.setApplicationName("MultiCrack")
    app.setStyle("Fusion")
    win = MainWindow()
    files = [a for a in argv if os.path.exists(a)]
    win.show()
    if files:
        win.add_files(files)
    return app.exec()


if __name__ == "__main__":
    sys.exit(main())
