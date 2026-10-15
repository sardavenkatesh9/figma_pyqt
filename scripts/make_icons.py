"""Render the app logo (Figma + Python + Qt motifs) to PNG, ICO and ICNS.

Run with ``python scripts/make_icons.py``; outputs land in ``src/figma_to_pyside6/assets/``.
Only PySide6 is needed, icon containers are written by hand.
"""

from __future__ import annotations

import struct
import sys
from pathlib import Path

from PySide6.QtCore import QBuffer, QByteArray, QIODevice, QPointF, QRectF, Qt
from PySide6.QtGui import (
    QBrush,
    QColor,
    QGuiApplication,
    QImage,
    QLinearGradient,
    QPainter,
    QPainterPath,
    QPen,
)

ASSETS = Path(__file__).resolve().parents[1] / "src" / "figma_to_pyside6" / "assets"
SIZE = 1024


def _fill(p: QPainter, color: str) -> None:
    p.setPen(Qt.PenStyle.NoPen)
    p.setBrush(QBrush(QColor(color)))


def _figma_mark(p: QPainter, x: float, y: float, unit: float) -> None:
    """Stylised five-shape Figma glyph: 2 columns x 3 rows."""
    r = unit / 2
    shapes = (
        ("#F24E1E", QRectF(x, y, unit, unit), (r, 0, 0, r)),
        ("#FF7262", QRectF(x + unit, y, unit, unit), (0, r, r, 0)),
        ("#A259FF", QRectF(x, y + unit, unit, unit), (r, 0, 0, r)),
        ("#1ABCFE", QRectF(x + unit, y + unit, unit, unit), None),
        ("#0ACF83", QRectF(x, y + 2 * unit, unit, unit), (r, 0, r, r)),
    )
    for color, rect, corners in shapes:
        _fill(p, color)
        if corners is None:
            p.drawEllipse(rect)
            continue
        path = QPainterPath()
        tl, tr, br, bl = corners
        path.addRoundedRect(rect, 0, 0)
        shape = QPainterPath()
        shape.moveTo(rect.left() + tl, rect.top())
        shape.lineTo(rect.right() - tr, rect.top())
        if tr:
            shape.arcTo(QRectF(rect.right() - 2 * tr, rect.top(), 2 * tr, 2 * tr), 90, -90)
        shape.lineTo(rect.right(), rect.bottom() - br)
        if br:
            shape.arcTo(
                QRectF(rect.right() - 2 * br, rect.bottom() - 2 * br, 2 * br, 2 * br), 0, -90
            )
        shape.lineTo(rect.left() + bl, rect.bottom())
        if bl:
            shape.arcTo(QRectF(rect.left(), rect.bottom() - 2 * bl, 2 * bl, 2 * bl), 270, -90)
        shape.lineTo(rect.left(), rect.top() + tl)
        if tl:
            shape.arcTo(QRectF(rect.left(), rect.top(), 2 * tl, 2 * tl), 180, -90)
        shape.closeSubpath()
        p.drawPath(shape)


def _python_badge(p: QPainter, rect: QRectF) -> None:
    half = rect.width() * 0.62
    blue = QRectF(rect.left(), rect.top(), half, half)
    yellow = QRectF(rect.right() - half, rect.bottom() - half, half, half)
    radius = half * 0.3
    _fill(p, "#3776AB")
    p.drawRoundedRect(blue, radius, radius)
    _fill(p, "#FFD43B")
    p.drawRoundedRect(yellow, radius, radius)
    _fill(p, "#FFFFFF")
    dot = half * 0.11
    p.drawEllipse(QPointF(blue.left() + half * 0.3, blue.top() + half * 0.3), dot, dot)
    _fill(p, "#306998")
    p.drawEllipse(QPointF(yellow.right() - half * 0.3, yellow.bottom() - half * 0.3), dot, dot)


def _qt_badge(p: QPainter, rect: QRectF) -> None:
    _fill(p, "#41CD52")
    p.drawRoundedRect(rect, rect.width() * 0.28, rect.width() * 0.28)
    # "Qt" drawn as strokes so the logo does not depend on installed fonts.
    stroke = rect.width() * 0.09
    p.setPen(QPen(QColor("#0B1F10"), stroke, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap))
    p.setBrush(Qt.BrushStyle.NoBrush)
    w, h = rect.width(), rect.height()
    q = QRectF(rect.left() + w * 0.16, rect.top() + h * 0.26, w * 0.34, h * 0.40)
    p.drawEllipse(q)
    p.drawLine(QPointF(q.center().x() + w * 0.04, q.center().y() + h * 0.06), q.bottomRight())
    tx = rect.left() + w * 0.70
    p.drawLine(QPointF(tx, rect.top() + h * 0.22), QPointF(tx, rect.top() + h * 0.64))
    p.drawLine(
        QPointF(tx - w * 0.09, rect.top() + h * 0.36), QPointF(tx + w * 0.10, rect.top() + h * 0.36)
    )


