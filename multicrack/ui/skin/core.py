"""Xenakis hardware skin: palettes, fonts, generated metal textures and the drawing kit.

Everything is painted in code (no bitmap assets besides the font), so it stays sharp at any
Windows scaling. Textures are generated once with numpy and tiled."""
from __future__ import annotations

import math
import os
import sys

import numpy as np
from PySide6.QtCore import QPointF, QRectF, Qt
from PySide6.QtGui import (QBrush, QColor, QConicalGradient, QFont, QFontDatabase, QImage,
                           QLinearGradient, QPainter, QPainterPath, QPen, QPixmap,
                           QRadialGradient, QTransform)
from PySide6.QtWidgets import QApplication

# ------------------------------------------------------------------ palettes
_COMMON = dict(
    module="#222326", module_hi="#33353A", module_lo="#0E0F10", module_edge="#3B3D42",
    outline="#9C3F2E", wire="#B4473A", wire_node="#C8553F",
    on_dark="#E9E5DD", on_dark_muted="#9D9890", on_dark_dim="#68645E",
    field="#161719", field_edge="#3C3E43", field_focus="#C2513D",
    glass="#121416", glass_grid="#22262A", glass_text="#E9E5DD",
    led_red="#FF3B2F", led_green="#4BE07A", led_amber="#FFB23D",
    red="#B8382A", red_hi="#D44A36", red_lo="#7F2117",
    key="#E7E2D8", key_hi="#F6F2EA", key_lo="#BDB5A7", key_text="#26262A",
    ok="#7BD88F", warn="#E8644E", info="#E9E5DD",
    wave="#46D18A", wave_edge="#9BF0C2", wave_dim="#6E7378", wave_neutral="#B9BDC1",
    groove=["#B8473A", "#3F73B5", "#8A5CC2", "#C9902E"], roll="#E8C547",
    row_sel="#2C2424", row_hover="#26272A", row_line="#2D2F33", header_text="#A9A49C",
)
LIGHT = dict(_COMMON, name="light",
             chassis="#D8D3C9", chassis_hi="#ECE8E0", chassis_lo="#A9A194", chassis_text="#2B2A27",
             chassis_muted="#625D55", plate="#E4DFD6", plate_text="#26252A", grime=(70, 58, 44))
DARK = dict(_COMMON, name="dark",
            chassis="#2B2C2F", chassis_hi="#3D3F43", chassis_lo="#141516", chassis_text="#E2DED6",
            chassis_muted="#9B968E", plate="#33353A", plate_text="#E9E5DD", grime=(0, 0, 0),
            module="#1D1E21", module_hi="#2E3034")

_mode = {"p": LIGHT}


def pal() -> dict:
    return _mode["p"]


def set_mode(name: str):
    _mode["p"] = DARK if name == "dark" else LIGHT


def C(key: str, alpha: int | None = None) -> QColor:
    c = QColor(pal()[key])
    if alpha is not None:
        c.setAlpha(alpha)
    return c


# --------------------------------------------------------------------- fonts
FAMILY = "IBM Plex Mono"
_fonts_loaded = {"done": False}


def _asset_root():
    roots = []
    if getattr(sys, "_MEIPASS", None):
        roots.append(sys._MEIPASS)
    here = os.path.dirname(os.path.abspath(__file__))
    roots.append(os.path.normpath(os.path.join(here, "..", "..", "..")))
    for r in roots:
        if os.path.isdir(os.path.join(r, "assets", "fonts")):
            return r
    return roots[-1]


def load_fonts():
    global FAMILY
    if _fonts_loaded["done"]:
        return
    d = os.path.join(_asset_root(), "assets", "fonts")
    fam = None
    if os.path.isdir(d):
        for f in sorted(os.listdir(d)):
            if f.lower().endswith(".ttf"):
                i = QFontDatabase.addApplicationFont(os.path.join(d, f))
                names = QFontDatabase.applicationFontFamilies(i) if i >= 0 else []
                if names and fam is None:
                    fam = names[0]
    FAMILY = fam or "Consolas"
    _fonts_loaded["done"] = True


