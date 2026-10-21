"""Hardware-style widgets for the Xenakis skin."""
from __future__ import annotations

import math

from PySide6.QtCore import QPointF, QRectF, QSize, Qt, Signal
from PySide6.QtGui import QColor, QLinearGradient, QPainter, QPen, QRadialGradient
from PySide6.QtWidgets import (QAbstractButton, QAbstractSpinBox, QDoubleSpinBox, QFrame,
                               QHBoxLayout, QLabel, QSizePolicy, QSplitter, QSplitterHandle,
                               QVBoxLayout, QWidget)

from . import core as K
from .core import C


def _dpr(w: QWidget) -> float:
    return w.devicePixelRatioF() if hasattr(w, "devicePixelRatioF") else 1.0


# ===================================================================== surfaces
class Chassis(QWidget):
    """The device body: textured bone (light) or graphite (dark), worn edges, corner screws,
    and decorative schematic wires between modules."""

    def __init__(self, parent=None, screws=True, frame=True):
        super().__init__(parent)
        self.screws = screws
        self.frame = frame
        self.wires = []   # callables -> (list[QPointF], label)

    def add_wire(self, a: QWidget, b: QWidget, frac: float, label: str = ""):
        """Horizontal wire from the right edge of a to the left edge of b at a's height frac."""
        def calc():
            if not (a.isVisible() and b.isVisible()):
                return None
            ra = a.geometry()
            rb = b.geometry()
            pa = a.parentWidget().mapTo(self, ra.topRight()) if a.parentWidget() is not self else ra.topRight()
            pb = b.parentWidget().mapTo(self, rb.topLeft()) if b.parentWidget() is not self else rb.topLeft()
            y = pa.y() + ra.height() * frac
            x0, x1 = pa.x() + 1, pb.x() - 1
            if x1 - x0 < 8:
                return None
            return [QPointF(x0, y), QPointF(x1, y)], label
        self.wires.append(calc)

    def add_bus(self, a: QWidget, widgets: list, fracs: list):
        """A vertical bus in the gap right of `a`, tapping each target widget."""
        def calc():
            if not a.isVisible():
                return None
            ra = a.geometry()
            pa = a.parentWidget().mapTo(self, ra.topRight())
            pts = []
            for w, f in zip(widgets, fracs):
                if not w.isVisible():
                    continue
                rw = w.geometry()
                pw = w.parentWidget().mapTo(self, rw.topLeft())
                pts.append((pa.x(), pw.x(), pw.y() + rw.height() * f))
            if not pts:
                return None
            return ("bus", pts, pa.y() + ra.height() * 0.08, pa.y() + ra.height() * 0.92)
        self.wires.append(calc)

    def paintEvent(self, _e):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        r = QRectF(self.rect())
        p.fillRect(r, C("chassis"))
        K.fill_textured(p, K.rrect(r, 0), K.chassis_texture())
        # worn, darker edges (vignette)
        g = pal_grime()
        for side in range(4):
            depth = 70.0
            if side == 0:
                lg = QLinearGradient(r.topLeft(), QPointF(r.left(), r.top() + depth))
                rect = QRectF(r.left(), r.top(), r.width(), depth)
            elif side == 1:
                lg = QLinearGradient(r.bottomLeft(), QPointF(r.left(), r.bottom() - depth))
                rect = QRectF(r.left(), r.bottom() - depth, r.width(), depth)
            elif side == 2:
                lg = QLinearGradient(r.topLeft(), QPointF(r.left() + depth, r.top()))
                rect = QRectF(r.left(), r.top(), depth, r.height())
            else:
                lg = QLinearGradient(r.topRight(), QPointF(r.right() - depth, r.top()))
                rect = QRectF(r.right() - depth, r.top(), depth, r.height())
            lg.setColorAt(0, QColor(g[0], g[1], g[2], 70))
            lg.setColorAt(1, QColor(g[0], g[1], g[2], 0))
            p.fillRect(rect, lg)
        if self.frame:
            K.bevel_edges(p, r.adjusted(1, 1, -1, -1), 3, C("chassis_hi", 200), C("chassis_lo", 230), 1.5)
        if self.screws:
            K.corner_screws(p, r, 10, 4.8)
        self._paint_wires(p)

    def _paint_wires(self, p: QPainter):
        pen = QPen(C("wire", 210), 1.3)
        lab = K.font(8.5, 500, 0.8)
        for calc in self.wires:
            try:
                res = calc()
            except RuntimeError:
                continue
            if res is None:
                continue
            if res[0] == "bus":
                _k, pts, y0, y1 = res
                xb = (pts[0][0] + pts[0][1]) / 2
                p.setPen(pen)
                ys = [y for _a, _b, y in pts]
                p.drawLine(QPointF(xb, min(ys + [y0])), QPointF(xb, max(ys + [y1])))
                for xa, xw, y in pts:
                    p.setPen(pen)
                    p.drawLine(QPointF(xa + 1, y), QPointF(xw - 1, y))
                    K.node(p, QPointF(xb, y), 2.6, C("wire"), filled=True)
                    K.node(p, QPointF(xw - 3, y), 2.4)
                K.node(p, QPointF(xb, min(ys + [y0])), 3.0)
                K.node(p, QPointF(xb, max(ys + [y1])), 3.0)
                continue
            pts, label = res
            p.setPen(pen)
            for i in range(len(pts) - 1):
                p.drawLine(pts[i], pts[i + 1])
            K.node(p, pts[0], 3.0)
            K.node(p, pts[-1], 3.0)
            if label:
                mid = QPointF((pts[0].x() + pts[-1].x()) / 2, pts[0].y())
                K.text(p, QRectF(mid.x() - 40, mid.y() - 15, 80, 12), label, lab,
                       C("wire", 200), Qt.AlignCenter)


def pal_grime():
    return K.pal()["grime"]


class Module(QFrame):
    """Dark graphite module with screws, an optional title and a red hairline outline."""

    def __init__(self, title: str = "", screws=True, outline=False, margins=(16, 12, 16, 14),
                 parent=None, title_size=15):
        super().__init__(parent)
        self.title = title
        self.screws = screws
        self.outline = outline
        self.title_size = title_size
        self.alert = False
        self.title_h = 34 if title else 0
        self.lay = QVBoxLayout(self)
        l, t, r_, b = margins
        extra = 10 if outline else 0
        self.lay.setContentsMargins(l + extra, t + self.title_h + extra, r_ + extra, b + extra)
        self.lay.setSpacing(10)

    def set_title(self, t):
        self.title = t
        self.update()

    def paintEvent(self, _e):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        r = QRectF(self.rect()).adjusted(3, 2, -3, -5)
        K.soft_shadow(p, r, 5, 6, 90, 2.5)
        path = K.rrect(r, 5)
        p.fillPath(path, C("module"))
        K.fill_textured(p, path, K.texture("module"))
        K.bevel_edges(p, r, 5, C("module_hi"), C("module_lo"), 1.6)
        K.hairline_frame(p, r.adjusted(1.5, 1.5, -1.5, -1.5), 4, QColor(0, 0, 0, 120), 1.0)
        if self.screws:
            K.corner_screws(p, r, 9, 4.3)
        if self.title:
            K.text(p, QRectF(r.left() + 20, r.top() + 8, r.width() - 60, 26),
                   self.title, K.font(self.title_size, 600, 2.2), C("on_dark"))
        if self.outline:
            o = QRectF(r.left() + 12, r.top() + self.title_h + 6, r.width() - 24,
                       r.height() - self.title_h - 18)
            K.hairline_frame(p, o, 5, C("warn") if self.alert else C("outline", 200), 1.1)


