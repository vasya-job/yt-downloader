#!/usr/bin/env python3
"""Рисует иконку приложения и собирает packaging/icon.icns.

Запуск из корня репозитория: .venv/bin/python packaging/make_icon.py
Нужны только PySide6 и iconutil (macOS). Результат детерминирован.
"""
import os
import shutil
import subprocess
import tempfile
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtCore import QPointF, QRectF, Qt  # noqa: E402
from PySide6.QtGui import (  # noqa: E402
    QColor, QGuiApplication, QImage, QLinearGradient, QPainter, QPainterPath,
    QPen,
)

CANVAS = 1024
MARGIN = 100                       # прозрачное поле вокруг формы (как в шаблоне Apple)
SIDE = CANVAS - 2 * MARGIN         # 824
RADIUS = SIDE * 0.224
ICNS_PATH = Path(__file__).resolve().parent / "icon.icns"
SIZES = (16, 32, 128, 256, 512)


def _shape() -> QPainterPath:
    path = QPainterPath()
    path.addRoundedRect(QRectF(MARGIN, MARGIN, SIDE, SIDE), RADIUS, RADIUS)
    return path


def _draw_shadow(p: QPainter) -> None:
    """Мягкая тень под формой: набор расширяющихся полупрозрачных слоёв."""
    steps = 28
    spread = 34.0
    dy = 14.0
    for i in range(steps):
        t = i / (steps - 1)               # 0 - внутренний слой, 1 - внешний
        grow = spread * t
        alpha = 9 * (1 - t) ** 1.6 + 0.6
        r = QRectF(MARGIN - grow, MARGIN - grow + dy,
                   SIDE + 2 * grow, SIDE + 2 * grow)
        p.setBrush(QColor(60, 0, 0, round(alpha)))
        p.setPen(Qt.PenStyle.NoPen)
        p.drawRoundedRect(r, RADIUS + grow, RADIUS + grow)


def _glyph_path() -> tuple[QPainterPath, QPainterPath]:
    cx = CANVAS / 2
    off = -6                              # оптическое выравнивание по центру
    arrow = QPainterPath()
    arrow.moveTo(cx, 270 + off)           # стержень
    arrow.lineTo(cx, 580 + off)
    arrow.moveTo(cx - 150, 430 + off)     # наконечник
    arrow.lineTo(cx, 580 + off)
    arrow.lineTo(cx + 150, 430 + off)
    tray = QPainterPath()
    tray.moveTo(cx - 222, 620 + off)      # лоток (U)
    tray.lineTo(cx - 222, 750 + off)
    tray.lineTo(cx + 222, 750 + off)
    tray.lineTo(cx + 222, 620 + off)
    return arrow, tray


def render_master() -> QImage:
    img = QImage(CANVAS, CANVAS, QImage.Format.Format_ARGB32_Premultiplied)
    img.fill(Qt.GlobalColor.transparent)
    p = QPainter(img)
    p.setRenderHints(QPainter.RenderHint.Antialiasing
                     | QPainter.RenderHint.SmoothPixmapTransform)
    shape = _shape()

    _draw_shadow(p)

    # Тело: вертикальный градиент
    grad = QLinearGradient(0, MARGIN, 0, MARGIN + SIDE)
    grad.setColorAt(0.0, QColor("#FF3B30"))
    grad.setColorAt(1.0, QColor("#B3001B"))
    p.setPen(Qt.PenStyle.NoPen)
    p.setBrush(grad)
    p.drawPath(shape)

    # Мягкий блик сверху (внутри формы)
    p.save()
    p.setClipPath(shape)
    hl = QLinearGradient(0, MARGIN, 0, MARGIN + SIDE * 0.5)
    hl.setColorAt(0.0, QColor(255, 255, 255, 70))
    hl.setColorAt(1.0, QColor(255, 255, 255, 0))
    p.setBrush(hl)
    p.drawRect(QRectF(MARGIN, MARGIN, SIDE, SIDE * 0.5))
    # Тонкая светлая внутренняя кромка
    rim = QLinearGradient(0, MARGIN, 0, MARGIN + SIDE)
    rim.setColorAt(0.0, QColor(255, 255, 255, 110))
    rim.setColorAt(0.35, QColor(255, 255, 255, 0))
    rim.setColorAt(1.0, QColor(255, 255, 255, 0))
    p.setBrush(Qt.BrushStyle.NoBrush)
    p.setPen(QPen(rim, 6))
    p.drawRoundedRect(QRectF(MARGIN + 3, MARGIN + 3, SIDE - 6, SIDE - 6),
                      RADIUS - 3, RADIUS - 3)
    p.restore()

    # Глиф «скачать»: тень, затем белый
    arrow, tray = _glyph_path()
    for color, dy in ((QColor(90, 0, 10, 70), 10), (QColor("#FFFFFF"), 0)):
        pen = QPen(color, 84)
        pen.setCapStyle(Qt.PenCapStyle.RoundCap)
        pen.setJoinStyle(Qt.PenJoinStyle.RoundJoin)
        p.setPen(pen)
        p.setBrush(Qt.BrushStyle.NoBrush)
        p.save()
        p.translate(QPointF(0, dy))
        p.drawPath(arrow)
        p.drawPath(tray)
        p.restore()

    p.end()
    return img


def build_icns(out: Path = ICNS_PATH) -> None:
    master = render_master()
    tmp = Path(tempfile.mkdtemp(suffix=".iconset"))
    try:
        for size in SIZES:
            for scale in (1, 2):
                px = size * scale
                scaled = master.scaled(
                    px, px, Qt.AspectRatioMode.IgnoreAspectRatio,
                    Qt.TransformationMode.SmoothTransformation)
                suffix = "@2x" if scale == 2 else ""
                name = f"icon_{size}x{size}{suffix}.png"
                if not scaled.save(str(tmp / name), "PNG"):
                    raise RuntimeError(f"не удалось сохранить {name}")
        subprocess.run(["iconutil", "-c", "icns", str(tmp), "-o", str(out)],
                       check=True)
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def main() -> None:
    app = QGuiApplication.instance() or QGuiApplication([])
    build_icns()
    print(f"OK {ICNS_PATH}")
    del app


if __name__ == "__main__":
    main()
