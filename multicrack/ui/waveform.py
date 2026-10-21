"""Waveform views in a dark sampler style: mirrored, filled, with grid and centre line."""
from __future__ import annotations

import numpy as np
from PySide6.QtCore import QPointF, QRectF, Qt, Signal
from PySide6.QtGui import QColor, QFont, QPainter, QPen, QPolygonF
from PySide6.QtWidgets import QSizePolicy, QWidget

from .theme import WAVE

BLOCK = 256


class PeakCache:
    """Min/max per pixel column, with a coarse block level for zoomed-out views."""

    def __init__(self, mono: np.ndarray):
        self.m = mono
        n = len(mono) // BLOCK * BLOCK
        if n:
            blk = mono[:n].reshape(-1, BLOCK)
            self.bmin, self.bmax = blk.min(axis=1), blk.max(axis=1)
        else:
            self.bmin = self.bmax = np.zeros(0, np.float32)
        self._key = None
        self._val = None

    def columns(self, a: int, b: int, cols: int):
        a, b = max(0, int(a)), min(len(self.m), int(b))
        key = (a, b, cols)
        if key == self._key:
            return self._val
        cols = max(1, cols)
        if b - a <= 1:
            z = np.zeros(cols, np.float32)
            val = (z, z)
        elif (b - a) / cols > BLOCK * 2 and len(self.bmin):
            ba, bb = a // BLOCK, max(a // BLOCK + 1, min(len(self.bmin), b // BLOCK))
            edges = np.linspace(ba, bb, cols + 1).astype(int)
            edges = np.minimum(edges, bb - 1)
            mins = np.minimum.reduceat(self.bmin[:bb], edges[:-1])
            maxs = np.maximum.reduceat(self.bmax[:bb], edges[:-1])
            val = (mins, maxs)
        else:
            seg = self.m[a:b]
            edges = np.linspace(0, len(seg), cols + 1).astype(int)
            edges = np.minimum(edges, len(seg) - 1)
            mins = np.minimum.reduceat(seg, edges[:-1])
            maxs = np.maximum.reduceat(seg, edges[:-1])
            val = (mins, maxs)
        self._key, self._val = key, val
        return val


def paint_wave(p: QPainter, rect: QRectF, mins, maxs, gain=1.0, grid=True):
    p.fillRect(rect, QColor(WAVE["bg"]))
    w, h = rect.width(), rect.height()
    cy = rect.top() + h / 2
    if grid and w > 120:
        p.setPen(QPen(QColor(WAVE["grid"]), 1))
        for k in range(1, 10):
            x = rect.left() + w * k / 10
            p.drawLine(QPointF(x, rect.top()), QPointF(x, rect.bottom()))
        for frac in (0.25, 0.75):
            y = rect.top() + h * frac
            p.drawLine(QPointF(rect.left(), y), QPointF(rect.right(), y))
    p.setPen(QPen(QColor(WAVE["center"]), 1))
    p.drawLine(QPointF(rect.left(), cy), QPointF(rect.right(), cy))
    n = len(mins)
    if n == 0:
        return
    half = h / 2 * 0.94
    xs = rect.left() + (np.arange(n) + 0.5) * (w / n)
    top = cy - np.clip(maxs * gain, -1, 1) * half
    bot = cy - np.clip(mins * gain, -1, 1) * half
    top = np.minimum(top, cy - 0.5)
    bot = np.maximum(bot, cy + 0.5)
    pts = [QPointF(float(x), float(y)) for x, y in zip(xs, top)]
    pts += [QPointF(float(x), float(y)) for x, y in zip(xs[::-1], bot[::-1])]
    poly = QPolygonF(pts)
    p.setPen(QPen(QColor(WAVE["edge"]), 0.8))
    p.setBrush(QColor(WAVE["fill"]))
    p.drawPolygon(poly)
    p.setBrush(Qt.NoBrush)


def _gain(mins, maxs):
    pk = max(float(np.max(np.abs(maxs))) if len(maxs) else 0.0,
             float(np.max(np.abs(mins))) if len(mins) else 0.0)
    return 1.0 / pk if pk > 1e-6 else 1.0