class Outline(QFrame):
    """Red hairline rounded frame (used around tables inside modules)."""

    def __init__(self, parent=None, color="outline", margins=(1, 1, 1, 1)):
        super().__init__(parent)
        self.color = color
        self.lay = QVBoxLayout(self)
        self.lay.setContentsMargins(*margins)
        self.lay.setSpacing(0)

    def paintEvent(self, _e):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        K.hairline_frame(p, QRectF(self.rect()), 5, C(self.color, 210), 1.1)


class Plate(QFrame):
    """Raised plate in the chassis material (bone or graphite) with screws."""

    def __init__(self, parent=None, screws=True, margins=(18, 8, 18, 8)):
        super().__init__(parent)
        self.screws = screws
        self.lay = QHBoxLayout(self)
        self.lay.setContentsMargins(*margins)
        self.lay.setSpacing(12)

    def paintEvent(self, _e):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        r = QRectF(self.rect()).adjusted(2, 2, -2, -4)
        K.soft_shadow(p, r, 5, 5, 70, 2)
        path = K.rrect(r, 5)
        p.fillPath(path, C("plate"))
        K.fill_textured(p, path, K.chassis_texture(), tint=QColor(255, 255, 255, 30)
                        if K.pal()["name"] == "light" else QColor(255, 255, 255, 8))
        K.bevel_edges(p, r, 5, C("chassis_hi"), C("chassis_lo"), 1.6)
        K.hairline_frame(p, r.adjusted(0.5, 0.5, -0.5, -0.5), 5, QColor(0, 0, 0, 90), 0.8)
        if self.screws:
            K.corner_screws(p, r, 8, 3.8)


class Recess(QFrame):
    """Dark recessed housing cut into the chassis."""

    def __init__(self, parent=None, screws=False, margins=(8, 6, 8, 6), radius=5):
        super().__init__(parent)
        self.screws = screws
        self.radius = radius
        self.lay = QHBoxLayout(self)
        self.lay.setContentsMargins(*margins)
        self.lay.setSpacing(6)

    def paintEvent(self, _e):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        r = QRectF(self.rect()).adjusted(1, 1, -1, -1)
        path = K.rrect(r, self.radius)
        p.fillPath(path, QColor("#141517"))
        K.fill_textured(p, path, K.texture("module"), tint=QColor(0, 0, 0, 90))
        K.inner_shadow(p, r, self.radius, 170, 8)
        K.bevel_edges(p, r, self.radius, C("chassis_lo", 230), C("chassis_hi", 230), 1.4)
        if self.screws:
            K.corner_screws(p, r, 8, 3.6)


class Tile(QFrame):
    """Control tile inside a module (slightly raised, thin border)."""

    def __init__(self, parent=None, margins=(12, 8, 12, 8), layout="h", alert=False):
        super().__init__(parent)
        self.alert = alert
        self.lay = QHBoxLayout(self) if layout == "h" else QVBoxLayout(self)
        self.lay.setContentsMargins(*margins)
        self.lay.setSpacing(8)

    def set_alert(self, on):
        self.alert = on
        self.update()

    def paintEvent(self, _e):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        r = QRectF(self.rect()).adjusted(0.5, 0.5, -0.5, -0.5)
        g = QLinearGradient(r.topLeft(), r.bottomLeft())
        g.setColorAt(0, QColor("#2A2C30"))
        g.setColorAt(1, QColor("#222326"))
        p.setBrush(g)
        p.setPen(QPen(C("warn") if self.alert else QColor("#3C3F44"), 1.1 if self.alert else 1.0))
        p.drawRoundedRect(r, 4, 4)
        p.setPen(QPen(QColor(255, 255, 255, 14), 1))
        p.drawLine(QPointF(r.left() + 4, r.top() + 1.2), QPointF(r.right() - 4, r.top() + 1.2))


# ====================================================================== labels
def cap(text: str, color_key="on_dark_muted", px=11, weight=500, spacing=1.6) -> QLabel:
    lb = QLabel(text)
    lb.setFont(K.font(px, weight, spacing, caps=True))
    lb.setProperty("skincolor", color_key)
    lb.setStyleSheet(f"color: {K.pal()[color_key]}; background: transparent;")
    return lb


def mono(text: str = "", color_key="on_dark", px=13, weight=400, spacing=0.3) -> QLabel:
    lb = QLabel(text)
    lb.setFont(K.font(px, weight, spacing))
    lb.setProperty("skincolor", color_key)
    lb.setStyleSheet(f"color: {K.pal()[color_key]}; background: transparent;")
    return lb


def recolor(lb: QLabel, color_key: str):
    lb.setProperty("skincolor", color_key)
    lb.setStyleSheet(f"color: {K.pal()[color_key]}; background: transparent;")


def refresh_labels(root: QWidget):
    """Re-apply palette colors to labels after a light/dark switch."""
    for lb in root.findChildren(QLabel):
        key = lb.property("skincolor")
        if key:
            lb.setStyleSheet(f"color: {K.pal()[key]}; background: transparent;")


