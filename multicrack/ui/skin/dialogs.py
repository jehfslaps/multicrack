"""Hardware-style dialogs: frameless, bone frame with screws, dark body, over a dimmed window."""
from __future__ import annotations

from PySide6.QtCore import QPoint, QPointF, QRectF, Qt
from PySide6.QtGui import QColor, QPainter
from PySide6.QtWidgets import QDialog, QHBoxLayout, QLabel, QVBoxLayout, QWidget

from . import core as K
from .core import C
from .widgets import HwButton, mono


class Dimmer(QWidget):
    def __init__(self, parent):
        super().__init__(parent)
        self.setAttribute(Qt.WA_TransparentForMouseEvents, False)
        self.setGeometry(parent.rect())

    def paintEvent(self, _e):
        p = QPainter(self)
        p.fillRect(self.rect(), QColor(0, 0, 0, 150))


class HwDialog(QDialog):
    """Bone outer frame + dark module body. Put content in self.body (QVBoxLayout)."""
    FRAME = 16
    TITLE_H = 54

    def __init__(self, parent, title: str, min_size=(560, 260)):
        super().__init__(parent)
        self.setWindowFlags(Qt.Dialog | Qt.FramelessWindowHint)
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.title = title
        self._drag = None
        self.setMinimumSize(*min_size)
        outer = QVBoxLayout(self)
        f = self.FRAME
        outer.setContentsMargins(f + 18, f + self.TITLE_H + 8, f + 18, f + 28)
        outer.setSpacing(12)
        self.body = outer
        self.close_btn = HwButton("", "icon", icon="x", min_h=30)
        self.close_btn.setParent(self)
        self.close_btn.clicked.connect(self.reject)
        self.close_btn.setToolTip("Close (Esc)")

    def resizeEvent(self, e):
        f = self.FRAME
        self.close_btn.setGeometry(self.width() - f - 46, f + 12, 30, 30)
        super().resizeEvent(e)

    def paintEvent(self, _e):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        r = QRectF(self.rect()).adjusted(6, 4, -6, -10)
        K.soft_shadow(p, r, 8, 10, 160, 4)
        frame = K.rrect(r, 8)
        p.fillPath(frame, QColor(K.LIGHT["chassis"]) if K.pal()["name"] == "light" else C("chassis"))
        K.fill_textured(p, frame, K.texture("bone") if K.pal()["name"] == "light" else K.texture("graphite"))
        K.bevel_edges(p, r, 8, C("chassis_hi"), C("chassis_lo"), 1.8)
        K.corner_screws(p, r, 10, 4.6)
        f = self.FRAME - 6
        body = r.adjusted(f + 6, f + 4, -(f + 6), -(f + 6))
        bp = K.rrect(body, 5)
        p.fillPath(bp, C("module"))
        K.fill_textured(p, bp, K.texture("module"))
        K.inner_shadow(p, body, 5, 150, 8)
        K.hairline_frame(p, body, 5, QColor(0, 0, 0, 200), 1.2)
        # title strip
        tr = QRectF(body.left() + 6, body.top() + 6, body.width() - 12, self.TITLE_H - 10)
        K.screw(p, QPointF(tr.left() + 14, tr.center().y()), 4.2)
        K.text(p, QRectF(tr.left() + 32, tr.top(), tr.width() - 90, tr.height()),
               f"( {self.title.upper()} )", K.font(19, 600, 3.0), C("on_dark"))
        p.setPen(QColor(0, 0, 0, 140))
        p.drawLine(QPointF(body.left() + 8, tr.bottom() + 2), QPointF(body.right() - 8, tr.bottom() + 2))
        p.setPen(QColor(255, 255, 255, 16))
        p.drawLine(QPointF(body.left() + 8, tr.bottom() + 3), QPointF(body.right() - 8, tr.bottom() + 3))

    # drag by the title strip
    def mousePressEvent(self, e):
        if e.button() == Qt.LeftButton and e.position().y() < self.FRAME + self.TITLE_H:
            self._drag = e.globalPosition().toPoint() - self.frameGeometry().topLeft()

    def mouseMoveEvent(self, e):
        if self._drag is not None:
            self.move(e.globalPosition().toPoint() - self._drag)

    def mouseReleaseEvent(self, _e):
        self._drag = None

    def exec(self):
        win = self.parentWidget().window() if self.parentWidget() else None
        dim = None
        cw = win.centralWidget() if (win is not None and hasattr(win, "centralWidget")) else None
        if cw is not None:
            dim = Dimmer(cw)
            dim.show()
            dim.raise_()
        if win is not None:
            self.adjustSize()
            g = win.geometry()
            self.move(g.center() - QPoint(self.width() // 2, self.height() // 2))
        try:
            return super().exec()
        finally:
            if dim is not None:
                dim.deleteLater()


class MessageDialog(HwDialog):
    def __init__(self, parent, title, message, buttons):
        super().__init__(parent, title, (600, 250))
        lb = mono(message, "on_dark", 14, 400, 0.2)
        lb.setWordWrap(True)
        lb.setMinimumWidth(520)
        lb.setTextInteractionFlags(Qt.TextSelectableByMouse)
        self.body.addWidget(lb)
        self.body.addStretch(1)
        row = QHBoxLayout()
        row.addStretch(1)
        self.result_key = None
        for key, text, variant in buttons:
            b = HwButton(text, variant, min_h=38, px=12.5)
            b.clicked.connect(lambda _c=False, k=key: self._done(k))
            row.addWidget(b)
        self.body.addLayout(row)

    def _done(self, k):
        self.result_key = k
        self.accept()


def ask(parent, message, yes="Yes", no="No", title="MultiCrack") -> bool:
    d = MessageDialog(parent, title, message, [("no", no, "dark"), ("yes", yes, "red")])
    d.exec()
    return d.result_key == "yes"


def inform(parent, message, title="MultiCrack", button="OK"):
    d = MessageDialog(parent, title, message, [("ok", button, "red")])
    d.exec()


def warn(parent, message, title="Heads up", button="OK"):
    d = MessageDialog(parent, title, message, [("ok", button, "red")])
    d.exec()
