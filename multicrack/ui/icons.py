"""Small line icons painted in code (no image files needed)."""
from PySide6.QtCore import QPointF, QRectF, Qt
from PySide6.QtGui import QColor, QIcon, QPainter, QPainterPath, QPen, QPixmap


def _pix(size=20):
    pm = QPixmap(size * 2, size * 2)
    pm.setDevicePixelRatio(2.0)
    pm.fill(Qt.transparent)
    return pm


def _painter(pm, color, width=1.7):
    p = QPainter(pm)
    p.setRenderHint(QPainter.Antialiasing)
    pen = QPen(QColor(color), width)
    pen.setCapStyle(Qt.RoundCap)
    pen.setJoinStyle(Qt.RoundJoin)
    p.setPen(pen)
    return p


def play(color, size=16):
    pm = _pix(size)
    p = QPainter(pm)
    p.setRenderHint(QPainter.Antialiasing)
    p.setPen(Qt.NoPen)
    p.setBrush(QColor(color))
    s = size
    path = QPainterPath(QPointF(s * 0.3, s * 0.18))
    path.lineTo(s * 0.82, s * 0.5)
    path.lineTo(s * 0.3, s * 0.82)
    path.closeSubpath()
    p.drawPath(path)
    p.end()
    return QIcon(pm)


def stop(color, size=16):
    pm = _pix(size)
    p = QPainter(pm)
    p.setRenderHint(QPainter.Antialiasing)
    p.setPen(Qt.NoPen)
    p.setBrush(QColor(color))
    p.drawRoundedRect(QRectF(size * 0.25, size * 0.25, size * 0.5, size * 0.5), 1.5, 1.5)
    p.end()
    return QIcon(pm)


def thumb(color, size=20):
    pm = _pix(size)
    p = _painter(pm, color, 1.6)
    s = size / 24.0
    path = QPainterPath(QPointF(7 * s, 10 * s))
    path.lineTo(7 * s, 21 * s)
    path.lineTo(3 * s, 21 * s)
    path.lineTo(3 * s, 10 * s)
    path.closeSubpath()
    p.drawPath(path)
    q = QPainterPath(QPointF(7 * s, 10 * s))
    q.lineTo(11 * s, 2.5 * s)
    q.cubicTo(12.8 * s, 2.5 * s, 14 * s, 3.8 * s, 14 * s, 5.5 * s)
    q.lineTo(14 * s, 9 * s)
    q.lineTo(19.5 * s, 9 * s)
    q.cubicTo(20.8 * s, 9 * s, 21.8 * s, 10.2 * s, 21.5 * s, 11.5 * s)
    q.lineTo(20 * s, 19.3 * s)
    q.cubicTo(19.7 * s, 20.4 * s, 18.9 * s, 21 * s, 17.9 * s, 21 * s)
    q.lineTo(7 * s, 21 * s)
    p.drawPath(q)
    p.end()
    return QIcon(pm)


def moon(color, size=16):
    pm = _pix(size)
    p = _painter(pm, color, 1.5)
    s = size / 24.0
    path = QPainterPath()
    path.addEllipse(QRectF(3 * s, 3 * s, 18 * s, 18 * s))
    cut = QPainterPath()
    cut.addEllipse(QRectF(9 * s, 0 * s, 16 * s, 16 * s))
    p.drawPath(path.subtracted(cut))
    p.end()
    return QIcon(pm)


def sun(color, size=16):
    pm = _pix(size)
    p = _painter(pm, color, 1.5)
    s = size / 24.0
    p.drawEllipse(QRectF(8 * s, 8 * s, 8 * s, 8 * s))
    import math
    for k in range(8):
        a = k * math.pi / 4
        p.drawLine(QPointF(12 * s + math.cos(a) * 7 * s, 12 * s + math.sin(a) * 7 * s),
                   QPointF(12 * s + math.cos(a) * 10 * s, 12 * s + math.sin(a) * 10 * s))
    p.end()
    return QIcon(pm)