# ===================================================================== buttons
class HwButton(QAbstractButton):
    """Painted hardware button.
    variants: key (cream keycap), dark (outlined), red (primary), seg (cream; red when checked),
    danger (red-outlined icon square), icon (dark icon square), round (round play button)."""

    def __init__(self, text="", variant="dark", icon=None, led=False, parent=None,
                 checkable=False, px=12, min_h=34, icon_size=16):
        super().__init__(parent)
        self.setText(text)
        self.variant = variant
        self.icon_name = icon
        self.led = led
        self.px = px
        self.min_h = min_h
        self.icon_size = icon_size
        self._floor_w = 0
        self.setCheckable(checkable)
        self.setCursor(Qt.PointingHandCursor)
        self.setFocusPolicy(Qt.NoFocus)
        self._hover = False
        self.setAttribute(Qt.WA_Hover)
        if variant in ("danger", "icon", "round"):
            self.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)

    def _font(self):
        w = 600 if self.variant in ("key", "red", "seg") else 500
        return K.font(self.px, w, 1.4 if self.variant != "dark" or self.px >= 12 else 1.0, caps=True)

    def sizeHint(self):
        if self.variant in ("danger", "icon"):
            return QSize(self.min_h, self.min_h)
        if self.variant == "round":
            return QSize(self.min_h, self.min_h)
        fm = self.fontMetrics() if False else None
        from PySide6.QtGui import QFontMetricsF
        fmf = QFontMetricsF(self._font())
        w = fmf.horizontalAdvance(self.text().upper()) + 34
        if self.icon_name:
            w += self.icon_size + 10
        if self.led:
            w += 26
        return QSize(int(max(w, self._floor_w)), self.min_h)

    def minimumSizeHint(self):
        return self.sizeHint()

    def width_for(self, text):
        """Width this button needs to show `text`."""
        from PySide6.QtGui import QFontMetricsF
        w = QFontMetricsF(self._font()).horizontalAdvance(text.upper()) + 34
        if self.icon_name:
            w += self.icon_size + 10
        if self.led:
            w += 26
        return int(w + 1)

    def setMinimumWidth(self, w):
        """A floor for the width; the label always gets at least the room it needs."""
        self._floor_w = int(w)
        self.updateGeometry()

    def setText(self, text):
        super().setText(text)
        self.updateGeometry()

    def enterEvent(self, e):
        self._hover = True
        self.update()
        super().enterEvent(e)

    def leaveEvent(self, e):
        self._hover = False
        self.update()
        super().leaveEvent(e)

    def paintEvent(self, _e):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        r = QRectF(self.rect()).adjusted(1.5, 1.5, -1.5, -2.5)
        down = self.isDown()
        en = self.isEnabled()
        v = self.variant
        checked = self.isChecked()
        if down:
            r.translate(0, 1)
        txt_color = C("on_dark")
        icon_color = C("on_dark")
        if v in ("key", "seg") and not (v == "seg" and checked):
            if en:
                K.soft_shadow(p, r, 4, 3 if down else 5, 90, 0.8 if down else 2.2)
                g = QLinearGradient(r.topLeft(), r.bottomLeft())
                top = QColor(K.pal()["key_hi"])
                mid = QColor(K.pal()["key"])
                bot = QColor(K.pal()["key_lo"])
                if self._hover:
                    top, mid = top.lighter(103), mid.lighter(104)
                if down:
                    top, mid = mid.darker(104), mid.darker(106)
                g.setColorAt(0, top)
                g.setColorAt(0.55, mid)
                g.setColorAt(1, bot)
                p.setBrush(g)
                p.setPen(QPen(QColor(20, 18, 16, 200), 1))
                p.drawRoundedRect(r, 3.5, 3.5)
                p.setPen(QPen(QColor(255, 255, 255, 170), 1))
                p.drawLine(QPointF(r.left() + 3, r.top() + 1.4), QPointF(r.right() - 3, r.top() + 1.4))
                p.setPen(QPen(QColor(0, 0, 0, 50), 1))
                p.drawLine(QPointF(r.left() + 3, r.bottom() - 1.4), QPointF(r.right() - 3, r.bottom() - 1.4))
                txt_color = icon_color = C("key_text")
            else:
                p.setBrush(QColor("#3A3B3E"))
                p.setPen(QPen(QColor("#4A4C50"), 1))
                p.drawRoundedRect(r, 3.5, 3.5)
                txt_color = icon_color = QColor("#7C7A75")
        elif v == "seg" and checked or v == "red":
            if en:
                gl = QRadialGradient(r.center(), r.width() * 0.7)
                gl.setColorAt(0, QColor(255, 70, 50, 70 if (v == "seg" or self._hover) else 40))
                gl.setColorAt(1, QColor(255, 70, 50, 0))
                p.setPen(Qt.NoPen)
                p.setBrush(gl)
                p.drawRoundedRect(r.adjusted(-6, -6, 6, 6), 9, 9)
                K.soft_shadow(p, r, 4, 4, 100, 1.5)
                g = QLinearGradient(r.topLeft(), r.bottomLeft())
                hi = QColor(K.pal()["red_hi"])
                mid = QColor(K.pal()["red"])
                lo = QColor(K.pal()["red_lo"])
                if self._hover:
                    hi, mid = hi.lighter(108), mid.lighter(108)
                if down:
                    hi, mid = mid, mid.darker(110)
                g.setColorAt(0, hi)
                g.setColorAt(0.6, mid)
                g.setColorAt(1, lo)
                p.setBrush(g)
                p.setPen(QPen(QColor("#FF7A5E") if v == "seg" else QColor(40, 10, 6, 220), 1.2))
                p.drawRoundedRect(r, 3.5, 3.5)
                p.setPen(QPen(QColor(255, 220, 200, 110), 1))
                p.drawLine(QPointF(r.left() + 3, r.top() + 1.5), QPointF(r.right() - 3, r.top() + 1.5))
                txt_color = icon_color = QColor("#FFF3EC")
            else:
                p.setBrush(QColor("#3A3B3E"))
                p.setPen(QPen(QColor("#4C4E52"), 1))
                p.drawRoundedRect(r, 3.5, 3.5)
                txt_color = icon_color = QColor("#85827C")
        elif v == "danger":
            col = C("warn") if en else QColor("#5A5A5A")
            p.setBrush(QColor(232, 100, 78, 40 if self._hover else 14) if en else Qt.NoBrush)
            p.setPen(QPen(col, 1.2))
            p.drawRoundedRect(r, 3, 3)
            K.draw_icon(p, "x", r.adjusted(7, 7, -7, -7), col, 1.8)
            return
        elif v == "round":
            c = r.center()
            rad = min(r.width(), r.height()) / 2
            K.soft_shadow(p, QRectF(c.x() - rad, c.y() - rad, 2 * rad, 2 * rad), rad, 3, 80, 1.5)
            g = QRadialGradient(QPointF(c.x(), c.y() - rad * 0.5), rad * 1.6)
            g.setColorAt(0, QColor("#3A3C40") if not self._hover else QColor("#46494E"))
            g.setColorAt(1, QColor("#121314"))
            p.setBrush(g)
            p.setPen(QPen(QColor("#C9C4BA") if self._hover else QColor("#8E8A83"), 1.5))
            p.drawEllipse(c, rad - 1, rad - 1)
            K.draw_icon(p, self.icon_name or "play",
                        QRectF(c.x() - rad * 0.55 + 1, c.y() - rad * 0.55, rad * 1.1, rad * 1.1),
                        QColor("#F3EFE7"))
            return
        else:   # dark / icon
            g = QLinearGradient(r.topLeft(), r.bottomLeft())
            g.setColorAt(0, QColor("#24262A") if not self._hover else QColor("#2C2F33"))
            g.setColorAt(1, QColor("#17181A"))
            if down:
                g.setColorAt(0, QColor("#141516"))
            p.setBrush(g)
            border = QColor("#8A867F") if en else QColor("#45474B")
            if self._hover and en:
                border = QColor("#D9D4CA")
            if checked:
                border = C("red_hi")
            p.setPen(QPen(border, 1.1))
            p.drawRoundedRect(r, 3.5, 3.5)
            txt_color = icon_color = C("on_dark") if en else QColor("#6D6A65")
            if v == "icon":
                K.draw_icon(p, self.icon_name, r.adjusted(8, 8, -8, -8), icon_color, 1.5)
                return
        # contents: [led] [icon] TEXT
        f = self._font()
        p.setFont(f)
        fm = p.fontMetrics()
        label = self.text().upper()
        tw = fm.horizontalAdvance(label)
        iw = (self.icon_size + 9) if self.icon_name else 0
        lw = 24 if self.led else 0
        total = lw + iw + tw
        x = r.center().x() - total / 2
        if self.led:
            K.led(p, QPointF(x + 7, r.center().y()), 6.0, K.pal()["led_red"], en)
            x += lw
        if self.icon_name:
            K.draw_icon(p, self.icon_name, QRectF(x, r.center().y() - self.icon_size / 2,
                                                  self.icon_size, self.icon_size), icon_color, 1.7)
            x += iw
        p.setPen(txt_color)
        p.drawText(QRectF(x, r.top(), tw + 4, r.height()), int(Qt.AlignLeft | Qt.AlignVCenter), label)


