"""Stylesheet for standard Qt controls in the hardware skin (+ generated indicator images)."""
from __future__ import annotations

import os
import tempfile

from PySide6.QtCore import QPointF, QRectF, Qt
from PySide6.QtGui import QColor, QLinearGradient, QPainter, QPainterPath, QPen, QPixmap

from . import core as K

_dir = os.path.join(tempfile.gettempdir(), "MultiCrack", "skin")


def _img(name, size, paint):
    path = os.path.join(_dir, f"{name}.png")
    dpr = 2.0
    pm = QPixmap(int(size[0] * dpr), int(size[1] * dpr))
    pm.fill(Qt.transparent)
    pm.setDevicePixelRatio(dpr)
    p = QPainter(pm)
    p.setRenderHint(QPainter.Antialiasing)
    paint(p, QRectF(0, 0, size[0], size[1]))
    p.end()
    K.save_png(pm, path)
    return path.replace("\\", "/")


def _caret(color, up=False):
    def paint(p, r):
        path = QPainterPath()
        cx, cy = r.center().x(), r.center().y()
        if up:
            path.moveTo(cx - 4, cy + 2)
            path.lineTo(cx + 4, cy + 2)
            path.lineTo(cx, cy - 2.5)
        else:
            path.moveTo(cx - 4, cy - 2)
            path.lineTo(cx + 4, cy - 2)
            path.lineTo(cx, cy + 2.5)
        path.closeSubpath()
        p.setPen(Qt.NoPen)
        p.setBrush(QColor(color))
        p.drawPath(path)
    return paint


def _check(checked: bool):
    def paint(p, r):
        b = r.adjusted(1, 1, -1, -1)
        if checked:
            g = QLinearGradient(b.topLeft(), b.bottomLeft())
            g.setColorAt(0, QColor("#F4F0E8"))
            g.setColorAt(1, QColor("#C9C2B5"))
            p.setBrush(g)
            p.setPen(QPen(QColor("#0E0E0E"), 1))
            p.drawRoundedRect(b, 2.5, 2.5)
            K.draw_icon(p, "check", b.adjusted(2, 2, -2, -2), QColor("#1E1D1B"), 2.3)
        else:
            p.setBrush(QColor("#141517"))
            p.setPen(QPen(QColor("#8A867F"), 1.1))
            p.drawRoundedRect(b, 2.5, 2.5)
    return paint


def _radio(checked: bool):
    def paint(p, r):
        c = r.center()
        rad = r.width() / 2 - 1
        p.setBrush(QColor("#121314"))
        p.setPen(QPen(QColor("#9A968E") if not checked else QColor("#E9E5DD"), 1.2))
        p.drawEllipse(c, rad, rad)
        if checked:
            K.led(p, c, rad * 0.55, K.pal()["led_red"], True, glow=False)
    return paint


def _arrow(color, d):
    def paint(p, r):
        path = QPainterPath()
        cx, cy = r.center().x(), r.center().y()
        pts = {"up": [(cx - 3.5, cy + 1.8), (cx + 3.5, cy + 1.8), (cx, cy - 2.2)],
               "down": [(cx - 3.5, cy - 1.8), (cx + 3.5, cy - 1.8), (cx, cy + 2.2)],
               "left": [(cx + 1.8, cy - 3.5), (cx + 1.8, cy + 3.5), (cx - 2.2, cy)],
               "right": [(cx - 1.8, cy - 3.5), (cx - 1.8, cy + 3.5), (cx + 2.2, cy)]}[d]
        path.moveTo(*pts[0])
        for q in pts[1:]:
            path.lineTo(*q)
        path.closeSubpath()
        p.setPen(Qt.NoPen)
        p.setBrush(QColor(color))
        p.drawPath(path)
    return paint


