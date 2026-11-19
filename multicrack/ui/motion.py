"""Fluid motion: damped springs instead of timers and easing curves.

Every value that moves (a button going down, an LED lighting, the waveform zooming, a page
changing) is a Spring. Setting a new target redirects it from where it is now, at its current
speed, so nothing ever jumps and every motion can be interrupted. One shared clock drives all
springs and only runs while something is moving.

Presets (response = roughly how long it takes to settle, damping 1 = no overshoot):
    UI      0.38 s / 0.78   panels, knobs, values
    PRESS   0.10 s / 1.0    button press
    FADE    0.475 s / 1.0   fades and quiet transitions
    SCROLL  0.42 s / 1.0    list scrolling
"""
from __future__ import annotations

import math
import os
import sys
import time
import weakref

from PySide6.QtCore import QObject, QTimer, Qt

UI = (0.38, 0.78)
PRESS = (0.10, 1.0)
FADE = (0.475, 1.0)
SCROLL = (0.42, 1.0)

_STEP = 1.0 / 240.0          # integrate at 240 Hz, whatever the screen rate


def reduced_motion() -> bool:
    """Windows "Animation effects" off (Settings > Accessibility > Visual effects), or
    XENAKIS_REDUCED_MOTION=1. Then everything goes straight to where it's going."""
    if os.environ.get("XENAKIS_REDUCED_MOTION", "") not in ("", "0"):
        return True
    if sys.platform == "win32":
        try:
            import ctypes
            on = ctypes.c_int(1)
            # SPI_GETCLIENTAREAANIMATION
            if ctypes.windll.user32.SystemParametersInfoW(0x1042, 0, ctypes.byref(on), 0):
                return not on.value
        except Exception:
            pass
    return False


class _Clock(QObject):
    """Ticks every spring that's moving; stops when they've all settled."""

    def __init__(self):
        super().__init__()
        self.timer = QTimer(self)
        self.timer.setTimerType(Qt.PreciseTimer)
        self.timer.setInterval(8)            # ~120 fps; Qt syncs repaints to the screen
        self.timer.timeout.connect(self._tick)
        self.live: list = []
        self.last = 0.0
        self.reduced = reduced_motion()
        self._checked = time.monotonic()

    def add(self, s):
        if s not in self.live:
            self.live.append(s)
        if not self.timer.isActive():
            self.last = time.monotonic()
            self.timer.start()

    def _tick(self):
        now = time.monotonic()
        dt = min(0.05, now - self.last)      # a stall never turns into a jump
        self.last = now
        if now - self._checked > 2.0:        # the user may change the Windows setting
            self._checked = now
            self.reduced = reduced_motion()
        for s in list(self.live):
            try:
                done = s._advance(dt)
            except RuntimeError:             # its widget was deleted
                done = True
            if done:
                self.live.remove(s)
        if not self.live:
            self.timer.stop()


_clock: _Clock | None = None


def clock() -> _Clock:
    global _clock
    if _clock is None:
        _clock = _Clock()
    return _clock


class Spring:
    """A value that moves to its target like a weight on a spring.

    `on_change(value)` (or `widget.update()`) is called on every frame while it moves."""

    def __init__(self, value=0.0, preset=UI, widget=None, on_change=None, eps=None):
        self.value = float(value)
        self.target = float(value)
        self.velocity = 0.0
        self.response, self.damping = preset
        self._widget = weakref.ref(widget) if widget is not None else None
        self.on_change = on_change
        self.eps = eps            # "close enough" (defaults to a thousandth of the move)
        self._acc = 0.0
        self._span = 1.0

    @property
    def moving(self):
        return self.value != self.target or self.velocity != 0.0

    def to(self, target, preset=None):
        """Head for `target` from wherever it is now, keeping its speed."""
        target = float(target)
        if preset is not None:
            self.response, self.damping = preset
        if target == self.target and not self.moving:
            return
        self._span = max(abs(target - self.value), abs(self.velocity) * self.response, 1e-9)
        self.target = target
        if clock().reduced:
            self.jump(target)
            return
        clock().add(self)

    def jump(self, value):
        """Go there now (no motion)."""
        self.value = self.target = float(value)
        self.velocity = 0.0
        self._changed()

    def nudge(self, velocity):
        """Add speed (a fling)."""
        self.velocity += velocity
        self._span = max(self._span, abs(velocity) * self.response)
        if clock().reduced:
            return
        clock().add(self)

    def _changed(self):
        if self.on_change is not None:
            self.on_change(self.value)
        if self._widget is not None:
            w = self._widget()
            if w is not None:
                w.update()

    def _advance(self, dt) -> bool:
        w = 2 * math.pi / max(1e-3, self.response)
        z = self.damping
        self._acc += dt
        while self._acc >= _STEP:
            self._acc -= _STEP
            a = -w * w * (self.value - self.target) - 2 * z * w * self.velocity
            self.velocity += a * _STEP
            self.value += self.velocity * _STEP
        eps = self.eps if self.eps is not None else self._span * 1e-3
        if abs(self.value - self.target) < eps and abs(self.velocity) < eps * w:
            self.value, self.velocity = self.target, 0.0
            self._changed()
            return True
        self._changed()
        return False


def move(spring: Spring, widget, value):
    """Animate when the widget is on screen; otherwise just be there (no motion at start-up
    or on rows that are being built)."""
    if widget.isVisible():
        spring.to(value)
    else:
        spring.jump(value)


def mix(a, b, t):
    return a + (b - a) * t