class LedToggle(QAbstractButton):
    """Latching switch tile: LED + LABEL + ON/OFF (+ optional icon)."""

    def __init__(self, label: str, color="green", icon=None, state_words=("ON", "OFF"),
                 parent=None, min_h=40, show_state=True):
        super().__init__(parent)
        self.label = label
        self.color = color
        self.icon_name = icon
        self.words = state_words
        self.show_state = show_state
        self.min_h = min_h
        self.setCheckable(True)
        self.setCursor(Qt.PointingHandCursor)
        self.setFocusPolicy(Qt.NoFocus)
        self.setAttribute(Qt.WA_Hover)
        self._hover = False

    def sizeHint(self):
        from PySide6.QtGui import QFontMetricsF
        fm = QFontMetricsF(K.font(12, 600, 1.4))
        w = 30 + fm.horizontalAdvance((self.label + "  " + (self.words[0] if self.show_state else "")).upper()) + 22
        if self.icon_name:
            w += 26
        return QSize(int(w), self.min_h)

    def minimumSizeHint(self):
        return self.sizeHint()

    def enterEvent(self, e):
        self._hover = True
        self.update()

    def leaveEvent(self, e):
        self._hover = False
        self.update()

    def paintEvent(self, _e):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        r = QRectF(self.rect()).adjusted(1, 1, -1, -1)
        en = self.isEnabled()
        on = self.isChecked() and en
        g = QLinearGradient(r.topLeft(), r.bottomLeft())
        g.setColorAt(0, QColor("#2C2E32") if self._hover and en else QColor("#26282B"))
        g.setColorAt(1, QColor("#1C1D20"))
        p.setBrush(g)
        p.setPen(QPen(QColor("#4A4D52") if en else QColor("#36383C"), 1))
        p.drawRoundedRect(r, 4, 4)
        col = K.pal()["led_green"] if self.color == "green" else K.pal()["led_red"]
        K.led(p, QPointF(r.left() + 17, r.center().y()), 5.2, col, on)
        x = r.left() + 32
        if self.icon_name:
            K.draw_icon(p, self.icon_name, QRectF(x, r.center().y() - 9, 18, 18),
                        QColor(col) if on else C("on_dark_muted"), 1.7)
            x += 26
        f = K.font(12, 600, 1.4, caps=True)
        p.setFont(f)
        fm = p.fontMetrics()
        p.setPen(C("on_dark") if en else QColor("#6D6A65"))
        p.drawText(QRectF(x, r.top(), r.width(), r.height()), int(Qt.AlignLeft | Qt.AlignVCenter),
                   self.label.upper())
        if self.show_state:
            x2 = x + fm.horizontalAdvance(self.label.upper()) + 10
            p.setPen(QColor(col) if on else C("on_dark_dim"))
            p.drawText(QRectF(x2, r.top(), r.width(), r.height()), int(Qt.AlignLeft | Qt.AlignVCenter),
                       self.words[0] if self.isChecked() else self.words[1])


class StepSelector(QWidget):
    """Three latching mode buttons with LEDs in a recessed housing."""
    clicked = Signal(int)

    def __init__(self, names, parent=None):
        super().__init__(parent)
        self.names = names
        self.current = 0
        self.enabled = [True] * len(names)
        self._hover = -1
        self.setMouseTracking(True)
        self.setCursor(Qt.PointingHandCursor)
        self.setMinimumHeight(48)
        from PySide6.QtGui import QFontMetricsF
        fm = QFontMetricsF(K.font(12, 600, 1.6))
        cell = max(fm.horizontalAdvance(n.upper()) for n in names) + 34 + 18
        self.setMinimumWidth(int(cell * len(names) + 4 * len(names) + 14))

    def set_current(self, i):
        self.current = i
        self.update()

    def set_enabled(self, i, on):
        self.enabled[i] = on
        self.update()

    def _cells(self):
        r = QRectF(self.rect()).adjusted(7, 7, -7, -7)
        w = r.width() / len(self.names)
        return [QRectF(r.left() + i * w + 2, r.top(), w - 4, r.height()) for i in range(len(self.names))]

    def mouseMoveEvent(self, e):
        h = next((i for i, c in enumerate(self._cells()) if c.contains(e.position())), -1)
        if h != self._hover:
            self._hover = h
            self.update()

    def leaveEvent(self, e):
        self._hover = -1
        self.update()

    def mousePressEvent(self, e):
        for i, c in enumerate(self._cells()):
            if c.contains(e.position()) and self.enabled[i]:
                self.clicked.emit(i)

    def paintEvent(self, _e):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        r = QRectF(self.rect()).adjusted(1, 1, -1, -1)
        path = K.rrect(r, 5)
        p.fillPath(path, QColor("#141517"))
        K.fill_textured(p, path, K.texture("module"), tint=QColor(0, 0, 0, 100))
        K.inner_shadow(p, r, 5, 170, 8)
        K.bevel_edges(p, r, 5, C("chassis_lo", 230), C("chassis_hi", 230), 1.4)
        for i, c in enumerate(self._cells()):
            active = i == self.current
            en = self.enabled[i]
            g = QLinearGradient(c.topLeft(), c.bottomLeft())
            base = QColor("#2A2C30") if (self._hover == i and en) else QColor("#232528")
            g.setColorAt(0, base.lighter(112) if not active else QColor("#1C1D20"))
            g.setColorAt(1, QColor("#17181A"))
            p.setBrush(g)
            p.setPen(QPen(QColor("#3F4247"), 1))
            p.drawRoundedRect(c, 3, 3)
            if not active:
                p.setPen(QPen(QColor(255, 255, 255, 18), 1))
                p.drawLine(QPointF(c.left() + 3, c.top() + 1.3), QPointF(c.right() - 3, c.top() + 1.3))
            K.led(p, QPointF(c.left() + 18, c.center().y()), 5.5, K.pal()["led_red"], active)
            num, _, name = self.names[i].partition(" ")
            f = K.font(12, 600 if active else 500, 1.6)
            p.setFont(f)
            col = C("on_dark") if active else (C("on_dark_muted") if en else C("on_dark_dim"))
            p.setPen(C("led_red") if active else col)
            fm = p.fontMetrics()
            p.drawText(QRectF(c.left() + 34, c.top(), 30, c.height()), int(Qt.AlignLeft | Qt.AlignVCenter), num)
            p.setPen(col)
            p.drawText(QRectF(c.left() + 34 + fm.horizontalAdvance(num) + 8, c.top(), c.width(), c.height()),
                       int(Qt.AlignLeft | Qt.AlignVCenter), name.upper())


