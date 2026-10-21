"""Waveform displays: dark oscilloscope-style glass, filled mirrored waveforms (Edison style)."""
from __future__ import annotations

import numpy as np
from PySide6.QtCore import QPointF, QRectF, Qt, Signal
from PySide6.QtGui import (QColor, QLinearGradient, QPainter, QPainterPath, QPen, QPolygonF)
from PySide6.QtWidgets import QSizePolicy, QWidget

from .skin import core as K
from .skin.core import C

BLOCK = 256
WAVE = {"groove": ["#B8473A", "#3F73B5", "#8A5CC2", "#C9902E"], "roll": "#E8C547"}
MARK = QColor("#E8483A")


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


def _gain(mins, maxs):
    pk = max(float(np.max(np.abs(maxs))) if len(maxs) else 0.0,
             float(np.max(np.abs(mins))) if len(mins) else 0.0)
    return 1.0 / pk if pk > 1e-6 else 1.0


def paint_glass(p: QPainter, r: QRectF, radius=4.0):
    """Recessed dark display glass."""
    path = K.rrect(r, radius)
    g = QLinearGradient(r.topLeft(), r.bottomLeft())
    g.setColorAt(0, QColor("#0E1012"))
    g.setColorAt(1, QColor("#15181B"))
    p.fillPath(path, g)
    K.inner_shadow(p, r, radius, 190, 10)
    p.save()
    p.setPen(QPen(QColor("#000000"), 1.2))
    p.setBrush(Qt.NoBrush)
    p.drawRoundedRect(r.adjusted(0.5, 0.5, -0.5, -0.5), radius, radius)
    p.setPen(QPen(QColor(255, 255, 255, 22), 1))
    p.drawLine(QPointF(r.left() + radius, r.bottom() + 0.5), QPointF(r.right() - radius, r.bottom() + 0.5))
    p.restore()


def wave_poly(rect: QRectF, mins, maxs, gain=1.0):
    n = len(mins)
    if n == 0:
        return None
    w, h = rect.width(), rect.height()
    cy = rect.top() + h / 2
    half = h / 2 * 0.92
    xs = rect.left() + (np.arange(n) + 0.5) * (w / n)
    top = cy - np.clip(maxs * gain, -1, 1) * half
    bot = cy - np.clip(mins * gain, -1, 1) * half
    top = np.minimum(top, cy - 0.6)
    bot = np.maximum(bot, cy + 0.6)
    pts = [QPointF(float(x), float(y)) for x, y in zip(xs, top)]
    pts += [QPointF(float(x), float(y)) for x, y in zip(xs[::-1], bot[::-1])]
    return QPolygonF(pts)


def paint_wave(p: QPainter, rect: QRectF, mins, maxs, gain=1.0, fill=None, edge=None, center=True):
    cy = rect.top() + rect.height() / 2
    if center:
        p.setPen(QPen(QColor("#2C3237"), 1))
        p.drawLine(QPointF(rect.left(), cy), QPointF(rect.right(), cy))
    poly = wave_poly(rect, mins, maxs, gain)
    if poly is None:
        return
    p.setPen(QPen(QColor(edge or K.pal()["wave_edge"]), 0.7))
    p.setBrush(QColor(fill or K.pal()["wave"]))
    p.drawPolygon(poly)
    p.setBrush(Qt.NoBrush)


def _time_steps(span_s):
    steps = [0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1, 2, 5, 10, 15, 30, 60]
    return next((s for s in steps if span_s / s <= 9), 60)