def stylesheet() -> str:
    P = K.pal()
    caret = _img("caret", (12, 12), _caret(P["on_dark"]))
    caret_dim = _img("caret_dim", (12, 12), _caret("#6D6A65"))
    chk_on = _img("check_on", (16, 16), _check(True))
    chk_off = _img("check_off", (16, 16), _check(False))
    rad_on = _img("radio_on_" + P["name"], (16, 16), _radio(True))
    rad_off = _img("radio_off", (16, 16), _radio(False))
    a_up = _img("arr_up", (12, 12), _arrow("#B8B3AA", "up"))
    a_dn = _img("arr_dn", (12, 12), _arrow("#B8B3AA", "down"))
    a_lf = _img("arr_lf", (12, 12), _arrow("#B8B3AA", "left"))
    a_rt = _img("arr_rt", (12, 12), _arrow("#B8B3AA", "right"))
    F = K.FAMILY
    return f"""
* {{ font-family: "{F}"; }}
QWidget {{ color: {P['on_dark']}; }}
QToolTip {{ background: #1A1B1D; color: {P['on_dark']}; border: 1px solid #55585E;
    padding: 5px 8px; font-size: 12px; }}

QLineEdit, QDoubleSpinBox, QSpinBox {{
    background: {P['field']}; border: 1px solid {P['field_edge']}; border-radius: 3px;
    padding: 5px 9px; color: {P['on_dark']}; font-size: 14px; min-height: 22px;
    selection-background-color: {P['red']}; selection-color: #FFFFFF; }}
QLineEdit:focus, QDoubleSpinBox:focus {{ border: 1px solid {P['field_focus']}; }}
QLineEdit:disabled {{ color: #6D6A65; }}
QAbstractSpinBox::up-button, QAbstractSpinBox::down-button {{ width: 0px; border: none;
    subcontrol-origin: border; }}
QAbstractSpinBox::up-arrow, QAbstractSpinBox::down-arrow {{ width: 0px; height: 0px; }}
QDoubleSpinBox#lcdbox {{ background: #0E0F10; border: 1px solid #3A3D42; color: {P['glass_text']};
    font-size: 13px; padding: 3px 4px; }}

QComboBox {{ background: {P['field']}; border: 1px solid {P['field_edge']}; border-radius: 3px;
    padding: 4px 26px 4px 10px; color: {P['on_dark']}; font-size: 13px; min-height: 20px; }}
QComboBox:hover {{ border: 1px solid #77736C; }}
QComboBox:focus {{ border: 1px solid {P['field_focus']}; }}
QComboBox:disabled {{ color: #6D6A65; }}
QComboBox::drop-down {{ border: none; width: 24px; subcontrol-origin: padding;
    subcontrol-position: center right; }}
QComboBox::down-arrow {{ image: url({caret}); width: 12px; height: 12px; }}
QComboBox::down-arrow:disabled {{ image: url({caret_dim}); }}
QComboBox QLineEdit {{ background: transparent; border: none; padding: 0; font-size: 13px; }}
QComboBox#flat {{ background: transparent; border: 1px solid transparent; padding-left: 4px; }}
QComboBox#flat:hover {{ border: 1px solid #55585E; background: {P['field']}; }}
QComboBox QAbstractItemView {{ background: #1A1B1D; border: 1px solid #4A4D52; outline: none;
    selection-background-color: {P['red']}; selection-color: #FFFFFF; color: {P['on_dark']};
    padding: 4px; font-size: 13px; }}

QCheckBox, QRadioButton {{ spacing: 9px; color: {P['on_dark']}; background: transparent;
    font-size: 13px; }}
QCheckBox::indicator {{ width: 16px; height: 16px; image: url({chk_off}); }}
QCheckBox::indicator:checked {{ image: url({chk_on}); }}
QRadioButton::indicator {{ width: 16px; height: 16px; image: url({rad_off}); }}
QRadioButton::indicator:checked {{ image: url({rad_on}); }}

QScrollArea {{ background: transparent; border: none; }}
QScrollArea > QWidget > QWidget {{ background: transparent; }}
QScrollBar:vertical {{ background: #121315; width: 16px; margin: 16px 0 16px 0;
    border-left: 1px solid #2E3034; }}
QScrollBar::handle:vertical {{ background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
    stop:0 #4A4D52, stop:1 #393B40); border: 1px solid #1A1B1D; border-radius: 3px;
    min-height: 34px; margin: 1px 2px; }}
QScrollBar::handle:vertical:hover {{ background: #5A5D63; }}
QScrollBar::sub-line:vertical {{ subcontrol-origin: margin; subcontrol-position: top; height: 16px;
    background: #1A1B1D; border: 1px solid #2E3034; image: url({a_up}); }}
QScrollBar::add-line:vertical {{ subcontrol-origin: margin; subcontrol-position: bottom; height: 16px;
    background: #1A1B1D; border: 1px solid #2E3034; image: url({a_dn}); }}
QScrollBar:horizontal {{ background: #121315; height: 14px; margin: 0 14px 0 14px;
    border-top: 1px solid #2E3034; }}
QScrollBar::handle:horizontal {{ background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
    stop:0 #4A4D52, stop:1 #393B40); border: 1px solid #1A1B1D; border-radius: 3px;
    min-width: 34px; margin: 2px 1px; }}
QScrollBar::handle:horizontal:hover {{ background: #5A5D63; }}
QScrollBar::sub-line:horizontal {{ subcontrol-origin: margin; subcontrol-position: left; width: 14px;
    background: #1A1B1D; border: 1px solid #2E3034; image: url({a_lf}); }}
QScrollBar::add-line:horizontal {{ subcontrol-origin: margin; subcontrol-position: right; width: 14px;
    background: #1A1B1D; border: 1px solid #2E3034; image: url({a_rt}); }}
QScrollBar::add-page, QScrollBar::sub-page {{ background: transparent; }}

QTableWidget, QListWidget {{ background: transparent; border: none; gridline-color: transparent;
    color: {P['on_dark']}; font-size: 13px; outline: none; }}
QTableWidget::item {{ border-bottom: 1px solid {P['row_line']}; padding: 0 6px; }}
QTableWidget::item:selected {{ background: {P['row_sel']}; color: {P['on_dark']}; }}
QListWidget::item {{ border-bottom: 1px solid {P['row_line']}; padding: 6px 10px; }}
QListWidget::item:selected {{ background: {P['row_sel']}; color: {P['on_dark']};
    border-left: 3px solid {P['red_hi']}; }}
QHeaderView {{ background: transparent; border: none; }}
QHeaderView::section {{ background: transparent; color: {P['header_text']}; border: none;
    border-bottom: 1px solid #3A3D42; padding: 8px 6px; font-size: 11px; font-weight: 600;
    letter-spacing: 1px; text-transform: uppercase; }}
QTableCornerButton::section {{ background: transparent; border: none; }}

QMenu {{ background: #1A1B1D; border: 1px solid #4A4D52; padding: 6px; color: {P['on_dark']}; }}
QMenu::item {{ padding: 7px 26px 7px 14px; border-radius: 3px; font-size: 13px; }}
QMenu::item:selected {{ background: {P['red']}; color: #FFFFFF; }}
QMenu::separator {{ height: 1px; background: #3A3D42; margin: 5px 6px; }}

QSlider::groove:horizontal {{ height: 4px; background: #0E0F10; border: 1px solid #3A3D42;
    border-radius: 2px; }}
QSlider::sub-page:horizontal {{ background: #5A5D63; border-radius: 2px; }}
QSlider::handle:horizontal {{ width: 14px; height: 14px; margin: -6px 0; border-radius: 7px;
    background: qradialgradient(cx:0.4, cy:0.35, radius:0.8, fx:0.35, fy:0.3,
    stop:0 #FFFFFF, stop:0.5 #D9D3C8, stop:1 #8E877B); border: 1px solid #1A1A1A; }}
"""