class LeverSwitch(QAbstractButton):
    """Bat-handle toggle switch. Unchecked = up (LIGHT), checked = down (DARK)."""

    def __init__(self, up="LIGHT", down="DARK", parent=None):
        super().__init__(parent)
        self.up, self.down = up, down
        self.setCheckable(True)
        self.setCursor(Qt.PointingHandCursor)
        self.setFocusPolicy(Qt.NoFocus)
        self.setFixedSize(132, 52)

    def paintEvent(self, _e):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        r = QRectF(self.rect()).adjusted(1, 1, -1, -1)
        path = K.rrect(r, 5)
        p.fillPath(path, QColor("#141517"))
        K.fill_textured(p, path, K.texture("module"), tint=QColor(0, 0, 0, 100))
        K.inner_shadow(p, r, 5, 160, 8)
        K.bevel_edges(p, r, 5, C("chassis_lo", 230), C("chassis_hi", 230), 1.4)
        c = QPointF(r.left() + 30, r.center().y())
        # mounting nut
        nut = QRadialGradient(QPointF(c.x() - 3, c.y() - 4), 16)
        nut.setColorAt(0, QColor("#E9E7E2"))
        nut.setColorAt(0.6, QColor("#8E8B85"))
        nut.setColorAt(1, QColor("#3E3D3A"))
        p.setBrush(nut)
        p.setPen(QPen(QColor(0, 0, 0, 160), 0.8))
        p.drawEllipse(c, 11, 11)
        p.setBrush(QColor("#2A2A2A"))
        p.drawEllipse(c, 4.5, 4.5)
        # bat handle
        down = self.isChecked()
        tip = QPointF(c.x() + 2, c.y() + (15 if down else -15))
        p.setPen(QPen(QColor(0, 0, 0, 90), 6.5, Qt.SolidLine, Qt.RoundCap))
        p.drawLine(QPointF(c.x() + 1, c.y() + 1.5), QPointF(tip.x() + 1, tip.y() + 1.5))
        lg = QLinearGradient(QPointF(c.x() - 3, 0), QPointF(c.x() + 4, 0))
        lg.setColorAt(0, QColor("#7A7874"))
        lg.setColorAt(0.4, QColor("#F4F2EE"))
        lg.setColorAt(1, QColor("#8E8B86"))
        p.setPen(QPen(lg, 5.2, Qt.SolidLine, Qt.RoundCap))
        p.drawLine(c, tip)
        tg = QRadialGradient(QPointF(tip.x() - 1.5, tip.y() - 1.5), 6)
        tg.setColorAt(0, QColor("#FFFFFF"))
        tg.setColorAt(1, QColor("#9C9993"))
        p.setPen(QPen(QColor(0, 0, 0, 120), 0.6))
        p.setBrush(tg)
        p.drawEllipse(tip, 4.3, 4.3)
        f = K.font(11.5, 600, 1.6)
        K.text(p, QRectF(r.left() + 52, r.top() + 4, 80, r.height() / 2 - 4), self.up, f,
               C("on_dark") if not down else C("on_dark_dim"))
        K.text(p, QRectF(r.left() + 52, r.center().y(), 80, r.height() / 2 - 4), self.down, f,
               C("on_dark") if down else C("on_dark_dim"))


class Lcd(QWidget):
    """Dark glass readout: small caption + big value."""

    def __init__(self, caption="", value="", parent=None, value_px=20, min_w=190):
        super().__init__(parent)
        self.caption = caption
        self.value = value
        self.value_px = value_px
        self.setMinimumWidth(min_w)
        self.setMinimumHeight(30)

    def set(self, caption=None, value=None):
        if caption is not None:
            self.caption = caption
        if value is not None:
            self.value = value
        self.update()

    def paintEvent(self, _e):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        r = QRectF(self.rect()).adjusted(1, 1, -1, -1)
        path = K.rrect(r, 5)
        g = QLinearGradient(r.topLeft(), r.bottomLeft())
        g.setColorAt(0, QColor("#0E0F10"))
        g.setColorAt(1, QColor("#16181A"))
        p.fillPath(path, g)
        K.inner_shadow(p, r, 5, 200, 9)
        K.bevel_edges(p, r, 5, C("chassis_lo", 230), C("chassis_hi", 230), 1.4)
        p.save()
        p.setClipPath(path)
        p.setPen(QPen(QColor(255, 255, 255, 7), 1))
        y = r.top() + 2
        while y < r.bottom():
            p.drawLine(QPointF(r.left(), y), QPointF(r.right(), y))
            y += 3
        hl = QLinearGradient(r.topLeft(), QPointF(r.left(), r.top() + r.height() * 0.5))
        hl.setColorAt(0, QColor(255, 255, 255, 14))
        hl.setColorAt(1, QColor(255, 255, 255, 0))
        p.fillRect(QRectF(r.left(), r.top(), r.width(), r.height() * 0.5), hl)
        p.restore()
        inner = r.adjusted(16, 4, -14, -4)
        if self.caption:
            K.text(p, QRectF(inner.left(), inner.top() + 2, inner.width(), 15), self.caption.upper(),
                   K.font(10.5, 500, 1.8), C("on_dark_muted"), elide=True)
            K.text(p, QRectF(inner.left(), inner.top() + 16, inner.width(), inner.height() - 16),
                   self.value, K.font(self.value_px, 500, 1.4), C("glass_text"), elide=True)
        else:
            K.text(p, inner, self.value, K.font(self.value_px, 500, 1.4), C("glass_text"), elide=True)


class Knob(QWidget):
    valueChanged = Signal(float)
    released = Signal()

    def __init__(self, lo=0.0, hi=1.0, value=0.0, default=None, step=0.1, size=40, curve=1.0,
                 parent=None, pad=16):
        super().__init__(parent)
        self.lo, self.hi = float(lo), float(hi)
        self._v = float(value)
        self.default = float(value if default is None else default)
        self.step = step
        self.size_ = size
        self.curve = curve           # >1 gives finer control near lo
        self._drag = None
        self.setFixedSize(size + pad, size + pad)
        self.setCursor(Qt.SizeVerCursor)
        self.setToolTip("Drag up/down (Shift = fine), scroll, double-click to reset")

    def value(self):
        return self._v

    def _frac(self, v=None):
        v = self._v if v is None else v
        t = (v - self.lo) / ((self.hi - self.lo) or 1)
        return max(0.0, min(1.0, t)) ** (1 / self.curve)

    def _from_frac(self, f):
        f = max(0.0, min(1.0, f))
        return self.lo + (self.hi - self.lo) * f ** self.curve

    def setValue(self, v, emit=False):
        v = max(min(self.lo, self.hi), min(max(self.lo, self.hi), float(v)))
        if self.step:
            v = round(v / self.step) * self.step
        if abs(v - self._v) < 1e-9:
            return
        self._v = v
        self.update()
        if emit:
            self.valueChanged.emit(v)

    def mousePressEvent(self, e):
        self._drag = (e.position().y(), self._frac())

    def mouseMoveEvent(self, e):
        if self._drag is None:
            return
        y0, f0 = self._drag
        sens = 600.0 if e.modifiers() & Qt.ShiftModifier else 160.0
        self.setValue(self._from_frac(f0 + (y0 - e.position().y()) / sens), emit=True)

    def mouseReleaseEvent(self, _e):
        if self._drag is not None:
            self._drag = None
            self.released.emit()

    def mouseDoubleClickEvent(self, _e):
        self.setValue(self.default, emit=True)
        self.released.emit()

    def wheelEvent(self, e):
        d = 1 if e.angleDelta().y() > 0 else -1
        f = self._frac() + d * (0.01 if e.modifiers() & Qt.ShiftModifier else 0.04)
        self.setValue(self._from_frac(f), emit=True)
        self.released.emit()

    def paintEvent(self, _e):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        c = QPointF(self.width() / 2, self.height() / 2)
        K.draw_knob(p, c, self.size_, self._frac(), _dpr(self))


