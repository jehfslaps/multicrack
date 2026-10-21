"""MultiCrack hardware skin."""
from PySide6.QtWidgets import QApplication

from . import core
from .qss import stylesheet


def apply(mode: str):
    """Switch light/dark: palette, stylesheet and a full repaint."""
    core.load_fonts()
    core.set_mode(mode)
    app = QApplication.instance()
    if app is not None:
        app.setFont(core.font(13))
        app.setStyleSheet(stylesheet())
        from .widgets import refresh_labels
        for w in app.topLevelWidgets():
            refresh_labels(w)
            w.update()
            for c in w.findChildren(object):
                if hasattr(c, "update"):
                    try:
                        c.update()
                    except TypeError:
                        pass