def render_logo(size: int = SIZE) -> QImage:
    """Render the logo at ``size`` pixels square."""
    image = QImage(size, size, QImage.Format.Format_ARGB32)
    image.fill(Qt.GlobalColor.transparent)
    p = QPainter(image)
    p.setRenderHint(QPainter.RenderHint.Antialiasing)
    p.scale(size / SIZE, size / SIZE)

    # Dark tile with neon rim.
    tile = QRectF(48, 48, SIZE - 96, SIZE - 96)
    gradient = QLinearGradient(tile.topLeft(), tile.bottomRight())
    gradient.setColorAt(0, QColor("#12122A"))
    gradient.setColorAt(1, QColor("#05050C"))
    for width, alpha in ((46, 35), (30, 60), (16, 110)):
        glow = QColor("#00F0FF")
        glow.setAlpha(alpha)
        p.setPen(QPen(glow, width))
        p.setBrush(Qt.BrushStyle.NoBrush)
        p.drawRoundedRect(tile, 190, 190)
    p.setPen(QPen(QColor("#00F0FF"), 10))
    p.setBrush(QBrush(gradient))
    p.drawRoundedRect(tile, 190, 190)

    # Figma glyph, centre-left.
    unit = 190
    _figma_mark(p, 190, 215, unit)

    # Python and Qt badges stacked on the right.
    _python_badge(p, QRectF(710, 290, 190, 190))
    _qt_badge(p, QRectF(710, 540, 190, 190))

    # Arrow: design -> code.
    p.setPen(QPen(QColor("#FF2BD6"), 26, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap))
    p.drawLine(QPointF(585, 500), QPointF(655, 500))
    p.drawLine(QPointF(625, 465), QPointF(660, 500))
    p.drawLine(QPointF(625, 535), QPointF(660, 500))
    p.end()
    return image


def _png_bytes(image: QImage) -> bytes:
    data = QByteArray()
    buffer = QBuffer(data)
    buffer.open(QIODevice.OpenModeFlag.WriteOnly)
    image.save(buffer, "PNG")
    return bytes(data.data())


def _scaled(image: QImage, size: int) -> bytes:
    return _png_bytes(
        image.scaled(
            size,
            size,
            Qt.AspectRatioMode.IgnoreAspectRatio,
            Qt.TransformationMode.SmoothTransformation,
        )
    )


def write_ico(image: QImage, path: Path) -> None:
    """Write a multi-size PNG-compressed Windows ICO file."""
    sizes = (16, 24, 32, 48, 64, 128, 256)
    payloads = [_scaled(image, s) for s in sizes]
    header = struct.pack("<HHH", 0, 1, len(sizes))
    offset = 6 + 16 * len(sizes)
    entries = b""
    for s, payload in zip(sizes, payloads, strict=True):
        entries += struct.pack("<BBBBHHII", s % 256, s % 256, 0, 0, 1, 32, len(payload), offset)
        offset += len(payload)
    path.write_bytes(header + entries + b"".join(payloads))


def write_icns(image: QImage, path: Path) -> None:
    """Write a macOS ICNS file made of PNG chunks."""
    types = {
        b"icp4": 16,
        b"icp5": 32,
        b"icp6": 64,
        b"ic07": 128,
        b"ic08": 256,
        b"ic09": 512,
        b"ic10": 1024,
    }
    chunks = b""
    for code, size in types.items():
        payload = _scaled(image, size)
        chunks += code + struct.pack(">I", len(payload) + 8) + payload
    path.write_bytes(b"icns" + struct.pack(">I", len(chunks) + 8) + chunks)


def main() -> int:
    """Render the logo and write all icon formats into the package assets folder."""
    app = QGuiApplication.instance() or QGuiApplication(sys.argv)
    assert app is not None
    ASSETS.mkdir(exist_ok=True)
    image = render_logo()
    (ASSETS / "icon.png").write_bytes(_scaled(image, 512))
    write_ico(image, ASSETS / "icon.ico")
    write_icns(image, ASSETS / "icon.icns")
    print(f"Wrote icons to {ASSETS}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