class LcdSpin(QDoubleSpinBox):
    """Small LCD number box you can type into."""

    def __init__(self, lo, hi, suffix, decimals=1, step=1.0, width=86):
        super().__init__()
        self.setRange(lo, hi)
        self.setDecimals(decimals)
        self.setSuffix(suffix)
        self.setSingleStep(step)
        self.setButtonSymbols(QAbstractSpinBox.NoButtons)
        self.setAlignment(Qt.AlignCenter)
        self.setKeyboardTracking(False)
        self.setObjectName("lcdbox")
        self.setFixedWidth(width)
        self.setFixedHeight(32)
        self.setFocusPolicy(Qt.ClickFocus)


class KnobTile(Tile):
    """LABEL  (knob)  [value box] — knob and box stay in sync."""
    valueChanged = Signal(float)
    released = Signal()

    def __init__(self, label, lo, hi, suffix, default, step=1.0, decimals=1, curve=1.0,
                 tip=""):
        super().__init__(margins=(14, 0, 10, 0))
        self.setFixedHeight(K.H_ROW)
        self.title = cap(label, "on_dark", 11.5, 600, 1.6)
        self.lay.addWidget(self.title)
        self.lay.addStretch(1)
        self.knob = Knob(lo, hi, default, default, step=step / (10 ** 0), size=32, curve=curve,
                         pad=14)
        self.box = LcdSpin(lo, hi, suffix, decimals, step)
        self.box.setFixedHeight(30)
        self.lay.addWidget(self.knob)
        self.lay.addWidget(self.box)
        if tip:
            self.setToolTip(tip)
        self._sync = False
        self.knob.valueChanged.connect(self._from_knob)
        self.knob.released.connect(self.released.emit)
        self.box.valueChanged.connect(self._from_box)

    def set_compact(self, on):
        self.title.setFont(K.font(10.5 if on else 11.5, 600, 1.0 if on else 1.6, caps=True))
        self.box.setFixedWidth(70 if on else 84)
        self.lay.setSpacing(4 if on else 8)
        self.lay.setContentsMargins(10 if on else 14, 0, 6 if on else 10, 0)

    def _from_knob(self, v):
        if self._sync:
            return
        self._sync = True
        self.box.setValue(v)
        self._sync = False
        self.valueChanged.emit(v)

    def _from_box(self, v):
        if self._sync:
            return
        self._sync = True
        self.knob.setValue(v)
        self._sync = False
        self.valueChanged.emit(v)
        self.released.emit()

    def value(self):
        return self.box.value()

    def setValue(self, v):
        self._sync = True
        self.knob.setValue(v)
        self.box.setValue(v)
        self._sync = False


class LedMeter(QWidget):
    """Segment LED bar (approval progress)."""

    def __init__(self, segments=26, parent=None):
        super().__init__(parent)
        self.segments = segments
        self.frac = 0.0
        self.setMinimumSize(240, 30)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)

    def set(self, frac):
        self.frac = max(0.0, min(1.0, frac))
        self.update()

    def paintEvent(self, _e):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        r = QRectF(self.rect()).adjusted(1, 1, -1, -1)
        path = K.rrect(r, 3)
        p.fillPath(path, QColor("#0D0E0F"))
        K.inner_shadow(p, r, 3, 200, 6)
        p.setPen(QPen(QColor("#3A3D42"), 1))
        p.setBrush(Qt.NoBrush)
        p.drawRoundedRect(r, 3, 3)
        inner = r.adjusted(6, 6, -6, -6)
        n = self.segments
        gap = 2.5
        w = (inner.width() - gap * (n - 1)) / n
        lit = int(round(self.frac * n)) if self.frac < 1 else n
        on = QColor(K.pal()["led_green"])
        for i in range(n):
            seg = QRectF(inner.left() + i * (w + gap), inner.top(), w, inner.height())
            if i < lit:
                gl = QColor(on)
                gl.setAlpha(60)
                p.setPen(Qt.NoPen)
                p.setBrush(gl)
                p.drawRoundedRect(seg.adjusted(-1.5, -1.5, 1.5, 1.5), 2, 2)
                g = QLinearGradient(seg.topLeft(), seg.bottomLeft())
                g.setColorAt(0, on.lighter(140))
                g.setColorAt(1, on.darker(110))
                p.setBrush(g)
            else:
                p.setPen(Qt.NoPen)
                p.setBrush(QColor(40, 70, 50, 120))
            p.drawRoundedRect(seg, 1.5, 1.5)