def font(px: float = 13, weight: int = 400, spacing: float = 0.0, caps=False) -> QFont:
    f = QFont(FAMILY)
    f.setPixelSize(max(6, int(round(px))))
    f.setWeight(QFont.Weight(weight))
    if spacing:
        f.setLetterSpacing(QFont.AbsoluteSpacing, spacing)
    if caps:
        f.setCapitalization(QFont.AllUppercase)
    f.setHintingPreference(QFont.PreferNoHinting)
    f.setStyleStrategy(QFont.PreferAntialias)
    return f


# ------------------------------------------------------------------ textures
def _periodic_noise(n, scale, rng):
    """Tileable smooth noise in [-1, 1] (white noise low-passed in frequency space)."""
    w = rng.standard_normal((n, n))
    F = np.fft.rfft2(w)
    fy = np.fft.fftfreq(n)[:, None]
    fx = np.fft.rfftfreq(n)[None, :]
    r = np.sqrt(fx ** 2 + fy ** 2) * n
    F *= np.exp(-(r / max(scale, 0.5)) ** 2)
    out = np.fft.irfft2(F, s=(n, n))
    out -= out.mean()
    m = np.abs(out).max() or 1.0
    return out / m


def _to_image(rgb: np.ndarray) -> QImage:
    h, w, _ = rgb.shape
    a = np.empty((h, w, 4), np.uint8)
    a[..., :3] = np.clip(rgb, 0, 255).astype(np.uint8)[..., ::-1]   # BGR
    a[..., 3] = 255
    img = QImage(a.data, w, h, 4 * w, QImage.Format_ARGB32)
    return img.copy()


def _draw_scratches(rgb, rng, count, color, alpha, n):
    """Thin faint scratches that wrap around the tile edges."""
    for _ in range(count):
        x0, y0 = rng.uniform(0, n, 2)
        ang = rng.uniform(0, math.pi)
        length = rng.uniform(n * 0.03, n * 0.16)
        steps = int(length * 2)
        t = np.linspace(0, 1, steps)
        bend = rng.uniform(-0.06, 0.06)
        xs = (x0 + np.cos(ang) * length * t + np.sin(ang) * bend * length * t ** 2) % n
        ys = (y0 + np.sin(ang) * length * t - np.cos(ang) * bend * length * t ** 2) % n
        fade = np.sin(np.pi * t) * alpha * rng.uniform(0.4, 1.0)
        xi, yi = xs.astype(int), ys.astype(int)
        for c in range(3):
            rgb[yi, xi, c] = rgb[yi, xi, c] * (1 - fade) + color[c] * fade


def _gen_texture(kind: str, n: int, seed: int) -> QImage:
    rng = np.random.default_rng(seed)
    p = pal()
    if kind == "bone":
        base = np.array(QColor(LIGHT["chassis"]).getRgb()[:3], float)
        mott = _periodic_noise(n, 3.5, rng) * 7 + _periodic_noise(n, 14, rng) * 3.5
        grain = rng.standard_normal((n, n)) * 4.2
        grime = np.clip(_periodic_noise(n, 5, rng) - 0.35, 0, None) * 26
        lum = mott + grain - grime
        rgb = base[None, None, :] + lum[..., None] * np.array([1.0, 0.97, 0.9])
        sp = rng.random((n, n)) < 0.0018
        rgb[sp] -= rng.uniform(18, 45, (sp.sum(), 1))
        _draw_scratches(rgb, rng, 26, (150, 142, 130), 0.35, n)
        _draw_scratches(rgb, rng, 14, (246, 243, 236), 0.30, n)
    elif kind == "graphite":
        base = np.array(QColor(DARK["chassis"]).getRgb()[:3], float)
        mott = _periodic_noise(n, 3.5, rng) * 4.5 + _periodic_noise(n, 16, rng) * 2.5
        grain = rng.standard_normal((n, n)) * 3.2
        brush = np.repeat(rng.standard_normal((n, 1)) * 1.6, n, axis=1)
        lum = mott + grain + brush
        rgb = base[None, None, :] + lum[..., None] * np.array([1.0, 1.0, 1.04])
        _draw_scratches(rgb, rng, 18, (80, 82, 88), 0.35, n)
    else:   # "module": fine dark powder coat
        base = np.array(QColor(p["module"]).getRgb()[:3], float)
        mott = _periodic_noise(n, 4, rng) * 3.2
        grain = rng.standard_normal((n, n)) * 2.6
        lum = mott + grain
        rgb = base[None, None, :] + lum[..., None]
        _draw_scratches(rgb, rng, 10, (64, 66, 72), 0.25, n)
    return _to_image(rgb)


