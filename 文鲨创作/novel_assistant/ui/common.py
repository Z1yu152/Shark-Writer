# -*- coding: utf-8 -*-
"""通用界面工具：字体、时间、图标和图片缓存。"""

from __future__ import annotations

from datetime import datetime
from pathlib import Path

from PySide6.QtCore import QSize, Qt
from PySide6.QtGui import QColor, QFont, QFontDatabase, QIcon, QPainter, QPen, QPixmap
from PySide6.QtWidgets import QApplication

from ..core.config import (
    DEFAULT_BODY_FONT_FAMILY,
    FONT_CANDIDATES,
    LOGO_FILE,
    PALETTE,
    RESOURCE_DIR,
    WHITE_LOGO_FILE,
)


PIXMAP_CACHE: dict[tuple[str, int, int, int], QPixmap] = {}


def fmt_time(value: str | None) -> str:
    if not value:
        return "-"
    try:
        dt = datetime.fromisoformat(value)
    except ValueError:
        return value
    today = datetime.now().date()
    prefix = "今天" if dt.date() == today else dt.strftime("%Y-%m-%d")
    return f"{prefix} {dt.strftime('%H:%M')}"


def load_application_fonts(app: QApplication) -> None:
    families: list[str] = []
    for font_path in FONT_CANDIDATES:
        if not font_path.exists():
            continue
        font_id = QFontDatabase.addApplicationFont(str(font_path))
        if font_id >= 0:
            families.extend(QFontDatabase.applicationFontFamilies(font_id))
    if families:
        app.setFont(QFont(families[0], 10))


def relative_time(value: str | None) -> str:
    if not value:
        return "-"
    try:
        dt = datetime.fromisoformat(value)
    except ValueError:
        return value
    seconds = int((datetime.now() - dt).total_seconds())
    if seconds < 60:
        return "刚刚"
    minutes = seconds // 60
    if minutes < 60:
        return f"{minutes} 分钟前"
    hours = minutes // 60
    if hours < 24:
        return f"{hours} 小时前"
    return f"{hours // 24} 天前"


def cached_pixmap(path: Path, target_size: QSize) -> QPixmap | None:
    if not path.exists():
        return None
    key = (str(path), target_size.width(), target_size.height(), path.stat().st_mtime_ns)
    pixmap = PIXMAP_CACHE.get(key)
    if pixmap is None:
        pixmap = QPixmap(str(path)).scaled(target_size, Qt.KeepAspectRatio, Qt.SmoothTransformation)
        PIXMAP_CACHE[key] = pixmap
    return pixmap


def white_logo_pixmap(target_size: QSize) -> QPixmap | None:
    source = WHITE_LOGO_FILE if WHITE_LOGO_FILE.exists() else LOGO_FILE
    return cached_pixmap(source, target_size)


def app_icon() -> QIcon:
    source = WHITE_LOGO_FILE if WHITE_LOGO_FILE.exists() else LOGO_FILE
    return QIcon(str(source)) if source.exists() else QIcon()


def text_icon(text: str, color: str = PALETTE["ink"], size: int = 20, bold: bool = True) -> QIcon:
    pixmap = QPixmap(size, size)
    pixmap.fill(Qt.transparent)
    painter = QPainter(pixmap)
    painter.setRenderHint(QPainter.Antialiasing)
    font = QFont(DEFAULT_BODY_FONT_FAMILY, max(8, int(size * 0.48)))
    font.setBold(bold)
    painter.setFont(font)
    painter.setPen(QColor(color))
    painter.drawText(pixmap.rect(), Qt.AlignCenter, text)
    painter.end()
    return QIcon(pixmap)


def nav_icon(kind: str, color: str = "#FFFFFF", size: int = 20) -> QIcon:
    pixmap = QPixmap(size, size)
    pixmap.fill(Qt.transparent)
    painter = QPainter(pixmap)
    painter.setRenderHint(QPainter.Antialiasing)
    pen = QPen(QColor(color), 1.8)
    pen.setCapStyle(Qt.RoundCap)
    pen.setJoinStyle(Qt.RoundJoin)
    painter.setPen(pen)
    painter.setBrush(Qt.NoBrush)

    if kind == "home":
        painter.drawLine(4, 10, 10, 5)
        painter.drawLine(10, 5, 16, 10)
        painter.drawRect(6, 10, 8, 6)
    elif kind == "editor":
        painter.drawRect(5, 4, 10, 12)
        painter.drawLine(8, 8, 13, 8)
        painter.drawLine(8, 11, 13, 11)
    elif kind == "outline":
        for y in (5, 10, 15):
            painter.drawEllipse(4, y - 1, 2, 2)
            painter.drawLine(9, y, 16, y)
    elif kind == "setting":
        painter.drawRoundedRect(4, 5, 12, 10, 2, 2)
        painter.drawLine(7, 9, 13, 9)
        painter.drawLine(7, 12, 11, 12)
    elif kind == "character":
        painter.drawEllipse(7, 4, 6, 6)
        painter.drawArc(4, 11, 12, 8, 20 * 16, 140 * 16)
    elif kind == "relation":
        painter.drawEllipse(3, 5, 5, 5)
        painter.drawEllipse(12, 5, 5, 5)
        painter.drawEllipse(8, 13, 5, 5)
        painter.drawLine(8, 8, 12, 8)
        painter.drawLine(6, 10, 10, 13)
        painter.drawLine(14, 10, 12, 13)
    else:
        painter.drawEllipse(5, 5, 10, 10)
        painter.drawLine(10, 3, 10, 6)
        painter.drawLine(10, 14, 10, 17)
        painter.drawLine(3, 10, 6, 10)
        painter.drawLine(14, 10, 17, 10)

    painter.end()
    return QIcon(pixmap)