class Trough(QWidget):
    """Progress trough with a percentage readout."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.v, self.n = 0, 100
        self.setMinimumHeight(22)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)

    def set(self, v, n):
        self.v, self.n = v, max(1, n)
        self.update()

    def paintEvent(self, _e):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        r = QRectF(self.rect()).adjusted(1, 1, -58, -1)
        r.setHeight(14)
        r.moveTop((self.height() - 14) / 2)
        p.fillPath(K.rrect(r, 7), QColor("#16171A"))
        K.inner_shadow(p, r, 7, 200, 6)
        p.setPen(QPen(C("chassis_lo"), 1))
        p.setBrush(Qt.NoBrush)
        p.drawRoundedRect(r, 7, 7)
        frac = max(0.0, min(1.0, self.v / self.n))
        if frac > 0:
            fr = QRectF(r.left() + 2, r.top() + 2, (r.width() - 4) * frac, r.height() - 4)
            g = QLinearGradient(fr.topLeft(), fr.bottomLeft())
            g.setColorAt(0, C("red_hi"))
            g.setColorAt(1, C("red_lo"))
            p.fillPath(K.rrect(fr, 5), g)
        K.text(p, QRectF(r.right() + 10, 0, 48, self.height()), f"{int(round(frac * 100))}%",
               K.font(12.5, 500, 1), C("chassis_text"))


class DropBay(QFrame):
    dropped = Signal(list)

    def __init__(self, text="DROP STEMS OR A WHOLE STEM FOLDER HERE", parent=None):
        super().__init__(parent)
        self.label = text
        self.hover = False
        self.setAcceptDrops(True)
        self.setMinimumHeight(118)
        self.setCursor(Qt.PointingHandCursor)

    def dragEnterEvent(self, e):
        if e.mimeData().hasUrls():
            e.acceptProposedAction()
            self.hover = True
            self.update()

    def dragLeaveEvent(self, _e):
        self.hover = False
        self.update()

    def dropEvent(self, e):
        self.hover = False
        self.update()
        paths = [u.toLocalFile() for u in e.mimeData().urls() if u.isLocalFile()]
        if paths:
            self.dropped.emit(paths)

    def paintEvent(self, _e):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        r = QRectF(self.rect()).adjusted(2, 2, -2, -2)
        if self.hover:
            p.fillPath(K.rrect(r, 5), QColor(200, 80, 60, 30))
        from PySide6.QtGui import QFontMetricsF
        px, sp = 13.5, 3.0
        while px > 9.5 and QFontMetricsF(K.font(px, 500, sp)).horizontalAdvance(self.label) > r.width() - 24:
            px -= 0.5
            sp = max(0.8, sp - 0.3)
        self._px, self._sp = px, sp
        pen = QPen(C("warn") if self.hover else QColor("#8C8880"), 1.2, Qt.DashLine)
        pen.setDashPattern([4, 3])
        p.setPen(pen)
        p.setBrush(Qt.NoBrush)
        p.drawRoundedRect(r, 5, 5)
        box = QRectF(r.center().x() - 27, r.top() + r.height() * 0.2, 54, 40)
        p.setPen(QPen(C("on_dark"), 1.4))
        p.drawRoundedRect(box, 3, 3)
        K.draw_icon(p, "upload", box.adjusted(13, 6, -13, -6), C("on_dark"), 1.5)
        K.text(p, QRectF(r.left(), box.bottom() + 12, r.width(), 24), self.label,
               K.font(self._px, 500, self._sp), C("on_dark"), Qt.AlignHCenter | Qt.AlignVCenter)


class Separator(QWidget):
    def __init__(self, vertical=False, parent=None):
        super().__init__(parent)
        self.vertical = vertical
        if vertical:
            self.setFixedWidth(10)
        else:
            self.setFixedHeight(10)

    def paintEvent(self, _e):
        p = QPainter(self)
        if self.vertical:
            x = self.width() / 2
            p.setPen(QPen(QColor(0, 0, 0, 160), 1))
            p.drawLine(QPointF(x, 4), QPointF(x, self.height() - 4))
            p.setPen(QPen(QColor(255, 255, 255, 20), 1))
            p.drawLine(QPointF(x + 1, 4), QPointF(x + 1, self.height() - 4))
        else:
            y = self.height() / 2
            p.setPen(QPen(QColor(0, 0, 0, 160), 1))
            p.drawLine(QPointF(4, y), QPointF(self.width() - 4, y))
            p.setPen(QPen(QColor(255, 255, 255, 20), 1))
            p.drawLine(QPointF(4, y + 1), QPointF(self.width() - 4, y + 1))


class IconLabel(QWidget):
    def __init__(self, icon, color_key="chassis_text", size=20, parent=None):
        super().__init__(parent)
        self.icon_name, self.color_key = icon, color_key
        self.setFixedSize(size, size)

    def paintEvent(self, _e):
        p = QPainter(self)
        K.draw_icon(p, self.icon_name, QRectF(self.rect()), C(self.color_key), 1.5)


class Lamp(QWidget):
    """A large status lamp (export done)."""

    def __init__(self, color="led_green", size=34, parent=None):
        super().__init__(parent)
        self.color = color
        self.on = True
        self.setFixedSize(size + 16, size + 16)

    def paintEvent(self, _e):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        half = min(self.width(), self.height()) / 2
        r = half / 2.3
        K.led(p, QPointF(self.width() / 2, self.height() / 2), r, K.pal()[self.color], self.on,
              glow_scale=half / r - 0.05)


class ModeSwitch(QAbstractButton):
    """● AUTO  MANUAL / AUTO  ● MANUAL — click to flip. Checked = manual."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setCheckable(True)
        self.setCursor(Qt.PointingHandCursor)
        self.setFocusPolicy(Qt.NoFocus)
        self.setFixedSize(150, 30)
        self.setToolTip("Auto: Xenakis chops it. Manual: you mark the regions yourself.")

    def paintEvent(self, _e):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        en = self.isEnabled()
        manual = self.isChecked()
        f = K.font(11.5, 600, 1.2)
        p.setFont(f)
        fm = p.fontMetrics()
        y = self.height() / 2
        x = 10
        words = (("AUTO", not manual), ("MANUAL", manual))
        if self.width() < 130:     # compact: only the active setting
            words = (("MANUAL", True),) if manual else (("AUTO", True),)
        for word, active in words:
            if active:
                K.led(p, QPointF(x + 6, y), 5.5, K.pal()["led_red"], en)
                x += 18
            p.setPen(C("on_dark") if active and en else C("on_dark_dim"))
            p.drawText(QPointF(x, y + fm.ascent() / 2 - 1), word)
            x += fm.horizontalAdvance(word) + 12


class ApprovePill(QAbstractButton):
    """LED + check + APPROVED / APPROVE."""

    def __init__(self, parent=None, width=142):
        super().__init__(parent)
        self.setCheckable(True)
        self.setCursor(Qt.PointingHandCursor)
        self.setFocusPolicy(Qt.NoFocus)
        self.setFixedSize(width, 34)
        self.px = 11.5 if width >= 130 else 10.5
        self.setAttribute(Qt.WA_Hover)
        self._hover = False

    def enterEvent(self, e):
        self._hover = True
        self.update()

    def leaveEvent(self, e):
        self._hover = False
        self.update()

    def paintEvent(self, _e):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        r = QRectF(self.rect()).adjusted(1, 2, -1, -2)
        on = self.isChecked()
        g = QLinearGradient(r.topLeft(), r.bottomLeft())
        g.setColorAt(0, QColor("#2A2C30") if self._hover else QColor("#232528"))
        g.setColorAt(1, QColor("#18191B"))
        p.setBrush(g)
        p.setPen(QPen(QColor(75, 224, 122, 140) if on else QColor("#45484D"), 1))
        p.drawRoundedRect(r, 4, 4)
        K.led(p, QPointF(r.left() + 15, r.center().y()), 4.8, K.pal()["led_green"], on)
        col = C("on_dark") if on else C("on_dark_muted")
        K.draw_icon(p, "check", QRectF(r.left() + 28, r.center().y() - 8, 16, 16),
                    QColor(K.pal()["led_green"]) if on else col, 2.0)
        K.text(p, QRectF(r.left() + 50, r.top(), r.width() - 50, r.height()),
               "APPROVED" if on else "APPROVE", K.font(self.px, 600, 1.3 if self.px > 11 else 0.8), col)


class GroupFrame(QFrame):
    """Thin light frame with its title cut into the top border (like an engraved panel group)."""

    def __init__(self, title="", parent=None, margins=(16, 22, 16, 12), layout="v", color=None):
        super().__init__(parent)
        self.title = title
        self.color = color
        self.lay = QVBoxLayout(self) if layout == "v" else QHBoxLayout(self)
        self.lay.setContentsMargins(*margins)
        self.lay.setSpacing(10)

    def paintEvent(self, _e):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        f = K.font(12, 600, 1.8)
        p.setFont(f)
        fm = p.fontMetrics()
        top = 9.5
        r = QRectF(self.rect()).adjusted(0.5, top, -0.5, -0.5)
        col = QColor(self.color) if self.color else QColor("#77736C")
        p.setPen(QPen(col, 1.1))
        p.setBrush(Qt.NoBrush)
        if self.title:
            tw = fm.horizontalAdvance(self.title.upper())
            p.save()
            p.setClipRegion(_clip_without(self.rect(), int(12), int(tw + 14)))
            p.drawRoundedRect(r, 4, 4)
            p.restore()
            p.setPen(C("on_dark"))
            p.drawText(QPointF(18, top + fm.ascent() / 2 - 1), self.title.upper())
            p.setPen(QPen(col, 1.1))
            p.drawLine(QPointF(4, top), QPointF(8, top - 4))
        else:
            p.drawRoundedRect(r, 4, 4)


def _clip_without(rect, x, w):
    from PySide6.QtGui import QRegion
    full = QRegion(rect)
    return full.subtracted(QRegion(x, 0, w, 20))