_tex_cache: dict = {}


def texture(kind: str) -> QPixmap:
    """Tileable texture pixmap for the current mode and screen scaling."""
    dpr = 1.0
    app = QApplication.instance()
    if app is not None and app.primaryScreen() is not None:
        dpr = app.primaryScreen().devicePixelRatio()
    key = (kind, pal()["name"] if kind == "module" else "", round(dpr, 2))
    pm = _tex_cache.get(key)
    if pm is None:
        n = int(384 * dpr)
        img = _gen_texture(kind, n, {"bone": 11, "graphite": 23, "module": 37}[kind])
        pm = QPixmap.fromImage(img)
        pm.setDevicePixelRatio(dpr)
        _tex_cache[key] = pm
    return pm


def chassis_texture() -> QPixmap:
    return texture("graphite" if pal()["name"] == "dark" else "bone")


# --------------------------------------------------------------- draw kit
def rrect(r: QRectF, rad: float) -> QPainterPath:
    p = QPainterPath()
    p.addRoundedRect(r, rad, rad)
    return p


def soft_shadow(p: QPainter, r: QRectF, rad: float, depth: float = 6, alpha: int = 70,
                dy: float = 2.0):
    """Cheap soft drop shadow: stacked rounded rects."""
    p.save()
    p.setPen(Qt.NoPen)
    steps = int(max(2, depth))
    for i in range(steps, 0, -1):
        a = int(alpha * (1 - i / (steps + 1)) ** 2 / steps * 2.2)
        p.setBrush(QColor(0, 0, 0, a))
        g = i * 0.9
        p.drawRoundedRect(r.adjusted(-g, -g + dy, g, g + dy), rad + g, rad + g)
    p.restore()


def fill_textured(p: QPainter, path: QPainterPath, pm: QPixmap, origin=QPointF(0, 0),
                  tint: QColor | None = None):
    br = QBrush(pm)
    br.setTransform(QTransform.fromTranslate(origin.x(), origin.y()))
    p.fillPath(path, br)
    if tint is not None:
        p.fillPath(path, tint)


def bevel_edges(p: QPainter, r: QRectF, rad: float, hi: QColor, lo: QColor, w: float = 1.0):
    """Light top-left / dark bottom-right edge, like a machined plate."""
    p.save()
    p.setBrush(Qt.NoBrush)
    g = QLinearGradient(r.topLeft(), r.bottomRight())
    g.setColorAt(0.0, hi)
    g.setColorAt(0.45, QColor(hi.red(), hi.green(), hi.blue(), 0))
    g.setColorAt(0.55, QColor(lo.red(), lo.green(), lo.blue(), 0))
    g.setColorAt(1.0, lo)
    p.setPen(QPen(QBrush(g), w))
    p.drawRoundedRect(r.adjusted(w / 2, w / 2, -w / 2, -w / 2), rad, rad)
    p.restore()


