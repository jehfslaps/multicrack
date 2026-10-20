"""Shared widgets and helpers for the pages."""
from __future__ import annotations

import numpy as np
from PySide6.QtCore import Qt
from PySide6.QtWidgets import (QComboBox, QFrame, QHBoxLayout, QLabel, QToolButton, QVBoxLayout,
                               QWidget)

from ..core import engines
from ..core.model import LABEL_GROUPS


def label(text="", name=None, wrap=False):
    lb = QLabel(text)
    if name:
        lb.setObjectName(name)
    lb.setWordWrap(wrap)
    return lb


def panel(layout_cls=QVBoxLayout, margins=(16, 14, 16, 14), spacing=10):
    f = QFrame()
    f.setObjectName("panel")
    lay = layout_cls(f)
    lay.setContentsMargins(*margins)
    lay.setSpacing(spacing)
    return f, lay


def hline():
    f = QFrame()
    f.setFixedHeight(1)
    f.setStyleSheet("background: rgba(128,128,128,0.25);")
    return f


def label_combo(current: str, parent=None) -> QComboBox:
    """Editable dropdown of sample types, grouped (custom labels can be typed)."""
    cb = QComboBox(parent)
    cb.setEditable(True)
    cb.setInsertPolicy(QComboBox.NoInsert)
    model = cb.model()
    for group, labels in LABEL_GROUPS:
        cb.addItem(f"— {group} —")
        item = model.item(cb.count() - 1)
        item.setEnabled(False)
        item.setSelectable(False)
        for l in labels:
            cb.addItem(l)
    idx = cb.findText(current)
    if idx < 0:
        cb.addItem(current)
        idx = cb.count() - 1
    cb.setCurrentIndex(idx)
    cb.setMinimumWidth(150)
    return cb


class Segmented(QWidget):
    """A row of toggle buttons where one is selected."""

    def __init__(self, options, current, on_change=None, parent=None):
        super().__init__(parent)
        lay = QHBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(0)
        self.buttons = {}
        self.on_change = on_change
        for o in options:
            b = QToolButton()
            b.setObjectName("seg")
            b.setText(str(o))
            b.setCheckable(True)
            b.setChecked(o == current)
            b.setMinimumHeight(30)
            b.clicked.connect(lambda _c=False, o=o: self.select(o))
            lay.addWidget(b)
            self.buttons[o] = b
        self.value = current

    def select(self, o, emit=True):
        self.value = o
        for k, b in self.buttons.items():
            b.setChecked(k == o)
        if emit and self.on_change:
            self.on_change(o)


def snap_to_sound(stem, s: int) -> int:
    """Move a start point to just before the sound actually begins."""
    an = engines.get_analysis(stem)
    sr = an.sr
    a = max(0, s - int(0.05 * sr))
    b = min(an.n, s + int(0.15 * sr))
    seg = np.abs(an.m[a:b])
    if len(seg) < 16 or seg.max() < an.peak * 10 ** (-60 / 20):
        return s
    k = max(1, int(0.0005 * sr))
    sm = np.convolve(seg, np.ones(k) / k, mode="same")
    p = int(np.argmax(sm))
    below = np.where(sm[:p + 1] < 0.05 * sm[p])[0]
    st = below[-1] if len(below) else 0
    return int(max(0, a + st - int(0.0008 * sr)))


def trim_tail(stem, s: int, e: int) -> int:
    """Pull an end point in to where the sound has died away (keeps reverb tails)."""
    an = engines.get_analysis(stem)
    H = an.HOP_ENV
    env = an.env[s // H:max(s // H + 1, e // H)]
    if not len(env):
        return e
    thr = max(env.max() * 10 ** (-60 / 20), an.floor * 1.5)
    above = np.where(env > thr)[0]
    if not len(above):
        return e
    return int(min(e, s + (above[-1] + 1) * H + int(0.005 * an.sr)))


def fmt_time(samples: int, sr: int) -> str:
    t = samples / float(sr)
    m = int(t // 60)
    return f"{m}:{t - 60 * m:06.3f}"


def fmt_len(samples: int, sr: int) -> str:
    t = samples / float(sr)
    if t >= 60:
        return f"{int(t // 60)}:{int(t % 60):02d}"
    return f"{t:.2f} s" if t < 10 else f"{t:.1f} s"


ALIGN_LEFT = Qt.AlignLeft | Qt.AlignVCenter