def upload(color, size=28):
    pm = _pix(size)
    p = _painter(pm, color, 1.6)
    s = size / 24.0
    p.drawLine(QPointF(12 * s, 15 * s), QPointF(12 * s, 3 * s))
    p.drawLine(QPointF(7 * s, 8 * s), QPointF(12 * s, 3 * s))
    p.drawLine(QPointF(17 * s, 8 * s), QPointF(12 * s, 3 * s))
    path = QPainterPath(QPointF(4 * s, 15 * s))
    path.lineTo(4 * s, 19 * s)
    path.quadTo(4 * s, 21 * s, 6 * s, 21 * s)
    path.lineTo(18 * s, 21 * s)
    path.quadTo(20 * s, 21 * s, 20 * s, 19 * s)
    path.lineTo(20 * s, 15 * s)
    p.drawPath(path)
    p.end()
    return QIcon(pm)


def check(color, size=32):
    pm = _pix(size)
    p = _painter(pm, color, 1.8)
    s = size / 24.0
    p.drawEllipse(QRectF(2 * s, 2 * s, 20 * s, 20 * s))
    path = QPainterPath(QPointF(7 * s, 12.5 * s))
    path.lineTo(10.2 * s, 15.7 * s)
    path.lineTo(17 * s, 9 * s)
    p.drawPath(path)
    p.end()
    return QIcon(pm)


def close(color, size=14):
    pm = _pix(size)
    p = _painter(pm, color, 1.5)
    s = size
    p.drawLine(QPointF(s * 0.28, s * 0.28), QPointF(s * 0.72, s * 0.72))
    p.drawLine(QPointF(s * 0.72, s * 0.28), QPointF(s * 0.28, s * 0.72))
    p.end()
    return QIcon(pm)


def copy(color, size=18):
    pm = _pix(size)
    p = _painter(pm, color, 1.5)
    s = size / 24.0
    p.drawRoundedRect(QRectF(8 * s, 8 * s, 12 * s, 12 * s), 2 * s, 2 * s)
    path = QPainterPath(QPointF(16 * s, 5 * s))
    path.lineTo(16 * s, 4 * s)
    path.lineTo(4 * s, 4 * s)
    path.lineTo(4 * s, 16 * s)
    path.lineTo(5 * s, 16 * s)
    p.drawPath(path)
    p.end()
    return QIcon(pm)


def trash(color, size=18):
    pm = _pix(size)
    p = _painter(pm, color, 1.5)
    s = size / 24.0
    p.drawLine(QPointF(4 * s, 6.5 * s), QPointF(20 * s, 6.5 * s))
    p.drawLine(QPointF(9.5 * s, 6.5 * s), QPointF(10 * s, 3.5 * s))
    p.drawLine(QPointF(10 * s, 3.5 * s), QPointF(14 * s, 3.5 * s))
    p.drawLine(QPointF(14 * s, 3.5 * s), QPointF(14.5 * s, 6.5 * s))
    path = QPainterPath(QPointF(6 * s, 6.5 * s))
    path.lineTo(7 * s, 20.5 * s)
    path.lineTo(17 * s, 20.5 * s)
    path.lineTo(18 * s, 6.5 * s)
    p.drawPath(path)
    p.drawLine(QPointF(10 * s, 10 * s), QPointF(10.3 * s, 17 * s))
    p.drawLine(QPointF(14 * s, 10 * s), QPointF(13.7 * s, 17 * s))
    p.end()
    return QIcon(pm)


def app_icon():
    size = 64
    pm = QPixmap(size, size)
    pm.fill(Qt.transparent)
    p = QPainter(pm)
    p.setRenderHint(QPainter.Antialiasing)
    p.setPen(Qt.NoPen)
    p.setBrush(QColor("#1C2126"))
    p.drawRoundedRect(QRectF(2, 2, 60, 60), 12, 12)
    pen = QPen(QColor("#86D9A0"), 4.5)
    pen.setCapStyle(Qt.RoundCap)
    pen.setJoinStyle(Qt.RoundJoin)
    p.setPen(pen)
    path = QPainterPath(QPointF(10, 32))
    for x, y in ((18, 32), (23, 16), (30, 48), (37, 20), (42, 40), (46, 32), (54, 32)):
        path.lineTo(x, y)
    p.drawPath(path)
    p.end()
    return QIcon(pm)