class MiniWave(QWidget):
    """Small static waveform of one chop (normalized for visibility)."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setMinimumHeight(36)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        self.cache = None
        self.a = self.b = 0
        self.reverse = False
        self.playhead = None      # 0..1 or None

    def set_chop(self, cache: PeakCache, a: int, b: int, reverse=False):
        self.cache, self.a, self.b, self.reverse = cache, a, b, reverse
        self.update()

    def set_playhead(self, frac):
        if frac != self.playhead:
            self.playhead = frac
            self.update()

    def paintEvent(self, _e):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        r = QRectF(self.rect())
        if self.cache is None:
            p.fillRect(r, QColor(WAVE["bg"]))
            return
        mins, maxs = self.cache.columns(self.a, self.b, max(8, int(r.width() / 2)))
        if self.reverse:
            mins, maxs = mins[::-1], maxs[::-1]
        paint_wave(p, r, mins, maxs, _gain(mins, maxs), grid=False)
        if self.playhead is not None:
            x = r.width() * self.playhead
            p.setPen(QPen(QColor("#FFFFFF"), 1.5))
            p.drawLine(QPointF(x, 0), QPointF(x, r.height()))


class TrimEditor(QWidget):
    """Large waveform of one chop with draggable start / end handles.

    Zoom with the wheel (or the page's buttons) all the way out to the whole stem.
    Drag a handle to trim, or drag across empty waveform to select a new section."""
    changed = Signal(int, int)
    viewChanged = Signal(int, int)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setMinimumHeight(170)
        self.setMouseTracking(True)
        self.cache = None
        self.n = 0
        self.start = self.end = 0
        self.view_a = self.view_b = 0
        self.drag = None
        self.sr = 44100
        self.snap = None   # callable(sample) -> sample
        self.fade_in = 0   # samples (drawn as ramps)
        self.fade_out = 0
        self.reverse = False
        self.playhead = None   # stem sample position or None

    def set_fx(self, fade_in: int, fade_out: int, reverse: bool):
        self.fade_in, self.fade_out, self.reverse = int(fade_in), int(fade_out), bool(reverse)
        self.update()

    def set_playhead(self, s):
        if s != self.playhead:
            self.playhead = s
            self.update()

    # ------------------------------------------------------------ view
    def set_chop(self, cache: PeakCache, n: int, sr: int, start: int, end: int, snap=None,
                 keep_view=False):
        same_stem = cache is self.cache and n == self.n
        self.cache, self.n, self.sr = cache, n, sr
        self.start, self.end = int(start), int(end)
        self.snap = snap
        if keep_view and same_stem and self.view_b > self.view_a:
            self.update()
            return
        self.show_chop()

    def show_chop(self):
        length = max(1, self.end - self.start)
        pad = max(int(0.25 * length), int(0.12 * self.sr))
        self.set_view(self.start - pad, self.end + pad)

    def show_all(self):
        self.set_view(0, self.n)

    def set_view(self, a, b):
        span = int(min(self.n, max(int(0.01 * self.sr), b - a)))
        a = int(max(0, min(self.n - span, a)))
        self.view_a, self.view_b = a, a + span
        self.update()
        self.viewChanged.emit(self.view_a, self.view_b)

    def zoom(self, factor, center=None):
        if self.cache is None:
            return
        span = self.view_b - self.view_a
        if center is None:
            center = self.view_a + span // 2
        new = span * factor
        a = center - (center - self.view_a) * new / max(1, span)
        self.set_view(int(a), int(a + new))

    def is_whole(self):
        return self.view_a <= 0 and self.view_b >= self.n

    def clear(self):
        self.cache = None
        self.update()

    def _x(self, s):
        w = self.width()
        return (s - self.view_a) / max(1, self.view_b - self.view_a) * w

    def _s(self, x):
        return int(self.view_a + x / max(1, self.width()) * (self.view_b - self.view_a))

    # ----------------------------------------------------------- paint
    def paintEvent(self, _e):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        r = QRectF(self.rect())
        if self.cache is None:
            p.fillRect(r, QColor(WAVE["bg"]))
            p.setPen(QColor("#8A949C"))
            p.drawText(r, Qt.AlignCenter, "Press play on a chop to load it here")
            return
        mins, maxs = self.cache.columns(self.view_a, self.view_b, max(8, int(r.width() / 1.5)))
        span = self.view_b - self.view_a
        if span > 4 * max(1, self.end - self.start):
            gain = min(_gain(mins, maxs), 8.0)        # zoomed out: scale to what's on screen
        else:
            cm, cx = self.cache.columns(self.start, self.end, 64)
            gain = _gain(cm, cx)
        paint_wave(p, r, mins, maxs, gain)
        f = QFont(self.font())
        f.setPointSizeF(8.5)
        p.setFont(f)
        self._ruler(p, r)
        xs, xe = self._x(self.start), self._x(self.end)
        shade = QColor(WAVE["shade"])
        shade.setAlpha(165)
        p.fillRect(QRectF(0, 0, max(0, min(xs, r.width())), r.height()), shade)
        if xe < r.width():
            p.fillRect(QRectF(max(0, xe), 0, r.width() - max(0, xe), r.height()), shade)
        hc = QColor(WAVE["handle"])
        if xe - xs < 3:     # tiny at this zoom: draw a visible marker
            p.fillRect(QRectF(xs - 1, 0, 3, r.height()), hc)
        p.setPen(QPen(hc, 2))
        p.drawLine(QPointF(xs, 0), QPointF(xs, r.height()))
        p.drawLine(QPointF(xe, 0), QPointF(xe, r.height()))
        p.setPen(Qt.NoPen)
        p.setBrush(hc)
        p.drawRoundedRect(QRectF(xs, 0, 12, 16), 2, 2)
        p.drawRoundedRect(QRectF(xe - 12, r.height() - 16, 12, 16), 2, 2)
        # fades (as heard: a reversed chop fades in from its original end)
        fi, fo = (self.fade_out, self.fade_in) if self.reverse else (self.fade_in, self.fade_out)
        ramp = QPen(QColor(255, 255, 255, 170), 1.4)
        ramp.setStyle(Qt.DashLine)
        p.setPen(ramp)
        if fi > 0:
            p.drawLine(QPointF(xs, r.height() - 2), QPointF(self._x(self.start + fi), 18))
        if fo > 0:
            p.drawLine(QPointF(self._x(self.end - fo), 18), QPointF(xe, r.height() - 2))
        if self.playhead is not None:
            xp = self._x(self.playhead)
            p.setPen(QPen(QColor("#FFFFFF"), 1.6))
            p.drawLine(QPointF(xp, 0), QPointF(xp, r.height()))
        p.setPen(QColor("#DDE3E8"))
        dur = (self.end - self.start) / self.sr
        p.drawText(QRectF(8, r.height() - 20, 400, 18), Qt.AlignLeft | Qt.AlignVCenter,
                   f"{dur:.3f} s selected" + ("  ·  plays reversed" if self.reverse else ""))

    def _ruler(self, p, r):
        span_s = (self.view_b - self.view_a) / self.sr
        steps = [0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1, 2, 5, 10, 15, 30, 60]
        step = next((s for s in steps if span_s / s <= 10), 60)
        t0 = (int(self.view_a / self.sr / step) + 1) * step
        p.setPen(QColor("#8A949C"))
        t = t0
        while t * self.sr < self.view_b:
            x = self._x(t * self.sr)
            p.drawLine(QPointF(x, 0), QPointF(x, 5))
            m = int(t // 60)
            sec = t - 60 * m
            txt = f"{m}:{sec:05.2f}" if step < 1 else f"{m}:{int(round(sec)):02d}"
            p.drawText(QRectF(x + 3, 2, 70, 14), Qt.AlignLeft | Qt.AlignVCenter, txt)
            t += step

    # ---------------------------------------------------------- input
    def wheelEvent(self, e):
        if self.cache is None:
            return
        dy, dx = e.angleDelta().y(), e.angleDelta().x()
        if e.modifiers() & Qt.ShiftModifier or abs(dx) > abs(dy):
            d = dx or dy
            span = self.view_b - self.view_a
            shift = int(-d / 120 * span * 0.15)
            self.set_view(self.view_a + shift, self.view_b + shift)
        else:
            self.zoom(0.8 if dy > 0 else 1.25, self._s(e.position().x()))

    def _near(self, x):
        ds, de = abs(x - self._x(self.start)), abs(x - self._x(self.end))
        if min(ds, de) < 10:
            return "start" if ds <= de else "end"
        return None

    def mousePressEvent(self, e):
        if self.cache is None:
            return
        x = e.position().x()
        part = self._near(x)
        if part:
            self.drag = part
        else:
            s = max(0, min(self.n, self._s(x)))
            self.drag = ("new", s)

    def mouseMoveEvent(self, e):
        x = e.position().x()
        if self.drag:
            s = max(0, min(self.n, self._s(x)))
            if isinstance(self.drag, tuple):
                anchor = self.drag[1]
                if abs(s - anchor) > int(0.005 * self.sr):
                    self.start, self.end = min(anchor, s), max(anchor, s)
                    self.drag = ("new", anchor, True)
            elif self.drag == "start":
                self.start = min(s, self.end - int(0.005 * self.sr))
            else:
                self.end = max(s, self.start + int(0.005 * self.sr))
            self.update()
        elif self.cache is not None:
            self.setCursor(Qt.SizeHorCursor if self._near(x) else Qt.IBeamCursor)

    def mouseReleaseEvent(self, _e):
        d = self.drag
        self.drag = None
        if not d:
            return
        if isinstance(d, tuple) and len(d) < 3:
            return          # a plain click on the waveform: keep the current selection
        if (d == "start" or isinstance(d, tuple)) and self.snap:
            self.start = int(self.snap(self.start))
            self.start = min(self.start, self.end - int(0.005 * self.sr))
        self.update()
        self.changed.emit(self.start, self.end)


class StemView(QWidget):
    """Whole-stem waveform with zoom, scroll and regions.

    regions: list of dicts {start, end, style: 'user'|'ai'|'loop'|'roll', tag}
    In editable mode you drag on empty space to add a region and drag region edges to resize.
    """
    regionAdded = Signal(int, int)
    regionChanged = Signal(int, int, int)
    regionSelected = Signal(int)

    def __init__(self, parent=None, editable=True):
        super().__init__(parent)
        self.editable = editable
        self.setMinimumHeight(180)
        self.setMouseTracking(True)
        self.cache = None
        self.n = 1
        self.sr = 44100
        self.view_a, self.view_b = 0, 1
        self.regions: list[dict] = []
        self.bands: list[dict] = []      # coloured section strips (start, end, color, name)
        self.selected = -1
        self._drag = None
        self.snap = None        # for newly drawn regions
        self.snap_edge = None   # for dragged region edges (gentle)
        self.strip = 22

    def set_stem(self, cache: PeakCache, n: int, sr: int):
        self.cache, self.n, self.sr = cache, max(1, n), sr
        self.view_a, self.view_b = 0, self.n
        self.update()

    def set_regions(self, regions, selected=-1):
        self.regions = regions
        self.selected = selected
        self.update()

    def zoom(self, factor, center=None):
        span = self.view_b - self.view_a
        if center is None:
            center = self.view_a + span / 2
        new = int(min(self.n, max(int(0.05 * self.sr), span * factor)))
        a = int(center - (center - self.view_a) * new / max(1, span))
        a = max(0, min(self.n - new, a))
        self.view_a, self.view_b = a, a + new
        self.update()

    def show_range(self, a, b):
        pad = int((b - a) * 0.3) + int(0.1 * self.sr)
        self.view_a, self.view_b = max(0, a - pad), min(self.n, b + pad)
        self.update()

    def _x(self, s):
        return (s - self.view_a) / max(1, self.view_b - self.view_a) * self.width()

    def _s(self, x):
        return int(self.view_a + x / max(1, self.width()) * (self.view_b - self.view_a))

    def wheelEvent(self, e):
        d = e.angleDelta().y()
        if e.modifiers() & Qt.ShiftModifier or abs(e.angleDelta().x()) > abs(d):
            dx = e.angleDelta().x() or d
            span = self.view_b - self.view_a
            shift = int(-dx / 120 * span * 0.15)
            a = max(0, min(self.n - span, self.view_a + shift))
            self.view_a, self.view_b = a, a + span
            self.update()
        else:
            self.zoom(0.8 if d > 0 else 1.25, self._s(e.position().x()))

    def paintEvent(self, _e):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        full = QRectF(self.rect())
        top = self.strip if self.bands else 0
        r = QRectF(0, top, full.width(), full.height() - top)
        if self.cache is None:
            p.fillRect(full, QColor(WAVE["bg"]))
            return
        if self.bands:
            p.fillRect(QRectF(0, 0, full.width(), top), QColor(WAVE["bg"]).lighter(115))
            f = QFont(self.font())
            f.setPointSizeF(8.5)
            p.setFont(f)
            for b in self.bands:
                x0, x1 = self._x(b["start"]), self._x(b["end"])
                if x1 < 0 or x0 > full.width():
                    continue
                c = QColor(b["color"])
                c.setAlpha(200)
                p.fillRect(QRectF(x0, 2, max(2, x1 - x0), top - 4), c)
                if x1 - x0 > 40:
                    p.setPen(QColor("#0B1A24"))
                    p.drawText(QRectF(x0 + 4, 2, x1 - x0 - 6, top - 4),
                               Qt.AlignVCenter | Qt.AlignLeft, b["name"])
        mins, maxs = self.cache.columns(self.view_a, self.view_b, max(8, int(r.width() / 1.5)))
        gm, gx = self.cache.columns(0, self.n, 256)
        paint_wave(p, r, mins, maxs, min(_gain(gm, gx), 4.0))
        f = QFont(self.font())
        f.setPointSizeF(8.5)
        f.setBold(True)
        p.setFont(f)
        for i, reg in enumerate(self.regions):
            x0, x1 = self._x(reg["start"]), self._x(reg["end"])
            if x1 < 0 or x0 > r.width():
                continue
            style = reg.get("style", "user")
            col = QColor(WAVE["ai"] if style == "ai" else WAVE["roll"] if style == "roll"
                         else WAVE["region"])
            fill = QColor(col)
            fill.setAlpha(70 if i == self.selected else 40)
            p.fillRect(QRectF(x0, r.top(), x1 - x0, r.height()), fill)
            pen = QPen(col, 2.5 if i == self.selected else 1.6)
            if style == "ai":
                pen.setStyle(Qt.DashLine)
            p.setPen(pen)
            p.drawRect(QRectF(x0, r.top() + 1, x1 - x0, r.height() - 2))
            tag = str(reg.get("tag", ""))
            if tag and x1 - x0 > 14:
                tw = 8 + 7 * len(tag)
                p.fillRect(QRectF(x0 + 3, r.top() + 4, tw, 16), col)
                p.setPen(QColor("#0B1A24"))
                p.drawText(QRectF(x0 + 3, r.top() + 4, tw, 16), Qt.AlignCenter, tag)
        if self._drag and self._drag[0] == "new":
            x0, x1 = sorted((self._x(self._drag[1]), self._x(self._drag[2])))
            col = QColor(WAVE["region"])
            fill = QColor(col)
            fill.setAlpha(50)
            p.fillRect(QRectF(x0, r.top(), x1 - x0, r.height()), fill)
            p.setPen(QPen(col, 1.6))
            p.drawRect(QRectF(x0, r.top() + 1, x1 - x0, r.height() - 2))

    # ---- editing
    def _hit(self, x):
        for i in range(len(self.regions) - 1, -1, -1):
            reg = self.regions[i]
            x0, x1 = self._x(reg["start"]), self._x(reg["end"])
            if abs(x - x0) < 7:
                return i, "start"
            if abs(x - x1) < 7:
                return i, "end"
            if x0 < x < x1:
                return i, "body"
        return -1, None

    def mousePressEvent(self, e):
        if self.cache is None:
            return
        x = e.position().x()
        i, part = self._hit(x)
        if i >= 0:
            self.selected = i
            self.regionSelected.emit(i)
            if self.editable and part in ("start", "end"):
                self._drag = ("edge", i, part)
            self.update()
            return
        if self.editable:
            s = self._s(x)
            self._drag = ("new", s, s)
            self.update()

    def mouseMoveEvent(self, e):
        x = e.position().x()
        if self._drag:
            s = max(0, min(self.n, self._s(x)))
            if self._drag[0] == "new":
                self._drag = ("new", self._drag[1], s)
            else:
                _k, i, part = self._drag
                reg = self.regions[i]
                if part == "start":
                    reg["start"] = min(s, reg["end"] - int(0.01 * self.sr))
                else:
                    reg["end"] = max(s, reg["start"] + int(0.01 * self.sr))
            self.update()
        elif self.editable:
            i, part = self._hit(x)
            self.setCursor(Qt.SizeHorCursor if part in ("start", "end") else
                           Qt.PointingHandCursor if part == "body" else Qt.IBeamCursor)

    def mouseReleaseEvent(self, _e):
        if not self._drag:
            return
        d = self._drag
        self._drag = None
        if d[0] == "new":
            a, b = sorted((d[1], d[2]))
            if b - a > int(0.02 * self.sr):
                if self.snap:
                    a = int(self.snap(a))
                self.regionAdded.emit(a, b)
        else:
            _k, i, part = d
            reg = self.regions[i]
            if part == "start" and self.snap_edge:
                reg["start"] = int(self.snap_edge(reg["start"]))
            self.regionChanged.emit(i, reg["start"], reg["end"])
        self.update()