class Swatch(QWidget):
    def __init__(self, color, size=14, parent=None):
        super().__init__(parent)
        self.color = color
        self.setFixedSize(size, size)

    def paintEvent(self, _e):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        p.setBrush(QColor(self.color))
        p.setPen(QPen(QColor(0, 0, 0, 160), 1))
        p.drawRoundedRect(QRectF(self.rect()).adjusted(0.5, 0.5, -0.5, -0.5), 2, 2)


class StatusText(QLabel):
    COLORS = {"ok": "ok", "warn": "warn", "info": "on_dark", "amber": "led_amber"}

    def set(self, text, kind="info"):
        self.setText(text)
        self.setFont(K.font(13, 500, 0.3))
        key = self.COLORS.get(kind, "on_dark")
        self.setProperty("skincolor", key)
        self.setStyleSheet(f"color: {K.pal()[key]}; background: transparent;")


class Badge(QWidget):
    """Small engraved inset label on a plate (e.g. the model / version tag)."""

    def __init__(self, text, color_key="plate_text", px=12.5, parent=None):
        super().__init__(parent)
        self.text_ = text
        self.color_key = color_key
        self.px = px
        from PySide6.QtGui import QFontMetricsF
        fm = QFontMetricsF(K.font(px, 500, 1.2))
        self.setFixedSize(int(fm.horizontalAdvance(text) + 26), 30)

    def paintEvent(self, _e):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        r = QRectF(self.rect()).adjusted(1, 1, -1, -1)
        p.setPen(QPen(QColor(0, 0, 0, 110), 1))
        p.setBrush(QColor(0, 0, 0, 18))
        p.drawRoundedRect(r, 3, 3)
        p.setPen(QPen(QColor(255, 255, 255, 60), 1))
        p.drawLine(QPointF(r.left() + 2, r.bottom() + 0.5), QPointF(r.right() - 2, r.bottom() + 0.5))
        K.text(p, r, self.text_, K.font(self.px, 500, 1.2), C(self.color_key), Qt.AlignCenter)


class LogoMark(QWidget):
    """The Xenakis mark in its dark display window, for the brand plate."""

    def __init__(self, size=46, parent=None):
        super().__init__(parent)
        self.setFixedSize(size, size)
        self.setToolTip("Xenakis")

    def paintEvent(self, e):
        from ..logo import paint_logo
        p = QPainter(self)
        paint_logo(p, QRectF(self.rect()), plate=False)
        p.end()


# ===================================================================== divider
class _GripHandle(QSplitterHandle):
    """Engraved slot across the chassis with a cream grip in the middle."""

    def __init__(self, orientation, parent):
        super().__init__(orientation, parent)
        self.setCursor(Qt.SplitVCursor)
        self.setAttribute(Qt.WA_Hover)
        self._hover = False
        self.setToolTip("Drag to give the editor or the list more room. "
                        "Drag all the way up to hide the editor. Double-click to reset.")

    def enterEvent(self, e):
        self._hover = True
        self.update()

    def leaveEvent(self, e):
        self._hover = False
        self.update()

    def mouseDoubleClickEvent(self, e):
        self.splitter().reset_split()

    def paintEvent(self, _e):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        r = QRectF(self.rect())
        cy = r.center().y()
        collapsed = self.splitter().editor_hidden()
        gw, gh = 72.0, 10.0
        grip = QRectF(r.center().x() - gw / 2, cy - gh / 2, gw, gh)
        # engraved slot either side of the grip
        for x0, x1 in ((r.left() + 14, grip.left() - 10), (grip.right() + 10, r.right() - 14)):
            if x1 - x0 < 8:
                continue
            p.setPen(QPen(C("chassis_lo", 200), 1))
            p.drawLine(QPointF(x0, cy - 0.5), QPointF(x1, cy - 0.5))
            p.setPen(QPen(C("chassis_hi", 200), 1))
            p.drawLine(QPointF(x0, cy + 0.5), QPointF(x1, cy + 0.5))
        K.soft_shadow(p, grip, 3, 2, 70, 1.2)
        g = QLinearGradient(grip.topLeft(), grip.bottomLeft())
        g.setColorAt(0, QColor("#FFFFFF") if self._hover else QColor(K.pal()["key_hi"]))
        g.setColorAt(1, QColor(K.pal()["key_lo"]))
        p.setBrush(g)
        p.setPen(QPen(QColor(20, 18, 16, 200), 1))
        p.drawRoundedRect(grip, 3, 3)
        p.setPen(QPen(QColor(40, 36, 32, 170), 1.1))
        for dx in (-9, -3, 3, 9):
            x = grip.center().x() + dx
            p.drawLine(QPointF(x, grip.top() + 2.5), QPointF(x, grip.bottom() - 2.5))
        if collapsed:
            f = K.font(10.5, 600, 1.8, caps=True)
            K.text(p, QRectF(grip.right() + 18, r.top(), 420, r.height()),
                   "EDITOR HIDDEN · DRAG DOWN OR DOUBLE-CLICK TO SHOW", f, C("chassis_text"))


class PanelSplitter(QSplitter):
    """Vertical divider between the trim editor (top) and the chop list (bottom).
    The top panel can be collapsed completely; double-click the grip to reset."""

    def __init__(self, default_top=0.46, parent=None):
        super().__init__(Qt.Vertical, parent)
        self.default_top = default_top
        self.setHandleWidth(18)
        self.setChildrenCollapsible(False)
        self.setOpaqueResize(True)

    def createHandle(self):
        return _GripHandle(self.orientation(), self)

    def editor_hidden(self):
        sz = self.sizes()
        return bool(sz) and sz[0] == 0

    def top_fraction(self):
        sz = self.sizes()
        tot = sum(sz)
        return sz[0] / tot if tot else self.default_top

    def set_top_fraction(self, f):
        tot = sum(self.sizes()) or max(1, self.height() - self.handleWidth())
        if f <= 0:
            self.setSizes([0, tot])
            return
        top = self.widget(0)
        bottom = self.widget(1)
        t = max(top.minimumSizeHint().height(), int(tot * f))
        t = min(t, tot - bottom.minimumSizeHint().height())
        self.setSizes([t, tot - t])

    def reset_split(self):
        self.set_top_fraction(self.default_top)
        self.splitterMoved.emit(self.sizes()[0], 1)


class ElidedLabel(QLabel):
    """One-line label that shortens itself with … instead of pushing the layout wider."""

    def __init__(self, text="", color_key="on_dark", px=13, weight=400, spacing=0.3):
        super().__init__()
        self._full = ""
        self.setFont(K.font(px, weight, spacing))
        recolor(self, color_key)
        self._min_w = 40
        self.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Preferred)
        self.setText(text)

    def setMinimumWidth(self, w):
        self._min_w = int(w)
        self.updateGeometry()

    def sizeHint(self):
        fm = self.fontMetrics()
        return QSize(max(self._min_w, int(fm.horizontalAdvance(self._full)) + 4),
                     super().sizeHint().height())

    def minimumSizeHint(self):
        return QSize(self._min_w, super().minimumSizeHint().height())

    def setText(self, text):
        self._full = text or ""
        self._elide()
        self.updateGeometry()

    def text_full(self):
        return self._full

    def resizeEvent(self, e):
        super().resizeEvent(e)
        self._elide()

    def _elide(self):
        fm = self.fontMetrics()
        QLabel.setText(self, fm.elidedText(self._full, Qt.ElideRight, max(10, self.width() - 2)))