def _fmt_t(t, step):
    m = int(t // 60)
    sec = t - 60 * m
    return f"{m}:{sec:05.2f}" if step < 1 else f"{m}:{int(round(sec)):02d}"


def _grid_and_ruler(p, area: QRectF, ruler: QRectF, a, b, sr, x_of):
    span_s = (b - a) / sr
    if span_s <= 0:
        return
    step = _time_steps(span_s)
    t = (int(a / sr / step) + 1) * step if a > 0 else 0.0
    f = K.font(11, 500, 0.6)
    p.setFont(f)
    while t * sr <= b:
        x = x_of(t * sr)
        p.setPen(QPen(QColor(255, 255, 255, 14), 1))
        p.drawLine(QPointF(x, area.top()), QPointF(x, area.bottom()))
        p.setPen(QPen(QColor(255, 255, 255, 60), 1))
        p.drawLine(QPointF(x, ruler.top()), QPointF(x, ruler.top() + 4))
        p.setPen(QColor("#A9A49C"))
        p.drawText(QRectF(x + 4, ruler.top(), 80, ruler.height()), int(Qt.AlignLeft | Qt.AlignVCenter),
                   _fmt_t(t, step))
        t += step
    for frac in (0.25, 0.75):
        y = area.top() + area.height() * frac
        p.setPen(QPen(QColor(255, 255, 255, 9), 1))
        p.drawLine(QPointF(area.left(), y), QPointF(area.right(), y))


class MiniWave(QWidget):
    """Small waveform of one chop for the list (no box, just the trace)."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setMinimumHeight(34)
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
        if self.cache is None:
            return
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        r = QRectF(self.rect()).adjusted(0, 2, 0, -2)
        mins, maxs = self.cache.columns(self.a, self.b, max(8, int(r.width() / 1.6)))
        if self.reverse:
            mins, maxs = mins[::-1], maxs[::-1]
        paint_wave(p, r, mins, maxs, _gain(mins, maxs), center=False)
        if self.playhead is not None:
            x = r.width() * self.playhead
            p.setPen(QPen(QColor("#FFFFFF"), 1.6))
            p.drawLine(QPointF(x, 0), QPointF(x, self.height()))


class TrimEditor(QWidget):
    """Large waveform of one chop with draggable start / end markers.

    Click anywhere to play the stem from that spot. Drag a marker to trim, drag the grab bar
    between the markers to move the whole selection (same length), or drag across the waveform
    to select a new section. Zoom with the wheel all the way out to the whole stem."""
    changed = Signal(int, int)
    viewChanged = Signal(int, int)
    selectionChanged = Signal(int, int)
    seekRequested = Signal(int)

    TOP = 24       # marker triangles + grab bar
    RULER = 24     # time labels

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setMinimumHeight(176)
        self.setMouseTracking(True)
        self.cache = None
        self.n = 0
        self.start = self.end = 0
        self.view_a = self.view_b = 0
        self.drag = None
        self.sr = 44100
        self.snap = None   # callable(sample) -> sample
        self.snap_move = None   # callable(start) -> start, applied while moving the selection
        self._hover_handle = False
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

    def _area(self):
        r = QRectF(self.rect()).adjusted(1, 1, -1, -1)
        return r, QRectF(r.left() + 2, r.top() + self.TOP, r.width() - 4,
                         r.height() - self.TOP - self.RULER)

    def _x(self, s):
        _r, a = self._area()
        return a.left() + (s - self.view_a) / max(1, self.view_b - self.view_a) * a.width()

    def _s(self, x):
        _r, a = self._area()
        return int(self.view_a + (x - a.left()) / max(1, a.width()) * (self.view_b - self.view_a))

    # ----------------------------------------------------------- paint
    def paintEvent(self, _e):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        r, area = self._area()
        paint_glass(p, r, 4)
        if self.cache is None:
            K.text(p, r, "PRESS PLAY ON A CHOP TO LOAD IT HERE", K.font(12, 500, 2.0),
                   QColor("#6E6A64"), Qt.AlignCenter)
            return
        ruler = QRectF(r.left() + 4, area.bottom() + 2, r.width() - 8, self.RULER - 4)
        p.save()
        p.setClipRect(r.adjusted(2, 2, -2, -2))
        _grid_and_ruler(p, area, ruler, self.view_a, self.view_b, self.sr, self._x)
        cols = max(8, int(area.width() / 1.4))
        mins, maxs = self.cache.columns(self.view_a, self.view_b, cols)
        span = self.view_b - self.view_a
        if span > 4 * max(1, self.end - self.start):
            gain = min(_gain(mins, maxs), 8.0)
        else:
            cm, cx = self.cache.columns(self.start, self.end, 64)
            gain = _gain(cm, cx)
        # whole view in grey, selection in green
        paint_wave(p, area, mins, maxs, gain, fill=K.pal()["wave_dim"], edge="#8A8F94")
        xs, xe = self._x(self.start), self._x(self.end)
        p.save()
        p.setClipRect(QRectF(xs, area.top() - 2, max(0, xe - xs), area.height() + 4))
        paint_wave(p, area, mins, maxs, gain, center=False)
        glow = QColor(K.pal()["wave"])
        glow.setAlpha(18)
        p.fillRect(QRectF(xs, area.top(), xe - xs, area.height()), glow)
        p.restore()
        # fades (as heard: a reversed chop fades in from its original end)
        fi, fo = (self.fade_out, self.fade_in) if self.reverse else (self.fade_in, self.fade_out)
        dash = QPen(QColor(235, 232, 225, 190), 1.3, Qt.DashLine)
        dash.setDashPattern([4, 3])
        p.setPen(dash)
        if fi > 0:
            p.drawLine(QPointF(xs, area.bottom()), QPointF(self._x(self.start + fi), area.top()))
        if fo > 0:
            p.drawLine(QPointF(self._x(self.end - fo), area.top()), QPointF(xe, area.bottom()))
        # region bar + grab handle (drag to move the whole selection)
        top = r.top() + 3
        bar = QColor(MARK)
        bar.setAlpha(70)
        p.fillRect(QRectF(xs, top + 5, max(0, xe - xs), 5), bar)
        hr = self._handle_rect()
        g = QLinearGradient(hr.topLeft(), hr.bottomLeft())
        moving = isinstance(self.drag, tuple) and self.drag[0] == "move"
        g.setColorAt(0, QColor("#FFFFFF") if (self._hover_handle or moving) else QColor("#F2EEE6"))
        g.setColorAt(1, QColor("#BDB5A7"))
        p.setPen(QPen(QColor(0, 0, 0, 200), 1))
        p.setBrush(g)
        p.drawRoundedRect(hr, 3, 3)
        p.setPen(QPen(QColor(40, 36, 32, 200), 1.2))
        cx = hr.center().x()
        for dx in (-6, -2, 2, 6):
            p.drawLine(QPointF(cx + dx, hr.top() + 3.5), QPointF(cx + dx, hr.bottom() - 3.5))
        # markers
        for x in (xs, xe):
            p.setPen(QPen(MARK, 1.8))
            p.drawLine(QPointF(x, r.top() + self.TOP - 2), QPointF(x, area.bottom()))
            tri = QPainterPath()
            tri.moveTo(x - 6.5, r.top() + 3)
            tri.lineTo(x + 6.5, r.top() + 3)
            tri.lineTo(x, r.top() + self.TOP - 1)
            tri.closeSubpath()
            p.setPen(Qt.NoPen)
            p.setBrush(MARK)
            p.drawPath(tri)
        if self.playhead is not None:
            xp = self._x(self.playhead)
            p.setPen(QPen(QColor("#FFFFFF"), 1.7))
            p.drawLine(QPointF(xp, r.top() + self.TOP - 2), QPointF(xp, area.bottom()))
            tri = QPainterPath()
            tri.moveTo(xp - 5.5, r.top() + 4)
            tri.lineTo(xp + 5.5, r.top() + 4)
            tri.lineTo(xp, r.top() + self.TOP - 2)
            tri.closeSubpath()
            p.setPen(Qt.NoPen)
            p.setBrush(QColor("#FFFFFF"))
            p.drawPath(tri)
        p.restore()

    # ----------------------------------------------------------- input
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

    def _handle_rect(self):
        r, _a = self._area()
        xs, xe = self._x(self.start), self._x(self.end)
        w = 44.0
        cx = (xs + xe) / 2
        return QRectF(cx - w / 2, r.top() + 2, w, 15)

    def _near(self, x):
        ds, de = abs(x - self._x(self.start)), abs(x - self._x(self.end))
        if min(ds, de) < 10:
            return "start" if ds <= de else "end"
        return None

    def mousePressEvent(self, e):
        if self.cache is None:
            return
        pos = e.position()
        x = pos.x()
        part = self._near(x)
        near_edge = min(abs(x - self._x(self.start)), abs(x - self._x(self.end))) < 5
        if self._handle_rect().adjusted(-3, -2, 3, 3).contains(pos) and not near_edge:
            _r, area = self._area()
            spp = (self.view_b - self.view_a) / max(1.0, area.width())   # samples per pixel
            self.drag = ("move", x, self.start, self.end, spp)
            self.setCursor(Qt.ClosedHandCursor)
            self.update()
        elif part:
            self.drag = part
        else:
            s = max(0, min(self.n, self._s(x)))
            self.drag = ("new", s)

    def _move_to(self, x):
        _k, x_press, a0, b0, spp = self.drag
        length = b0 - a0
        # the selection follows the mouse 1:1 at the zoom level the drag started with
        ns = int(max(0, min(self.n - length, a0 + (x - x_press) * spp)))
        if self.snap_move:
            ns = int(max(0, min(self.n - length, self.snap_move(ns))))
        self.start, self.end = ns, ns + length
        # keep the selection in view while sweeping through the stem
        span = self.view_b - self.view_a
        if self.end > self.view_b and span < self.n:
            self.set_view(self.end - span + int(span * 0.05), self.end + int(span * 0.05))
        elif self.start < self.view_a and span < self.n:
            self.set_view(self.start - int(span * 0.05), self.start - int(span * 0.05) + span)

    def mouseMoveEvent(self, e):
        x = e.position().x()
        if isinstance(self.drag, tuple) and self.drag[0] == "move":
            self._move_to(x)
            self.update()
            self.selectionChanged.emit(self.start, self.end)
            return
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
            self.selectionChanged.emit(self.start, self.end)
        elif self.cache is not None:
            over = self._handle_rect().adjusted(-3, -2, 3, 3).contains(e.position()) and \
                min(abs(x - self._x(self.start)), abs(x - self._x(self.end))) >= 5
            if over != self._hover_handle:
                self._hover_handle = over
                self.update()
            self.setCursor(Qt.OpenHandCursor if over else
                           Qt.SizeHorCursor if self._near(x) else Qt.PointingHandCursor)
            self.setToolTip("Drag to move the whole selection (same length)" if over else
                            "Click to play from here · drag to select a new section"
                            if not self._near(x) else "Drag to trim")

    def leaveEvent(self, _e):
        if self._hover_handle:
            self._hover_handle = False
            self.update()

    def mouseReleaseEvent(self, _e):
        d = self.drag
        self.drag = None
        if not d:
            return
        if isinstance(d, tuple) and d[0] == "move":
            if (self.start, self.end) == (d[2], d[3]):
                self.update()
                return
            if self.snap and not self.snap_move:
                length = self.end - self.start
                ns = int(max(0, min(self.n - length, self.snap(self.start))))
                self.start, self.end = ns, ns + length
            self.setCursor(Qt.OpenHandCursor)
            self.update()
            self.changed.emit(self.start, self.end)
            return
        if isinstance(d, tuple) and len(d) < 3:
            self.seekRequested.emit(int(d[1]))   # a plain click: play from here
            return
        if (d == "start" or isinstance(d, tuple)) and self.snap:
            self.start = int(self.snap(self.start))
            self.start = min(self.start, self.end - int(0.005 * self.sr))
        self.update()
        self.changed.emit(self.start, self.end)


class StemView(QWidget):
    """Whole-stem display with zoom, scroll, colored section strips and regions.

    regions: list of dicts {start, end, style: 'user'|'ai'|'loop'|'roll', tag, color?}
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
        self.ticks: list = []            # small markers along the bottom (sample positions)
        self.bar_labels: list = []       # (sample, text) under the display
        self.selected = -1
        self._drag = None
        self.snap = None        # for newly drawn regions
        self.snap_edge = None   # for dragged region edges (gentle)
        self.strip = 26

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

    def _rects(self):
        r = QRectF(self.rect()).adjusted(1, 1, -1, -1)
        top = self.strip if self.bands else 6
        bottom = 22 if self.bar_labels else 22
        area = QRectF(r.left() + 3, r.top() + top, r.width() - 6, r.height() - top - bottom)
        return r, area

    def _x(self, s):
        _r, a = self._rects()
        return a.left() + (s - self.view_a) / max(1, self.view_b - self.view_a) * a.width()

    def _s(self, x):
        _r, a = self._rects()
        return int(self.view_a + (x - a.left()) / max(1, a.width()) * (self.view_b - self.view_a))

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
        r, area = self._rects()
        paint_glass(p, r, 4)
        if self.cache is None:
            return
        p.save()
        p.setClipRect(r.adjusted(2, 2, -2, -2))
        ruler = QRectF(r.left() + 4, area.bottom() + 1, r.width() - 8, 20)
        if not self.bar_labels:
            _grid_and_ruler(p, area, ruler, self.view_a, self.view_b, self.sr, self._x)
        # section strips
        if self.bands:
            f = K.font(12, 500, 0.8)
            for b in self.bands:
                x0, x1 = self._x(b["start"]), self._x(b["end"])
                if x1 < r.left() or x0 > r.right():
                    continue
                c = QColor(b["color"])
                c.setAlpha(225)
                br = QRectF(x0, r.top() + 4, max(2, x1 - x0), self.strip - 8)
                p.fillRect(br, c)
                p.setPen(QPen(QColor(255, 255, 255, 40), 1))
                p.drawLine(br.topLeft(), br.topRight())
                if x1 - x0 > 60:
                    K.text(p, br, b["name"], f, QColor("#F4EFE8"), Qt.AlignCenter)
        cols = max(8, int(area.width() / 1.4))
        mins, maxs = self.cache.columns(self.view_a, self.view_b, cols)
        gm, gx = self.cache.columns(0, self.n, 256)
        gain = min(_gain(gm, gx), 4.0)
        paint_wave(p, area, mins, maxs, gain, fill=K.pal()["wave_neutral"], edge="#E3E6E8")
        # regions
        tagf = K.font(11, 700, 0.5)
        for i, reg in enumerate(self.regions):
            x0, x1 = self._x(reg["start"]), self._x(reg["end"])
            if x1 < area.left() or x0 > area.right():
                continue
            style = reg.get("style", "user")
            col = QColor(reg.get("color") or (K.pal()["wave_neutral"] if style == "ai" else
                                              WAVE["roll"] if style == "roll" else "#4CC2FF"))
            if style in ("user", "loop", "roll") and not reg.get("color"):
                col = QColor("#E8483A") if style == "user" else col
            fill = QColor(col)
            fill.setAlpha(70 if i == self.selected else 42)
            box = QRectF(x0, area.top(), x1 - x0, area.height())
            p.fillRect(box, fill)
            # tint the waveform inside the region
            p.save()
            p.setClipRect(box)
            paint_wave(p, area, mins, maxs, gain, fill=col.lighter(115).name(), edge=col.lighter(150).name(),
                       center=False)
            p.restore()
            pen = QPen(col, 2.4 if i == self.selected else 1.6)
            if style == "ai":
                pen.setStyle(Qt.DashLine)
            p.setPen(pen)
            p.setBrush(Qt.NoBrush)
            p.drawRect(box.adjusted(0, 0.8, 0, -0.8))
            tag = str(reg.get("tag", ""))
            if tag and x1 - x0 > 16:
                tw = 10 + 7.5 * len(tag)
                tr = QRectF(x0 + 3, area.top() + 4, tw, 17)
                p.fillRect(tr, col)
                K.text(p, tr, tag, tagf, QColor("#0B0B0C"), Qt.AlignCenter)
        for s in self.ticks:
            x = self._x(s)
            if area.left() <= x <= area.right():
                p.setPen(QPen(QColor(WAVE["roll"]), 2.2))
                p.drawLine(QPointF(x, area.bottom() - 9), QPointF(x, area.bottom() - 1))
        if self.bar_labels:
            f = K.font(11.5, 500, 0.6)
            for s, label in self.bar_labels:
                x = self._x(s)
                if r.left() - 2 <= x <= r.right() + 2:
                    p.setPen(QPen(QColor(255, 255, 255, 50), 1))
                    p.drawLine(QPointF(x, area.bottom()), QPointF(x, area.bottom() + 4))
                    K.text(p, QRectF(x - 30, area.bottom() + 3, 60, 18), label, f, QColor("#C9C4BA"),
                           Qt.AlignCenter)
        if self._drag and self._drag[0] == "new":
            x0, x1 = sorted((self._x(self._drag[1]), self._x(self._drag[2])))
            col = QColor("#E8483A")
            fill = QColor(col)
            fill.setAlpha(50)
            p.fillRect(QRectF(x0, area.top(), x1 - x0, area.height()), fill)
            p.setPen(QPen(col, 1.6))
            p.drawRect(QRectF(x0, area.top() + 1, x1 - x0, area.height() - 2))
        p.restore()

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