def mix_color(a, b, t):
    from PySide6.QtGui import QColor
    a, b = QColor(a), QColor(b)
    t = max(0.0, min(1.0, t))
    return QColor(round(mix(a.red(), b.red(), t)), round(mix(a.green(), b.green(), t)),
                  round(mix(a.blue(), b.blue(), t)), round(mix(a.alpha(), b.alpha(), t)))


def _snapshot(widget):
    """The widget and its children on a transparent background (grab() would fill it)."""
    from PySide6.QtCore import QPoint
    from PySide6.QtGui import QPixmap, QRegion
    from PySide6.QtWidgets import QWidget
    dpr = widget.devicePixelRatioF()
    pix = QPixmap(max(1, round(widget.width() * dpr)), max(1, round(widget.height() * dpr)))
    pix.setDevicePixelRatio(dpr)
    pix.fill(Qt.transparent)
    widget.render(pix, QPoint(), QRegion(), QWidget.RenderFlag.DrawChildren)
    return pix


class PageFader:
    """Page changes: the new page fades in on top while the page you leave drifts a little the
    other way underneath and fades out behind it, so the screen never washes out mid-change.
    Interrupting it (clicking another page mid-way) carries on from what's on screen.
    Everything stays inside the page area."""

    SLIDE = 26.0

    def __init__(self, stack):
        from PySide6.QtWidgets import QGraphicsOpacityEffect, QWidget

        self.stack = stack
        fader = self

        class _Layer(QWidget):
            def paintEvent(self, _e):
                from PySide6.QtGui import QPainter
                p = QPainter(self)
                for pix, alpha, off, _src in fader.layers:
                    a = max(0.0, min(1.0, alpha.value))
                    if a > 0.002:
                        p.setOpacity(a)
                        p.drawPixmap(round(off.value), 0, pix)

        self.overlay = _Layer(stack.parentWidget())
        self.overlay.setAttribute(Qt.WA_TransparentForMouseEvents)
        self.overlay.hide()
        self.effect = None
        self.layers: list = []
        self.live = Spring(1.0, (0.30, 1.0), on_change=self._live_changed)
        self._QEffect = QGraphicsOpacityEffect

    def _live_changed(self, v):
        if self.effect is not None:
            self.effect.setOpacity(max(0.0, min(1.0, v)))
        self.overlay.update()
        self._maybe_done()

    def _maybe_done(self):
        if getattr(self, "_starting", False):
            return
        if self.live.moving or any(a.moving or o.moving for _, a, o, _s in self.layers):
            return
        self.layers.clear()
        self.overlay.hide()
        if self.effect is not None:
            self.stack.setGraphicsEffect(None)    # deletes it
            self.effect = None

    def go(self, index):
        st = self.stack
        old = st.currentIndex()
        if index == old:
            return
        if clock().reduced or not st.isVisible():
            st.setCurrentIndex(index)
            return
        # what's leaving: the current page as it looks now, at the opacity it has now
        leaving = _snapshot(st.currentWidget())
        # going back to a page that is still drifting away: bring its picture back into line
        for _pix, _a, off, src in self.layers:
            if src == index:
                off.to(0.0)
        start_alpha = self.live.value if self.effect is not None else 1.0
        direction = 1.0 if index > old else -1.0
        # the old page stays underneath while the new one arrives, then fades out behind it
        a = Spring(start_alpha, (0.55, 1.0), on_change=lambda _v: (self.overlay.update(), self._maybe_done()))
        o = Spring(0.0, UI, on_change=lambda _v: self.overlay.update())
        self.layers.append((leaving, a, o, old))
        del self.layers[:-3]
        st.setCurrentIndex(index)
        self.overlay.setGeometry(st.geometry())
        self.overlay.stackUnder(st)
        self.overlay.show()
        if self.effect is None:
            self.effect = self._QEffect(st)
            st.setGraphicsEffect(self.effect)
        self._starting = True
        self.live.jump(0.0)
        self.effect.setOpacity(0.0)
        a.to(0.0)
        o.to(-direction * self.SLIDE)
        self.live.to(1.0)
        self._starting = False


class SmoothWheel(QObject):
    """Mouse-wheel scrolling that glides to a stop instead of jumping a notch at a time, with
    quick turns adding up. Trackpads (which scroll by pixels) stay 1:1 with your fingers."""

    def __init__(self, scroll_area, step=120):
        super().__init__(scroll_area)
        self.area = scroll_area
        self.bar = scroll_area.verticalScrollBar()
        self.step = step
        self.spring = Spring(self.bar.value(), SCROLL, on_change=self._apply, eps=0.5)
        self._setting = False
        scroll_area.viewport().installEventFilter(self)
        self.bar.valueChanged.connect(self._bar_moved)

    def _apply(self, v):
        self._setting = True
        self.bar.setValue(int(round(v)))
        self._setting = False

    def _bar_moved(self, v):
        # moved some other way (dragging the bar, keys, ensureVisible): follow it, no glide
        if not self._setting:
            self.spring.jump(v)

    def eventFilter(self, obj, e):
        from PySide6.QtCore import QEvent
        if e.type() != QEvent.Wheel or e.modifiers() & (Qt.ControlModifier | Qt.ShiftModifier):
            return False
        if not e.pixelDelta().isNull() or clock().reduced:
            self.spring.jump(self.bar.value())
            return False                       # trackpad: Qt scrolls it 1:1
        dy = e.angleDelta().y()
        if dy == 0:
            return False
        lo, hi = self.bar.minimum(), self.bar.maximum()
        base = self.spring.target if self.spring.moving else self.bar.value()
        target = max(lo, min(hi, base - dy / 120 * self.step))
        self.spring.to(target)
        return True