def tool_icon(kind: str, color: str = PALETTE["ink"], size: int = 22) -> QIcon:
    pixmap = QPixmap(size, size)
    pixmap.fill(Qt.transparent)
    painter = QPainter(pixmap)
    painter.setRenderHint(QPainter.Antialiasing)
    if size != 22:
        scale = size / 22
        painter.scale(scale, scale)
    pen = QPen(QColor(color), 1.8)
    pen.setCapStyle(Qt.RoundCap)
    pen.setJoinStyle(Qt.RoundJoin)
    painter.setPen(pen)
    painter.setBrush(Qt.NoBrush)

    if kind == "undo":
        painter.drawArc(6, 6, 12, 10, 30 * 16, 230 * 16)
        painter.drawLine(7, 7, 3, 7)
        painter.drawLine(3, 7, 6, 4)
    elif kind == "redo":
        painter.drawArc(4, 6, 12, 10, -80 * 16, 230 * 16)
        painter.drawLine(15, 7, 19, 7)
        painter.drawLine(19, 7, 16, 4)
    elif kind == "bold":
        painter.drawLine(7, 5, 7, 17)
        painter.drawLine(7, 5, 12, 5)
        painter.drawArc(9, 5, 6, 6, 90 * 16, -180 * 16)
        painter.drawLine(7, 11, 13, 11)
        painter.drawArc(9, 11, 7, 6, 90 * 16, -180 * 16)
        painter.drawLine(7, 17, 13, 17)
    elif kind == "heading":
        painter.drawLine(6, 5, 6, 17)
        painter.drawLine(16, 5, 16, 17)
        painter.drawLine(6, 11, 16, 11)
    elif kind == "comment":
        painter.drawRoundedRect(4, 5, 14, 10, 3, 3)
        painter.drawLine(9, 15, 7, 18)
        painter.drawLine(7, 18, 12, 15)
        painter.drawPoint(8, 10)
        painter.drawPoint(11, 10)
        painter.drawPoint(14, 10)
    elif kind == "eraser":
        painter.drawLine(7, 15, 14, 8)
        painter.drawLine(10, 18, 17, 11)
        painter.drawLine(7, 15, 10, 18)
        painter.drawLine(14, 8, 17, 11)
        painter.drawLine(5, 18, 17, 18)
    elif kind == "align":
        painter.drawLine(5, 6, 17, 6)
        painter.drawLine(5, 10, 14, 10)
        painter.drawLine(5, 14, 17, 14)
        painter.drawLine(5, 18, 12, 18)
    elif kind == "font":
        painter.drawLine(6, 17, 11, 5)
        painter.drawLine(11, 5, 16, 17)
        painter.drawLine(8, 12, 14, 12)
        painter.drawLine(5, 19, 17, 19)
    elif kind == "line-spacing":
        painter.drawLine(8, 5, 17, 5)
        painter.drawLine(8, 10, 17, 10)
        painter.drawLine(8, 15, 17, 15)
        painter.drawLine(5, 5, 5, 15)
        painter.drawLine(3, 7, 5, 5)
        painter.drawLine(7, 7, 5, 5)
        painter.drawLine(3, 13, 5, 15)
        painter.drawLine(7, 13, 5, 15)
    elif kind == "save":
        painter.drawRoundedRect(5, 4, 12, 14, 2, 2)
        painter.drawLine(8, 4, 8, 9)
        painter.drawLine(8, 9, 14, 9)
        painter.drawRect(8, 13, 6, 4)
    elif kind == "send":
        painter.drawLine(4, 11, 18, 4)
        painter.drawLine(18, 4, 14, 18)
        painter.drawLine(14, 18, 10, 12)
        painter.drawLine(10, 12, 4, 11)
        painter.drawLine(10, 12, 18, 4)
    elif kind == "stop":
        painter.drawRoundedRect(7, 7, 10, 10, 1, 1)
    elif kind == "image-add":
        painter.drawRoundedRect(4, 5, 14, 11, 2, 2)
        painter.drawLine(6, 14, 10, 10)
        painter.drawLine(10, 10, 13, 13)
        painter.drawEllipse(13, 7, 2, 2)
        painter.drawLine(17, 15, 21, 15)
        painter.drawLine(19, 13, 19, 17)
    elif kind == "replace":
        painter.drawArc(5, 5, 12, 12, 35 * 16, 250 * 16)
        painter.drawLine(15, 5, 18, 5)
        painter.drawLine(18, 5, 18, 2)
        painter.drawArc(5, 5, 12, 12, 215 * 16, 250 * 16)
        painter.drawLine(7, 17, 4, 17)
        painter.drawLine(4, 17, 4, 20)
    elif kind == "trash":
        painter.drawLine(7, 7, 17, 7)
        painter.drawLine(10, 5, 14, 5)
        painter.drawRoundedRect(8, 8, 8, 10, 1, 1)
        painter.drawLine(10, 10, 10, 16)
        painter.drawLine(14, 10, 14, 16)
    elif kind == "eye":
        painter.drawEllipse(9, 8, 4, 4)
        painter.drawArc(4, 6, 16, 10, 20 * 16, 140 * 16)
        painter.drawArc(4, 6, 16, 10, 200 * 16, 140 * 16)
    else:
        painter.end()
        return text_icon(kind, color, size)

    painter.end()
    return QIcon(pixmap)
