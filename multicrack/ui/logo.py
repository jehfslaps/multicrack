"""Xenakis logo: an X woven from two hyperboloid bands of straight lines (a nod to Xenakis'
ruled-surface glissandi and the Philips Pavilion), in an oscilloscope window on a screwed plate."""
from __future__ import annotations

import math

from PySide6.QtCore import QPointF, QRectF, Qt
from PySide6.QtGui import (QColor, QIcon, QLinearGradient, QPainter, QPainterPath, QPen, QPixmap,
                           QRadialGradient)

RED = QColor("#E8483A")


def paint_mark(p: QPainter, c: QPointF, size: float, color: QColor = RED, lines: int | None = None,
               width: float | None = None, phi_deg: float = 136, radius: float = 0.13,
               reach: float = 0.47):
    """Just the X. `size` is the box it fills."""
    n = lines or (7 if size < 28 else 12 if size < 60 else 16 if size < 160 else 22)
    w = width or max(0.9, size * (0.06 if size < 28 else 0.024 if size < 60 else
                                  0.016 if size < 160 else 0.0075))
    p.save()
    p.setRenderHint(QPainter.Antialiasing)
    p.setPen(QPen(color, w, Qt.SolidLine, Qt.RoundCap))
    phi = math.radians(phi_deg)
    a = size * reach
    R = size * radius
    for dx, dy in ((1, 1), (1, -1)):
        d = (dx / math.sqrt(2), dy / math.sqrt(2))
        q = (-d[1], d[0])
        for k in range(n):
            th = 2 * math.pi * k / n
            r0, r1 = R * math.cos(th), R * math.cos(th + phi)
            p.drawLine(QPointF(c.x() - a * d[0] + r0 * q[0], c.y() - a * d[1] + r0 * q[1]),
                       QPointF(c.x() + a * d[0] + r1 * q[0], c.y() + a * d[1] + r1 * q[1]))
    p.restore()


def _screw(p, c, r):
    p.setPen(Qt.NoPen)
    p.setBrush(QColor(0, 0, 0, 90))
    p.drawEllipse(QPointF(c.x() + r * 0.1, c.y() + r * 0.2), r * 1.25, r * 1.25)
    g = QRadialGradient(QPointF(c.x() - r * 0.35, c.y() - r * 0.45), r * 1.6)
    g.setColorAt(0, QColor("#F2F1EE"))
    g.setColorAt(0.45, QColor("#B7B4AE"))
    g.setColorAt(1, QColor("#5F5D59"))
    p.setBrush(g)
    p.setPen(QPen(QColor(30, 30, 30, 160), max(0.5, r * 0.15)))
    p.drawEllipse(c, r, r)
    # single slot, set at an angle (a cross-head would echo the X mark)
    p.setPen(QPen(QColor(40, 38, 36, 230), max(0.6, r * 0.26), Qt.SolidLine, Qt.RoundCap))
    a = math.radians(-28)
    k = r * 0.62
    p.drawLine(QPointF(c.x() - k * math.cos(a), c.y() - k * math.sin(a)),
               QPointF(c.x() + k * math.cos(a), c.y() + k * math.sin(a)))


def paint_logo(p: QPainter, r: QRectF, plate: bool = True):
    """Full logo tile (plate + window + mark), scaled to r."""
    p.save()
    p.setRenderHint(QPainter.Antialiasing)
    s = min(r.width(), r.height())
    box = QRectF(r.center().x() - s / 2, r.center().y() - s / 2, s, s)
    small = s < 40
    if plate:
        rad = s * 0.2
        body = box.adjusted(s * 0.02, s * 0.02, -s * 0.02, -s * 0.04)
        # shadow
        p.setPen(Qt.NoPen)
        p.setBrush(QColor(0, 0, 0, 70))
        p.drawRoundedRect(body.translated(0, s * 0.02), rad, rad)
        g = QLinearGradient(body.topLeft(), body.bottomRight())
        g.setColorAt(0, QColor("#EFEBE3"))
        g.setColorAt(0.55, QColor("#D8D3C9"))
        g.setColorAt(1, QColor("#AFA799"))
        p.setBrush(g)
        p.setPen(QPen(QColor(30, 26, 22, 200), max(0.8, s * 0.008)))
        p.drawRoundedRect(body, rad, rad)
        if not small:
            p.setPen(QPen(QColor(255, 255, 255, 150), max(0.8, s * 0.006)))
            p.drawLine(QPointF(body.left() + rad, body.top() + s * 0.012),
                       QPointF(body.right() - rad, body.top() + s * 0.012))
            sr = s * 0.026
            ins = s * 0.085
            for x, y in ((body.left() + ins, body.top() + ins), (body.right() - ins, body.top() + ins),
                         (body.left() + ins, body.bottom() - ins), (body.right() - ins, body.bottom() - ins)):
                _screw(p, QPointF(x, y), sr)
        win = body.adjusted(s * (0.13 if not small else 0.1), s * (0.13 if not small else 0.1),
                            -s * (0.13 if not small else 0.1), -s * (0.13 if not small else 0.1))
    else:
        win = box
    wr = s * 0.09
    wg = QLinearGradient(win.topLeft(), win.bottomLeft())
    wg.setColorAt(0, QColor("#0D0F11"))
    wg.setColorAt(1, QColor("#181B1E"))
    p.setPen(QPen(QColor("#000000"), max(0.8, s * 0.01)))
    p.setBrush(wg)
    p.drawRoundedRect(win, wr, wr)
    if not small:
        # faint oscilloscope grid + top glare
        p.save()
        path = QPainterPath()
        path.addRoundedRect(win, wr, wr)
        p.setClipPath(path)
        p.setPen(QPen(QColor(255, 255, 255, 14), max(0.6, s * 0.004)))
        for k in range(1, 4):
            x = win.left() + win.width() * k / 4
            y = win.top() + win.height() * k / 4
            p.drawLine(QPointF(x, win.top()), QPointF(x, win.bottom()))
            p.drawLine(QPointF(win.left(), y), QPointF(win.right(), y))
        gl = QLinearGradient(win.topLeft(), QPointF(win.left(), win.top() + win.height() * 0.5))
        gl.setColorAt(0, QColor(255, 255, 255, 22))
        gl.setColorAt(1, QColor(255, 255, 255, 0))
        p.fillRect(QRectF(win.left(), win.top(), win.width(), win.height() * 0.5), gl)
        p.restore()
    # soft red glow behind the mark
    glow = QRadialGradient(win.center(), win.width() * 0.55)
    glow.setColorAt(0, QColor(232, 72, 58, 55))
    glow.setColorAt(1, QColor(232, 72, 58, 0))
    p.setPen(Qt.NoPen)
    p.setBrush(glow)
    p.drawEllipse(win.center(), win.width() * 0.55, win.height() * 0.55)
    paint_mark(p, win.center(), win.width() * 0.86)
    p.restore()


def logo_pixmap(size: int, plate=True, dpr: float = 1.0) -> QPixmap:
    pm = QPixmap(int(size * dpr), int(size * dpr))
    pm.fill(Qt.transparent)
    pm.setDevicePixelRatio(dpr)
    p = QPainter(pm)
    paint_logo(p, QRectF(0, 0, size, size), plate)
    p.end()
    return pm


def app_icon() -> QIcon:
    ic = QIcon()
    for s in (16, 24, 32, 48, 64, 128, 256):
        ic.addPixmap(logo_pixmap(s))
    return ic