def inner_shadow(p: QPainter, r: QRectF, rad: float, strength: int = 120, size: float = 7):
    """Recessed look: darkness falling from the top edge inside a shape."""
    p.save()
    p.setClipPath(rrect(r, rad))
    g = QLinearGradient(r.topLeft(), QPointF(r.left(), r.top() + size))
    g.setColorAt(0, QColor(0, 0, 0, strength))
    g.setColorAt(1, QColor(0, 0, 0, 0))
    p.fillRect(QRectF(r.left(), r.top(), r.width(), size), g)
    g2 = QLinearGradient(r.topLeft(), QPointF(r.left() + size * 0.7, r.top()))
    g2.setColorAt(0, QColor(0, 0, 0, strength // 2))
    g2.setColorAt(1, QColor(0, 0, 0, 0))
    p.fillRect(QRectF(r.left(), r.top(), size * 0.7, r.height()), g2)
    p.restore()


def screw(p: QPainter, c: QPointF, r: float = 5.0, seed: float = 0.0):
    """Phillips-head screw with a recess shadow and a random-looking slot angle."""
    p.save()
    p.setRenderHint(QPainter.Antialiasing)
    p.setPen(Qt.NoPen)
    p.setBrush(QColor(0, 0, 0, 90))
    p.drawEllipse(QPointF(c.x() + 0.4, c.y() + 0.9), r + 1.3, r + 1.3)
    g = QRadialGradient(QPointF(c.x() - r * 0.35, c.y() - r * 0.45), r * 1.6)
    g.setColorAt(0, QColor("#F2F1EE"))
    g.setColorAt(0.45, QColor("#B7B4AE"))
    g.setColorAt(1, QColor("#5F5D59"))
    p.setBrush(g)
    p.setPen(QPen(QColor(30, 30, 30, 160), 0.8))
    p.drawEllipse(c, r, r)
    ang = (math.sin(c.x() * 12.9898 + c.y() * 78.233 + seed) * 43758.5453) % 180
    p.translate(c)
    p.rotate(ang)
    p.setPen(QPen(QColor(40, 38, 36, 230), max(1.0, r * 0.28), Qt.SolidLine, Qt.RoundCap))
    k = r * 0.58
    p.drawLine(QPointF(-k, 0), QPointF(k, 0))
    p.drawLine(QPointF(0, -k), QPointF(0, k))
    p.setPen(QPen(QColor(255, 255, 255, 70), 0.7))
    p.drawLine(QPointF(-k + 0.6, 0.9), QPointF(k - 0.6, 0.9))
    p.restore()


def corner_screws(p: QPainter, r: QRectF, inset: float = 9, rad: float = 4.6):
    for x, y in ((r.left() + inset, r.top() + inset), (r.right() - inset, r.top() + inset),
                 (r.left() + inset, r.bottom() - inset), (r.right() - inset, r.bottom() - inset)):
        screw(p, QPointF(x, y), rad)


def led(p: QPainter, c: QPointF, r: float, color: str | QColor, on: bool, glow: bool = True,
        glow_scale: float = 3.6):
    """Jewel LED with bezel. `color` is the lit color."""
    p.save()
    p.setRenderHint(QPainter.Antialiasing)
    col = QColor(color)
    # bezel
    bz = QRadialGradient(QPointF(c.x(), c.y() - r * 0.4), r * 2.0)
    bz.setColorAt(0, QColor("#4A4C50"))
    bz.setColorAt(1, QColor("#0B0B0C"))
    p.setPen(Qt.NoPen)
    p.setBrush(bz)
    p.drawEllipse(c, r * 1.45, r * 1.45)
    if on and glow:
        gl = QRadialGradient(c, r * glow_scale)
        g0 = QColor(col)
        g0.setAlpha(120)
        gl.setColorAt(0, g0)
        g1 = QColor(col)
        g1.setAlpha(0)
        gl.setColorAt(1, g1)
        p.setBrush(gl)
        p.drawEllipse(c, r * glow_scale, r * glow_scale)
    lens = QRadialGradient(QPointF(c.x() - r * 0.3, c.y() - r * 0.35), r * 1.3)
    if on:
        lens.setColorAt(0, QColor(255, 255, 255))
        lens.setColorAt(0.25, col.lighter(130))
        lens.setColorAt(0.8, col)
        lens.setColorAt(1, col.darker(170))
    else:
        dim = QColor(col).darker(520)
        lens.setColorAt(0, QColor(dim).lighter(240))
        lens.setColorAt(0.5, dim)
        lens.setColorAt(1, QColor(8, 8, 8))
    p.setBrush(lens)
    p.drawEllipse(c, r, r)
    p.setBrush(QColor(255, 255, 255, 150 if on else 60))
    p.drawEllipse(QPointF(c.x() - r * 0.32, c.y() - r * 0.38), r * 0.28, r * 0.2)
    p.restore()


def hairline_frame(p: QPainter, r: QRectF, rad: float, color: QColor, w: float = 1.0):
    p.save()
    p.setBrush(Qt.NoBrush)
    p.setPen(QPen(color, w))
    p.drawRoundedRect(r.adjusted(w / 2, w / 2, -w / 2, -w / 2), rad, rad)
    p.restore()


def text(p: QPainter, r: QRectF, s: str, f: QFont, color: QColor,
         align=Qt.AlignLeft | Qt.AlignVCenter, elide=False):
    p.save()
    p.setFont(f)
    p.setPen(color)
    if elide:
        s = p.fontMetrics().elidedText(s, Qt.ElideRight, int(r.width()))
    p.drawText(r, int(align), s)
    p.restore()


def node(p: QPainter, c: QPointF, r: float = 3.2, color: QColor | None = None, filled=False):
    p.save()
    col = color or C("wire")
    p.setPen(QPen(col, 1.2))
    p.setBrush(col if filled else C("chassis"))
    p.drawEllipse(c, r, r)
    p.restore()


# -------------------------------------------------------------------- knob
_knob_cache: dict = {}


def knob_body(size: int, dpr: float) -> QPixmap:
    """Cream knurled knob seen from above, rendered once per size."""
    key = (size, round(dpr, 2))
    if key in _knob_cache:
        return _knob_cache[key]
    s = int(size * dpr)
    pm = QPixmap(s, s)
    pm.fill(Qt.transparent)
    p = QPainter(pm)
    p.setRenderHint(QPainter.Antialiasing)
    c = QPointF(s / 2, s / 2)
    R = s / 2 - 1.5 * dpr
    # drop shadow
    for i in range(6, 0, -1):
        p.setPen(Qt.NoPen)
        p.setBrush(QColor(0, 0, 0, 18))
        p.drawEllipse(QPointF(c.x() + 0.6 * dpr, c.y() + i * 0.45 * dpr), R - 1 + i * 0.4, R - 1 + i * 0.4)
    # knurled skirt
    skirt = QConicalGradient(c, 135)
    for t, col in ((0.0, "#F4F0E8"), (0.18, "#CFC8BB"), (0.38, "#8F887C"), (0.55, "#A39C90"),
                   (0.75, "#DCD6CB"), (1.0, "#F4F0E8")):
        skirt.setColorAt(t, QColor(col))
    p.setBrush(skirt)
    p.setPen(QPen(QColor(40, 36, 30, 170), 0.9 * dpr))
    p.drawEllipse(c, R, R)
    n_ridges = 36
    for k in range(n_ridges):
        a = 2 * math.pi * k / n_ridges
        light = 0.5 + 0.5 * math.cos(a + math.pi * 0.75)
        p.setPen(QPen(QColor(60, 54, 46, int(40 + 70 * (1 - light))), 0.9 * dpr))
        r0, r1 = R * 0.8, R - 0.6 * dpr
        p.drawLine(QPointF(c.x() + math.cos(a) * r0, c.y() + math.sin(a) * r0),
                   QPointF(c.x() + math.cos(a) * r1, c.y() + math.sin(a) * r1))
    # cap
    Rc = R * 0.76
    cap = QRadialGradient(QPointF(c.x() - Rc * 0.35, c.y() - Rc * 0.45), Rc * 1.7)
    cap.setColorAt(0, QColor("#FBF8F2"))
    cap.setColorAt(0.5, QColor("#E3DDD2"))
    cap.setColorAt(1, QColor("#A9A295"))
    p.setBrush(cap)
    p.setPen(QPen(QColor(255, 255, 255, 120), 0.8 * dpr))
    p.drawEllipse(c, Rc, Rc)
    rim = QPen(QColor(70, 64, 55, 120), 0.8 * dpr)
    p.setPen(rim)
    p.setBrush(Qt.NoBrush)
    p.drawEllipse(c, Rc + 0.6 * dpr, Rc + 0.6 * dpr)
    # subtle concentric machining
    for k in range(4):
        p.setPen(QPen(QColor(255, 255, 255, 18), 0.6 * dpr))
        p.drawEllipse(c, Rc * (0.25 + 0.17 * k), Rc * (0.25 + 0.17 * k))
    p.end()
    pm.setDevicePixelRatio(dpr)
    _knob_cache[key] = pm
    return pm


def draw_knob(p: QPainter, c: QPointF, size: float, frac: float, dpr: float, ticks=True,
              tick_color: QColor | None = None):
    """Knob at center c; frac 0..1 maps to −135°..+135°."""
    p.save()
    p.setRenderHint(QPainter.Antialiasing)
    R = size / 2
    if ticks:
        tc = tick_color or C("on_dark_muted")
        for k in range(11):
            a = math.radians(-225 + 27 * k)
            r0, r1 = R + 3.0, R + (6.0 if k in (0, 5, 10) else 4.6)
            p.setPen(QPen(tc, 1.1 if k in (0, 5, 10) else 0.8))
            p.drawLine(QPointF(c.x() + math.cos(a) * r0, c.y() + math.sin(a) * r0),
                       QPointF(c.x() + math.cos(a) * r1, c.y() + math.sin(a) * r1))
    pm = knob_body(int(size), dpr)
    p.drawPixmap(QPointF(c.x() - size / 2, c.y() - size / 2), pm)
    ang = math.radians(-225 + 270 * max(0.0, min(1.0, frac)))
    Rc = R * 0.76
    p.setPen(QPen(QColor("#1C1B1A"), max(1.6, size * 0.055), Qt.SolidLine, Qt.RoundCap))
    p.drawLine(QPointF(c.x() + math.cos(ang) * Rc * 0.28, c.y() + math.sin(ang) * Rc * 0.28),
               QPointF(c.x() + math.cos(ang) * Rc * 0.94, c.y() + math.sin(ang) * Rc * 0.94))
    p.restore()


# -------------------------------------------------------------------- icons
def icon_path(name: str, s: float) -> QPainterPath:
    """Simple line icons as paths in an s×s box (stroke them)."""
    P = QPainterPath()
    k = s / 24.0

    def pt(x, y):
        return QPointF(x * k, y * k)

    if name == "play":
        P.moveTo(pt(8, 5.5))
        P.lineTo(pt(19, 12))
        P.lineTo(pt(8, 18.5))
        P.closeSubpath()
    elif name == "stop":
        P.addRoundedRect(QRectF(pt(6.5, 6.5), pt(17.5, 17.5)), 1.5 * k, 1.5 * k)
    elif name == "undo":
        P.moveTo(pt(9, 5))
        P.lineTo(pt(4.5, 9.5))
        P.lineTo(pt(9, 14))
        P.moveTo(pt(4.5, 9.5))
        P.lineTo(pt(14, 9.5))
        P.cubicTo(pt(22, 9.5), pt(22, 20), pt(14, 20))
        P.lineTo(pt(9, 20))
    elif name == "redo":
        P.moveTo(pt(15, 5))
        P.lineTo(pt(19.5, 9.5))
        P.lineTo(pt(15, 14))
        P.moveTo(pt(19.5, 9.5))
        P.lineTo(pt(10, 9.5))
        P.cubicTo(pt(2, 9.5), pt(2, 20), pt(10, 20))
        P.lineTo(pt(15, 20))
    elif name == "check":
        P.moveTo(pt(4.5, 12.5))
        P.lineTo(pt(9.5, 17.5))
        P.lineTo(pt(19.5, 6.5))
    elif name == "export":
        P.moveTo(pt(12, 15))
        P.lineTo(pt(12, 3.5))
        P.moveTo(pt(7.5, 8))
        P.lineTo(pt(12, 3.5))
        P.lineTo(pt(16.5, 8))
        P.moveTo(pt(4.5, 13))
        P.lineTo(pt(4.5, 20))
        P.lineTo(pt(19.5, 20))
        P.lineTo(pt(19.5, 13))
    elif name == "file":
        P.moveTo(pt(6, 3))
        P.lineTo(pt(14, 3))
        P.lineTo(pt(19, 8))
        P.lineTo(pt(19, 21))
        P.lineTo(pt(6, 21))
        P.closeSubpath()
        P.moveTo(pt(14, 3))
        P.lineTo(pt(14, 8))
        P.lineTo(pt(19, 8))
    elif name == "folder":
        P.moveTo(pt(3, 6))
        P.lineTo(pt(9, 6))
        P.lineTo(pt(11, 8.5))
        P.lineTo(pt(21, 8.5))
        P.lineTo(pt(21, 19))
        P.lineTo(pt(3, 19))
        P.closeSubpath()
    elif name == "upload":
        P.addRoundedRect(QRectF(pt(3, 6), pt(21, 20)), 1.5 * k, 1.5 * k)
        P.moveTo(pt(12, 17))
        P.lineTo(pt(12, 9.5))
        P.moveTo(pt(8.8, 12.5))
        P.lineTo(pt(12, 9.3))
        P.lineTo(pt(15.2, 12.5))
    elif name == "pencil":
        P.moveTo(pt(5, 19))
        P.lineTo(pt(6, 15))
        P.lineTo(pt(16, 5))
        P.lineTo(pt(19, 8))
        P.lineTo(pt(9, 18))
        P.closeSubpath()
    elif name == "x":
        P.moveTo(pt(6.5, 6.5))
        P.lineTo(pt(17.5, 17.5))
        P.moveTo(pt(17.5, 6.5))
        P.lineTo(pt(6.5, 17.5))
    elif name == "copy":
        P.addRoundedRect(QRectF(pt(8.5, 8.5), pt(19.5, 19.5)), 1.5 * k, 1.5 * k)
        P.moveTo(pt(15.5, 5.5))
        P.lineTo(pt(15.5, 4.5))
        P.lineTo(pt(4.5, 4.5))
        P.lineTo(pt(4.5, 15.5))
        P.lineTo(pt(5.5, 15.5))
    elif name == "trash":
        P.moveTo(pt(4, 6.5))
        P.lineTo(pt(20, 6.5))
        P.moveTo(pt(9.5, 6.5))
        P.lineTo(pt(10, 3.8))
        P.lineTo(pt(14, 3.8))
        P.lineTo(pt(14.5, 6.5))
        P.moveTo(pt(6, 6.5))
        P.lineTo(pt(7, 20.5))
        P.lineTo(pt(17, 20.5))
        P.lineTo(pt(18, 6.5))
        P.moveTo(pt(10, 10))
        P.lineTo(pt(10.3, 17))
        P.moveTo(pt(14, 10))
        P.lineTo(pt(13.7, 17))
    elif name == "reset":
        P.moveTo(pt(5, 5))
        P.lineTo(pt(5, 10))
        P.lineTo(pt(10, 10))
        P.moveTo(pt(5.5, 9.5))
        P.cubicTo(pt(7, 5.5), pt(11, 4), pt(13, 4))
        P.cubicTo(pt(17.5, 4), pt(20.5, 7.5), pt(20.5, 12))
        P.cubicTo(pt(20.5, 16.5), pt(17, 20), pt(12.5, 20))
        P.cubicTo(pt(9.5, 20), pt(7, 18.5), pt(5.6, 16))
    elif name == "magnet":
        P.moveTo(pt(6, 4))
        P.lineTo(pt(6, 12))
        P.cubicTo(pt(6, 21), pt(18, 21), pt(18, 12))
        P.lineTo(pt(18, 4))
        P.moveTo(pt(6, 8))
        P.lineTo(pt(10, 8))
        P.moveTo(pt(14, 8))
        P.lineTo(pt(18, 8))
        P.moveTo(pt(10, 4))
        P.lineTo(pt(10, 12))
        P.cubicTo(pt(10, 15.5), pt(14, 15.5), pt(14, 12))
        P.lineTo(pt(14, 4))
    elif name == "loop":
        P.moveTo(pt(7, 7.5))
        P.lineTo(pt(17, 7.5))
        P.cubicTo(pt(21, 7.5), pt(21, 16.5), pt(17, 16.5))
        P.moveTo(pt(14, 4.5))
        P.lineTo(pt(17, 7.5))
        P.lineTo(pt(14, 10.5))
        P.moveTo(pt(17, 16.5))
        P.lineTo(pt(7, 16.5))
        P.cubicTo(pt(3, 16.5), pt(3, 7.5), pt(7, 7.5))
    elif name == "warning":
        P.moveTo(pt(12, 3.5))
        P.lineTo(pt(21.5, 20))
        P.lineTo(pt(2.5, 20))
        P.closeSubpath()
        P.moveTo(pt(12, 9.5))
        P.lineTo(pt(12, 14))
        P.moveTo(pt(12, 16.8))
        P.lineTo(pt(12, 17.2))
    elif name == "bulb":
        P.moveTo(pt(9, 17))
        P.lineTo(pt(15, 17))
        P.moveTo(pt(9.8, 20))
        P.lineTo(pt(14.2, 20))
        P.moveTo(pt(9, 17))
        P.cubicTo(pt(9, 14), pt(5.5, 12.5), pt(5.5, 9))
        P.cubicTo(pt(5.5, 5.4), pt(8.5, 3), pt(12, 3))
        P.cubicTo(pt(15.5, 3), pt(18.5, 5.4), pt(18.5, 9))
        P.cubicTo(pt(18.5, 12.5), pt(15, 14), pt(15, 17))
    elif name == "menu":
        for y in (6.5, 12, 17.5):
            P.moveTo(pt(4, y))
            P.lineTo(pt(20, y))
    elif name == "minus":
        P.moveTo(pt(6, 12))
        P.lineTo(pt(18, 12))
    elif name == "plus":
        P.moveTo(pt(6, 12))
        P.lineTo(pt(18, 12))
        P.moveTo(pt(12, 6))
        P.lineTo(pt(12, 18))
    elif name == "expand":
        P.moveTo(pt(3.5, 9))
        P.lineTo(pt(3.5, 4))
        P.lineTo(pt(8.5, 4))
        P.moveTo(pt(15.5, 4))
        P.lineTo(pt(20.5, 4))
        P.lineTo(pt(20.5, 9))
        P.moveTo(pt(20.5, 15))
        P.lineTo(pt(20.5, 20))
        P.lineTo(pt(15.5, 20))
        P.moveTo(pt(8.5, 20))
        P.lineTo(pt(3.5, 20))
        P.lineTo(pt(3.5, 15))
    elif name == "fit":
        P.moveTo(pt(4, 12))
        P.lineTo(pt(9, 12))
        P.moveTo(pt(6.5, 9.5))
        P.lineTo(pt(9, 12))
        P.lineTo(pt(6.5, 14.5))
        P.moveTo(pt(20, 12))
        P.lineTo(pt(15, 12))
        P.moveTo(pt(17.5, 9.5))
        P.lineTo(pt(15, 12))
        P.lineTo(pt(17.5, 14.5))
        P.moveTo(pt(12, 5))
        P.lineTo(pt(12, 19))
    elif name == "reverse":
        P.moveTo(pt(20, 12))
        P.lineTo(pt(4, 12))
        P.moveTo(pt(9, 7))
        P.lineTo(pt(4, 12))
        P.lineTo(pt(9, 17))
    elif name == "sun":
        P.addEllipse(pt(12, 12), 4 * k, 4 * k)
        for a in range(8):
            ang = a * math.pi / 4
            P.moveTo(pt(12 + math.cos(ang) * 7, 12 + math.sin(ang) * 7))
            P.lineTo(pt(12 + math.cos(ang) * 9.5, 12 + math.sin(ang) * 9.5))
    elif name == "moon":
        a = QPainterPath()
        a.addEllipse(QRectF(pt(4, 4), pt(20, 20)))
        b = QPainterPath()
        b.addEllipse(QRectF(pt(9, 1), pt(24, 16)))
        P = a.subtracted(b)
    elif name == "grip":
        for x in (9, 15):
            for y in (6, 12, 18):
                P.addEllipse(pt(x, y), 1.3 * k, 1.3 * k)
    return P


def draw_icon(p: QPainter, name: str, r: QRectF, color: QColor, width: float = 1.6,
              filled: bool = False):
    p.save()
    p.setRenderHint(QPainter.Antialiasing)
    s = min(r.width(), r.height())
    p.translate(r.center().x() - s / 2, r.center().y() - s / 2)
    path = icon_path(name, s)
    if filled or name in ("play", "stop", "grip"):
        p.setPen(Qt.NoPen)
        p.setBrush(color)
    else:
        p.setPen(QPen(color, width, Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin))
        p.setBrush(Qt.NoBrush)
    p.drawPath(path)
    p.restore()


def icon_pixmap(name: str, size: int, color: str, width: float = 1.6) -> QPixmap:
    dpr = 2.0
    pm = QPixmap(int(size * dpr), int(size * dpr))
    pm.fill(Qt.transparent)
    pm.setDevicePixelRatio(dpr)
    p = QPainter(pm)
    draw_icon(p, name, QRectF(0, 0, size, size), QColor(color), width)
    p.end()
    return pm


def save_png(pm: QPixmap, path: str):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    pm.save(path, "PNG")
