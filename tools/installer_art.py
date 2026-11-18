"""Draw the Windows installer pictures (installer/side.bmp 164x314, installer/header.bmp 150x57)
with the app's own logo and font, so the installer matches Xenakis.

    QT_QPA_PLATFORM=offscreen python tools/installer_art.py
"""
from __future__ import annotations

import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtCore import QPointF, QRectF, Qt  # noqa: E402
from PySide6.QtGui import (QColor, QFont, QFontDatabase, QGuiApplication, QImage,  # noqa: E402
                           QLinearGradient, QPainter, QPen)

from multicrack.ui.logo import paint_logo  # noqa: E402

OUT = os.path.join(ROOT, "installer")


def font(family, px, weight=QFont.Normal, spacing=0.0):
    f = QFont(family)
    f.setPixelSize(px)
    f.setWeight(weight)
    if spacing:
        f.setLetterSpacing(QFont.AbsoluteSpacing, spacing)
    return f


def save_bmp(img: QImage, name: str, scale: int):
    small = img.scaled(img.width() // scale, img.height() // scale, Qt.IgnoreAspectRatio,
                       Qt.SmoothTransformation).convertToFormat(QImage.Format_RGB888)
    path = os.path.join(OUT, name)
    small.save(path, "BMP")
    print(path, small.width(), small.height())


def main():
    app = QGuiApplication(sys.argv)  # noqa: F841
    fam = None
    for f in ("IBMPlexMono-Regular", "IBMPlexMono-Medium", "IBMPlexMono-SemiBold", "IBMPlexMono-Bold"):
        i = QFontDatabase.addApplicationFont(os.path.join(ROOT, "assets", "fonts", f + ".ttf"))
        fam = fam or QFontDatabase.applicationFontFamilies(i)[0]
    os.makedirs(OUT, exist_ok=True)
    S = 4  # draw big, shrink smooth

    # ---------------------------------------------------------------- side panel
    W, H = 164 * S, 314 * S
    img = QImage(W, H, QImage.Format_ARGB32)
    p = QPainter(img)
    p.setRenderHint(QPainter.Antialiasing)
    p.setRenderHint(QPainter.TextAntialiasing)
    g = QLinearGradient(0, 0, 0, H)
    g.setColorAt(0, QColor("#2B2C30"))
    g.setColorAt(1, QColor("#17181A"))
    p.fillRect(0, 0, W, H, g)
    # a thin red rule down the left edge (the patch-wire colour)
    p.fillRect(0, 0, 4 * S, H, QColor("#B4473A"))
    # faint ruled lines fanning across the bottom (straight lines making a curve)
    p.setPen(QPen(QColor(233, 229, 221, 26), 1.0 * S))
    n = 18
    for k in range(n + 1):
        t = k / n
        p.drawLine(QPointF(4 * S + t * (W - 4 * S), H), QPointF(W, H - (1 - t) * H * 0.42))
    paint_logo(p, QRectF(26 * S, 34 * S, 112 * S, 112 * S))
    p.setPen(QColor("#E9E5DD"))
    p.setFont(font(fam, 23 * S, QFont.Bold, 3.2 * S))
    p.drawText(QRectF(0, 160 * S, W, 34 * S), Qt.AlignHCenter | Qt.AlignVCenter, "XENAKIS")
    p.setPen(QColor("#9D9890"))
    p.setFont(font(fam, 10 * S, QFont.Medium, 0.6 * S))
    p.drawText(QRectF(0, 196 * S, W, 16 * S), Qt.AlignHCenter | Qt.AlignVCenter, "stem chopper")
    p.drawText(QRectF(0, 212 * S, W, 16 * S), Qt.AlignHCenter | Qt.AlignVCenter, "by slapworx")
    p.end()
    save_bmp(img, "side.bmp", S)

    # ---------------------------------------------------------------- header (sits on white)
    W, H = 150 * S, 57 * S
    img = QImage(W, H, QImage.Format_ARGB32)
    img.fill(QColor("#FFFFFF"))
    p = QPainter(img)
    p.setRenderHint(QPainter.Antialiasing)
    paint_logo(p, QRectF(W - 54 * S, 5 * S, 47 * S, 47 * S))
    p.end()
    save_bmp(img, "header.bmp", S)


if __name__ == "__main__":
    main()
