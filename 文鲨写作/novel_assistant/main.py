# -*- coding: utf-8 -*-
from __future__ import annotations

import json
import shutil
import sqlite3
import sys
import ctypes
import urllib.error
import urllib.request
import uuid
import zipfile
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any

from PySide6.QtCore import QPoint, QPointF, QSize, Qt, QThread, QTimer, QUrl, Signal
from PySide6.QtGui import (
    QAction,
    QBrush,
    QColor,
    QDesktopServices,
    QFont,
    QFontDatabase,
    QIcon,
    QKeySequence,
    QPainter,
    QPen,
    QPixmap,
    QShortcut,
    QTextBlockFormat,
    QTextCharFormat,
    QTextCursor,
)
from PySide6.QtWidgets import (
    QApplication,
    QCheckBox,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFileDialog,
    QFontComboBox,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QInputDialog,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMainWindow,
    QMenu,
    QMessageBox,
    QProxyStyle,
    QPushButton,
    QScrollArea,
    QSplitter,
    QSpinBox,
    QStackedWidget,
    QSizePolicy,
    QTextEdit,
    QToolButton,
    QTreeWidget,
    QTreeWidgetItem,
    QVBoxLayout,
    QStyle,
    QWidget,
)


FROZEN = bool(getattr(sys, "frozen", False))
RESOURCE_DIR = Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parent.parent))
APP_DIR = Path(sys.executable).resolve().parent if FROZEN else Path(__file__).resolve().parent.parent
STATE_DIR = APP_DIR / ".app_state"
STATE_FILE = STATE_DIR / "recent_projects.json"
APP_SETTINGS_FILE = STATE_DIR / "settings.json"
PROJECT_CONFIG = "project.json"
DRAFT_FILE = "draft.json"
APP_NAME = "文鲨创作"
APP_VERSION = "1.0"
PARAGRAPH_INDENT = "\u3000\u3000"
DEFAULT_BODY_FONT_FAMILY = "Microsoft YaHei"
DEFAULT_BODY_FONT_SIZE = 15
DEFAULT_TITLE_FONT_SIZE = 22
DEFAULT_LINE_SPACING = 34
DEFAULT_LETTER_SPACING = 104
DEFAULT_EDITOR_STYLE_VERSION = 2
LOGO_FILE = RESOURCE_DIR / "assets" / "brand" / "wensha_logo_selected_v1.png"
WHITE_LOGO_FILE = RESOURCE_DIR / "assets" / "brand" / "wensha_logo_white.png"
IMAGE_EXTENSIONS = {".png", ".jpg", ".jpeg", ".webp", ".bmp"}
PIXMAP_CACHE: dict[tuple[str, int, int, int], QPixmap] = {}
FONT_CANDIDATES = (
    Path("C:/Windows/Fonts/msyh.ttc"),
    Path("C:/Windows/Fonts/simhei.ttf"),
    Path("C:/Windows/Fonts/simsun.ttc"),
)


PALETTE = {
    "bg": "#F5F6F2",
    "paper": "#FFFDFC",
    "panel": "#ECEFE8",
    "line": "#D8DDD3",
    "ink": "#25313B",
    "muted": "#65716E",
    "nav": "#203330",
    "nav2": "#2D4642",
    "accent": "#B94A48",
    "amber": "#D79A3A",
    "blue": "#466A8C",
    "green": "#4D7A68",
    "soft_red": "#F6E7E4",
    "soft_blue": "#E6EEF5",
    "soft_green": "#E4EEE8",
    "soft_yellow": "#F5EBD0",
    "eye": "#DDEED8",
}


class WenshaCheckStyle(QProxyStyle):
    def pixelMetric(self, metric, option=None, widget=None) -> int:
        if metric in {QStyle.PixelMetric.PM_IndicatorWidth, QStyle.PixelMetric.PM_IndicatorHeight}:
            return 16
        return super().pixelMetric(metric, option, widget)

    def drawPrimitive(self, element, option, painter, widget=None) -> None:
        check_elements = {
            QStyle.PrimitiveElement.PE_IndicatorCheckBox,
            QStyle.PrimitiveElement.PE_IndicatorItemViewItemCheck,
        }
        if element not in check_elements:
            super().drawPrimitive(element, option, painter, widget)
            return

        state = option.state
        enabled = bool(state & QStyle.StateFlag.State_Enabled)
        checked = bool(state & QStyle.StateFlag.State_On)
        partial = bool(state & QStyle.StateFlag.State_NoChange)
        hovered = bool(state & QStyle.StateFlag.State_MouseOver)

        rect = option.rect.adjusted(1, 1, -1, -1)
        side = min(rect.width(), rect.height(), 16)
        left = rect.x() + (rect.width() - side) / 2
        top = rect.y() + (rect.height() - side) / 2
        box = rect.__class__(round(left), round(top), side, side)

        border = QColor(PALETTE["ink"] if enabled else PALETTE["muted"])
        background = QColor(PALETTE["panel"] if enabled and hovered else PALETTE["paper"])
        painter.save()
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        painter.setPen(QPen(border, 1.4))
        painter.setBrush(QBrush(background))
        painter.drawRoundedRect(box, 3, 3)

        if checked:
            pen = QPen(border, 2.0)
            pen.setCapStyle(Qt.PenCapStyle.RoundCap)
            pen.setJoinStyle(Qt.PenJoinStyle.RoundJoin)
            painter.setPen(pen)
            painter.drawLine(QPointF(box.left() + side * 0.25, box.top() + side * 0.52), QPointF(box.left() + side * 0.43, box.top() + side * 0.70))
            painter.drawLine(QPointF(box.left() + side * 0.43, box.top() + side * 0.70), QPointF(box.left() + side * 0.76, box.top() + side * 0.30))
        elif partial:
            pen = QPen(border, 2.0)
            pen.setCapStyle(Qt.PenCapStyle.RoundCap)
            painter.setPen(pen)
            painter.drawLine(QPointF(box.left() + side * 0.25, box.center().y()), QPointF(box.left() + side * 0.75, box.center().y()))
        painter.restore()


def install_wensha_check_style(app: QApplication | None) -> None:
    if app is None or app.property("wensha_check_style_installed"):
        return
    app.setStyle(WenshaCheckStyle(app.style()))
    app.setProperty("wensha_check_style_installed", True)


def default_app_settings() -> dict[str, Any]:
    return {
        "eye_mode": False,
        "ui_scale": 100,
        "font_family": DEFAULT_BODY_FONT_FAMILY,
        "body_font_size": DEFAULT_BODY_FONT_SIZE,
        "title_font_size": DEFAULT_TITLE_FONT_SIZE,
        "auto_save_enabled": True,
        "auto_save_minutes": 10,
        "backup_retention": 10,
        "ai_enabled": True,
        "api_key": "",
        "base_url": "https://api.deepseek.com/v1",
        "model": "deepseek-chat",
        "max_context_items": 60,
        "ai_confirm_each_call": True,
        "ai_role_name": "AI",
        "ai_role_identity": "创作助手",
        "ai_role_prompt": "",
        "outline_ai_scope": default_outline_ai_scope(),
        "character_ai_scope": default_character_ai_scope(),
        "export_format": "Markdown",
        "export_include_volume": True,
        "export_include_chapter_title": True,
        "export_include_chapter_status": False,
    }


def default_outline_ai_scope() -> dict[str, bool]:
    return {
        "outline": True,
        "timeline": True,
        "world": True,
        "characters": True,
        "relations": True,
        "summaries": True,
        "current_chapter_body": False,
        "selected_chapter_bodies": False,
        "all_chapter_bodies": False,
    }


def default_character_ai_scope() -> dict[str, bool]:
    return {
        "current_character": True,
        "current_relations": True,
        "world": True,
        "summaries": True,
        "all_characters": False,
        "all_relations": False,
        "outline": False,
        "timeline": False,
        "current_chapter_body": False,
        "selected_chapter_bodies": False,
        "all_chapter_bodies": False,
    }


def load_app_settings() -> dict[str, Any]:
    settings = default_app_settings()
    if APP_SETTINGS_FILE.exists():
        try:
            data = json.loads(APP_SETTINGS_FILE.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            data = {}
        if isinstance(data, dict):
            settings.update({key: value for key, value in data.items() if key in settings})
    outline_scope = settings.get("outline_ai_scope")
    defaults = default_outline_ai_scope()
    if isinstance(outline_scope, dict):
        settings["outline_ai_scope"] = {key: bool(outline_scope.get(key, value)) for key, value in defaults.items()}
    else:
        settings["outline_ai_scope"] = defaults
    character_scope = settings.get("character_ai_scope")
    character_defaults = default_character_ai_scope()
    if isinstance(character_scope, dict):
        settings["character_ai_scope"] = {key: bool(character_scope.get(key, value)) for key, value in character_defaults.items()}
    else:
        settings["character_ai_scope"] = character_defaults
    return settings


def save_app_settings(settings: dict[str, Any]) -> None:
    STATE_DIR.mkdir(exist_ok=True)
    payload = default_app_settings()
    payload.update({key: value for key, value in settings.items() if key in payload})
    outline_scope = payload.get("outline_ai_scope")
    defaults = default_outline_ai_scope()
    if isinstance(outline_scope, dict):
        payload["outline_ai_scope"] = {key: bool(outline_scope.get(key, value)) for key, value in defaults.items()}
    else:
        payload["outline_ai_scope"] = defaults
    character_scope = payload.get("character_ai_scope")
    character_defaults = default_character_ai_scope()
    if isinstance(character_scope, dict):
        payload["character_ai_scope"] = {key: bool(character_scope.get(key, value)) for key, value in character_defaults.items()}
    else:
        payload["character_ai_scope"] = character_defaults
    APP_SETTINGS_FILE.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


class AIStreamThread(QThread):
    chunk_received = Signal(str)
    result_ready = Signal(bool, str, bool)

    def __init__(self, settings: dict[str, Any], messages: list[dict[str, str]], max_tokens: int = 900) -> None:
        super().__init__()
        self.settings = dict(settings)
        self.messages = list(messages)
        self.max_tokens = max_tokens
        self.stop_requested = False

    def request_stop(self) -> None:
        self.stop_requested = True

    def run(self) -> None:
        base_url = str(self.settings.get("base_url", "")).strip().rstrip("/")
        payload = {
            "model": str(self.settings.get("model", "")).strip(),
            "messages": self.messages,
            "max_tokens": self.max_tokens,
            "temperature": 0.4,
            "stream": True,
        }
        request = urllib.request.Request(
            f"{base_url}/chat/completions",
            data=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
            headers={
                "Authorization": f"Bearer {str(self.settings.get('api_key', '')).strip()}",
                "Content-Type": "application/json",
                "Accept": "text/event-stream",
                "Connection": "close",
                "User-Agent": f"WenshaCreator/{APP_VERSION}",
            },
            method="POST",
        )
        received = False
        try:
            with urllib.request.urlopen(request, timeout=60) as response:
                while not self.stop_requested:
                    raw_line = response.readline()
                    if not raw_line:
                        break
                    line = raw_line.decode("utf-8", errors="replace").strip()
                    if not line or not line.startswith("data:"):
                        continue
                    data = line[5:].strip()
                    if data == "[DONE]":
                        break
                    try:
                        payload = json.loads(data)
                    except json.JSONDecodeError:
                        continue
                    for choice in payload.get("choices", []):
                        delta = choice.get("delta", {})
                        content = delta.get("content", "")
                        if content:
                            received = True
                            self.chunk_received.emit(str(content))
                if self.stop_requested:
                    self.result_ready.emit(True, "已停止生成。", True)
                elif received:
                    self.result_ready.emit(True, "", False)
                else:
                    self.result_ready.emit(False, "AI 请求失败：未返回有效内容。", False)
        except urllib.error.HTTPError as exc:
            self.result_ready.emit(False, f"AI 请求失败：HTTP {exc.code}。请检查 Key、Base URL 或模型名。", False)
        except urllib.error.URLError as exc:
            self.result_ready.emit(False, f"AI 请求失败：{exc.reason}", False)
        except TimeoutError:
            self.result_ready.emit(False, "AI 请求失败：连接超时。", False)


def now_iso() -> str:
    return datetime.now().isoformat(timespec="seconds")


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


def move_path_to_recycle_bin(path: Path) -> None:
    if not sys.platform.startswith("win"):
        raise OSError("当前版本仅支持在 Windows 上移入回收站。")

    class SHFILEOPSTRUCTW(ctypes.Structure):
        _fields_ = [
            ("hwnd", ctypes.c_void_p),
            ("wFunc", ctypes.c_uint),
            ("pFrom", ctypes.c_wchar_p),
            ("pTo", ctypes.c_wchar_p),
            ("fFlags", ctypes.c_ushort),
            ("fAnyOperationsAborted", ctypes.c_int),
            ("hNameMappings", ctypes.c_void_p),
            ("lpszProgressTitle", ctypes.c_wchar_p),
        ]

    operation = SHFILEOPSTRUCTW()
    operation.wFunc = 0x0003  # FO_DELETE
    operation.pFrom = str(path.resolve()) + "\0\0"
    operation.fFlags = 0x0040  # FOF_ALLOWUNDO: send to Recycle Bin when possible.

    result = ctypes.windll.shell32.SHFileOperationW(ctypes.byref(operation))
    if result != 0:
        raise OSError(f"移入回收站失败，系统错误码：{result}")
    if operation.fAnyOperationsAborted:
        raise OSError("删除操作已取消。")


@dataclass
class ProjectMeta:
    name: str
    path: str
    author: str = ""
    template: str = "长篇"
    writing_stage: str = "构思中"
    health: str = "正常"
    health_color: str = "green"
    current_position: str = "尚未开始"
    total_words: int = 0
    today_words: int = 0
    pending_summaries: int = 0
    resources_status: str = "资源完整"
    cover_image_path: str | None = None
    auto_save_minutes: int = 10
    ai_summary_enabled: bool = True
    created_at: str = field(default_factory=now_iso)
    last_opened_at: str = field(default_factory=now_iso)
    last_manual_save_at: str | None = None
    last_auto_save_at: str | None = None
    last_backup_at: str | None = None

    @classmethod
    def from_dict(cls, data: dict[str, Any], path: Path) -> "ProjectMeta":
        payload = dict(data)
        payload["path"] = str(path)
        allowed = {f.name for f in cls.__dataclass_fields__.values()}
        return cls(**{k: v for k, v in payload.items() if k in allowed})

    def to_project_json(self) -> dict[str, Any]:
        data = self.__dict__.copy()
        data.pop("path", None)
        return data


class ProjectStore:
    def __init__(self) -> None:
        STATE_DIR.mkdir(exist_ok=True)
        self.recent: list[ProjectMeta] = self.load_recent()

    def load_recent(self) -> list[ProjectMeta]:
        if not STATE_FILE.exists():
            return self.sample_recent()
        try:
            data = json.loads(STATE_FILE.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return self.sample_recent()
        projects: list[ProjectMeta] = []
        for item in data.get("projects", []):
            path = Path(item.get("path", ""))
            projects.append(ProjectMeta.from_dict(item, path))
        return projects or self.sample_recent()

    def sample_recent(self) -> list[ProjectMeta]:
        base = APP_DIR / "sample_projects"
        return [
            ProjectMeta(
                name="长夜纪事",
                path=str(base / "长夜纪事"),
                writing_stage="连载中",
                health="正常",
                health_color="green",
                current_position="第一卷 · 第十二章",
                total_words=186420,
                today_words=2180,
                pending_summaries=2,
                resources_status="人物图片完整",
                last_manual_save_at=now_iso(),
                last_auto_save_at=now_iso(),
                last_backup_at=now_iso(),
            ),
            ProjectMeta(
                name="雾港手记",
                path=str(base / "雾港手记"),
                writing_stage="修订中",
                health="待备份",
                health_color="amber",
                current_position="第二卷 · 第三章",
                total_words=72400,
                today_words=640,
                pending_summaries=0,
                resources_status="资源完整",
                last_auto_save_at=now_iso(),
            ),
            ProjectMeta(
                name="旧神目录",
                path=str(base / "旧神目录"),
                writing_stage="构思中",
                health="摘要待更新",
                health_color="accent",
                current_position="大纲 · 第一幕",
                total_words=18300,
                today_words=0,
                pending_summaries=4,
                resources_status="人物关系待整理",
            ),
        ]

    def save_recent(self) -> None:
        payload = {"projects": [p.__dict__ for p in self.recent]}
        STATE_FILE.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")

    def add_recent(self, project: ProjectMeta) -> None:
        normalized = str(Path(project.path))
        self.recent = [p for p in self.recent if str(Path(p.path)) != normalized]
        self.recent.insert(0, project)
        self.recent = self.recent[:12]
        self.save_recent()

    def create_project(
        self,
        name: str,
        root_dir: Path,
        author: str,
        template: str,
        auto_save_minutes: int,
        ai_summary_enabled: bool,
    ) -> ProjectMeta:
        project_dir = root_dir / name
        project_dir.mkdir(parents=True, exist_ok=True)
        for sub in ["assets/portraits", "assets/covers", "exports", "backups"]:
            (project_dir / sub).mkdir(parents=True, exist_ok=True)
        project = ProjectMeta(
            name=name,
            path=str(project_dir),
            author=author,
            template=template,
            auto_save_minutes=auto_save_minutes,
            ai_summary_enabled=ai_summary_enabled,
            last_manual_save_at=now_iso(),
            last_auto_save_at=now_iso(),
        )
        self.write_project(project)
        self.init_db(project_dir / "project.db")
        self.add_recent(project)
        return project

    def open_project(self, folder: Path) -> ProjectMeta:
        config_path = folder / PROJECT_CONFIG
        if not config_path.exists():
            raise ValueError("所选文件夹不是有效小说项目：缺少 project.json")
        data = json.loads(config_path.read_text(encoding="utf-8"))
        project = ProjectMeta.from_dict(data, folder)
        project.last_opened_at = now_iso()
        self.write_project(project)
        self.add_recent(project)
        return project

    def write_project(self, project: ProjectMeta) -> None:
        path = Path(project.path)
        path.mkdir(parents=True, exist_ok=True)
        (path / PROJECT_CONFIG).write_text(
            json.dumps(project.to_project_json(), ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

    def init_db(self, db_path: Path) -> None:
        with sqlite3.connect(db_path) as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS meta (
                    key TEXT PRIMARY KEY,
                    value TEXT NOT NULL
                )
                """
            )
            conn.execute("INSERT OR REPLACE INTO meta(key, value) VALUES('schema_version', '1')")


class DraftStore:
    @staticmethod
    def new_id(prefix: str) -> str:
        return f"{prefix}_{uuid.uuid4().hex[:10]}"

    @staticmethod
    def default_draft() -> dict[str, Any]:
        volume_id = DraftStore.new_id("vol")
        chapter_id = DraftStore.new_id("ch")
        return {
            "version": 1,
            "current_chapter_id": chapter_id,
            "volumes": [
                {
                    "id": volume_id,
                    "title": "第一卷",
                    "chapters": [
                        {
                            "id": chapter_id,
                            "title": "第一章",
                            "content": f"<h1 style='text-align:center;'>第一章</h1><p>{PARAGRAPH_INDENT}从这里开始写正文。</p>",
                            "summary": {
                                "time": "",
                                "place": "",
                                "characters": "",
                                "events": "尚未生成总结。",
                                "key_sentence": "",
                            },
                            "status": "草稿",
                            "updated_at": now_iso(),
                        }
                    ],
                }
            ],
        }

    @staticmethod
    def path_for(project: ProjectMeta) -> Path:
        return Path(project.path) / DRAFT_FILE

    @classmethod
    def load(cls, project: ProjectMeta) -> dict[str, Any]:
        path = cls.path_for(project)
        if not path.exists():
            draft = cls.default_draft()
            cls.save(project, draft)
            return draft
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            data = cls.default_draft()
        if not data.get("volumes"):
            data = cls.default_draft()
        return data

    @classmethod
    def save(cls, project: ProjectMeta, draft: dict[str, Any]) -> None:
        path = cls.path_for(project)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(draft, ensure_ascii=False, indent=2), encoding="utf-8")

    @staticmethod
    def iter_chapters(draft: dict[str, Any]):
        for volume in draft.get("volumes", []):
            for chapter in volume.get("chapters", []):
                yield volume, chapter

    @staticmethod
    def find_volume(draft: dict[str, Any], volume_id: str) -> dict[str, Any] | None:
        for volume in draft.get("volumes", []):
            if volume.get("id") == volume_id:
                return volume
        return None

    @classmethod
    def find_chapter(cls, draft: dict[str, Any], chapter_id: str) -> tuple[dict[str, Any], dict[str, Any]] | None:
        for volume, chapter in cls.iter_chapters(draft):
            if chapter.get("id") == chapter_id:
                return volume, chapter
        return None

    @classmethod
    def first_chapter(cls, draft: dict[str, Any]) -> tuple[dict[str, Any], dict[str, Any]] | None:
        for volume, chapter in cls.iter_chapters(draft):
            return volume, chapter
        return None

    @staticmethod
    def text_count(html: str) -> int:
        text = QTextEdit()
        text.setHtml(html)
        plain = text.toPlainText()
        return len("".join(plain.split()))


class ManuscriptEditor(QTextEdit):
    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.body_font_family = DEFAULT_BODY_FONT_FAMILY
        self.body_font_size = DEFAULT_BODY_FONT_SIZE
        self.title_font_size = DEFAULT_TITLE_FONT_SIZE
        self.line_spacing = DEFAULT_LINE_SPACING
        self.letter_spacing = DEFAULT_LETTER_SPACING
        self.canvas_background = PALETTE["paper"]
        self.setAcceptRichText(True)
        self.viewport().setAutoFillBackground(False)
        self.document().setDocumentMargin(28)
        self.apply_editor_defaults()

    def set_canvas_background(self, color: str) -> None:
        self.canvas_background = color
        self.viewport().update()

    def set_editor_style(self, font_family: str, font_size: int, line_spacing: int, letter_spacing: int | None = None) -> None:
        self.body_font_family = font_family or self.body_font_family
        self.body_font_size = font_size
        self.line_spacing = line_spacing
        if letter_spacing is not None:
            self.letter_spacing = letter_spacing
        self.apply_line_spacing_to_document()
        self.viewport().update()

    def body_char_format(self) -> QTextCharFormat:
        fmt = QTextCharFormat()
        fmt.setFontFamily(self.body_font_family)
        fmt.setFontPointSize(self.body_font_size)
        fmt.setFontWeight(QFont.Normal)
        fmt.setFontLetterSpacingType(QFont.PercentageSpacing)
        fmt.setFontLetterSpacing(self.letter_spacing)
        return fmt

    def title_char_format(self) -> QTextCharFormat:
        fmt = QTextCharFormat()
        fmt.setFontFamily(self.body_font_family)
        fmt.setFontPointSize(self.title_font_size)
        fmt.setFontWeight(QFont.Bold)
        fmt.setFontLetterSpacingType(QFont.PercentageSpacing)
        fmt.setFontLetterSpacing(self.letter_spacing)
        return fmt

    def body_block_format(self) -> QTextBlockFormat:
        fmt = QTextBlockFormat()
        fmt.setAlignment(Qt.AlignLeft)
        fmt.setLineHeight(float(self.line_spacing), QTextBlockFormat.FixedHeight.value)
        fmt.setTopMargin(0)
        fmt.setBottomMargin(0)
        return fmt

    def title_block_format(self) -> QTextBlockFormat:
        fmt = QTextBlockFormat()
        fmt.setAlignment(Qt.AlignHCenter)
        fmt.setLineHeight(float(max(self.line_spacing, self.title_font_size + 12)), QTextBlockFormat.FixedHeight.value)
        fmt.setTopMargin(4)
        fmt.setBottomMargin(6)
        return fmt

    def apply_editor_defaults(self) -> None:
        font = QFont(self.body_font_family, self.body_font_size)
        font.setLetterSpacing(QFont.PercentageSpacing, self.letter_spacing)
        self.setFont(font)
        self.document().setDefaultFont(font)
        self.apply_line_spacing_to_document()

    def apply_line_spacing_to_document(self) -> None:
        block = self.document().firstBlock()
        while block.isValid():
            cursor = QTextCursor(block)
            block_format = block.blockFormat()
            block_format.setLineHeight(float(self.line_spacing), QTextBlockFormat.FixedHeight.value)
            block_format.setTopMargin(0)
            block_format.setBottomMargin(0)
            cursor.setBlockFormat(block_format)
            block = block.next()

    def apply_document_structure(self) -> None:
        block = self.document().firstBlock()
        is_title = True
        while block.isValid():
            cursor = QTextCursor(block)
            if is_title:
                cursor.mergeBlockFormat(self.title_block_format())
                cursor.select(QTextCursor.BlockUnderCursor)
                cursor.mergeCharFormat(self.title_char_format())
                is_title = False
            else:
                cursor.mergeBlockFormat(self.body_block_format())
            block = block.next()

    def format_current_block_as_title(self) -> None:
        cursor = self.textCursor()
        cursor.mergeBlockFormat(self.title_block_format())
        cursor.mergeCharFormat(self.title_char_format())
        self.setTextCursor(cursor)

    def format_current_block_as_body(self) -> None:
        cursor = self.textCursor()
        cursor.mergeBlockFormat(self.body_block_format())
        cursor.mergeCharFormat(self.body_char_format())
        self.setTextCursor(cursor)

    def ensure_body_cursor(self) -> None:
        cursor = self.textCursor()
        if cursor.blockNumber() > 0:
            cursor.mergeBlockFormat(self.body_block_format())
            cursor.mergeCharFormat(self.body_char_format())
            self.setTextCursor(cursor)

    def line_start_y(self) -> int:
        return int(self.first_body_top_y())

    def first_body_top_y(self) -> float:
        first = self.document().firstBlock()
        if not first.isValid():
            return self.document().documentMargin()
        second = first.next()
        if second.isValid():
            return self.document().documentLayout().blockBoundingRect(second).top()
        title_rect = self.document().documentLayout().blockBoundingRect(first)
        return title_rect.top() + max(self.line_spacing, self.title_font_size + 12) + 6

    def ensure_current_body_indent(self) -> None:
        cursor = self.textCursor()
        if cursor.blockNumber() == 0:
            return
        if cursor.block().text().strip():
            return
        cursor.movePosition(QTextCursor.StartOfBlock)
        cursor.insertText(PARAGRAPH_INDENT)
        self.setTextCursor(cursor)

    def keyPressEvent(self, event: Any) -> None:
        if event.key() in (Qt.Key_Return, Qt.Key_Enter):
            cursor = self.textCursor()
            block_number = cursor.blockNumber()
            cursor.insertBlock()
            self.setTextCursor(cursor)
            if block_number == 0:
                self.format_current_block_as_body()
            else:
                self.ensure_body_cursor()
            cursor = self.textCursor()
            cursor.insertText(PARAGRAPH_INDENT)
            self.setTextCursor(cursor)
            return
        super().keyPressEvent(event)

    def mousePressEvent(self, event: Any) -> None:
        raw_pos = event.position() if hasattr(event, "position") else event.pos()
        click_y = raw_pos.y() + self.verticalScrollBar().value()
        line_start = self.line_start_y()
        target_block = 0 if click_y < line_start else int((click_y - line_start) // self.line_spacing) + 1
        if target_block >= self.document().blockCount():
            cursor = QTextCursor(self.document())
            cursor.movePosition(QTextCursor.End)
            while self.document().blockCount() <= target_block:
                cursor.insertBlock(self.body_block_format(), self.body_char_format())
                cursor.insertText(PARAGRAPH_INDENT)
            self.setTextCursor(cursor)
            self.setFocus()
            return
        super().mousePressEvent(event)
        self.ensure_current_body_indent()

    def paintEvent(self, event: Any) -> None:
        painter = QPainter(self.viewport())
        painter.fillRect(event.rect(), QColor(self.canvas_background))
        painter.end()
        super().paintEvent(event)


class NewProjectDialog(QDialog):
    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("新建小说项目")
        self.setMinimumWidth(520)

        self.name_edit = QLineEdit()
        self.name_edit.setPlaceholderText("例如：长夜纪事")
        self.author_edit = QLineEdit()
        self.author_edit.setPlaceholderText("可选")
        self.path_edit = QLineEdit(str(APP_DIR / "projects"))
        self.template_box = QComboBox()
        self.template_box.addItems(["长篇", "单卷", "系列作", "空白"])
        self.auto_save_spin = QSpinBox()
        self.auto_save_spin.setRange(1, 30)
        self.auto_save_spin.setValue(10)
        self.auto_save_spin.setSuffix(" 分钟")
        self.ai_summary_check = QCheckBox("保存章节时启用 AI 总结")
        self.ai_summary_check.setChecked(True)

        browse_btn = QPushButton("选择位置")
        browse_btn.clicked.connect(self.choose_path)

        form = QGridLayout()
        form.addWidget(QLabel("项目名称"), 0, 0)
        form.addWidget(self.name_edit, 0, 1, 1, 2)
        form.addWidget(QLabel("保存位置"), 1, 0)
        form.addWidget(self.path_edit, 1, 1)
        form.addWidget(browse_btn, 1, 2)
        form.addWidget(QLabel("作者/笔名"), 2, 0)
        form.addWidget(self.author_edit, 2, 1, 1, 2)
        form.addWidget(QLabel("类型模板"), 3, 0)
        form.addWidget(self.template_box, 3, 1, 1, 2)
        form.addWidget(QLabel("自动保存"), 4, 0)
        form.addWidget(self.auto_save_spin, 4, 1, 1, 2)
        form.addWidget(self.ai_summary_check, 5, 1, 1, 2)

        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.button(QDialogButtonBox.Ok).setText("创建项目")
        buttons.button(QDialogButtonBox.Cancel).setText("取消")
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)

        layout = QVBoxLayout(self)
        title = QLabel("新建项目")
        title.setObjectName("DialogTitle")
        layout.addWidget(title)
        layout.addLayout(form)
        layout.addWidget(buttons)

    def choose_path(self) -> None:
        folder = QFileDialog.getExistingDirectory(self, "选择项目保存位置", self.path_edit.text())
        if folder:
            self.path_edit.setText(folder)

    def accept(self) -> None:
        if not self.name_edit.text().strip():
            QMessageBox.warning(self, "缺少项目名称", "请输入项目名称。")
            return
        super().accept()

    def values(self) -> dict[str, Any]:
        return {
            "name": self.name_edit.text().strip(),
            "root_dir": Path(self.path_edit.text().strip()),
            "author": self.author_edit.text().strip(),
            "template": self.template_box.currentText(),
            "auto_save_minutes": self.auto_save_spin.value(),
            "ai_summary_enabled": self.ai_summary_check.isChecked(),
        }


class ProjectHomeWindow(QMainWindow):
    def __init__(self) -> None:
        super().__init__()
        install_wensha_check_style(QApplication.instance())
        self.store = ProjectStore()
        self.app_settings = load_app_settings()
        self.preview_app_settings: dict[str, Any] | None = None
        self.loading_settings_page = False
        self.selected_project: ProjectMeta | None = self.store.recent[0] if self.store.recent else None
        self.current_page = "home"
        self.nav_buttons: dict[str, QPushButton] = {}
        self.draft: dict[str, Any] | None = None
        self.current_chapter_id: str | None = None
        self.current_outline_node_id: str | None = None
        self.current_world_entry_id: str | None = None
        self.current_character_id: str | None = None
        self.loading_chapter = False
        self.loading_outline = False
        self.loading_worldbuilding = False
        self.loading_character = False
        self.status_icon_cache: dict[str, QIcon] = {}
        self.editor_ai_thread: AIStreamThread | None = None
        self.editor_ai_stream_text = ""
        self.outline_ai_thread: AIStreamThread | None = None
        self.outline_ai_stream_text = ""
        self.outline_selected_chapter_ids: set[str] = set()
        self.character_ai_thread: AIStreamThread | None = None
        self.character_ai_stream_text = ""
        self.character_selected_chapter_ids: set[str] = set()

        self.setWindowTitle(f"{APP_NAME} - 项目首页")
        self.setWindowIcon(app_icon())
        self.resize(1440, 900)
        self.setMinimumSize(1180, 760)
        self.setCentralWidget(self.build_ui())
        self.setup_shortcuts()
        self.apply_styles()
        self.refresh_projects()
        self.update_topbar_actions()

        self.clock = QTimer(self)
        self.clock.timeout.connect(self.update_status_line)
        self.clock.start(60_000)

    def build_ui(self) -> QWidget:
        root = QWidget()
        root_layout = QHBoxLayout(root)
        root_layout.setContentsMargins(0, 0, 0, 0)
        root_layout.setSpacing(0)

        root_layout.addWidget(self.build_sidebar())

        content = QWidget()
        content.setObjectName("Content")
        self.content_layout = QVBoxLayout(content)
        self.content_layout.setContentsMargins(28, 24, 28, 28)
        self.content_layout.setSpacing(18)

        self.topbar_widget = QWidget()
        self.topbar_widget.setLayout(self.build_topbar())
        self.content_layout.addWidget(self.topbar_widget)

        self.page_stack = QStackedWidget()
        self.home_page = self.build_home_page()
        self.editor_page = self.build_editor_page()
        self.outline_page = self.build_outline_page()
        self.worldbuilding_page = self.build_worldbuilding_page()
        self.character_page = self.build_character_page()
        self.settings_page = self.build_settings_page()
        self.page_stack.addWidget(self.home_page)
        self.page_stack.addWidget(self.editor_page)
        self.page_stack.addWidget(self.outline_page)
        self.page_stack.addWidget(self.worldbuilding_page)
        self.page_stack.addWidget(self.character_page)
        self.page_stack.addWidget(self.settings_page)
        self.content_layout.addWidget(self.page_stack, 1)

        root_layout.addWidget(content, 1)
        return root

    def make_tool_button(
        self,
        icon_text: str,
        tooltip: str,
        callback: Any,
        *,
        primary: bool = False,
        color: str | None = None,
    ) -> QToolButton:
        button = QToolButton()
        button.setObjectName("ToolPrimaryButton" if primary else "ToolIconButton")
        icon_color = color or ("#FFFFFF" if primary else PALETTE["ink"])
        button.setIcon(tool_icon(icon_text, icon_color, 22))
        button.setIconSize(QSize(22, 22))
        button.setToolTip(tooltip)
        button.setAccessibleName(tooltip.split(" Ctrl", 1)[0])
        button.clicked.connect(callback)
        return button

    def build_home_page(self) -> QWidget:
        page = QWidget()
        body = QHBoxLayout(page)
        body.setContentsMargins(0, 0, 0, 0)
        body.setSpacing(18)
        body.addWidget(self.build_project_detail(), 5)
        body.addWidget(self.build_project_list(), 2)
        return page

    def build_sidebar(self) -> QWidget:
        sidebar = QFrame()
        sidebar.setObjectName("Sidebar")
        sidebar.setFixedWidth(210)
        layout = QVBoxLayout(sidebar)
        layout.setContentsMargins(22, 28, 22, 28)
        layout.setSpacing(14)

        brand = QHBoxLayout()
        brand.setSpacing(10)
        logo_mark = QLabel()
        logo_mark.setObjectName("LogoMark")
        logo_mark.setFixedSize(44, 44)
        pixmap = white_logo_pixmap(QSize(44, 44))
        if pixmap:
            logo_mark.setPixmap(pixmap)
            logo_mark.setAlignment(Qt.AlignCenter)
        else:
            logo_mark.setText("文")
            logo_mark.setAlignment(Qt.AlignCenter)
        brand_text = QVBoxLayout()
        logo = QLabel(APP_NAME)
        logo.setObjectName("Logo")
        brand_text.addWidget(logo)
        subtitle = QLabel("本地小说项目")
        subtitle.setObjectName("SidebarSub")
        brand_text.addWidget(subtitle)
        version_label = QLabel(f"版本 {APP_VERSION}")
        version_label.setObjectName("SidebarVersion")
        brand_text.addWidget(version_label)
        brand.addWidget(logo_mark)
        brand.addLayout(brand_text, 1)
        layout.addLayout(brand)
        layout.addSpacing(22)

        for text, page_name, icon_name, active in [
            ("项目首页", "home", "home", True),
            ("正文", "editor", "editor", False),
            ("大纲", "outline", "outline", False),
            ("设定库", "worldbuilding", "setting", False),
            ("人物卡", "character", "character", False),
            ("设置", "settings", "config", False),
        ]:
            item = QPushButton(text)
            item.setObjectName("NavActive" if active else "NavItem")
            item.setIcon(nav_icon(icon_name, PALETTE["ink"] if active else "#FFFFFF"))
            item.setIconSize(QSize(20, 20))
            item.setMinimumHeight(42)
            item.setProperty("nav_icon", icon_name)
            item.clicked.connect(lambda checked=False, name=page_name: self.switch_page(name))
            self.nav_buttons[page_name] = item
            layout.addWidget(item)
        layout.addStretch(1)
        return sidebar

    def build_topbar(self) -> QHBoxLayout:
        top = QHBoxLayout()
        title_box = QVBoxLayout()
        self.page_title = QLabel("项目首页")
        self.page_title.setObjectName("PageTitle")
        self.status_line = QLabel("")
        self.status_line.setObjectName("Muted")
        title_box.addWidget(self.page_title)
        title_box.addWidget(self.status_line)
        top.addLayout(title_box, 1)

        new_btn = QPushButton("新建项目")
        new_btn.setObjectName("PrimaryButton")
        new_btn.clicked.connect(self.new_project)
        open_btn = QPushButton("打开项目")
        open_btn.clicked.connect(self.open_project)
        settings_btn = QPushButton("全局设置")
        settings_btn.clicked.connect(lambda: self.switch_page("settings"))
        save_btn = QPushButton("保存当前项目")
        save_btn.setObjectName("PrimaryButton")
        save_btn.clicked.connect(self.save_current_project)

        self.project_action_buttons = [new_btn, open_btn, settings_btn, save_btn]
        for btn in [new_btn, open_btn, settings_btn, save_btn]:
            btn.setMinimumHeight(38)
            top.addWidget(btn)
        return top

    def build_settings_card(self, title: str, subtitle: str = "", danger: bool = False) -> tuple[QFrame, QVBoxLayout]:
        card = QFrame()
        card.setObjectName("SettingsDangerCard" if danger else "SettingsCard")
        layout = QVBoxLayout(card)
        layout.setContentsMargins(18, 16, 18, 16)
        layout.setSpacing(12)
        layout.setAlignment(Qt.AlignTop)
        title_label = QLabel(title)
        title_label.setObjectName("SettingsCardTitle")
        layout.addWidget(title_label)
        if subtitle:
            sub_label = QLabel(subtitle)
            sub_label.setObjectName("Muted")
            sub_label.setWordWrap(True)
            layout.addWidget(sub_label)
        return card, layout

    def add_settings_row(
        self,
        layout: QGridLayout,
        row: int,
        label: str,
        widget: QWidget,
        note: str = "",
    ) -> None:
        label_widget = QLabel(label)
        label_widget.setObjectName("SettingsRowLabel")
        layout.addWidget(label_widget, row, 0, Qt.AlignTop)
        layout.addWidget(widget, row, 1)
        if note:
            note_label = QLabel(note)
            note_label.setObjectName("Muted")
            note_label.setWordWrap(True)
            layout.addWidget(note_label, row + 1, 1)

    def make_settings_combo(self, values: list[str], editable: bool = False) -> QComboBox:
        combo = QComboBox()
        combo.setObjectName("SettingsCombo")
        combo.setEditable(editable)
        combo.addItems(values)
        combo.setMinimumHeight(34)
        return combo

    def set_combo_text(self, combo: QComboBox, value: Any) -> None:
        text = str(value)
        if combo.findText(text) < 0:
            combo.addItem(text)
        combo.setCurrentText(text)

    def combo_int_value(self, combo: QComboBox, default: int, minimum: int, maximum: int) -> int:
        raw = combo.currentText().strip()
        digits = "".join(ch for ch in raw if ch.isdigit())
        if not digits:
            return default
        return min(max(int(digits), minimum), maximum)

    def build_settings_page(self) -> QWidget:
        page = QWidget()
        page.setObjectName("SettingsPage")
        layout = QVBoxLayout(page)
        layout.setContentsMargins(28, 24, 28, 24)
        layout.setSpacing(16)

        header = QHBoxLayout()
        title_box = QVBoxLayout()
        title = QLabel("设置")
        title.setObjectName("PageTitle")
        subtitle = QLabel("全局配置、AI 接口、自动保存、快捷键和当前项目维护。")
        subtitle.setObjectName("Muted")
        title_box.addWidget(title)
        title_box.addWidget(subtitle)
        header.addLayout(title_box, 1)

        save_btn = QPushButton("保存设置")
        save_btn.setObjectName("PrimaryButton")
        save_btn.clicked.connect(self.save_app_settings_from_ui)
        reset_btn = QPushButton("恢复默认")
        reset_btn.clicked.connect(self.restore_default_app_settings)
        header.addWidget(reset_btn)
        header.addWidget(save_btn)
        layout.addLayout(header)

        scroll = QScrollArea()
        scroll.setObjectName("SettingsScroll")
        scroll.setWidgetResizable(True)
        content = QWidget()
        grid = QGridLayout(content)
        grid.setContentsMargins(0, 0, 0, 0)
        grid.setHorizontalSpacing(16)
        grid.setVerticalSpacing(16)
        grid.setColumnStretch(0, 1)
        grid.setColumnStretch(1, 1)

        appearance_card, appearance_layout = self.build_settings_card("外观与编辑默认", "护眼模式和默认编辑字体会影响新项目或后续打开的编辑体验。")
        appearance_form = QGridLayout()
        appearance_form.setHorizontalSpacing(12)
        appearance_form.setVerticalSpacing(8)
        self.eye_mode_check = QCheckBox("打开后页面背景变成护眼绿")
        self.eye_mode_check.toggled.connect(self.preview_eye_mode_from_ui)
        self.settings_font_box = QFontComboBox()
        self.settings_font_box.setObjectName("SettingsCombo")
        self.settings_font_box.setMinimumHeight(34)
        self.settings_body_font_size_box = self.make_settings_combo(["12", "13", "14", "15", "16", "18", "20", "22", "24"], True)
        self.settings_title_font_size_box = self.make_settings_combo(["18", "20", "22", "24", "26", "28", "30", "32"], True)
        self.ui_scale_box = self.make_settings_combo(["100%", "110%", "125%"])
        self.add_settings_row(appearance_form, 0, "护眼模式", self.eye_mode_check)
        self.add_settings_row(appearance_form, 2, "默认字体", self.settings_font_box)
        self.add_settings_row(appearance_form, 4, "正文字号", self.settings_body_font_size_box)
        self.add_settings_row(appearance_form, 6, "标题字号", self.settings_title_font_size_box)
        self.add_settings_row(appearance_form, 8, "界面缩放", self.ui_scale_box, "第一版先提供常用比例，后续可做更细的显示适配。")
        appearance_layout.addLayout(appearance_form)

        save_card, save_layout = self.build_settings_card("保存与备份", "自动保存默认 10 分钟一次；手动备份会生成当前项目压缩包。")
        save_form = QGridLayout()
        save_form.setHorizontalSpacing(12)
        save_form.setVerticalSpacing(8)
        self.auto_save_enabled_check = QCheckBox("启用自动保存")
        self.settings_auto_save_box = self.make_settings_combo(["1 分钟", "3 分钟", "5 分钟", "10 分钟", "15 分钟", "30 分钟"], True)
        self.backup_retention_box = self.make_settings_combo(["3 份", "5 份", "10 份", "20 份", "50 份"], True)
        self.settings_last_auto_label = QLabel("-")
        self.settings_last_auto_label.setObjectName("SettingsValueLabel")
        backup_buttons = QHBoxLayout()
        manual_backup_btn = QPushButton("创建备份")
        manual_backup_btn.clicked.connect(self.create_manual_backup)
        restore_btn = QPushButton("从备份恢复")
        restore_btn.clicked.connect(self.restore_from_backup)
        backup_buttons.addWidget(manual_backup_btn)
        backup_buttons.addWidget(restore_btn)
        backup_buttons.addStretch(1)
        backup_widget = QWidget()
        backup_widget.setObjectName("SettingsInlineGroup")
        backup_widget.setLayout(backup_buttons)
        self.add_settings_row(save_form, 0, "自动保存", self.auto_save_enabled_check)
        self.add_settings_row(save_form, 2, "保存间隔", self.settings_auto_save_box)
        self.add_settings_row(save_form, 4, "上次自动保存", self.settings_last_auto_label)
        self.add_settings_row(save_form, 6, "备份保留", self.backup_retention_box)
        self.add_settings_row(save_form, 8, "手动备份", backup_widget)
        save_layout.addLayout(save_form)

        export_card, export_layout = self.build_settings_card("导出默认", "这里设置导出正文与大纲时的默认格式，具体导出入口仍放在对应页面。")
        export_form = QGridLayout()
        export_form.setHorizontalSpacing(12)
        export_form.setVerticalSpacing(8)
        self.export_format_box = QComboBox()
        self.export_format_box.setObjectName("SettingsCombo")
        self.export_format_box.addItems(["Markdown", "TXT"])
        self.export_volume_check = QCheckBox("包含卷名")
        self.export_chapter_check = QCheckBox("包含章节标题")
        self.export_status_check = QCheckBox("包含章节状态")
        export_options = QWidget()
        export_options.setObjectName("SettingsInlineGroup")
        export_options_layout = QVBoxLayout(export_options)
        export_options_layout.setContentsMargins(0, 0, 0, 0)
        export_options_layout.setSpacing(6)
        export_options_layout.addWidget(self.export_volume_check)
        export_options_layout.addWidget(self.export_chapter_check)
        export_options_layout.addWidget(self.export_status_check)
        self.add_settings_row(export_form, 0, "默认格式", self.export_format_box)
        self.add_settings_row(export_form, 2, "正文导出", export_options)
        export_layout.addLayout(export_form)

        ai_card, ai_layout = self.build_settings_card("AI 接口", "OpenAI 兼容接口；AI 默认读取章节总结、设定库、人物卡与大纲，不直接读取完整正文。")
        ai_form = QGridLayout()
        ai_form.setHorizontalSpacing(12)
        ai_form.setVerticalSpacing(8)
        self.ai_enabled_check = QCheckBox("启用 AI 辅助")
        self.ai_key_edit = QLineEdit()
        self.ai_key_edit.setObjectName("SettingsInput")
        self.ai_key_edit.setEchoMode(QLineEdit.Password)
        self.ai_key_edit.setPlaceholderText("API Key 仅保存在本机全局设置")
        self.ai_base_url_box = self.make_settings_combo(
            [
                "https://api.deepseek.com/v1",
                "https://api.openai.com/v1",
                "https://dashscope.aliyuncs.com/compatible-mode/v1",
                "http://localhost:11434/v1",
            ],
            True,
        )
        self.ai_model_box = self.make_settings_combo(
            [
                "deepseek-chat",
                "gpt-4o-mini",
                "gpt-4.1-mini",
                "qwen-plus",
                "qwen-turbo",
                "local-model",
            ],
            True,
        )
        self.ai_context_box = self.make_settings_combo(["60", "100", "500", "1000", "3000", "5000", "10000"], True)
        self.ai_status_label = QLabel("尚未测试连接。")
        self.ai_status_label.setObjectName("Muted")
        self.ai_role_name_edit = QLineEdit()
        self.ai_role_name_edit.setObjectName("SettingsInput")
        self.ai_role_name_edit.setPlaceholderText("默认：AI")
        self.ai_role_identity_edit = QLineEdit()
        self.ai_role_identity_edit.setObjectName("SettingsInput")
        self.ai_role_identity_edit.setPlaceholderText("例如：创作助手、剧情顾问、严厉审稿人")
        self.ai_role_prompt_edit = QTextEdit()
        self.ai_role_prompt_edit.setObjectName("SummaryBox")
        self.ai_role_prompt_edit.setPlaceholderText("补充 AI 的性格、说话口吻、工作原则、偏好和禁忌。")
        self.ai_role_prompt_edit.setMinimumHeight(96)
        ai_buttons = QHBoxLayout()
        test_btn = QPushButton("测试连接")
        test_btn.setObjectName("PrimaryButton")
        test_btn.clicked.connect(self.test_ai_connection)
        clear_ai_btn = QPushButton("清空密钥")
        clear_ai_btn.clicked.connect(lambda: self.ai_key_edit.clear())
        ai_buttons.addWidget(test_btn)
        ai_buttons.addWidget(clear_ai_btn)
        ai_buttons.addStretch(1)
        ai_buttons_widget = QWidget()
        ai_buttons_widget.setObjectName("SettingsInlineGroup")
        ai_buttons_widget.setLayout(ai_buttons)
        scope_box = QLabel("读取范围：章节总结 / 大纲 / 设定库 / 人物卡 / 人物关系备注。正文全文只在用户手动要求或局部选择时进入 AI。")
        scope_box.setObjectName("SettingsScopeBox")
        scope_box.setWordWrap(True)
        self.add_settings_row(ai_form, 0, "AI 开关", self.ai_enabled_check)
        self.add_settings_row(ai_form, 2, "API Key", self.ai_key_edit)
        self.add_settings_row(ai_form, 4, "Base URL", self.ai_base_url_box)
        self.add_settings_row(ai_form, 6, "模型名", self.ai_model_box)
        self.add_settings_row(ai_form, 8, "上下文上限", self.ai_context_box)
        self.add_settings_row(ai_form, 10, "连接", ai_buttons_widget)
        ai_form.addWidget(self.ai_status_label, 12, 1)
        self.add_settings_row(ai_form, 14, "AI 名称", self.ai_role_name_edit)
        self.add_settings_row(ai_form, 16, "AI 身份", self.ai_role_identity_edit)
        self.add_settings_row(ai_form, 18, "角色设定", self.ai_role_prompt_edit)
        ai_form.addWidget(scope_box, 20, 0, 1, 2)
        ai_layout.addLayout(ai_form)

        shortcut_card, shortcut_layout = self.build_settings_card("快捷键", "第一版先固定常用快捷键，后续再做自定义快捷键编辑。")
        shortcut_lines = [
            ("Ctrl + S", "保存当前章节或当前项目"),
            ("Ctrl + F", "正文查找"),
            ("Ctrl + B", "加粗"),
            ("Ctrl + Z", "撤销"),
            ("Ctrl + Y / Ctrl + Shift + Z", "重做"),
        ]
        for shortcut, desc in shortcut_lines:
            row = QHBoxLayout()
            key = QLabel(shortcut)
            key.setObjectName("ShortcutKey")
            value = QLabel(desc)
            value.setObjectName("Muted")
            row.addWidget(key)
            row.addWidget(value, 1)
            shortcut_layout.addLayout(row)

        maintenance_card, maintenance_layout = self.build_settings_card("当前项目维护", "这里放项目级操作，删除项目仍需要输入项目名二次确认。", danger=True)
        maintenance_grid = QGridLayout()
        maintenance_grid.setHorizontalSpacing(10)
        maintenance_grid.setVerticalSpacing(10)
        open_folder_btn = QPushButton("打开项目文件夹")
        open_folder_btn.clicked.connect(self.open_project_folder)
        relink_btn = QPushButton("重新关联项目")
        relink_btn.clicked.connect(self.relink_selected_project)
        integrity_btn = QPushButton("检查项目完整性")
        integrity_btn.clicked.connect(self.check_project_integrity)
        clear_missing_btn = QPushButton("清理失效图片引用")
        clear_missing_btn.clicked.connect(self.clear_missing_image_refs)
        delete_btn = QPushButton("删除当前项目")
        delete_btn.setObjectName("DangerButton")
        delete_btn.clicked.connect(self.delete_selected_project)
        maintenance_grid.addWidget(open_folder_btn, 0, 0)
        maintenance_grid.addWidget(relink_btn, 0, 1)
        maintenance_grid.addWidget(integrity_btn, 1, 0)
        maintenance_grid.addWidget(clear_missing_btn, 1, 1)
        maintenance_grid.addWidget(delete_btn, 2, 0, 1, 2)
        maintenance_layout.addLayout(maintenance_grid)

        grid.addWidget(appearance_card, 0, 0)
        grid.addWidget(ai_card, 0, 1, 2, 1)
        grid.addWidget(save_card, 1, 0)
        grid.addWidget(export_card, 2, 0)
        grid.addWidget(shortcut_card, 2, 1)
        grid.addWidget(maintenance_card, 3, 0, 1, 2)
        grid.setRowStretch(4, 1)

        scroll.setWidget(content)
        layout.addWidget(scroll, 1)
        self.load_settings_page()
        return page

    def build_editor_page(self) -> QWidget:
        page = QWidget()
        page.setObjectName("EditorPage")
        layout = QHBoxLayout(page)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        chapter_sidebar = self.build_chapter_sidebar()
        chapter_sidebar.setFixedWidth(274)
        ai_panel = self.build_ai_panel()
        ai_panel.setFixedWidth(350)
        layout.addWidget(chapter_sidebar)
        layout.addWidget(self.build_editor_center(), 1)
        layout.addWidget(ai_panel)
        return page

    def build_chapter_sidebar(self) -> QWidget:
        box = QFrame()
        box.setObjectName("EditorChapterPane")
        layout = QVBoxLayout(box)
        layout.setContentsMargins(18, 22, 12, 18)
        layout.setSpacing(16)

        header = QHBoxLayout()
        title = QLabel("正文目录")
        title.setObjectName("SectionTitle")
        header.addWidget(title, 1)

        add_btn = QPushButton("+")
        add_btn.setObjectName("RoundToolButton")
        add_menu = QMenu(add_btn)
        add_menu.addAction("新增卷", self.add_volume)
        add_menu.addAction("新增章节", self.add_chapter)
        add_btn.setMenu(add_menu)

        remove_btn = QPushButton("-")
        remove_btn.setObjectName("RoundToolButton")
        remove_btn.clicked.connect(self.delete_selected_outline_item)
        header.addWidget(add_btn)
        header.addWidget(remove_btn)
        layout.addLayout(header)

        self.chapter_tree = QTreeWidget()
        self.chapter_tree.setObjectName("ChapterTree")
        self.chapter_tree.setHeaderHidden(True)
        self.chapter_tree.setIndentation(10)
        self.chapter_tree.setIconSize(QSize(10, 10))
        self.chapter_tree.setContextMenuPolicy(Qt.CustomContextMenu)
        self.chapter_tree.itemSelectionChanged.connect(self.on_outline_selected)
        self.chapter_tree.customContextMenuRequested.connect(self.show_outline_context_menu)
        layout.addWidget(self.chapter_tree, 1)
        return box

    def build_editor_center(self) -> QWidget:
        box = QFrame()
        box.setObjectName("EditorCenterPane")
        layout = QVBoxLayout(box)
        layout.setContentsMargins(24, 22, 24, 26)
        layout.setSpacing(14)

        top = QHBoxLayout()
        title_group = QVBoxLayout()
        title_group.setSpacing(4)
        self.chapter_title_label = QLabel("正文")
        self.chapter_title_label.setObjectName("SectionTitle")
        self.chapter_meta_label = QLabel("本章 0 字 · 今日 0 字 · 尚未保存")
        self.chapter_meta_label.setObjectName("Muted")
        self.chapter_meta_label.setMinimumWidth(620)
        self.chapter_meta_label.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        title_group.addWidget(self.chapter_title_label)
        title_group.addWidget(self.chapter_meta_label)
        top.addLayout(title_group, 1)

        self.chapter_status_btn = QPushButton("草稿")
        self.chapter_status_btn.setObjectName("StatusDraft")
        status_menu = QMenu(self.chapter_status_btn)
        status_menu.addAction("修订中", lambda: self.set_chapter_status("修订中"))
        status_menu.addAction("草稿", lambda: self.set_chapter_status("草稿"))
        status_menu.addAction("完稿", lambda: self.set_chapter_status("完稿"))
        self.chapter_status_btn.setMenu(status_menu)
        self.chapter_status_btn.setMinimumWidth(92)
        top.addWidget(self.chapter_status_btn)

        self.find_edit = QLineEdit()
        self.find_edit.setPlaceholderText("查找正文")
        self.find_edit.setFixedWidth(150)
        self.find_edit.returnPressed.connect(self.find_in_editor)
        find_btn = QPushButton("查找")
        find_btn.setObjectName("SmallButton")
        find_btn.clicked.connect(self.find_in_editor)
        self.find_btn = find_btn
        self.find_edit.hide()
        self.find_btn.hide()
        layout.addLayout(top)

        toolbar = QHBoxLayout()
        toolbar.setSpacing(6)
        undo_btn = self.make_tool_button("undo", "撤销 Ctrl+Z", self.editor_undo)
        redo_btn = self.make_tool_button("redo", "重做 Ctrl+Y / Ctrl+Shift+Z", self.editor_redo)
        bold_btn = self.make_tool_button("bold", "加粗 Ctrl+B", self.toggle_bold)
        heading_btn = self.make_tool_button("heading", "设为标题", self.apply_heading)
        note_btn = self.make_tool_button("comment", "插入批注", self.apply_comment_style)
        clear_format_btn = self.make_tool_button("eraser", "清除格式", self.clear_editor_format)
        align_btn = self.make_tool_button("align", "对齐方式", lambda: None)
        align_menu = QMenu(align_btn)
        align_menu.addAction("左对齐", lambda: self.set_editor_alignment(Qt.AlignLeft))
        align_menu.addAction("居中", lambda: self.set_editor_alignment(Qt.AlignHCenter))
        align_menu.addAction("右对齐", lambda: self.set_editor_alignment(Qt.AlignRight))
        align_btn.setMenu(align_menu)
        align_btn.setPopupMode(QToolButton.InstantPopup)

        line_spacing_btn = self.make_tool_button("line-spacing", "行距", lambda: None)
        line_spacing_menu = QMenu(line_spacing_btn)
        for spacing in [28, 30, 34, 38, 42, 48, 56]:
            line_spacing_menu.addAction(f"{spacing} px", lambda checked=False, value=spacing: self.apply_editor_line_spacing(value))
        line_spacing_btn.setMenu(line_spacing_menu)
        line_spacing_btn.setPopupMode(QToolButton.InstantPopup)

        self.font_box = QFontComboBox()
        self.font_box.setObjectName("ToolbarFontCombo")
        self.font_box.setToolTip("字体")
        self.font_box.setFixedSize(154, 34)
        self.font_box.currentFontChanged.connect(self.change_editor_font)
        self.font_size_spin = QSpinBox()
        self.font_size_spin.setObjectName("CompactSpin")
        self.font_size_spin.setToolTip("字号")
        self.font_size_spin.setRange(10, 32)
        self.font_size_spin.setValue(DEFAULT_BODY_FONT_SIZE)
        self.font_size_spin.setSuffix(" pt")
        self.font_size_spin.setFixedWidth(76)
        self.font_size_spin.valueChanged.connect(self.change_editor_font_size)
        self.font_size_spin.hide()
        self.font_size_box = QComboBox()
        self.font_size_box.setObjectName("ToolbarSizeCombo")
        self.font_size_box.setToolTip("字号")
        self.font_size_box.setFixedSize(70, 34)
        self.font_size_box.setEditable(True)
        for size in [10, 12, 14, 15, 16, 18, 20, 22, 24, 28, 32]:
            self.font_size_box.addItem(str(size), size)
        self.font_size_box.setCurrentText(str(DEFAULT_BODY_FONT_SIZE))
        self.font_size_box.currentTextChanged.connect(self.on_font_size_box_changed)
        self.line_spacing_spin = QSpinBox()
        self.line_spacing_spin.setObjectName("CompactSpin")
        self.line_spacing_spin.setRange(24, 56)
        self.line_spacing_spin.setValue(DEFAULT_LINE_SPACING)
        self.line_spacing_spin.setSuffix(" px")
        self.line_spacing_spin.valueChanged.connect(self.change_editor_line_spacing)
        self.line_spacing_spin.hide()
        self.word_count_label = self.chapter_meta_label
        save_btn = self.make_tool_button("save", "保存当前章节 Ctrl+S", self.save_current_chapter, primary=True)
        for button in [undo_btn, redo_btn, bold_btn, heading_btn, note_btn, clear_format_btn, align_btn]:
            toolbar.addWidget(button)
        toolbar.addWidget(self.font_box)
        toolbar.addWidget(self.font_size_box)
        toolbar.addWidget(line_spacing_btn)
        toolbar.addWidget(self.find_edit)
        toolbar.addWidget(self.find_btn)
        toolbar.addStretch(1)
        toolbar.addWidget(save_btn)
        layout.addLayout(toolbar)

        self.editor = ManuscriptEditor()
        self.editor.setObjectName("ManuscriptEditor")
        self.editor.textChanged.connect(self.on_editor_changed)
        self.editor.cursorPositionChanged.connect(self.sync_editor_toolbar_state)
        layout.addWidget(self.editor, 1)
        return box

    def build_ai_chat_input(self, placeholder: str, callback) -> QTextEdit:
        edit = QTextEdit()
        edit.setObjectName("AIChatInput")
        edit.setAcceptRichText(False)
        edit.setPlaceholderText(placeholder)
        edit.setTabChangesFocus(True)
        edit.setMinimumHeight(124)
        edit.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        edit.setToolTip("Ctrl+Enter 发送")
        for sequence in ["Ctrl+Return", "Ctrl+Enter"]:
            shortcut = QShortcut(QKeySequence(sequence), edit)
            shortcut.activated.connect(callback)
        return edit

    def build_ai_icon_button(self, icon: str, tooltip: str, callback: Any, *, primary: bool = False) -> QToolButton:
        button = QToolButton()
        button.setObjectName("AIPrimaryIconButton" if primary else "AIIconButton")
        icon_color = "#FFFFFF" if primary else PALETTE["ink"]
        button.setIcon(tool_icon(icon, icon_color, 16))
        button.setIconSize(QSize(16, 16))
        button.setFixedSize(28, 28)
        button.setToolTip(tooltip)
        button.setAccessibleName(tooltip)
        button.clicked.connect(callback)
        return button

    def build_ai_panel(self) -> QWidget:
        box = QFrame()
        box.setObjectName("EditorAIPane")
        layout = QVBoxLayout(box)
        layout.setContentsMargins(18, 22, 18, 22)
        layout.setSpacing(18)

        title = QLabel("AI 区域")
        title.setObjectName("SectionTitle")
        layout.addWidget(title)

        summary_title = QLabel("本章总结")
        summary_title.setObjectName("DetailName")
        summary_header = QHBoxLayout()
        summary_header.addWidget(summary_title, 1)
        self.ai_chapter_enabled_check = QCheckBox("本章允许 AI 辅助")
        self.ai_chapter_enabled_check.setChecked(True)
        self.ai_chapter_enabled_check.toggled.connect(self.set_current_chapter_ai_enabled)
        summary_header.addWidget(self.ai_chapter_enabled_check)
        self.summary_generate_btn = QPushButton("生成总结")
        self.summary_generate_btn.setObjectName("SmallButton")
        self.summary_generate_btn.clicked.connect(self.request_chapter_summary)
        summary_header.addWidget(self.summary_generate_btn)
        layout.addLayout(summary_header)

        self.summary_ai_progress_label = QLabel("")
        self.summary_ai_progress_label.setObjectName("Muted")
        self.summary_ai_progress_label.setWordWrap(True)
        self.summary_ai_progress_label.hide()
        layout.addWidget(self.summary_ai_progress_label)

        self.summary_box = QTextEdit()
        self.summary_box.setObjectName("SummaryBox")
        self.summary_box.setPlaceholderText("点击“生成总结”后，由 AI 生成本章总结；也可以手动编辑保存。")
        self.summary_box.setMinimumHeight(230)
        self.summary_box.textChanged.connect(self.on_summary_changed)
        layout.addWidget(self.summary_box)

        chat_title = QLabel("AI 聊天助手")
        chat_title.setObjectName("DetailName")
        layout.addWidget(chat_title)

        self.editor_ai_scope_label = QLabel("读取范围：章节总结 / 大纲 / 时间线 / 设定库 / 人物卡 / 人物关系记录；默认不读取完整正文。")
        self.editor_ai_scope_label.setObjectName("ScopeBadge")
        self.editor_ai_scope_label.setWordWrap(True)
        layout.addWidget(self.editor_ai_scope_label)

        self.chat_log = QTextEdit()
        self.chat_log.setObjectName("SummaryBox")
        self.chat_log.setReadOnly(True)
        self.chat_log.setText("AI 聊天会在接口配置完成后启用。\n\n默认读取章节总结、设定、人物卡、人物关系记录和时间线；不直接读取完整正文。")
        layout.addWidget(self.chat_log, 1)

        chat_input_box = QWidget()
        chat_input_box.setObjectName("AIInputPanel")
        chat_input_layout = QVBoxLayout(chat_input_box)
        chat_input_layout.setContentsMargins(0, 0, 0, 0)
        chat_input_layout.setSpacing(6)
        self.chat_input = self.build_ai_chat_input("向 AI 提问", self.send_ai_message)
        chat_input_layout.addWidget(self.chat_input)
        self.chat_send_btn = self.build_ai_icon_button("send", "发送", self.send_ai_message, primary=True)
        self.chat_stop_btn = self.build_ai_icon_button("stop", "停止生成", self.stop_editor_ai_stream)
        self.chat_stop_btn.setEnabled(False)
        self.chat_clear_btn = self.build_ai_icon_button("trash", "清除对话", self.clear_ai_chat)
        chat_actions = QHBoxLayout()
        chat_actions.setContentsMargins(0, 0, 0, 0)
        chat_actions.setSpacing(6)
        chat_actions.addStretch(1)
        chat_actions.addWidget(self.chat_send_btn)
        chat_actions.addWidget(self.chat_stop_btn)
        chat_actions.addWidget(self.chat_clear_btn)
        chat_input_layout.addLayout(chat_actions)
        layout.addWidget(chat_input_box)
        return box

    def build_outline_page(self) -> QWidget:
        page = QWidget()
        page.setObjectName("OutlinePage")
        layout = QVBoxLayout(page)
        layout.setContentsMargins(24, 20, 24, 22)
        layout.setSpacing(14)

        header = QHBoxLayout()
        title_group = QVBoxLayout()
        title_group.setSpacing(4)
        title = QLabel("大纲")
        title.setObjectName("PageTitle")
        self.outline_status_label = QLabel("未打开项目")
        self.outline_status_label.setObjectName("Muted")
        title_group.addWidget(title)
        title_group.addWidget(self.outline_status_label)
        header.addLayout(title_group, 1)

        save_btn = QPushButton("保存当前项目")
        save_btn.setObjectName("PrimaryButton")
        save_btn.clicked.connect(self.save_current_project)
        export_btn = QPushButton("导出大纲")
        export_btn.clicked.connect(self.export_outline)
        for btn in (save_btn, export_btn):
            btn.setMinimumHeight(38)
            header.addWidget(btn)
        layout.addLayout(header)

        body = QHBoxLayout()
        body.setSpacing(18)
        body.addWidget(self.build_outline_sidebar())

        center = QVBoxLayout()
        center.setSpacing(14)
        center.addWidget(self.build_outline_editor_panel(), 1)
        center.addWidget(self.build_outline_timeline_panel())
        body.addLayout(center, 1)
        body.addWidget(self.build_outline_ai_panel())
        layout.addLayout(body, 1)
        return page

    def build_outline_sidebar(self) -> QWidget:
        box = QFrame()
        box.setObjectName("OutlineDirectoryPane")
        box.setFixedWidth(274)
        layout = QVBoxLayout(box)
        layout.setContentsMargins(18, 18, 14, 18)
        layout.setSpacing(14)

        title = QLabel("大纲目录")
        title.setObjectName("SectionTitle")
        subtitle = QLabel("总纲、卷、章、剧情节点")
        subtitle.setObjectName("Muted")
        layout.addWidget(title)
        layout.addWidget(subtitle)

        actions = QHBoxLayout()
        for label, kind in [("+ 卷", "volume"), ("+ 章", "chapter"), ("+ 节点", "node")]:
            btn = QPushButton(label)
            btn.setObjectName("SmallButton" if kind != "node" else "PrimaryButton")
            btn.clicked.connect(lambda checked=False, value=kind: self.add_outline_node(value))
            actions.addWidget(btn)
        layout.addLayout(actions)

        self.outline_tree = QTreeWidget()
        self.outline_tree.setObjectName("OutlineTree")
        self.outline_tree.setHeaderHidden(True)
        self.outline_tree.setIndentation(14)
        self.outline_tree.setIconSize(QSize(10, 10))
        self.outline_tree.setContextMenuPolicy(Qt.CustomContextMenu)
        self.outline_tree.itemSelectionChanged.connect(self.on_outline_node_selected)
        self.outline_tree.customContextMenuRequested.connect(self.show_outline_node_menu)
        layout.addWidget(self.outline_tree, 1)
        return box

    def build_outline_editor_panel(self) -> QWidget:
        box = QFrame()
        box.setObjectName("OutlineEditorPane")
        layout = QVBoxLayout(box)
        layout.setContentsMargins(18, 18, 18, 14)
        layout.setSpacing(12)

        top = QHBoxLayout()
        title_group = QVBoxLayout()
        title_group.setSpacing(3)
        self.outline_node_title_label = QLabel("细纲编辑")
        self.outline_node_title_label.setObjectName("SectionTitle")
        self.outline_node_meta_label = QLabel("选择左侧目录开始编辑")
        self.outline_node_meta_label.setObjectName("Muted")
        title_group.addWidget(self.outline_node_title_label)
        title_group.addWidget(self.outline_node_meta_label)
        top.addLayout(title_group, 1)
        save_btn = QPushButton("保存细纲")
        save_btn.setObjectName("PrimaryButton")
        save_btn.clicked.connect(self.save_current_outline_node)
        top.addWidget(save_btn)
        layout.addLayout(top)

        toolbar = QHBoxLayout()
        toolbar.setSpacing(6)
        for icon, tooltip, callback in [
            ("undo", "撤销", lambda: self.outline_editor.undo()),
            ("redo", "重做", lambda: self.outline_editor.redo()),
            ("bold", "加粗", self.toggle_bold),
            ("heading", "设为标题", self.apply_heading),
            ("comment", "插入批注", self.apply_comment_style),
        ]:
            toolbar.addWidget(self.make_tool_button(icon, tooltip, callback))
        self.outline_font_box = QFontComboBox()
        self.outline_font_box.setObjectName("ToolbarFontCombo")
        self.outline_font_box.setFixedSize(180, 34)
        self.outline_font_box.setCurrentFont(QFont(DEFAULT_BODY_FONT_FAMILY))
        self.outline_font_box.currentFontChanged.connect(self.change_outline_font)
        self.outline_font_size_box = QComboBox()
        self.outline_font_size_box.setObjectName("ToolbarSizeCombo")
        self.outline_font_size_box.setFixedSize(78, 34)
        self.outline_font_size_box.setEditable(True)
        for size in [10, 12, 14, 15, 16, 18, 20, 22, 24, 28]:
            self.outline_font_size_box.addItem(str(size), size)
        self.outline_font_size_box.setCurrentText("14")
        self.outline_font_size_box.currentTextChanged.connect(self.change_outline_font_size)
        toolbar.addWidget(self.outline_font_box)
        toolbar.addWidget(self.outline_font_size_box)
        toolbar.addStretch(1)
        layout.addLayout(toolbar)

        goal_frame = QFrame()
        goal_frame.setObjectName("OutlineGoalBox")
        goal_layout = QHBoxLayout(goal_frame)
        goal_layout.setContentsMargins(14, 10, 14, 10)
        goal = QLabel("本节点目标")
        goal.setObjectName("DetailName")
        self.outline_goal_edit = QLineEdit()
        self.outline_goal_edit.setPlaceholderText("写下这一段细纲要解决的剧情目标")
        self.outline_timeline_tag_edit = QLineEdit()
        self.outline_timeline_tag_edit.setPlaceholderText("时间线标签，如 主线 · T0")
        self.outline_timeline_tag_edit.setFixedWidth(160)
        goal_layout.addWidget(goal)
        goal_layout.addWidget(self.outline_goal_edit, 1)
        goal_layout.addWidget(self.outline_timeline_tag_edit)
        layout.addWidget(goal_frame)

        self.outline_editor = QTextEdit()
        self.outline_editor.setObjectName("OutlineTextEdit")
        self.outline_editor.setAcceptRichText(True)
        self.outline_editor.setPlaceholderText("在这里写总纲、细纲、剧情节点、伏笔、节奏备注。")
        self.outline_editor.textChanged.connect(self.on_outline_text_changed)
        layout.addWidget(self.outline_editor, 1)
        return box

    def build_outline_timeline_panel(self) -> QWidget:
        box = QFrame()
        box.setObjectName("OutlineTimelinePane")
        layout = QVBoxLayout(box)
        layout.setContentsMargins(18, 14, 18, 14)
        layout.setSpacing(10)

        header = QHBoxLayout()
        title = QLabel("时间轴")
        title.setObjectName("SectionTitle")
        subtitle = QLabel("底部抽屉，可自由展开 / 收起")
        subtitle.setObjectName("Muted")
        header.addWidget(title)
        header.addWidget(subtitle, 1)
        add_btn = QPushButton("+ 时间点")
        add_btn.setObjectName("PrimaryButton")
        add_btn.clicked.connect(self.add_timeline_point)
        self.timeline_toggle_btn = QPushButton("收起时间轴")
        self.timeline_toggle_btn.clicked.connect(self.toggle_outline_timeline)
        header.addWidget(add_btn)
        header.addWidget(self.timeline_toggle_btn)
        layout.addLayout(header)

        self.timeline_body = QWidget()
        timeline_layout = QVBoxLayout(self.timeline_body)
        timeline_layout.setContentsMargins(0, 0, 0, 0)
        self.timeline_tree = QTreeWidget()
        self.timeline_tree.setObjectName("TimelineTree")
        self.timeline_tree.setHeaderLabels(["时间", "事件", "线索/章节"])
        self.timeline_tree.setRootIsDecorated(False)
        self.timeline_tree.setAlternatingRowColors(False)
        timeline_layout.addWidget(self.timeline_tree)
        layout.addWidget(self.timeline_body)
        return box

    def build_outline_ai_panel(self) -> QWidget:
        box = QFrame()
        box.setObjectName("OutlineAIPane")
        box.setFixedWidth(330)
        layout = QVBoxLayout(box)
        layout.setContentsMargins(18, 18, 18, 18)
        layout.setSpacing(14)

        title = QLabel("AI 大纲助手")
        title.setObjectName("SectionTitle")
        layout.addWidget(title)

        self.outline_scope_toggle_btn = QPushButton("读取范围 >")
        self.outline_scope_toggle_btn.setObjectName("SmallButton")
        self.outline_scope_toggle_btn.clicked.connect(self.toggle_outline_ai_scope)
        layout.addWidget(self.outline_scope_toggle_btn)

        self.outline_scope_frame = QFrame()
        self.outline_scope_frame.setObjectName("OutlineScopeBox")
        scope_layout = QVBoxLayout(self.outline_scope_frame)
        scope_layout.setContentsMargins(12, 10, 12, 10)
        scope_layout.setSpacing(8)
        scope_title = QLabel("读取范围")
        scope_title.setObjectName("DetailName")
        scope_layout.addWidget(scope_title)

        self.outline_scope_checks: dict[str, QCheckBox] = {}
        scope_grid = QGridLayout()
        scope_grid.setHorizontalSpacing(8)
        scope_grid.setVerticalSpacing(4)
        scope_items = [
            ("outline", "大纲"),
            ("timeline", "时间轴"),
            ("world", "设定库"),
            ("characters", "人物卡"),
            ("relations", "关系记录"),
            ("summaries", "章节总结"),
            ("current_chapter_body", "当前章正文"),
            ("selected_chapter_bodies", "指定章节正文"),
            ("all_chapter_bodies", "全书正文"),
        ]
        defaults = default_outline_ai_scope()
        for index, (key, label) in enumerate(scope_items):
            check = QCheckBox(label)
            check.setChecked(defaults.get(key, False))
            check.toggled.connect(self.on_outline_ai_scope_changed)
            self.outline_scope_checks[key] = check
            scope_grid.addWidget(check, index // 2, index % 2)
        scope_layout.addLayout(scope_grid)

        selected_row = QHBoxLayout()
        self.outline_selected_chapters_label = QLabel("未选择章节")
        self.outline_selected_chapters_label.setObjectName("Muted")
        self.outline_select_chapters_btn = QPushButton("选择章节")
        self.outline_select_chapters_btn.clicked.connect(self.choose_outline_ai_chapters)
        selected_row.addWidget(self.outline_selected_chapters_label, 1)
        selected_row.addWidget(self.outline_select_chapters_btn)
        scope_layout.addLayout(selected_row)

        self.outline_scope_hint_label = QLabel("默认不读取完整正文；勾选正文类范围后会在请求前确认。")
        self.outline_scope_hint_label.setObjectName("ScopeBadge")
        self.outline_scope_hint_label.setWordWrap(True)
        scope_layout.addWidget(self.outline_scope_hint_label)
        self.outline_scope_frame.setVisible(False)
        layout.addWidget(self.outline_scope_frame)

        action_row = QHBoxLayout()
        self.outline_check_btn = QPushButton("检查大纲")
        self.outline_check_btn.setObjectName("PrimaryButton")
        self.outline_check_btn.clicked.connect(self.check_outline_with_ai)
        self.outline_suggest_btn = QPushButton("生成建议")
        self.outline_suggest_btn.clicked.connect(self.suggest_outline_with_ai)
        action_row.addWidget(self.outline_check_btn)
        action_row.addWidget(self.outline_suggest_btn)
        layout.addLayout(action_row)

        self.outline_chat_log = QTextEdit()
        self.outline_chat_log.setObjectName("SummaryBox")
        self.outline_chat_log.setReadOnly(True)
        self.outline_chat_log.setText(
            "AI 大纲助手会在接口配置完成后启用。\n\n"
            "它会读取大纲、时间轴、设定、人物卡和章节总结，用于检查节奏、时间线矛盾和伏笔回收。"
        )

        self.outline_ai_splitter = QSplitter(Qt.Vertical)
        self.outline_ai_splitter.setObjectName("AIPanelSplitter")
        self.outline_ai_splitter.addWidget(self.outline_chat_log)
        input_box = QWidget()
        input_box.setObjectName("AIInputPanel")
        input_layout = QVBoxLayout(input_box)
        input_layout.setContentsMargins(0, 0, 0, 0)
        input_layout.setSpacing(6)
        self.outline_chat_input = self.build_ai_chat_input("输入问题...", self.send_outline_ai_message)
        input_layout.addWidget(self.outline_chat_input)
        self.outline_send_btn = self.build_ai_icon_button("send", "发送", self.send_outline_ai_message, primary=True)
        self.outline_stop_btn = self.build_ai_icon_button("stop", "停止生成", self.stop_outline_ai_stream)
        self.outline_stop_btn.setEnabled(False)
        self.outline_clear_btn = self.build_ai_icon_button("trash", "清除对话", self.clear_outline_ai_chat)
        chat_actions = QHBoxLayout()
        chat_actions.setContentsMargins(0, 0, 0, 0)
        chat_actions.setSpacing(6)
        chat_actions.addStretch(1)
        chat_actions.addWidget(self.outline_send_btn)
        chat_actions.addWidget(self.outline_stop_btn)
        chat_actions.addWidget(self.outline_clear_btn)
        input_layout.addLayout(chat_actions)
        self.outline_ai_splitter.addWidget(input_box)
        self.outline_ai_splitter.setStretchFactor(0, 3)
        self.outline_ai_splitter.setStretchFactor(1, 2)
        self.outline_ai_splitter.setSizes([260, 150])
        layout.addWidget(self.outline_ai_splitter, 1)
        return box

    def outline_defaults(self) -> dict[str, Any]:
        total_id = DraftStore.new_id("ol")
        volume_id = DraftStore.new_id("ol")
        chapter_id = DraftStore.new_id("ol")
        node_id = DraftStore.new_id("ol")
        return {
            "current_node_id": chapter_id,
            "timeline_expanded": True,
            "nodes": [
                {
                    "id": total_id,
                    "title": "故事总纲",
                    "kind": "总纲",
                    "goal": "记录全书核心矛盾、主线推进和结局方向。",
                    "timeline_tag": "主线",
                    "content": "<p>在这里整理全书总纲。</p>",
                    "status": "草稿",
                    "children": [],
                },
                {
                    "id": volume_id,
                    "title": "第一卷",
                    "kind": "卷",
                    "goal": "建立主要人物、世界入口和第一阶段冲突。",
                    "timeline_tag": "主线",
                    "content": "<p>第一卷细纲。</p>",
                    "status": "草稿",
                    "children": [
                        {
                            "id": chapter_id,
                            "title": "第一章",
                            "kind": "章",
                            "goal": "让主角进入事件，并留下章末悬念。",
                            "timeline_tag": "主线 · T0",
                            "content": "<h2>开场钩子</h2><p>主角收到异常线索，确认事件不是偶然。</p>",
                            "status": "草稿",
                            "children": [
                                {
                                    "id": node_id,
                                    "title": "开场钩子",
                                    "kind": "节点",
                                    "goal": "制造第一处疑问。",
                                    "timeline_tag": "主线 · T0",
                                    "content": "<p>这里写具体剧情节点。</p>",
                                    "status": "草稿",
                                    "children": [],
                                }
                            ],
                        }
                    ],
                },
            ],
            "timeline_points": [
                {"id": DraftStore.new_id("tl"), "time": "T-1", "event": "名单送达", "line": "主线"},
                {"id": DraftStore.new_id("tl"), "time": "T0", "event": "本章调查", "line": "当前章"},
                {"id": DraftStore.new_id("tl"), "time": "T+1", "event": "黑石码头", "line": "下一章"},
            ],
            "ai_chat": "",
        }

    def ensure_outline_data(self) -> dict[str, Any]:
        if self.draft is None:
            raise RuntimeError("draft is not loaded")
        outline = self.draft.setdefault("outline", self.outline_defaults())
        if not outline.get("nodes"):
            self.draft["outline"] = self.outline_defaults()
            outline = self.draft["outline"]
        outline.setdefault("timeline_points", [])
        outline.setdefault("timeline_expanded", True)
        outline.setdefault("ai_chat", "")
        self.normalize_outline_tree(outline)
        return outline

    def is_story_outline_node(self, node: dict[str, Any] | None) -> bool:
        if not node:
            return False
        return node.get("kind") == "总纲" or node.get("title") == "故事总纲"

    def normalize_outline_tree(self, outline: dict[str, Any]) -> None:
        nodes = outline.setdefault("nodes", [])
        normalized_nodes: list[dict[str, Any]] = []
        orphan_chapters: list[dict[str, Any]] = []
        orphan_nodes: list[dict[str, Any]] = []

        for node in nodes:
            if not self.is_story_outline_node(node):
                normalized_nodes.append(node)
                continue
            children = node.pop("children", []) or []
            node["children"] = []
            normalized_nodes.append(node)
            for child in children:
                child_kind = child.get("kind")
                if child_kind == "卷":
                    normalized_nodes.append(child)
                elif child_kind == "章":
                    orphan_chapters.append(child)
                else:
                    orphan_nodes.append(child)

        target_volume = next((node for node in normalized_nodes if node.get("kind") == "卷"), None)
        if orphan_chapters or orphan_nodes:
            if target_volume is None:
                target_volume = {
                    "id": DraftStore.new_id("ol"),
                    "title": "未归卷",
                    "kind": "卷",
                    "goal": "",
                    "timeline_tag": "",
                    "content": "<p>由旧大纲层级自动整理。</p>",
                    "status": "草稿",
                    "children": [],
                }
                normalized_nodes.append(target_volume)
            target_volume.setdefault("children", []).extend(orphan_chapters)
            if orphan_nodes:
                target_chapter = next((child for child in target_volume.get("children", []) if child.get("kind") == "章"), None)
                if target_chapter is None:
                    target_chapter = {
                        "id": DraftStore.new_id("ol"),
                        "title": "未归章节",
                        "kind": "章",
                        "goal": "",
                        "timeline_tag": "",
                        "content": "<p>由旧大纲层级自动整理。</p>",
                        "status": "草稿",
                        "children": [],
                    }
                    target_volume.setdefault("children", []).append(target_chapter)
                target_chapter.setdefault("children", []).extend(orphan_nodes)

        story_nodes = [node for node in normalized_nodes if self.is_story_outline_node(node)]
        other_nodes = [node for node in normalized_nodes if not self.is_story_outline_node(node)]
        outline["nodes"] = story_nodes + other_nodes

    def load_outline_project(self) -> None:
        if not self.selected_project:
            return
        self.draft = DraftStore.load(self.selected_project)
        outline = self.ensure_outline_data()
        self.current_outline_node_id = outline.get("current_node_id")
        if not self.current_outline_node_id:
            first = self.first_outline_node(outline.get("nodes", []))
            self.current_outline_node_id = first.get("id") if first else None
        self.populate_outline_tree(self.current_outline_node_id)
        self.populate_timeline()
        self.timeline_body.setVisible(bool(outline.get("timeline_expanded", True)))
        self.timeline_toggle_btn.setText("收起时间轴" if outline.get("timeline_expanded", True) else "展开时间轴")
        chat = outline.get("ai_chat", "")
        if chat:
            self.outline_chat_log.setPlainText(chat)
        self.apply_outline_ai_scope_settings()
        self.outline_selected_chapter_ids = set()
        self.update_outline_selected_chapters_label()
        self.update_outline_ai_scope_controls()
        if self.current_outline_node_id:
            self.load_outline_node(self.current_outline_node_id)
        self.update_outline_status()

    def iter_outline_nodes(self, nodes: list[dict[str, Any]], parent: dict[str, Any] | None = None):
        for node in nodes:
            yield parent, node
            yield from self.iter_outline_nodes(node.get("children", []), node)

    def first_outline_node(self, nodes: list[dict[str, Any]]) -> dict[str, Any] | None:
        for _, node in self.iter_outline_nodes(nodes):
            return node
        return None

    def find_outline_node(self, node_id: str | None) -> tuple[dict[str, Any] | None, dict[str, Any]] | None:
        if self.draft is None or not node_id:
            return None
        outline = self.ensure_outline_data()
        for parent, node in self.iter_outline_nodes(outline.get("nodes", [])):
            if node.get("id") == node_id:
                return parent, node
        return None

    def find_outline_node_chain(self, node_id: str | None) -> list[tuple[dict[str, Any] | None, dict[str, Any]]]:
        if self.draft is None or not node_id:
            return []
        outline = self.ensure_outline_data()

        def walk(nodes: list[dict[str, Any]], parent: dict[str, Any] | None, chain: list[tuple[dict[str, Any] | None, dict[str, Any]]]):
            for node in nodes:
                current_chain = chain + [(parent, node)]
                if node.get("id") == node_id:
                    return current_chain
                found = walk(node.get("children", []), node, current_chain)
                if found:
                    return found
            return []

        return walk(outline.get("nodes", []), None, [])

    def populate_outline_tree(self, selected_node_id: str | None = None) -> None:
        if self.draft is None:
            return
        outline = self.ensure_outline_data()
        self.outline_tree.blockSignals(True)
        self.outline_tree.clear()
        selected_item: QTreeWidgetItem | None = None

        def add_items(parent_item: QTreeWidgetItem | None, nodes: list[dict[str, Any]]) -> None:
            nonlocal selected_item
            for node in nodes:
                label = node.get("title", "未命名")
                item = QTreeWidgetItem([label])
                item.setIcon(0, self.status_icon(node.get("status", "草稿")))
                item.setData(0, Qt.UserRole, node.get("id"))
                item.setToolTip(0, f"{node.get('kind', '节点')} · {node.get('timeline_tag', '')}")
                if parent_item is None:
                    self.outline_tree.addTopLevelItem(item)
                else:
                    parent_item.addChild(item)
                if node.get("id") == selected_node_id:
                    selected_item = item
                add_items(item, node.get("children", []))
                item.setExpanded(True)

        add_items(None, outline.get("nodes", []))
        if selected_item:
            self.outline_tree.setCurrentItem(selected_item)
        self.outline_tree.blockSignals(False)

    def load_outline_node(self, node_id: str) -> None:
        found = self.find_outline_node(node_id)
        if not found:
            return
        _, node = found
        self.loading_outline = True
        self.current_outline_node_id = node_id
        self.ensure_outline_data()["current_node_id"] = node_id
        self.outline_node_title_label.setText(node.get("title", "未命名"))
        self.outline_node_meta_label.setText(f"{node.get('kind', '节点')} · {node.get('timeline_tag', '未关联时间线')}")
        self.outline_goal_edit.setText(node.get("goal", ""))
        self.outline_timeline_tag_edit.setText(node.get("timeline_tag", ""))
        self.outline_editor.setHtml(node.get("content", ""))
        self.loading_outline = False
        self.update_outline_status()

    def save_current_outline_node(self, silent: bool = False) -> None:
        if not self.selected_project or self.draft is None or not self.current_outline_node_id:
            return
        found = self.find_outline_node(self.current_outline_node_id)
        if not found:
            return
        _, node = found
        node["goal"] = self.outline_goal_edit.text().strip()
        node["timeline_tag"] = self.outline_timeline_tag_edit.text().strip()
        node["content"] = self.outline_editor.toHtml()
        node["updated_at"] = now_iso()
        outline = self.ensure_outline_data()
        outline["current_node_id"] = self.current_outline_node_id
        outline["ai_chat"] = self.outline_chat_log.toPlainText()
        DraftStore.save(self.selected_project, self.draft)
        self.update_outline_status()
        if not silent:
            QMessageBox.information(self, "已保存", "当前细纲已保存。")

    def on_outline_text_changed(self) -> None:
        if self.loading_outline:
            return
        self.update_outline_status(dirty=True)

    def update_outline_status(self, dirty: bool = False) -> None:
        project = self.selected_project
        prefix = project.name if project else "未打开项目"
        node = self.find_outline_node(self.current_outline_node_id)
        node_title = node[1].get("title", "未命名") if node else "未选择节点"
        suffix = "有未保存修改" if dirty else "自动保存覆盖大纲内容"
        self.outline_status_label.setText(f"{prefix} · 当前：{node_title} · {suffix}")

    def on_outline_node_selected(self) -> None:
        if self.loading_outline:
            return
        item = self.outline_tree.currentItem()
        if not item:
            return
        node_id = item.data(0, Qt.UserRole)
        if not node_id:
            return
        if self.current_outline_node_id and node_id != self.current_outline_node_id:
            self.save_current_outline_node(silent=True)
        self.load_outline_node(node_id)

    def selected_outline_node(self) -> tuple[dict[str, Any] | None, dict[str, Any]] | None:
        item = self.outline_tree.currentItem()
        if not item:
            return self.find_outline_node(self.current_outline_node_id)
        return self.find_outline_node(item.data(0, Qt.UserRole))

    def selected_outline_node_chain(self) -> list[tuple[dict[str, Any] | None, dict[str, Any]]]:
        item = self.outline_tree.currentItem()
        node_id = item.data(0, Qt.UserRole) if item else self.current_outline_node_id
        return self.find_outline_node_chain(node_id)

    def target_outline_children_for_new_node(self, kind: str) -> list[dict[str, Any]] | None:
        outline = self.ensure_outline_data()
        if kind == "volume":
            return outline.setdefault("nodes", [])
        chain = self.selected_outline_node_chain()
        if kind == "chapter":
            for _parent, node in reversed(chain):
                if node.get("kind") == "卷":
                    return node.setdefault("children", [])
            QMessageBox.information(self, "请选择卷", "请先选择一个卷。")
            return None
        if chain:
            selected_node = chain[-1][1]
            if selected_node.get("kind") in {"章", "节点"}:
                return selected_node.setdefault("children", [])
        QMessageBox.information(self, "请选择章节", "请先选择一个章节。")
        return None

    def add_outline_node(self, kind: str) -> None:
        if self.draft is None:
            self.load_outline_project()
        if self.draft is None:
            return
        self.save_current_outline_node(silent=True)
        kind_label = {"volume": "卷", "chapter": "章", "node": "节点"}.get(kind, "节点")
        default_title = f"第{self.count_outline_kind(kind_label) + 1}{kind_label}" if kind != "node" else f"剧情节点 {self.count_outline_kind(kind_label) + 1}"
        target_children = self.target_outline_children_for_new_node(kind)
        if target_children is None:
            return
        title, ok = QInputDialog.getText(self, f"新增{kind_label}", f"{kind_label}名称：", text=default_title)
        if not ok:
            return
        title = title.strip() or default_title
        node = {
            "id": DraftStore.new_id("ol"),
            "title": title,
            "kind": kind_label,
            "goal": "",
            "timeline_tag": "",
            "content": f"<h2>{title}</h2><p>在这里写{kind_label}细纲。</p>",
            "status": "草稿",
            "updated_at": now_iso(),
            "children": [],
        }
        target_children.append(node)
        self.current_outline_node_id = node["id"]
        DraftStore.save(self.selected_project, self.draft)
        self.populate_outline_tree(node["id"])
        self.load_outline_node(node["id"])

    def count_outline_kind(self, kind_label: str) -> int:
        if self.draft is None:
            return 0
        outline = self.ensure_outline_data()
        return sum(1 for _, node in self.iter_outline_nodes(outline.get("nodes", [])) if node.get("kind") == kind_label)

    def show_outline_node_menu(self, pos: QPoint) -> None:
        if self.draft is None:
            return
        item = self.outline_tree.itemAt(pos)
        menu = QMenu(self.outline_tree)
        if item:
            self.outline_tree.setCurrentItem(item)
            node_id = item.data(0, Qt.UserRole)
            menu.addAction("新增子节点", lambda: self.add_outline_node("node"))
            menu.addAction("更改名称", lambda: self.rename_outline_node(node_id))
            menu.addSeparator()
            menu.addAction("删除节点", lambda: self.delete_outline_node(node_id))
        else:
            menu.addAction("新增卷", lambda: self.add_outline_node("volume"))
            menu.addAction("新增章", lambda: self.add_outline_node("chapter"))
            menu.addAction("新增节点", lambda: self.add_outline_node("node"))
        menu.exec(self.outline_tree.viewport().mapToGlobal(pos))

    def rename_outline_node(self, node_id: str) -> None:
        found = self.find_outline_node(node_id)
        if not found:
            return
        _, node = found
        title, ok = QInputDialog.getText(self, "更改名称", "名称：", text=node.get("title", "未命名"))
        if not ok:
            return
        title = title.strip()
        if not title:
            return
        node["title"] = title
        node["updated_at"] = now_iso()
        DraftStore.save(self.selected_project, self.draft)
        self.populate_outline_tree(node_id)
        self.load_outline_node(node_id)

    def delete_outline_node(self, node_id: str) -> None:
        found = self.find_outline_node(node_id)
        if not found or self.draft is None:
            return
        parent, node = found
        answer = QMessageBox.question(
            self,
            "删除大纲节点",
            f"确定删除“{node.get('title', '未命名')}”及其子节点吗？",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No,
        )
        if answer != QMessageBox.Yes:
            return
        outline = self.ensure_outline_data()
        self.draft.setdefault("deleted_items", []).append({"type": "outline_node", "deleted_at": now_iso(), "data": node})
        if parent is None:
            outline["nodes"] = [item for item in outline.get("nodes", []) if item.get("id") != node_id]
        else:
            parent["children"] = [item for item in parent.get("children", []) if item.get("id") != node_id]
        first = self.first_outline_node(outline.get("nodes", []))
        self.current_outline_node_id = first.get("id") if first else None
        outline["current_node_id"] = self.current_outline_node_id
        DraftStore.save(self.selected_project, self.draft)
        self.populate_outline_tree(self.current_outline_node_id)
        if self.current_outline_node_id:
            self.load_outline_node(self.current_outline_node_id)
        else:
            self.outline_editor.clear()
            self.outline_goal_edit.clear()
            self.outline_timeline_tag_edit.clear()

    def populate_timeline(self) -> None:
        if self.draft is None:
            return
        outline = self.ensure_outline_data()
        self.timeline_tree.clear()
        for point in outline.get("timeline_points", []):
            item = QTreeWidgetItem([point.get("time", ""), point.get("event", ""), point.get("line", "")])
            item.setData(0, Qt.UserRole, point.get("id"))
            self.timeline_tree.addTopLevelItem(item)
        self.timeline_tree.resizeColumnToContents(0)
        self.timeline_tree.resizeColumnToContents(2)

    def toggle_outline_timeline(self) -> None:
        if self.draft is None:
            return
        visible = not self.timeline_body.isVisible()
        self.timeline_body.setVisible(visible)
        self.timeline_toggle_btn.setText("收起时间轴" if visible else "展开时间轴")
        self.ensure_outline_data()["timeline_expanded"] = visible
        DraftStore.save(self.selected_project, self.draft)

    def add_timeline_point(self) -> None:
        if self.draft is None:
            self.load_outline_project()
        if self.draft is None:
            return
        time, ok = QInputDialog.getText(self, "新增时间点", "时间标记：", text="T0")
        if not ok:
            return
        event, ok = QInputDialog.getText(self, "新增时间点", "事件名称：", text="新事件")
        if not ok:
            return
        line, ok = QInputDialog.getText(self, "新增时间点", "所属线索/章节：", text="主线")
        if not ok:
            return
        point = {"id": DraftStore.new_id("tl"), "time": time.strip(), "event": event.strip(), "line": line.strip()}
        self.ensure_outline_data().setdefault("timeline_points", []).append(point)
        DraftStore.save(self.selected_project, self.draft)
        self.populate_timeline()

    def outline_chapter_items(self) -> list[tuple[dict[str, Any], dict[str, Any]]]:
        if self.draft is None:
            return []
        return list(DraftStore.iter_chapters(self.draft))

    def chapter_display_name(self, volume: dict[str, Any], chapter: dict[str, Any]) -> str:
        return f"{volume.get('title', '未命名卷')} / {chapter.get('title', '未命名章节')}"

    def apply_outline_ai_scope_settings(self) -> None:
        if not hasattr(self, "outline_scope_checks"):
            return
        saved = self.app_settings.get("outline_ai_scope", {})
        defaults = default_outline_ai_scope()
        scope = {key: bool(saved.get(key, value)) if isinstance(saved, dict) else value for key, value in defaults.items()}
        for key, check in self.outline_scope_checks.items():
            check.blockSignals(True)
            check.setChecked(scope.get(key, defaults.get(key, False)))
            check.blockSignals(False)

    def current_outline_ai_scope(self) -> dict[str, bool]:
        defaults = default_outline_ai_scope()
        if not hasattr(self, "outline_scope_checks"):
            return defaults
        return {key: self.outline_scope_checks.get(key).isChecked() if key in self.outline_scope_checks else value for key, value in defaults.items()}

    def saved_outline_ai_scope_preferences(self) -> dict[str, bool]:
        scope = self.current_outline_ai_scope()
        for key in ("current_chapter_body", "selected_chapter_bodies", "all_chapter_bodies"):
            scope[key] = False
        return scope

    def on_outline_ai_scope_changed(self) -> None:
        self.update_outline_ai_scope_controls()
        self.app_settings["outline_ai_scope"] = self.saved_outline_ai_scope_preferences()
        try:
            save_app_settings(self.app_settings)
        except OSError:
            pass

    def update_outline_selected_chapters_label(self) -> None:
        if not hasattr(self, "outline_selected_chapters_label"):
            return
        count = len(self.outline_selected_chapter_ids)
        self.outline_selected_chapters_label.setText(f"已选 {count} 章" if count else "未选择章节")

    def update_outline_ai_scope_controls(self) -> None:
        if not hasattr(self, "outline_scope_checks"):
            return
        busy = bool((self.outline_ai_thread and self.outline_ai_thread.isRunning()) or self.outline_stop_btn.isEnabled())
        has_current_chapter = bool(self.draft and (self.draft.get("current_chapter_id") or self.current_chapter_id))
        for check in self.outline_scope_checks.values():
            check.setEnabled(not busy)
        self.outline_scope_checks["current_chapter_body"].setEnabled(has_current_chapter and not busy)
        selected_enabled = self.outline_scope_checks["selected_chapter_bodies"].isChecked()
        self.outline_select_chapters_btn.setEnabled(selected_enabled and not busy)
        if not has_current_chapter:
            self.outline_scope_checks["current_chapter_body"].setChecked(False)
        self.update_outline_selected_chapters_label()

    def toggle_outline_ai_scope(self) -> None:
        visible = not self.outline_scope_frame.isVisible()
        self.outline_scope_frame.setVisible(visible)
        self.outline_scope_toggle_btn.setText("读取范围 v" if visible else "读取范围 >")

    def build_ai_chapter_selection_tree(self, selected_ids: set[str]) -> tuple[QTreeWidget, list[tuple[QTreeWidgetItem, str]]]:
        tree = QTreeWidget()
        tree.setHeaderHidden(True)
        tree.setProperty("updating_ai_chapter_checks", False)
        chapter_items: list[tuple[QTreeWidgetItem, str]] = []
        volumes = self.draft.get("volumes", []) if self.draft else []
        if not any(volume.get("chapters", []) for volume in volumes):
            empty_item = QTreeWidgetItem(["暂无正文章节"])
            empty_item.setFlags(empty_item.flags() & ~Qt.ItemIsEnabled)
            tree.addTopLevelItem(empty_item)
            return tree, chapter_items
        for volume in volumes:
            volume_item = QTreeWidgetItem([volume.get("title", "未命名卷")])
            volume_item.setData(0, Qt.UserRole, {"kind": "volume"})
            volume_item.setFlags(volume_item.flags() | Qt.ItemIsUserCheckable | Qt.ItemIsEnabled)
            volume_item.setCheckState(0, Qt.Unchecked)
            tree.addTopLevelItem(volume_item)
            for chapter in volume.get("chapters", []):
                chapter_id = chapter.get("id", "")
                chapter_item = QTreeWidgetItem([chapter.get("title", "未命名章节")])
                chapter_item.setData(0, Qt.UserRole, {"kind": "chapter", "id": chapter_id})
                chapter_item.setFlags(chapter_item.flags() | Qt.ItemIsUserCheckable | Qt.ItemIsEnabled)
                chapter_item.setCheckState(0, Qt.Checked if chapter_id in selected_ids else Qt.Unchecked)
                volume_item.addChild(chapter_item)
                chapter_items.append((chapter_item, chapter_id))
            self.sync_ai_chapter_volume_state(volume_item)
            volume_item.setExpanded(True)
        tree.itemChanged.connect(lambda item, column: self.on_ai_chapter_selection_item_changed(tree, item, column))
        return tree, chapter_items

    def on_ai_chapter_selection_item_changed(self, tree: QTreeWidget, item: QTreeWidgetItem, column: int) -> None:
        if column != 0 or tree.property("updating_ai_chapter_checks"):
            return
        data = item.data(0, Qt.UserRole) or {}
        tree.setProperty("updating_ai_chapter_checks", True)
        try:
            if data.get("kind") == "volume":
                state = item.checkState(0)
                if state != Qt.PartiallyChecked:
                    for index in range(item.childCount()):
                        item.child(index).setCheckState(0, state)
            elif data.get("kind") == "chapter" and item.parent():
                self.sync_ai_chapter_volume_state(item.parent())
        finally:
            tree.setProperty("updating_ai_chapter_checks", False)

    def sync_ai_chapter_volume_state(self, volume_item: QTreeWidgetItem) -> None:
        total = volume_item.childCount()
        if total == 0:
            volume_item.setCheckState(0, Qt.Unchecked)
            return
        checked = 0
        partial = 0
        for index in range(total):
            state = volume_item.child(index).checkState(0)
            if state == Qt.Checked:
                checked += 1
            elif state == Qt.PartiallyChecked:
                partial += 1
        if checked == total:
            volume_item.setCheckState(0, Qt.Checked)
        elif checked == 0 and partial == 0:
            volume_item.setCheckState(0, Qt.Unchecked)
        else:
            volume_item.setCheckState(0, Qt.PartiallyChecked)

    def clear_ai_chapter_selection_tree(self, tree: QTreeWidget) -> None:
        tree.setProperty("updating_ai_chapter_checks", True)
        try:
            for top_index in range(tree.topLevelItemCount()):
                volume_item = tree.topLevelItem(top_index)
                volume_item.setCheckState(0, Qt.Unchecked)
                for child_index in range(volume_item.childCount()):
                    volume_item.child(child_index).setCheckState(0, Qt.Unchecked)
        finally:
            tree.setProperty("updating_ai_chapter_checks", False)

    def selected_ai_chapter_ids_from_tree(self, chapter_items: list[tuple[QTreeWidgetItem, str]]) -> set[str]:
        return {
            chapter_id
            for item, chapter_id in chapter_items
            if chapter_id and item.checkState(0) == Qt.Checked
        }

    def choose_ai_chapters(self, selected_ids: set[str]) -> set[str] | None:
        if self.draft is None:
            QMessageBox.information(self, "没有项目", "请先打开一个小说项目。")
            return None
        dialog = QDialog(self)
        dialog.setWindowTitle("选择 AI 可读取的章节正文")
        dialog.resize(420, 520)
        layout = QVBoxLayout(dialog)
        label = QLabel("勾选本次允许 AI 读取正文的章节。")
        label.setObjectName("Muted")
        layout.addWidget(label)
        tree, chapter_items = self.build_ai_chapter_selection_tree(selected_ids)
        layout.addWidget(tree, 1)
        count_label = QLabel()
        count_label.setObjectName("ScopeBadge")

        def update_count_label() -> None:
            count = len(self.selected_ai_chapter_ids_from_tree(chapter_items))
            count_label.setText(f"已选 {count} 章" if count else "未选择章节")

        tree.itemChanged.connect(lambda _item, _column: update_count_label())
        update_count_label()
        layout.addWidget(count_label)
        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.button(QDialogButtonBox.Ok).setText("确定")
        buttons.button(QDialogButtonBox.Cancel).setText("取消")
        clear_btn = buttons.addButton("清除全部", QDialogButtonBox.ActionRole)
        clear_btn.clicked.connect(lambda: (self.clear_ai_chapter_selection_tree(tree), update_count_label()))
        buttons.accepted.connect(dialog.accept)
        buttons.rejected.connect(dialog.reject)
        layout.addWidget(buttons)
        if dialog.exec() != QDialog.Accepted:
            return None
        return self.selected_ai_chapter_ids_from_tree(chapter_items)

    def choose_outline_ai_chapters(self) -> None:
        self.save_current_outline_node(silent=True)
        if self.selected_project:
            self.draft = DraftStore.load(self.selected_project)
            self.ensure_outline_data()
        selected_ids = self.choose_ai_chapters(self.outline_selected_chapter_ids)
        if selected_ids is None:
            return
        self.outline_selected_chapter_ids = selected_ids
        if self.outline_selected_chapter_ids:
            self.outline_scope_checks["selected_chapter_bodies"].setChecked(True)
        self.update_outline_selected_chapters_label()

    def validate_outline_ai_ready(self, settings: dict[str, Any]) -> tuple[bool, str]:
        if not self.selected_project or self.draft is None:
            return False, "请先打开一个小说项目。"
        if not settings.get("ai_enabled", True):
            return False, "AI 辅助已关闭，请先到设置页启用。"
        if not str(settings.get("api_key", "")).strip():
            return False, "AI 接口未配置：缺少 API Key。"
        if not str(settings.get("base_url", "")).strip():
            return False, "AI 接口未配置：缺少 Base URL。"
        if not str(settings.get("model", "")).strip():
            return False, "AI 接口未配置：缺少模型名。"
        return True, ""

    def build_outline_ai_context(self) -> list[tuple[str, str]]:
        sections: list[tuple[str, str]] = []
        if self.draft is None:
            return sections
        scope = self.current_outline_ai_scope()
        outline = self.ensure_outline_data()
        if scope.get("outline"):
            for _parent, node in self.iter_outline_nodes(outline.get("nodes", [])):
                node_text = "\n".join(
                    item
                    for item in [
                        f"类型：{node.get('kind', '节点')}",
                        f"目标：{node.get('goal', '')}",
                        f"时间线：{node.get('timeline_tag', '')}",
                        self.short_plain_text(node.get("content", ""), 700),
                    ]
                    if item.strip() and not item.endswith("：")
                )
                self.append_context_section(sections, f"大纲 - {node.get('title', '未命名')}", node_text)
        if scope.get("timeline"):
            timeline_lines = [
                f"{point.get('time', '')} / {point.get('line', '')}：{point.get('event', '')}"
                for point in outline.get("timeline_points", [])
                if point.get("time") or point.get("event") or point.get("line")
            ]
            self.append_context_section(sections, "时间线", "\n".join(timeline_lines))
        if scope.get("summaries"):
            for volume, chapter in self.outline_chapter_items():
                summary = self.chapter_summary_text(chapter)
                if summary:
                    self.append_context_section(sections, f"章节总结 - {self.chapter_display_name(volume, chapter)}", summary)
        if scope.get("world"):
            world = self.draft.get("worldbuilding")
            world_lines: list[str] = []
            if isinstance(world, dict):
                for module in world.get("modules", []):
                    for _parent, node in self.iter_world_nodes([module]):
                        if node.get("kind") != "entry":
                            continue
                        if node.get("ai_read_allowed", node.get("allow_ai_read", node.get("ai_enabled", True))) is False:
                            continue
                        tags = "，".join(node.get("tags", []))
                        world_lines.append(
                            f"{node.get('title', '未命名词条')} [{node.get('entry_type', '设定')}] {tags}\n"
                            f"{self.short_plain_text(node.get('content', ''), 600)}"
                        )
            self.append_context_section(sections, "设定库", "\n\n".join(world_lines))
        if scope.get("characters") or scope.get("relations"):
            characters = self.draft.get("characters")
            card_lines: list[str] = []
            relation_lines: list[str] = []
            if isinstance(characters, dict):
                for card in characters.get("cards", []):
                    if scope.get("characters"):
                        tags = []
                        for tag_name, values in card.get("tags", {}).items():
                            if values:
                                tags.append(f"{tag_name}：{'，'.join(values)}")
                        card_lines.append(
                            "\n".join(
                                item
                                for item in [
                                    f"{card.get('name', '未命名')} / {card.get('identity', '')} / {card.get('status', '')}",
                                    f"阵营：{card.get('faction', '')}",
                                    "；".join(tags),
                                    self.short_plain_text(card.get("notes", ""), 550),
                                ]
                                if item.strip()
                            )
                        )
                    if scope.get("relations"):
                        for relation in card.get("relations", []):
                            relation_lines.append(
                                f"{card.get('name', '未命名')} -> {relation.get('target_name', '未命名')}："
                                f"{relation.get('type', '关系')} / {relation.get('status', '')} / {relation.get('note', '')}"
                            )
            self.append_context_section(sections, "人物卡", "\n\n".join(card_lines))
            self.append_context_section(sections, "人物关系记录", "\n".join(relation_lines))

        seen_body_ids: set[str] = set()
        if scope.get("all_chapter_bodies"):
            for volume, chapter in self.outline_chapter_items():
                seen_body_ids.add(chapter.get("id", ""))
                self.append_context_section(sections, f"正文 - {self.chapter_display_name(volume, chapter)}", self.html_to_plain_text(chapter.get("content", "")))
        else:
            if scope.get("current_chapter_body"):
                current_id = self.draft.get("current_chapter_id") or self.current_chapter_id
                found = DraftStore.find_chapter(self.draft, current_id)
                if found:
                    volume, chapter = found
                    seen_body_ids.add(chapter.get("id", ""))
                    self.append_context_section(sections, f"当前章正文 - {self.chapter_display_name(volume, chapter)}", self.html_to_plain_text(chapter.get("content", "")))
            if scope.get("selected_chapter_bodies"):
                for volume, chapter in self.outline_chapter_items():
                    chapter_id = chapter.get("id")
                    if chapter_id in self.outline_selected_chapter_ids and chapter_id not in seen_body_ids:
                        seen_body_ids.add(chapter_id)
                        self.append_context_section(sections, f"指定章正文 - {self.chapter_display_name(volume, chapter)}", self.html_to_plain_text(chapter.get("content", "")))
        return sections

    def outline_ai_context_preview(self, sections: list[tuple[str, str]]) -> str:
        preview = self.ai_context_preview(sections)
        total_chars = sum(len(body) for _title, body in sections)
        return f"{preview}\n\n预计读取：{len(sections)} 项，约 {total_chars} 字符。"

    def confirm_outline_ai_call(self, title: str, sections: list[tuple[str, str]], settings: dict[str, Any]) -> bool:
        scope = self.current_outline_ai_scope()
        if scope.get("selected_chapter_bodies") and not self.outline_selected_chapter_ids:
            QMessageBox.information(self, "未选择章节", "已勾选“指定章节正文”，请先选择至少一个章节。")
            return False
        if settings.get("ai_confirm_each_call", True):
            answer = QMessageBox.question(
                self,
                title,
                "本次 AI 将读取以下范围：\n\n"
                f"{self.outline_ai_context_preview(sections)}\n\n"
                "AI 只会返回建议，不会自动覆盖正文、设定、人物卡或大纲。是否继续？",
                QMessageBox.Yes | QMessageBox.No,
                QMessageBox.No,
            )
            if answer != QMessageBox.Yes:
                return False
        if scope.get("all_chapter_bodies"):
            answer = QMessageBox.question(
                self,
                "确认读取全书正文",
                "你勾选了“全书正文”。这可能增加接口成本、等待时间和隐私暴露范围。确定继续吗？",
                QMessageBox.Yes | QMessageBox.No,
                QMessageBox.No,
            )
            if answer != QMessageBox.Yes:
                return False
        return True

    def outline_ai_system_prompt(self) -> str:
        settings = self.ai_settings_for_request()
        return (
            f"{self.ai_role_instruction(settings)}\n\n"
            "你是本地小说创作软件中的 AI 大纲助手。你只能基于本次提供的上下文回答，"
            "重点帮助作者梳理故事结构、章节细纲、时间线、伏笔回收、节奏和人物动机。"
            "不要声称已经修改正文、设定、人物卡或大纲；如需要修改，只输出候选文本和理由，等待用户确认。"
        )

    def set_outline_ai_streaming(self, active: bool) -> None:
        self.outline_send_btn.setEnabled(not active)
        self.outline_check_btn.setEnabled(not active)
        self.outline_suggest_btn.setEnabled(not active)
        self.outline_stop_btn.setEnabled(active)
        self.outline_clear_btn.setEnabled(not active)
        self.outline_chat_input.setEnabled(not active)
        self.update_outline_ai_scope_controls()

    def append_outline_chat_text(self, text: str) -> None:
        cursor = self.outline_chat_log.textCursor()
        cursor.movePosition(QTextCursor.End)
        cursor.insertText(text)
        self.outline_chat_log.setTextCursor(cursor)
        self.outline_chat_log.ensureCursorVisible()

    def start_outline_ai_stream(self, settings: dict[str, Any], messages: list[dict[str, str]], max_tokens: int = 1000) -> None:
        self.outline_ai_stream_text = ""
        self.outline_ai_thread = AIStreamThread(settings, messages, max_tokens=max_tokens)
        self.outline_ai_thread.chunk_received.connect(self.on_outline_ai_stream_chunk)
        self.outline_ai_thread.result_ready.connect(self.on_outline_ai_stream_finished)
        self.outline_ai_thread.start()

    def on_outline_ai_stream_chunk(self, text: str) -> None:
        self.outline_ai_stream_text += text
        self.append_outline_chat_text(text)

    def on_outline_ai_stream_finished(self, ok: bool, message: str, stopped: bool) -> None:
        if message and (stopped or not ok or not self.outline_ai_stream_text.strip()):
            self.append_outline_chat_text(message)
        self.append_outline_chat_text("\n")
        self.set_outline_ai_streaming(False)
        if self.draft is not None:
            self.ensure_outline_data()["ai_chat"] = self.outline_chat_log.toPlainText()
            DraftStore.save(self.selected_project, self.draft)
        if self.outline_ai_thread:
            self.outline_ai_thread.wait(1000)
            self.outline_ai_thread = None

    def stop_outline_ai_stream(self) -> None:
        if self.outline_ai_thread and self.outline_ai_thread.isRunning():
            self.outline_ai_thread.request_stop()
            self.outline_stop_btn.setEnabled(False)

    def run_outline_ai_task(self, visible_question: str, prompt: str, max_tokens: int = 1000) -> None:
        if self.outline_ai_thread and self.outline_ai_thread.isRunning():
            return
        self.save_current_outline_node(silent=True)
        settings = self.ai_settings_for_request()
        role_name = self.ai_role_name(settings)
        current_log = self.outline_chat_log.toPlainText().strip()
        if current_log:
            current_log += "\n\n"
        current_log += f"你：{visible_question}"
        ready, message = self.validate_outline_ai_ready(settings)
        if not ready:
            current_log += f"\n\n{role_name}：{message}"
            self.outline_chat_log.setPlainText(current_log)
            self.outline_chat_log.moveCursor(QTextCursor.End)
            self.outline_chat_input.clear()
            return
        sections = self.limited_ai_context(self.build_outline_ai_context(), settings)
        if not self.confirm_outline_ai_call("发送给 AI 大纲助手", sections, settings):
            return
        messages = [
            {"role": "system", "content": self.outline_ai_system_prompt()},
            {
                "role": "user",
                "content": (
                    "下面是本次允许读取的项目上下文。请严格基于这些内容回答。\n\n"
                    f"{self.ai_context_text(sections)}\n\n"
                    f"用户请求：{prompt}"
                ),
            },
        ]
        current_log += f"\n\n{role_name}："
        self.outline_chat_log.setPlainText(current_log)
        self.outline_chat_log.moveCursor(QTextCursor.End)
        self.outline_chat_input.clear()
        self.set_outline_ai_streaming(True)
        self.start_outline_ai_stream(settings, messages, max_tokens=max_tokens)

    def send_outline_ai_message(self) -> None:
        question = self.outline_chat_input.toPlainText().strip()
        if not question:
            return
        self.run_outline_ai_task(question, question, max_tokens=1000)

    def check_outline_with_ai(self) -> None:
        self.run_outline_ai_task(
            "检查大纲",
            "请检查当前大纲的结构完整度、章节节奏、时间线矛盾、人物动机断点、伏笔回收风险，并按问题严重程度输出修改建议。",
            max_tokens=1200,
        )

    def suggest_outline_with_ai(self) -> None:
        self.run_outline_ai_task(
            "生成建议",
            "请基于当前大纲和已授权资料，生成可直接参考的细纲补充建议。优先补足冲突推进、关键转折、人物行动理由和下一章承接点。",
            max_tokens=1200,
        )

    def append_outline_ai_placeholder(self, text: str) -> None:
        current_log = self.outline_chat_log.toPlainText().strip()
        self.outline_chat_log.setPlainText(f"{current_log}\n\n{text}".strip())
        self.outline_chat_log.moveCursor(QTextCursor.End)
        if self.draft is not None:
            self.ensure_outline_data()["ai_chat"] = self.outline_chat_log.toPlainText()
            DraftStore.save(self.selected_project, self.draft)

    def clear_outline_ai_chat(self) -> None:
        if self.outline_ai_thread and self.outline_ai_thread.isRunning():
            self.outline_ai_thread.request_stop()
        text = "当前对话已清除。\n\nAI 大纲助手会读取大纲、时间轴、设定、人物卡和章节总结。"
        self.outline_chat_log.setPlainText(text)
        if self.draft is not None:
            self.ensure_outline_data()["ai_chat"] = text
            DraftStore.save(self.selected_project, self.draft)

    def change_outline_font(self, font: QFont) -> None:
        if self.current_page != "outline":
            return
        char_format = QTextCharFormat()
        char_format.setFontFamily(font.family())
        cursor = self.outline_editor.textCursor()
        if cursor.hasSelection():
            cursor.mergeCharFormat(char_format)
        else:
            self.outline_editor.mergeCurrentCharFormat(char_format)

    def change_outline_font_size(self, value: str) -> None:
        if self.current_page != "outline":
            return
        try:
            size = int(value.replace("pt", "").strip())
        except ValueError:
            return
        char_format = QTextCharFormat()
        char_format.setFontPointSize(size)
        cursor = self.outline_editor.textCursor()
        if cursor.hasSelection():
            cursor.mergeCharFormat(char_format)
        else:
            self.outline_editor.mergeCurrentCharFormat(char_format)

    def outline_to_markdown(self) -> str:
        if self.draft is None:
            return ""
        outline = self.ensure_outline_data()
        lines = [f"# {self.selected_project.name if self.selected_project else '大纲'}", ""]
        temp = QTextEdit()

        def append_node(node: dict[str, Any], level: int) -> None:
            heading = "#" * min(level + 1, 6)
            lines.append(f"{heading} {node.get('title', '未命名')}")
            if node.get("goal"):
                lines.append(f"- 目标：{node.get('goal')}")
            if node.get("timeline_tag"):
                lines.append(f"- 时间线：{node.get('timeline_tag')}")
            content = node.get("content", "")
            if content:
                temp.setHtml(content)
                plain = temp.toPlainText().strip()
                if plain:
                    lines.extend(["", plain])
            lines.append("")
            for child in node.get("children", []):
                append_node(child, level + 1)

        for node in outline.get("nodes", []):
            append_node(node, 1)
        if outline.get("timeline_points"):
            lines.extend(["## 时间轴", ""])
            for point in outline.get("timeline_points", []):
                lines.append(f"- {point.get('time', '')}：{point.get('event', '')}（{point.get('line', '')}）")
        return "\n".join(lines).strip() + "\n"

    def export_outline(self) -> None:
        if not self.selected_project:
            QMessageBox.information(self, "没有项目", "请先选择或创建一个项目。")
            return
        self.save_current_outline_node(silent=True)
        export_dir = Path(self.selected_project.path) / "exports"
        export_dir.mkdir(parents=True, exist_ok=True)
        output = export_dir / f"{self.selected_project.name}_大纲.md"
        try:
            output.write_text(self.outline_to_markdown(), encoding="utf-8")
        except OSError as exc:
            QMessageBox.critical(self, "导出失败", str(exc))
            return
        QMessageBox.information(self, "已导出", f"大纲已导出到：\n{output}")

    def build_worldbuilding_page(self) -> QWidget:
        page = QWidget()
        page.setObjectName("WorldbuildingPage")
        layout = QVBoxLayout(page)
        layout.setContentsMargins(24, 20, 24, 22)
        layout.setSpacing(14)

        header = QHBoxLayout()
        title_group = QVBoxLayout()
        title_group.setSpacing(4)
        title = QLabel("设定库")
        title.setObjectName("PageTitle")
        self.world_status_label = QLabel("未打开项目")
        self.world_status_label.setObjectName("Muted")
        title_group.addWidget(title)
        title_group.addWidget(self.world_status_label)
        header.addLayout(title_group, 1)
        save_btn = QPushButton("保存当前项目")
        save_btn.setObjectName("PrimaryButton")
        save_btn.clicked.connect(self.save_current_project)
        export_btn = QPushButton("导出设定")
        export_btn.clicked.connect(self.export_worldbuilding)
        header.addWidget(save_btn)
        header.addWidget(export_btn)
        layout.addLayout(header)

        body = QHBoxLayout()
        body.setSpacing(18)
        body.addWidget(self.build_worldbuilding_sidebar())
        body.addWidget(self.build_worldbuilding_editor(), 1)
        body.addWidget(self.build_worldbuilding_right_panel())
        layout.addLayout(body, 1)
        return page

    def build_worldbuilding_sidebar(self) -> QWidget:
        box = QFrame()
        box.setObjectName("WorldDirectoryPane")
        box.setFixedWidth(286)
        layout = QVBoxLayout(box)
        layout.setContentsMargins(18, 18, 14, 18)
        layout.setSpacing(14)

        title = QLabel("设定模块")
        title.setObjectName("SectionTitle")
        subtitle = QLabel("默认五类，可新增同级词库模块")
        subtitle.setObjectName("Muted")
        layout.addWidget(title)
        layout.addWidget(subtitle)

        actions = QHBoxLayout()
        submenu_btn = QPushButton("+ 子模块")
        submenu_btn.setObjectName("SmallButton")
        submenu_btn.clicked.connect(lambda: self.add_world_node("submenu"))
        entry_btn = QPushButton("+ 词条")
        entry_btn.setObjectName("PrimaryButton")
        entry_btn.clicked.connect(lambda: self.add_world_node("entry"))
        manage_btn = QPushButton("管理")
        manage_btn.setObjectName("SmallButton")
        manage_btn.clicked.connect(self.show_world_module_manage_info)
        actions.addWidget(submenu_btn)
        actions.addWidget(entry_btn)
        actions.addWidget(manage_btn)
        layout.addLayout(actions)

        self.world_tree = QTreeWidget()
        self.world_tree.setObjectName("WorldTree")
        self.world_tree.setHeaderHidden(True)
        self.world_tree.setIndentation(14)
        self.world_tree.setIconSize(QSize(10, 10))
        self.world_tree.setContextMenuPolicy(Qt.CustomContextMenu)
        self.world_tree.itemSelectionChanged.connect(self.on_world_node_selected)
        self.world_tree.customContextMenuRequested.connect(self.show_world_node_menu)
        layout.addWidget(self.world_tree, 1)

        hint = QLabel("+ 子模块用于新建同级词库模块；+ 词条可在模块或现有词条下新建词条。")
        hint.setObjectName("ScopeBadge")
        hint.setWordWrap(True)
        layout.addWidget(hint)
        return box

    def build_worldbuilding_editor(self) -> QWidget:
        box = QFrame()
        box.setObjectName("WorldEditorPane")
        layout = QVBoxLayout(box)
        layout.setContentsMargins(18, 18, 18, 14)
        layout.setSpacing(12)

        top = QHBoxLayout()
        title_group = QVBoxLayout()
        title_group.setSpacing(3)
        self.world_entry_title_label = QLabel("词条卡编辑")
        self.world_entry_title_label.setObjectName("SectionTitle")
        self.world_entry_meta_label = QLabel("选择左侧词条开始编辑")
        self.world_entry_meta_label.setObjectName("Muted")
        title_group.addWidget(self.world_entry_title_label)
        title_group.addWidget(self.world_entry_meta_label)
        top.addLayout(title_group, 1)
        save_btn = QPushButton("保存词条")
        save_btn.setObjectName("PrimaryButton")
        save_btn.clicked.connect(self.save_current_world_entry)
        top.addWidget(save_btn)
        layout.addLayout(top)

        entry_header = QFrame()
        entry_header.setObjectName("OutlineGoalBox")
        entry_header_layout = QHBoxLayout(entry_header)
        entry_header_layout.setContentsMargins(14, 10, 14, 10)
        entry_header_layout.setSpacing(14)

        image_box = QFrame()
        image_box.setObjectName("WorldImageBox")
        image_layout = QVBoxLayout(image_box)
        image_layout.setContentsMargins(10, 10, 10, 10)
        image_layout.setSpacing(8)
        image_title = QLabel("词条图片")
        image_title.setObjectName("DetailName")
        self.world_image_label = QLabel("未添加图片\n点击放大预览")
        self.world_image_label.setObjectName("WorldImagePreview")
        self.world_image_label.setFixedSize(150, 108)
        self.world_image_label.setAlignment(Qt.AlignCenter)
        self.world_image_label.setWordWrap(True)
        self.world_image_label.setCursor(Qt.PointingHandCursor)
        self.world_image_label.mousePressEvent = lambda event: self.preview_world_entry_image()
        image_actions = QHBoxLayout()
        image_actions.setSpacing(6)
        image_actions.addStretch(1)
        for icon, tooltip, callback in [
            ("image-add", "添加词条图片", self.choose_world_entry_image),
            ("replace", "替换词条图片", self.choose_world_entry_image),
            ("trash", "删除词条图片", self.remove_world_entry_image),
            ("eye", "预览词条图片", self.preview_world_entry_image),
        ]:
            image_actions.addWidget(self.make_tool_button(icon, tooltip, callback))
        image_actions.addStretch(1)
        image_layout.addWidget(image_title)
        image_layout.addWidget(self.world_image_label)
        image_layout.addLayout(image_actions)
        entry_header_layout.addWidget(image_box)

        form = QWidget()
        form_layout = QGridLayout(form)
        form_layout.setContentsMargins(0, 0, 0, 0)
        form_layout.setHorizontalSpacing(10)
        form_layout.setVerticalSpacing(10)
        name_label = QLabel("词条名")
        name_label.setObjectName("DetailName")
        type_label = QLabel("类型")
        type_label.setObjectName("DetailName")
        tags_label = QLabel("设定标签")
        tags_label.setObjectName("DetailName")
        self.world_entry_name_edit = QLineEdit()
        self.world_entry_type_edit = QLineEdit()
        self.world_entry_tags_edit = QLineEdit()
        self.world_entry_name_edit.setPlaceholderText("词条名")
        self.world_entry_type_edit.setPlaceholderText("地点 / 组织 / 能力 / 道具")
        self.world_entry_tags_edit.setPlaceholderText("用逗号分隔，例如 雾港, 港口, 可跳转标签")
        form_layout.addWidget(name_label, 0, 0)
        form_layout.addWidget(self.world_entry_name_edit, 0, 1)
        form_layout.addWidget(type_label, 0, 2)
        form_layout.addWidget(self.world_entry_type_edit, 0, 3)
        form_layout.addWidget(tags_label, 1, 0)
        form_layout.addWidget(self.world_entry_tags_edit, 1, 1, 1, 3)
        entry_header_layout.addWidget(form, 1)
        layout.addWidget(entry_header)

        toolbar = QHBoxLayout()
        toolbar.setSpacing(6)
        for icon, tooltip, callback in [
            ("undo", "撤销", lambda: self.world_entry_editor.undo()),
            ("redo", "重做", lambda: self.world_entry_editor.redo()),
            ("bold", "加粗", self.toggle_bold),
            ("heading", "设为标题", self.apply_heading),
            ("comment", "插入批注", self.apply_comment_style),
        ]:
            toolbar.addWidget(self.make_tool_button(icon, tooltip, callback))
        self.world_font_box = QFontComboBox()
        self.world_font_box.setObjectName("ToolbarFontCombo")
        self.world_font_box.setFixedSize(180, 34)
        self.world_font_box.setCurrentFont(QFont(DEFAULT_BODY_FONT_FAMILY))
        self.world_font_box.currentFontChanged.connect(self.change_world_font)
        self.world_font_size_box = QComboBox()
        self.world_font_size_box.setObjectName("ToolbarSizeCombo")
        self.world_font_size_box.setFixedSize(92, 34)
        self.world_font_size_box.setEditable(True)
        for size in [10, 12, 14, 15, 16, 18, 20, 22, 24, 28]:
            self.world_font_size_box.addItem(str(size), size)
        self.world_font_size_box.setCurrentText("14")
        self.world_font_size_box.currentTextChanged.connect(self.change_world_font_size)
        toolbar.addWidget(self.world_font_box)
        toolbar.addWidget(self.world_font_size_box)
        toolbar.addStretch(1)
        layout.addLayout(toolbar)

        self.world_entry_editor = QTextEdit()
        self.world_entry_editor.setObjectName("WorldTextEdit")
        self.world_entry_editor.setAcceptRichText(True)
        self.world_entry_editor.setPlaceholderText("写设定概述、细节、限制、引用备注。")
        self.world_entry_editor.textChanged.connect(self.on_world_text_changed)
        layout.addWidget(self.world_entry_editor, 1)

        hint = QLabel("提示：人物卡里的阵营、能力、地点等标签可以引用这些设定词条；点击标签时跳转到对应词条卡。")
        hint.setObjectName("ScopeBadge")
        hint.setWordWrap(True)
        layout.addWidget(hint)
        return box

    def build_worldbuilding_right_panel(self) -> QWidget:
        box = QFrame()
        box.setObjectName("WorldAIPane")
        box.setFixedWidth(360)
        layout = QVBoxLayout(box)
        layout.setContentsMargins(18, 18, 18, 18)
        layout.setSpacing(14)

        title = QLabel("搜索与引用")
        title.setObjectName("SectionTitle")
        sub = QLabel("直接搜索词条，点击跳转")
        sub.setObjectName("Muted")
        layout.addWidget(title)
        layout.addWidget(sub)

        search_row = QHBoxLayout()
        self.world_search_edit = QLineEdit()
        self.world_search_edit.setPlaceholderText("搜索设定词条")
        self.world_search_edit.returnPressed.connect(self.search_world_entries)
        search_btn = QPushButton("搜索")
        search_btn.setObjectName("PrimaryButton")
        search_btn.clicked.connect(self.search_world_entries)
        search_row.addWidget(self.world_search_edit, 1)
        search_row.addWidget(search_btn)
        layout.addLayout(search_row)

        result_title = QLabel("搜索结果")
        result_title.setObjectName("DetailName")
        layout.addWidget(result_title)
        self.world_search_results = QListWidget()
        self.world_search_results.setObjectName("RecentList")
        self.world_search_results.itemActivated.connect(self.open_world_search_result)
        self.world_search_results.itemClicked.connect(self.open_world_search_result)
        layout.addWidget(self.world_search_results, 2)

        ref_title = QLabel("引用关系")
        ref_title.setObjectName("DetailName")
        layout.addWidget(ref_title)
        self.world_reference_box = QTextEdit()
        self.world_reference_box.setObjectName("SummaryBox")
        self.world_reference_box.setReadOnly(True)
        self.world_reference_box.setMaximumHeight(150)
        layout.addWidget(self.world_reference_box)

        ai_title = QLabel("AI 设定检查")
        ai_title.setObjectName("DetailName")
        layout.addWidget(ai_title)
        ai_btn = QPushButton("检查矛盾")
        ai_btn.setObjectName("PrimaryButton")
        ai_btn.clicked.connect(self.check_worldbuilding_with_ai)
        layout.addWidget(ai_btn)
        self.world_ai_box = QTextEdit()
        self.world_ai_box.setObjectName("SummaryBox")
        self.world_ai_box.setReadOnly(True)
        self.world_ai_box.setText("AI 接口配置完成后，可读取全项目设定、人物卡和章节总结，检查命名冲突或规则矛盾。")
        layout.addWidget(self.world_ai_box, 1)
        return box

    def build_character_page(self) -> QWidget:
        page = QWidget()
        page.setObjectName("CharacterPage")
        layout = QVBoxLayout(page)
        layout.setContentsMargins(24, 20, 24, 22)
        layout.setSpacing(14)

        header = QHBoxLayout()
        title_group = QVBoxLayout()
        title_group.setSpacing(4)
        title = QLabel("人物卡")
        title.setObjectName("PageTitle")
        self.character_status_label = QLabel("未打开项目")
        self.character_status_label.setObjectName("Muted")
        title_group.addWidget(title)
        title_group.addWidget(self.character_status_label)
        header.addLayout(title_group, 1)
        save_btn = QPushButton("保存当前项目")
        save_btn.setObjectName("PrimaryButton")
        save_btn.clicked.connect(self.save_current_project)
        header.addWidget(save_btn)
        layout.addLayout(header)

        body = QHBoxLayout()
        body.setSpacing(18)
        body.addWidget(self.build_character_sidebar())
        body.addWidget(self.build_character_editor(), 1)
        body.addWidget(self.build_character_ai_panel())
        layout.addLayout(body, 1)
        return page

    def build_character_sidebar(self) -> QWidget:
        box = QFrame()
        box.setObjectName("CharacterListPane")
        box.setFixedWidth(310)
        layout = QVBoxLayout(box)
        layout.setContentsMargins(18, 18, 18, 18)
        layout.setSpacing(12)

        title = QLabel("人物列表")
        title.setObjectName("SectionTitle")
        subtitle = QLabel("按阵营或自定义分组整理")
        subtitle.setObjectName("Muted")
        layout.addWidget(title)
        layout.addWidget(subtitle)

        actions = QHBoxLayout()
        add_btn = QPushButton("+ 人物")
        add_btn.setObjectName("PrimaryButton")
        add_btn.clicked.connect(self.add_character)
        group_btn = QPushButton("+ 分组")
        group_btn.setObjectName("SmallButton")
        group_btn.clicked.connect(self.add_character_group)
        actions.addWidget(add_btn)
        actions.addWidget(group_btn)
        layout.addLayout(actions)

        self.character_search_edit = QLineEdit()
        self.character_search_edit.setPlaceholderText("搜索人物")
        self.character_search_edit.textChanged.connect(lambda text: self.populate_character_tree(self.current_character_id))
        layout.addWidget(self.character_search_edit)

        self.character_tree = QTreeWidget()
        self.character_tree.setObjectName("CharacterTree")
        self.character_tree.setHeaderHidden(True)
        self.character_tree.setIndentation(18)
        self.character_tree.setContextMenuPolicy(Qt.CustomContextMenu)
        self.character_tree.itemSelectionChanged.connect(self.on_character_selected)
        self.character_tree.customContextMenuRequested.connect(self.show_character_menu)
        layout.addWidget(self.character_tree, 1)

        hint = QLabel("当前阵营会自动决定人物所在分组；删除分组时人物移入“未分组”。")
        hint.setObjectName("ScopeBadge")
        hint.setWordWrap(True)
        layout.addWidget(hint)
        return box

    def build_character_editor(self) -> QWidget:
        scroll = QScrollArea()
        scroll.setObjectName("CharacterEditorScroll")
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.NoFrame)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.character_editor_scroll = scroll

        box = QFrame()
        box.setObjectName("CharacterEditorPane")
        layout = QVBoxLayout(box)
        layout.setContentsMargins(18, 18, 18, 14)
        layout.setSpacing(12)

        top = QHBoxLayout()
        title_group = QVBoxLayout()
        title_group.setSpacing(3)
        self.character_title_label = QLabel("人物卡编辑")
        self.character_title_label.setObjectName("SectionTitle")
        self.character_meta_label = QLabel("选择左侧人物开始编辑")
        self.character_meta_label.setObjectName("Muted")
        title_group.addWidget(self.character_title_label)
        title_group.addWidget(self.character_meta_label)
        top.addLayout(title_group, 1)
        save_btn = QPushButton("保存人物卡")
        save_btn.setObjectName("PrimaryButton")
        save_btn.clicked.connect(self.save_current_character)
        top.addWidget(save_btn)
        layout.addLayout(top)

        card = QFrame()
        card.setObjectName("OutlineGoalBox")
        card_layout = QHBoxLayout(card)
        card_layout.setContentsMargins(14, 10, 14, 10)
        card_layout.setSpacing(14)

        portrait_box = QFrame()
        portrait_box.setObjectName("CharacterPortraitBox")
        portrait_layout = QVBoxLayout(portrait_box)
        portrait_layout.setContentsMargins(10, 10, 10, 10)
        portrait_layout.setSpacing(8)
        portrait_title = QLabel("人物画像")
        portrait_title.setObjectName("DetailName")
        self.character_portrait_label = QLabel("未添加画像\n点击放大预览")
        self.character_portrait_label.setObjectName("CharacterPortraitPreview")
        self.character_portrait_label.setFixedSize(150, 150)
        self.character_portrait_label.setAlignment(Qt.AlignCenter)
        self.character_portrait_label.setWordWrap(True)
        self.character_portrait_label.setCursor(Qt.PointingHandCursor)
        self.character_portrait_label.mousePressEvent = lambda event: self.preview_character_portrait()
        portrait_actions = QHBoxLayout()
        portrait_actions.setSpacing(6)
        portrait_actions.addStretch(1)
        for icon, tooltip, callback in [
            ("image-add", "添加画像", self.choose_character_portrait),
            ("replace", "替换画像", self.choose_character_portrait),
            ("trash", "删除画像", self.remove_character_portrait),
            ("eye", "预览画像", self.preview_character_portrait),
        ]:
            portrait_actions.addWidget(self.make_tool_button(icon, tooltip, callback))
        portrait_actions.addStretch(1)
        portrait_layout.addWidget(portrait_title)
        portrait_layout.addWidget(self.character_portrait_label)
        portrait_layout.addLayout(portrait_actions)
        card_layout.addWidget(portrait_box)

        form = QWidget()
        form_layout = QGridLayout(form)
        form_layout.setContentsMargins(0, 0, 0, 0)
        form_layout.setHorizontalSpacing(10)
        form_layout.setVerticalSpacing(10)
        self.character_name_edit = QLineEdit()
        self.character_gender_box = QComboBox()
        self.character_gender_box.setEditable(True)
        self.character_gender_box.addItems(["男", "女", "未知", "其他"])
        self.character_age_edit = QLineEdit()
        self.character_identity_edit = QLineEdit()
        self.character_faction_box = QComboBox()
        self.character_faction_box.setEditable(True)
        self.character_faction_box.activated.connect(lambda index: self.on_character_faction_committed())
        self.character_faction_box.lineEdit().editingFinished.connect(self.on_character_faction_committed)
        self.character_status_box = QComboBox()
        self.character_status_box.setEditable(True)
        self.character_status_box.addItems(["构思中", "登场", "调查中", "失踪", "被通缉", "死亡"])
        for widget in [
            self.character_name_edit,
            self.character_age_edit,
            self.character_identity_edit,
        ]:
            widget.setObjectName("CharacterFieldInput")
            widget.setMinimumHeight(34)
        for widget in [
            self.character_gender_box,
            self.character_faction_box,
            self.character_status_box,
        ]:
            widget.setObjectName("CharacterFieldCombo")
            widget.setMinimumHeight(34)
        for widget in [
            self.character_name_edit,
            self.character_gender_box,
            self.character_age_edit,
            self.character_identity_edit,
            self.character_faction_box,
            self.character_status_box,
        ]:
            widget.setMinimumWidth(220)
        for row, (label, widget) in enumerate(
            [
                ("角色名", self.character_name_edit),
                ("性别", self.character_gender_box),
                ("年龄", self.character_age_edit),
                ("身份", self.character_identity_edit),
                ("当前阵营", self.character_faction_box),
                ("当前状态", self.character_status_box),
            ]
        ):
            label_widget = QLabel(label)
            label_widget.setObjectName("DetailName")
            form_layout.addWidget(label_widget, row, 0)
            form_layout.addWidget(widget, row, 1)
        form_layout.setColumnStretch(1, 1)
        card_layout.addWidget(form, 1)
        layout.addWidget(card)

        tag_card = QFrame()
        tag_card.setObjectName("CharacterTagBox")
        tag_layout = QGridLayout(tag_card)
        tag_layout.setContentsMargins(12, 10, 12, 10)
        tag_layout.setHorizontalSpacing(10)
        tag_layout.setVerticalSpacing(10)
        self.character_tag_edits: dict[str, QLineEdit] = {}
        for row, tag_name in enumerate(["性格", "能力", "角色特点", "喜好"]):
            label = QLabel(tag_name)
            label.setObjectName("DetailName")
            edit = QLineEdit()
            edit.setPlaceholderText("用逗号分隔，可自由添加")
            edit.textChanged.connect(lambda text, name=tag_name: self.update_character_status(dirty=True) if not self.loading_character else None)
            edit.editingFinished.connect(self.on_character_tags_committed)
            self.character_tag_edits[tag_name] = edit
            tag_layout.addWidget(label, row, 0)
            tag_layout.addWidget(edit, row, 1)
        self.character_ability_links_widget = QWidget()
        self.character_ability_links_layout = QHBoxLayout(self.character_ability_links_widget)
        self.character_ability_links_layout.setContentsMargins(0, 0, 0, 0)
        self.character_ability_links_layout.setSpacing(6)
        ability_hint = QLabel("能力标签")
        ability_hint.setObjectName("DetailName")
        tag_layout.addWidget(ability_hint, 4, 0)
        tag_layout.addWidget(self.character_ability_links_widget, 4, 1)
        layout.addWidget(tag_card)

        format_toolbar = QHBoxLayout()
        format_toolbar.setSpacing(6)
        for icon, tooltip, callback in [
            ("undo", "撤销", lambda: self.character_notes_editor.undo()),
            ("redo", "重做", lambda: self.character_notes_editor.redo()),
            ("bold", "加粗", self.toggle_bold),
            ("heading", "设为标题", self.apply_heading),
            ("comment", "插入批注", self.apply_comment_style),
        ]:
            format_toolbar.addWidget(self.make_tool_button(icon, tooltip, callback))
        format_toolbar.addStretch(1)
        layout.addLayout(format_toolbar)

        font_toolbar = QHBoxLayout()
        font_toolbar.setSpacing(6)
        self.character_font_box = QFontComboBox()
        self.character_font_box.setObjectName("ToolbarFontCombo")
        self.character_font_box.setFixedSize(300, 34)
        self.character_font_box.setCurrentFont(QFont(DEFAULT_BODY_FONT_FAMILY))
        self.character_font_box.currentFontChanged.connect(self.change_character_font)
        self.character_font_size_box = QComboBox()
        self.character_font_size_box.setObjectName("ToolbarSizeCombo")
        self.character_font_size_box.setFixedSize(92, 34)
        self.character_font_size_box.setEditable(True)
        for size in [10, 12, 14, 15, 16, 18, 20, 22, 24, 28]:
            self.character_font_size_box.addItem(str(size), size)
        self.character_font_size_box.setCurrentText("14")
        self.character_font_size_box.currentTextChanged.connect(self.change_character_font_size)
        font_toolbar.addWidget(self.character_font_box)
        font_toolbar.addWidget(self.character_font_size_box)
        font_toolbar.addStretch(1)
        layout.addLayout(font_toolbar)

        self.character_notes_editor = QTextEdit()
        self.character_notes_editor.setObjectName("CharacterTextEdit")
        self.character_notes_editor.setAcceptRichText(True)
        self.character_notes_editor.setPlaceholderText("写人物背景、秘密、行为习惯、关系备注。")
        self.character_notes_editor.textChanged.connect(self.on_character_text_changed)
        layout.addWidget(self.character_notes_editor, 1)

        self.character_history_toggle = QPushButton("人物历程 >")
        self.character_history_toggle.setObjectName("SmallButton")
        self.character_history_toggle.clicked.connect(self.toggle_character_history)
        layout.addWidget(self.character_history_toggle)
        self.character_history_box = QFrame()
        self.character_history_box.setObjectName("CharacterHistoryBox")
        history_layout = QVBoxLayout(self.character_history_box)
        history_layout.setContentsMargins(12, 10, 12, 10)
        history_layout.setSpacing(8)
        history_actions = QHBoxLayout()
        history_title = QLabel("人物历程")
        history_title.setObjectName("DetailName")
        history_actions.addWidget(history_title, 1)
        add_history_btn = QPushButton("+ 记录")
        add_history_btn.setObjectName("SmallButton")
        add_history_btn.clicked.connect(self.add_character_history)
        delete_history_btn = QPushButton("删除记录")
        delete_history_btn.setObjectName("SmallButton")
        delete_history_btn.clicked.connect(self.delete_character_history)
        history_actions.addWidget(add_history_btn)
        history_actions.addWidget(delete_history_btn)
        self.character_history_list = QListWidget()
        self.character_history_list.setFixedHeight(126)
        history_layout.addLayout(history_actions)
        history_layout.addWidget(self.character_history_list)
        self.character_history_box.setVisible(False)
        layout.addWidget(self.character_history_box)

        self.character_relation_toggle = QPushButton("人物关系 >")
        self.character_relation_toggle.setObjectName("SmallButton")
        self.character_relation_toggle.clicked.connect(self.toggle_character_relations)
        layout.addWidget(self.character_relation_toggle)
        self.character_relation_box = QFrame()
        self.character_relation_box.setObjectName("CharacterRelationBox")
        relation_layout = QVBoxLayout(self.character_relation_box)
        relation_layout.setContentsMargins(12, 10, 12, 10)
        relation_layout.setSpacing(8)
        relation_actions = QHBoxLayout()
        relation_title = QLabel("人物关系")
        relation_title.setObjectName("DetailName")
        relation_hint = QLabel("双击记录可编辑")
        relation_hint.setObjectName("Muted")
        relation_actions.addWidget(relation_title)
        relation_actions.addWidget(relation_hint, 1)
        relation_buttons = QHBoxLayout()
        relation_buttons.setSpacing(6)
        add_relation_btn = QPushButton("+ 关系")
        add_relation_btn.setObjectName("SmallButton")
        add_relation_btn.clicked.connect(self.add_character_relation)
        delete_relation_btn = QPushButton("删除")
        delete_relation_btn.setObjectName("SmallButton")
        delete_relation_btn.clicked.connect(self.delete_character_relation)
        relation_buttons.addWidget(add_relation_btn)
        relation_buttons.addWidget(delete_relation_btn)
        relation_buttons.addStretch(1)
        self.character_relation_list = QListWidget()
        self.character_relation_list.setObjectName("CharacterRelationList")
        self.character_relation_list.setFixedHeight(132)
        self.character_relation_list.itemDoubleClicked.connect(lambda item: self.edit_character_relation())
        relation_layout.addLayout(relation_actions)
        relation_layout.addLayout(relation_buttons)
        relation_layout.addWidget(self.character_relation_list)
        self.character_relation_box.setVisible(False)
        layout.addWidget(self.character_relation_box)
        scroll.setWidget(box)
        return scroll

    def build_character_ai_panel(self) -> QWidget:
        box = QFrame()
        box.setObjectName("CharacterAIPane")
        box.setFixedWidth(350)
        layout = QVBoxLayout(box)
        layout.setContentsMargins(18, 18, 18, 18)
        layout.setSpacing(14)

        title = QLabel("AI 人物建议")
        title.setObjectName("SectionTitle")
        layout.addWidget(title)

        self.character_scope_toggle_btn = QPushButton("读取范围 >")
        self.character_scope_toggle_btn.setObjectName("SmallButton")
        self.character_scope_toggle_btn.clicked.connect(self.toggle_character_ai_scope)
        layout.addWidget(self.character_scope_toggle_btn)

        self.character_scope_frame = QFrame()
        self.character_scope_frame.setObjectName("OutlineScopeBox")
        scope_layout = QVBoxLayout(self.character_scope_frame)
        scope_layout.setContentsMargins(12, 10, 12, 10)
        scope_layout.setSpacing(8)
        scope_title = QLabel("读取范围")
        scope_title.setObjectName("DetailName")
        scope_layout.addWidget(scope_title)

        self.character_scope_checks: dict[str, QCheckBox] = {}
        scope_grid = QGridLayout()
        scope_grid.setHorizontalSpacing(8)
        scope_grid.setVerticalSpacing(4)
        scope_items = [
            ("current_character", "当前人物卡"),
            ("current_relations", "当前关系"),
            ("world", "设定库"),
            ("summaries", "章节总结"),
            ("all_characters", "全部人物卡"),
            ("all_relations", "全部关系"),
            ("outline", "大纲"),
            ("timeline", "时间轴"),
            ("current_chapter_body", "当前章正文"),
            ("selected_chapter_bodies", "指定章节正文"),
            ("all_chapter_bodies", "全书正文"),
        ]
        defaults = default_character_ai_scope()
        for index, (key, label) in enumerate(scope_items):
            check = QCheckBox(label)
            check.setChecked(defaults.get(key, False))
            check.toggled.connect(self.on_character_ai_scope_changed)
            self.character_scope_checks[key] = check
            scope_grid.addWidget(check, index // 2, index % 2)
        scope_layout.addLayout(scope_grid)

        selected_row = QHBoxLayout()
        self.character_selected_chapters_label = QLabel("未选择章节")
        self.character_selected_chapters_label.setObjectName("Muted")
        self.character_select_chapters_btn = QPushButton("选择章节")
        self.character_select_chapters_btn.clicked.connect(self.choose_character_ai_chapters)
        selected_row.addWidget(self.character_selected_chapters_label, 1)
        selected_row.addWidget(self.character_select_chapters_btn)
        scope_layout.addLayout(selected_row)

        self.character_scope_hint_label = QLabel("默认不读取完整正文；正文类范围请求前会确认。")
        self.character_scope_hint_label.setObjectName("ScopeBadge")
        self.character_scope_hint_label.setWordWrap(True)
        scope_layout.addWidget(self.character_scope_hint_label)
        self.character_scope_frame.setVisible(False)
        layout.addWidget(self.character_scope_frame)

        self.character_ai_suggest_btn = QPushButton("生成建议")
        self.character_ai_suggest_btn.setObjectName("PrimaryButton")
        self.character_ai_suggest_btn.clicked.connect(self.generate_character_ai_suggestions)
        layout.addWidget(self.character_ai_suggest_btn)

        self.character_ai_box = QTextEdit()
        self.character_ai_box.setObjectName("CharacterAIBox")
        self.character_ai_box.setReadOnly(True)
        self.character_ai_box.setText(
            "AI 接口配置完成后，可根据当前人物卡、人物关系记录、设定库和章节总结检查性格一致性、能力限制、剧情风险和关系建议。"
        )

        self.character_recent_label = QLabel("最近登场：自动读取将在正文检索接入后启用。")
        self.character_recent_label.setObjectName("ScopeBadge")
        self.character_recent_label.setWordWrap(True)

        self.character_ai_splitter = QSplitter(Qt.Vertical)
        self.character_ai_splitter.setObjectName("AIPanelSplitter")
        self.character_ai_splitter.addWidget(self.character_ai_box)
        input_box = QWidget()
        input_box.setObjectName("AIInputPanel")
        input_layout = QVBoxLayout(input_box)
        input_layout.setContentsMargins(0, 0, 0, 0)
        input_layout.setSpacing(6)
        input_layout.addWidget(self.character_recent_label)
        self.character_ai_input = self.build_ai_chat_input("向 AI 询问这个人物...", self.send_character_ai_message)
        input_layout.addWidget(self.character_ai_input)
        self.character_ai_send_btn = self.build_ai_icon_button("send", "发送", self.send_character_ai_message, primary=True)
        self.character_ai_stop_btn = self.build_ai_icon_button("stop", "停止生成", self.stop_character_ai_stream)
        self.character_ai_stop_btn.setEnabled(False)
        self.character_ai_clear_btn = self.build_ai_icon_button("trash", "清除对话", self.clear_character_ai_chat)
        chat_actions = QHBoxLayout()
        chat_actions.setContentsMargins(0, 0, 0, 0)
        chat_actions.setSpacing(6)
        chat_actions.addStretch(1)
        chat_actions.addWidget(self.character_ai_send_btn)
        chat_actions.addWidget(self.character_ai_stop_btn)
        chat_actions.addWidget(self.character_ai_clear_btn)
        input_layout.addLayout(chat_actions)
        self.character_ai_splitter.addWidget(input_box)
        self.character_ai_splitter.setStretchFactor(0, 3)
        self.character_ai_splitter.setStretchFactor(1, 2)
        self.character_ai_splitter.setSizes([260, 170])
        layout.addWidget(self.character_ai_splitter, 1)
        return box

    def character_defaults(self) -> dict[str, Any]:
        first_id = DraftStore.new_id("char")
        second_id = DraftStore.new_id("char")
        return {
            "current_character_id": first_id,
            "groups": ["雾港巡逻队", "旧港商会", "未分组"],
            "cards": [
                {
                    "id": first_id,
                    "name": "沈砚",
                    "gender": "男",
                    "age": "24",
                    "identity": "巡逻队记录员",
                    "faction": "雾港巡逻队",
                    "status": "调查中",
                    "portrait_path": "",
                    "tags": {
                        "性格": ["内敛", "敏锐", "谨慎"],
                        "能力": ["文书整理", "观察力", "推理"],
                        "角色特点": ["记忆力好", "注重细节"],
                        "喜好": ["记录日记", "茶", "旧书"],
                    },
                    "ability_links": {},
                    "notes": "<p>沈砚出身普通，曾在雾港巡逻队担任文书工作。因其出色的记录与分析能力，被安排专门负责各类案件与巡逻日志的整理。</p>",
                    "history": [
                        {"id": DraftStore.new_id("his"), "time": "T-1", "event": "加入雾港巡逻队。"},
                        {"id": DraftStore.new_id("his"), "time": "T0", "event": "开始调查黑石码头。"},
                    ],
                    "relations": [
                        {
                            "id": DraftStore.new_id("rel"),
                            "target_id": second_id,
                            "target_name": "苏雁回",
                            "type": "合作",
                            "status": "当前",
                            "note": "通过旧港商会账目线索产生交集。",
                        }
                    ],
                    "updated_at": now_iso(),
                },
                {
                    "id": second_id,
                    "name": "苏雁回",
                    "gender": "女",
                    "age": "28",
                    "identity": "旧港商会账房",
                    "faction": "旧港商会",
                    "status": "登场",
                    "portrait_path": "",
                    "tags": {"性格": ["冷静"], "能力": ["账目核查"], "角色特点": ["消息灵通"], "喜好": ["算盘"]},
                    "ability_links": {},
                    "notes": "<p>苏雁回掌握旧港商会的账目线索，常以旁观者身份提供关键信息。</p>",
                    "history": [],
                    "relations": [
                        {
                            "id": DraftStore.new_id("rel"),
                            "target_id": first_id,
                            "target_name": "沈砚",
                            "type": "合作",
                            "status": "当前",
                            "note": "向沈砚提供旧港账目相关信息。",
                        }
                    ],
                    "updated_at": now_iso(),
                },
            ],
            "ai_note": "",
        }

    def ensure_character_data(self) -> dict[str, Any]:
        if self.draft is None:
            raise RuntimeError("draft is not loaded")
        characters = self.draft.setdefault("characters", self.character_defaults())
        if not characters.get("cards"):
            self.draft["characters"] = self.character_defaults()
            characters = self.draft["characters"]
        characters.setdefault("groups", ["未分组"])
        if "未分组" not in characters["groups"]:
            characters["groups"].append("未分组")
        characters.setdefault("ai_note", "")
        for card in characters.get("cards", []):
            card.setdefault("faction", "未分组")
            card.setdefault("status", "")
            card.setdefault("portrait_path", "")
            card.setdefault("tags", {})
            card.setdefault("ability_links", {})
            card.setdefault("history", [])
            card.setdefault("relations", [])
            for tag_name in ["性格", "能力", "角色特点", "喜好"]:
                card["tags"].setdefault(tag_name, [])
            faction = card.get("faction") or "未分组"
            if faction not in characters["groups"]:
                characters["groups"].append(faction)
        return characters

    def load_character_project(self) -> None:
        if not self.selected_project:
            return
        self.draft = DraftStore.load(self.selected_project)
        characters = self.ensure_character_data()
        self.current_character_id = characters.get("current_character_id")
        if not self.find_character(self.current_character_id):
            first = self.first_character()
            self.current_character_id = first.get("id") if first else None
        self.populate_character_tree(self.current_character_id)
        self.apply_character_ai_scope_settings()
        self.character_selected_chapter_ids = set()
        self.update_character_selected_chapters_label()
        self.update_character_ai_scope_controls()
        note = characters.get("ai_note", "")
        if note:
            self.character_ai_box.setPlainText(note)
        if self.current_character_id:
            self.load_character(self.current_character_id)
        self.update_character_status()

    def first_character(self) -> dict[str, Any] | None:
        if self.draft is None:
            return None
        cards = self.ensure_character_data().get("cards", [])
        return cards[0] if cards else None

    def find_character(self, character_id: str | None) -> dict[str, Any] | None:
        if self.draft is None or not character_id:
            return None
        for card in self.ensure_character_data().get("cards", []):
            if card.get("id") == character_id:
                return card
        return None

    def selected_character_group(self) -> str:
        item = self.character_tree.currentItem() if hasattr(self, "character_tree") else None
        if not item:
            return "未分组"
        data = item.data(0, Qt.UserRole) or {}
        if data.get("kind") == "group":
            return data.get("name") or "未分组"
        if data.get("kind") == "character":
            card = self.find_character(data.get("id"))
            return card.get("faction") or "未分组" if card else "未分组"
        return "未分组"

    def populate_character_tree(self, selected_id: str | None = None) -> None:
        if self.draft is None or not hasattr(self, "character_tree"):
            return
        self.character_tree.blockSignals(True)
        self.character_tree.clear()
        selected_item: QTreeWidgetItem | None = None
        characters = self.ensure_character_data()
        keyword = self.character_search_edit.text().strip() if hasattr(self, "character_search_edit") else ""
        cards_by_group: dict[str, list[dict[str, Any]]] = {group: [] for group in characters.get("groups", [])}
        for card in characters.get("cards", []):
            haystack = " ".join(
                [
                    card.get("name", ""),
                    card.get("identity", ""),
                    card.get("status", ""),
                    " ".join(sum((card.get("tags", {}).get(name, []) for name in ["性格", "能力", "角色特点", "喜好"]), [])),
                ]
            )
            if keyword and keyword not in haystack:
                continue
            cards_by_group.setdefault(card.get("faction") or "未分组", []).append(card)
        for group in characters.get("groups", []):
            group_item = QTreeWidgetItem([f"{group}  ({len(cards_by_group.get(group, []))})"])
            group_item.setData(0, Qt.UserRole, {"kind": "group", "name": group})
            group_item.setIcon(0, text_icon("组", PALETTE["green"], 18, True))
            self.character_tree.addTopLevelItem(group_item)
            for card in cards_by_group.get(group, []):
                item = QTreeWidgetItem([f"{card.get('name', '未命名')}    {card.get('identity', '')}"])
                item.setData(0, Qt.UserRole, {"kind": "character", "id": card.get("id")})
                item.setIcon(0, self.character_icon(card))
                group_item.addChild(item)
                if card.get("id") == selected_id:
                    selected_item = item
            group_item.setExpanded(True)
        if selected_item:
            self.character_tree.setCurrentItem(selected_item)
        self.character_tree.blockSignals(False)

    def character_icon(self, card: dict[str, Any]) -> QIcon:
        path = self.current_character_portrait_path(card)
        if path:
            pixmap = cached_pixmap(path, QSize(20, 20))
            if pixmap:
                return QIcon(pixmap)
        return text_icon("人", PALETTE["green"], 20, True)

    def load_character(self, character_id: str) -> None:
        card = self.find_character(character_id)
        if not card:
            return
        self.loading_character = True
        self.current_character_id = character_id
        self.ensure_character_data()["current_character_id"] = character_id
        self.character_title_label.setText("人物卡编辑")
        self.character_meta_label.setText(f"{card.get('faction') or '未分组'} / {card.get('name', '未命名')}")
        self.character_name_edit.setText(card.get("name", ""))
        self.character_gender_box.setCurrentText(card.get("gender", ""))
        self.character_age_edit.setText(str(card.get("age", "")))
        self.character_identity_edit.setText(card.get("identity", ""))
        self.refresh_character_group_options(card.get("faction") or "未分组")
        self.character_status_box.setCurrentText(card.get("status", ""))
        tags = card.get("tags", {})
        for tag_name, edit in self.character_tag_edits.items():
            edit.setText("，".join(tags.get(tag_name, [])))
        self.character_notes_editor.setHtml(card.get("notes", ""))
        self.populate_character_history(card)
        self.populate_character_relations(card)
        self.update_character_portrait_preview(card)
        self.update_ability_tag_buttons(card)
        self.character_recent_label.setText(self.character_recent_text(card))
        self.loading_character = False
        self.update_character_status()

    def refresh_character_group_options(self, current: str = "") -> None:
        characters = self.ensure_character_data()
        self.character_faction_box.blockSignals(True)
        self.character_faction_box.clear()
        for group in characters.get("groups", []):
            self.character_faction_box.addItem(group)
        self.character_faction_box.setCurrentText(current or "未分组")
        self.character_faction_box.blockSignals(False)

    def tag_values_from_edit(self, tag_name: str) -> list[str]:
        edit = self.character_tag_edits[tag_name]
        return [item.strip() for item in edit.text().replace("，", ",").split(",") if item.strip()]

    def save_current_character(self, silent: bool = False, refresh_ui: bool = True) -> None:
        if not self.selected_project or self.draft is None or not self.current_character_id:
            return
        card = self.find_character(self.current_character_id)
        if not card:
            return
        old_faction = card.get("faction") or "未分组"
        old_name = card.get("name", "")
        name = self.character_name_edit.text().strip() or card.get("name", "未命名")
        faction = self.character_faction_box.currentText().strip() or "未分组"
        characters = self.ensure_character_data()
        if faction not in characters["groups"]:
            characters["groups"].append(faction)
        card["name"] = name
        card["gender"] = self.character_gender_box.currentText().strip()
        card["age"] = self.character_age_edit.text().strip()
        card["identity"] = self.character_identity_edit.text().strip()
        card["faction"] = faction
        card["status"] = self.character_status_box.currentText().strip()
        card["tags"] = {tag_name: self.tag_values_from_edit(tag_name) for tag_name in ["性格", "能力", "角色特点", "喜好"]}
        links = card.setdefault("ability_links", {})
        for tag in list(links):
            if tag not in card["tags"].get("能力", []):
                links.pop(tag, None)
        card["notes"] = self.character_notes_editor.toHtml()
        card["updated_at"] = now_iso()
        if name != old_name:
            self.sync_character_relation_target_name(card["id"], name)
        characters["current_character_id"] = self.current_character_id
        DraftStore.save(self.selected_project, self.draft)
        if refresh_ui:
            if old_faction != faction:
                self.refresh_character_group_options(faction)
            self.populate_character_tree(self.current_character_id)
            self.update_ability_tag_buttons(card)
        self.update_character_status()
        if not silent:
            QMessageBox.information(self, "已保存", "当前人物卡已保存。")

    def on_character_selected(self) -> None:
        if self.loading_character:
            return
        item = self.character_tree.currentItem()
        if not item:
            return
        data = item.data(0, Qt.UserRole) or {}
        if data.get("kind") != "character":
            return
        character_id = data.get("id")
        if self.current_character_id and character_id != self.current_character_id:
            self.save_current_character(silent=True, refresh_ui=False)
        self.load_character(character_id)

    def on_character_faction_committed(self) -> None:
        value = self.character_faction_box.currentText()
        if self.loading_character or not value.strip() or not self.current_character_id:
            return
        characters = self.ensure_character_data()
        faction = value.strip()
        if faction not in characters.get("groups", []):
            answer = QMessageBox.question(
                self,
                "新建分组",
                f"人物分组“{faction}”不存在，是否新建并把当前人物归入该分组？",
                QMessageBox.Yes | QMessageBox.No,
                QMessageBox.Yes,
            )
            if answer != QMessageBox.Yes:
                return
            characters["groups"].append(faction)
        self.save_current_character(silent=True)

    def on_character_text_changed(self) -> None:
        if self.loading_character:
            return
        self.update_character_status(dirty=True)

    def on_character_tags_committed(self) -> None:
        if self.loading_character or not self.current_character_id:
            return
        self.save_current_character(silent=True)

    def update_character_status(self, dirty: bool = False) -> None:
        project = self.selected_project
        card = self.find_character(self.current_character_id)
        title = card.get("name", "未选择人物") if card else "未选择人物"
        suffix = "有未保存修改" if dirty else "自动保存覆盖人物卡内容"
        if hasattr(self, "character_status_label"):
            self.character_status_label.setText(f"{project.name if project else '未打开项目'} · 当前：{title} · {suffix}")

    def show_character_menu(self, pos: QPoint) -> None:
        if self.draft is None:
            return
        item = self.character_tree.itemAt(pos)
        menu = QMenu(self.character_tree)
        if item:
            self.character_tree.setCurrentItem(item)
            data = item.data(0, Qt.UserRole) or {}
            if data.get("kind") == "character":
                char_id = data.get("id")
                menu.addAction("更改名称", lambda: self.rename_character(char_id))
                menu.addAction("删除人物", lambda: self.delete_character(char_id))
            elif data.get("kind") == "group":
                group = data.get("name", "未分组")
                menu.addAction("添加人物到此分组", lambda: self.add_character(group))
                menu.addAction("更改分组名称", lambda: self.rename_character_group(group))
                menu.addAction("删除分组", lambda: self.delete_character_group(group))
        else:
            menu.addAction("添加人物", self.add_character)
            menu.addAction("添加分组", self.add_character_group)
        menu.exec(self.character_tree.viewport().mapToGlobal(pos))

    def add_character_group(self) -> None:
        if self.draft is None:
            self.load_character_project()
        if self.draft is None:
            return
        characters = self.ensure_character_data()
        title, ok = QInputDialog.getText(self, "新增分组", "分组名称：", text=f"新分组 {len(characters.get('groups', [])) + 1}")
        if not ok or not title.strip():
            return
        title = title.strip()
        if title not in characters["groups"]:
            characters["groups"].append(title)
        DraftStore.save(self.selected_project, self.draft)
        self.refresh_character_group_options(title)
        self.populate_character_tree(self.current_character_id)

    def add_character(self, group: str | None = None) -> None:
        if self.draft is None:
            self.load_character_project()
        if self.draft is None:
            return
        self.save_current_character(silent=True)
        characters = self.ensure_character_data()
        group = group or self.selected_character_group() or "未分组"
        if group not in characters["groups"]:
            characters["groups"].append(group)
        title, ok = QInputDialog.getText(self, "新增人物", "角色名：", text=f"新人物 {len(characters.get('cards', [])) + 1}")
        if not ok:
            return
        title = title.strip() or "新人物"
        card = {
            "id": DraftStore.new_id("char"),
            "name": title,
            "gender": "",
            "age": "",
            "identity": "",
            "faction": group,
            "status": "构思中",
            "portrait_path": "",
            "tags": {"性格": [], "能力": [], "角色特点": [], "喜好": []},
            "ability_links": {},
            "notes": "<p></p>",
            "history": [],
            "relations": [],
            "updated_at": now_iso(),
        }
        characters.setdefault("cards", []).append(card)
        self.current_character_id = card["id"]
        DraftStore.save(self.selected_project, self.draft)
        self.populate_character_tree(card["id"])
        self.load_character(card["id"])

    def rename_character(self, character_id: str) -> None:
        card = self.find_character(character_id)
        if not card:
            return
        title, ok = QInputDialog.getText(self, "更改人物名称", "角色名：", text=card.get("name", "未命名"))
        if not ok or not title.strip():
            return
        card["name"] = title.strip()
        self.sync_character_relation_target_name(character_id, card["name"])
        if character_id == self.current_character_id:
            self.character_name_edit.setText(card["name"])
        DraftStore.save(self.selected_project, self.draft)
        self.populate_character_tree(self.current_character_id)
        self.update_character_status()

    def delete_character(self, character_id: str) -> None:
        characters = self.ensure_character_data()
        card = self.find_character(character_id)
        if not card:
            return
        answer = QMessageBox.question(
            self,
            "删除人物",
            f"确定删除人物“{card.get('name', '未命名')}”吗？\n\n第一版会从人物列表中移除，并记录到草稿回收区。",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No,
        )
        if answer != QMessageBox.Yes:
            return
        self.draft.setdefault("deleted_items", []).append({"type": "character", "deleted_at": now_iso(), "data": card})
        characters["cards"] = [item for item in characters.get("cards", []) if item.get("id") != character_id]
        for item in characters.get("cards", []):
            item["relations"] = [relation for relation in item.get("relations", []) if relation.get("target_id") != character_id]
        first = self.first_character()
        self.current_character_id = first.get("id") if first else None
        characters["current_character_id"] = self.current_character_id
        DraftStore.save(self.selected_project, self.draft)
        self.populate_character_tree(self.current_character_id)
        if self.current_character_id:
            self.load_character(self.current_character_id)

    def rename_character_group(self, group: str) -> None:
        if group == "未分组":
            QMessageBox.information(self, "默认分组", "“未分组”用于接收无阵营人物，不建议更名。")
            return
        characters = self.ensure_character_data()
        title, ok = QInputDialog.getText(self, "更改分组名称", "分组名称：", text=group)
        if not ok or not title.strip():
            return
        title = title.strip()
        characters["groups"] = [title if item == group else item for item in characters.get("groups", [])]
        for card in characters.get("cards", []):
            if card.get("faction") == group:
                card["faction"] = title
        DraftStore.save(self.selected_project, self.draft)
        self.refresh_character_group_options(title)
        self.populate_character_tree(self.current_character_id)
        if self.current_character_id:
            self.load_character(self.current_character_id)

    def delete_character_group(self, group: str) -> None:
        if group == "未分组":
            QMessageBox.information(self, "默认分组", "“未分组”不能删除。")
            return
        characters = self.ensure_character_data()
        answer = QMessageBox.question(
            self,
            "删除分组",
            f"确定删除分组“{group}”吗？\n\n分组下人物不会删除，会移动到“未分组”。",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No,
        )
        if answer != QMessageBox.Yes:
            return
        characters["groups"] = [item for item in characters.get("groups", []) if item != group]
        if "未分组" not in characters["groups"]:
            characters["groups"].append("未分组")
        for card in characters.get("cards", []):
            if card.get("faction") == group:
                card["faction"] = "未分组"
        DraftStore.save(self.selected_project, self.draft)
        self.refresh_character_group_options("未分组")
        self.populate_character_tree(self.current_character_id)
        if self.current_character_id:
            self.load_character(self.current_character_id)

    def populate_character_history(self, card: dict[str, Any]) -> None:
        self.character_history_list.clear()
        for item in card.get("history", []):
            row = QListWidgetItem(f"{item.get('time', '')}    {item.get('event', '')}")
            row.setData(Qt.UserRole, item.get("id"))
            self.character_history_list.addItem(row)

    def toggle_character_history(self) -> None:
        visible = not self.character_history_box.isVisible()
        self.character_history_box.setVisible(visible)
        self.character_history_toggle.setText("人物历程 v" if visible else "人物历程 >")

    def add_character_history(self) -> None:
        card = self.find_character(self.current_character_id)
        if not card:
            return
        time_text, ok = QInputDialog.getText(self, "新增历程", "时间点/章节：", text="T0")
        if not ok:
            return
        event_text, ok = QInputDialog.getText(self, "新增历程", "事件说明：", text="状态变化：")
        if not ok or not event_text.strip():
            return
        card.setdefault("history", []).append({"id": DraftStore.new_id("his"), "time": time_text.strip(), "event": event_text.strip()})
        DraftStore.save(self.selected_project, self.draft)
        self.populate_character_history(card)

    def delete_character_history(self) -> None:
        card = self.find_character(self.current_character_id)
        row = self.character_history_list.currentItem()
        if not card or not row:
            return
        history_id = row.data(Qt.UserRole)
        card["history"] = [item for item in card.get("history", []) if item.get("id") != history_id]
        DraftStore.save(self.selected_project, self.draft)
        self.populate_character_history(card)

    def populate_character_relations(self, card: dict[str, Any]) -> None:
        self.character_relation_list.clear()
        for item in card.get("relations", []):
            row = QListWidgetItem(self.character_relation_text(item))
            row.setData(Qt.UserRole, item.get("id"))
            self.character_relation_list.addItem(row)
        if not card.get("relations"):
            row = QListWidgetItem("暂无人物关系，点击“+ 关系”添加。")
            row.setFlags(row.flags() & ~Qt.ItemIsSelectable)
            self.character_relation_list.addItem(row)

    def character_relation_text(self, relation: dict[str, Any]) -> str:
        target = relation.get("target_name", "").strip()
        if relation.get("target_id"):
            target_card = self.find_character(relation.get("target_id"))
            if target_card:
                target = target_card.get("name", target) or target
        relation_type = relation.get("type", "关系").strip() or "关系"
        status = relation.get("status", "当前").strip() or "当前"
        note = relation.get("note", "").strip()
        return f"{target or '未命名'}    {relation_type} / {status}    {note}"

    def toggle_character_relations(self) -> None:
        visible = not self.character_relation_box.isVisible()
        self.character_relation_box.setVisible(visible)
        self.character_relation_toggle.setText("人物关系 v" if visible else "人物关系 >")

    def relation_target_options(self) -> list[tuple[str, str]]:
        current_id = self.current_character_id
        options: list[tuple[str, str]] = []
        for card in self.ensure_character_data().get("cards", []):
            if card.get("id") != current_id:
                options.append((card.get("name", "未命名"), card.get("id", "")))
        options.append(("手动输入...", ""))
        return options

    def prompt_character_relation(self, relation: dict[str, Any] | None = None) -> dict[str, Any] | None:
        relation = dict(relation or {})
        options = self.relation_target_options()
        labels = [name for name, _id in options]
        current_name = relation.get("target_name", "")
        if current_name and current_name not in labels:
            labels.insert(0, current_name)
        current_index = labels.index(current_name) if current_name in labels else 0
        target_name, ok = QInputDialog.getItem(self, "人物关系", "关联人物：", labels, current_index, True)
        if not ok or not target_name.strip():
            return None
        target_name = target_name.strip()
        target_id = ""
        for name, character_id in options:
            if name == target_name and character_id:
                target_id = character_id
                break
        manual_target = target_name == "手动输入..."
        if manual_target:
            target_name, ok = QInputDialog.getText(self, "人物关系", "关联人物名称：", text=relation.get("target_name", ""))
            if not ok or not target_name.strip():
                return None
            target_name = target_name.strip()

        type_options = ["合作", "朋友", "敌人", "亲属", "师徒", "上下级", "暧昧", "自定义"]
        relation_type, ok = QInputDialog.getItem(
            self,
            "人物关系",
            "关系类型：",
            type_options,
            type_options.index(relation.get("type")) if relation.get("type") in type_options else 0,
            True,
        )
        if not ok:
            return None
        status_options = ["当前", "曾经", "隐藏", "破裂", "未公开", "自定义"]
        status, ok = QInputDialog.getItem(
            self,
            "人物关系",
            "关系状态：",
            status_options,
            status_options.index(relation.get("status")) if relation.get("status") in status_options else 0,
            True,
        )
        if not ok:
            return None
        note, ok = QInputDialog.getText(self, "人物关系", "关系说明：", text=relation.get("note", ""))
        if not ok:
            return None
        return {
            "id": relation.get("id") or DraftStore.new_id("rel"),
            "target_id": "" if manual_target else target_id or relation.get("target_id", ""),
            "target_name": target_name,
            "type": relation_type.strip() or "关系",
            "status": status.strip() or "当前",
            "note": note.strip(),
        }

    def add_character_relation(self) -> None:
        card = self.find_character(self.current_character_id)
        if not card:
            return
        relation = self.prompt_character_relation()
        if not relation:
            return
        card.setdefault("relations", []).append(relation)
        DraftStore.save(self.selected_project, self.draft)
        self.populate_character_relations(card)
        self.update_character_status()

    def edit_character_relation(self) -> None:
        card = self.find_character(self.current_character_id)
        row = self.character_relation_list.currentItem()
        if not card or not row:
            return
        relation_id = row.data(Qt.UserRole)
        relation = next((item for item in card.get("relations", []) if item.get("id") == relation_id), None)
        if not relation:
            return
        updated = self.prompt_character_relation(relation)
        if not updated:
            return
        relation.update(updated)
        DraftStore.save(self.selected_project, self.draft)
        self.populate_character_relations(card)
        self.update_character_status()

    def delete_character_relation(self) -> None:
        card = self.find_character(self.current_character_id)
        row = self.character_relation_list.currentItem()
        if not card or not row:
            return
        relation_id = row.data(Qt.UserRole)
        relation = next((item for item in card.get("relations", []) if item.get("id") == relation_id), None)
        if not relation:
            return
        answer = QMessageBox.question(
            self,
            "删除关系",
            f"确定删除与“{relation.get('target_name', '未命名')}”的关系记录吗？",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No,
        )
        if answer != QMessageBox.Yes:
            return
        card["relations"] = [item for item in card.get("relations", []) if item.get("id") != relation_id]
        DraftStore.save(self.selected_project, self.draft)
        self.populate_character_relations(card)
        self.update_character_status()

    def sync_character_relation_target_name(self, character_id: str, name: str) -> None:
        if not character_id:
            return
        for card in self.ensure_character_data().get("cards", []):
            for relation in card.get("relations", []):
                if relation.get("target_id") == character_id:
                    relation["target_name"] = name

    def update_ability_tag_buttons(self, card: dict[str, Any]) -> None:
        while self.character_ability_links_layout.count():
            item = self.character_ability_links_layout.takeAt(0)
            widget = item.widget()
            if widget:
                widget.deleteLater()
        abilities = card.get("tags", {}).get("能力", [])
        links = card.get("ability_links", {})
        if not abilities:
            label = QLabel("暂无能力标签")
            label.setObjectName("Muted")
            self.character_ability_links_layout.addWidget(label)
        for ability in abilities:
            button = QPushButton(("↗ " if links.get(ability) else "+ ") + ability)
            button.setObjectName("TagLinkButton")
            button.clicked.connect(lambda checked=False, tag=ability: self.handle_character_ability_tag(tag))
            self.character_ability_links_layout.addWidget(button)
        self.character_ability_links_layout.addStretch(1)

    def handle_character_ability_tag(self, tag: str) -> None:
        card = self.find_character(self.current_character_id)
        if not card:
            return
        self.save_current_character(silent=True, refresh_ui=False)
        links = card.setdefault("ability_links", {})
        target_id = links.get(tag)
        if target_id and self.find_world_node(target_id):
            self.open_world_entry_from_character(target_id)
            return
        found = self.find_world_entry_by_title(tag)
        if found:
            links[tag] = found.get("id")
            DraftStore.save(self.selected_project, self.draft)
            self.open_world_entry_from_character(found.get("id"))
            return
        answer = QMessageBox.question(
            self,
            "新建能力词条",
            f"设定库中没有找到能力词条“{tag}”。是否在“能力设定”下新建同名词条并绑定？",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.Yes,
        )
        if answer != QMessageBox.Yes:
            return
        node = self.create_world_ability_entry(tag)
        links[tag] = node.get("id")
        DraftStore.save(self.selected_project, self.draft)
        self.open_world_entry_from_character(node.get("id"))

    def find_world_entry_by_title(self, title: str) -> dict[str, Any] | None:
        world = self.ensure_worldbuilding_data()
        for _, node in self.iter_world_nodes(world.get("modules", [])):
            if node.get("kind") == "entry" and node.get("title") == title:
                return node
        return None

    def create_world_ability_entry(self, title: str) -> dict[str, Any]:
        world = self.ensure_worldbuilding_data()
        module = next((item for item in world.get("modules", []) if item.get("title") == "能力设定"), None)
        if module is None:
            module = {"id": DraftStore.new_id("wb"), "title": "能力设定", "kind": "module", "default": True, "children": []}
            world.setdefault("modules", []).append(module)
        node = {
            "id": DraftStore.new_id("wb"),
            "title": title,
            "kind": "entry",
            "entry_type": "能力",
            "tags": ["人物卡生成"],
            "content": f"<p>由人物卡能力标签“{title}”创建，请补充能力规则、限制和代价。</p>",
            "updated_at": now_iso(),
            "children": [],
        }
        module.setdefault("children", []).append(node)
        return node

    def open_world_entry_from_character(self, node_id: str | None) -> None:
        if not node_id:
            return
        self.current_world_entry_id = node_id
        self.switch_page("worldbuilding")
        self.current_world_entry_id = node_id
        self.populate_world_tree(node_id)
        self.load_world_entry(node_id)

    def current_character_portrait_path(self, card: dict[str, Any] | None = None) -> Path | None:
        if not self.selected_project:
            return None
        if card is None:
            card = self.find_character(self.current_character_id)
        if not card:
            return None
        portrait_path = card.get("portrait_path", "")
        if not portrait_path:
            return None
        path = Path(portrait_path)
        if not path.is_absolute():
            path = Path(self.selected_project.path) / path
        return path

    def update_character_portrait_preview(self, card: dict[str, Any] | None = None) -> None:
        if not hasattr(self, "character_portrait_label"):
            return
        path = self.current_character_portrait_path(card)
        if path:
            pixmap = cached_pixmap(path, QSize(150, 150))
            if pixmap:
                self.character_portrait_label.setPixmap(pixmap)
                self.character_portrait_label.setText("")
                self.character_portrait_label.setToolTip("点击放大预览")
                return
        self.character_portrait_label.clear()
        self.character_portrait_label.setText("未添加画像\n点击放大预览")
        self.character_portrait_label.setToolTip("当前人物没有画像")

    def set_character_portrait(self, source: Path) -> None:
        if not self.selected_project or self.draft is None or not self.current_character_id:
            return
        if source.suffix.lower() not in IMAGE_EXTENSIONS:
            QMessageBox.warning(self, "格式不支持", "请选择 png、jpg、jpeg、webp 或 bmp 图片。")
            return
        card = self.find_character(self.current_character_id)
        if not card:
            return
        self.save_current_character(silent=True, refresh_ui=False)
        project_dir = Path(self.selected_project.path)
        if not project_dir.exists():
            QMessageBox.warning(self, "路径不存在", "项目路径不存在，无法保存图片。")
            return
        portrait_dir = project_dir / "assets" / "portraits"
        portrait_dir.mkdir(parents=True, exist_ok=True)
        target = portrait_dir / f"{self.current_character_id}{source.suffix.lower()}"
        try:
            if source.resolve() != target.resolve():
                shutil.copyfile(source, target)
            card["portrait_path"] = str(target.relative_to(project_dir))
            card["updated_at"] = now_iso()
            DraftStore.save(self.selected_project, self.draft)
        except OSError as exc:
            QMessageBox.critical(self, "图片保存失败", str(exc))
            return
        PIXMAP_CACHE.clear()
        self.update_character_portrait_preview(card)
        self.populate_character_tree(self.current_character_id)

    def choose_character_portrait(self) -> None:
        if not self.selected_project or self.draft is None or not self.current_character_id:
            QMessageBox.information(self, "未选择人物", "请先选择一个人物。")
            return
        project_dir = Path(self.selected_project.path)
        file_name, _ = QFileDialog.getOpenFileName(self, "选择人物画像", str(project_dir), "图片文件 (*.png *.jpg *.jpeg *.webp *.bmp)")
        if not file_name:
            return
        self.set_character_portrait(Path(file_name))

    def remove_character_portrait(self) -> None:
        card = self.find_character(self.current_character_id)
        if not self.selected_project or self.draft is None or not card:
            return
        path = self.current_character_portrait_path(card)
        card.pop("portrait_path", None)
        card["updated_at"] = now_iso()
        if path and path.exists():
            try:
                project_dir = Path(self.selected_project.path).resolve()
                image_resolved = path.resolve()
                if project_dir in image_resolved.parents and image_resolved.parent.name == "portraits":
                    path.unlink()
            except OSError:
                pass
        DraftStore.save(self.selected_project, self.draft)
        PIXMAP_CACHE.clear()
        self.update_character_portrait_preview(card)
        self.populate_character_tree(self.current_character_id)

    def preview_character_portrait(self) -> None:
        path = self.current_character_portrait_path()
        if not path or not path.exists():
            QMessageBox.information(self, "没有画像", "当前人物还没有添加画像。")
            return
        dialog = QDialog(self)
        dialog.setWindowTitle("人物画像预览")
        dialog.resize(640, 640)
        layout = QVBoxLayout(dialog)
        preview = QLabel()
        preview.setAlignment(Qt.AlignCenter)
        pixmap = QPixmap(str(path)).scaled(QSize(560, 520), Qt.KeepAspectRatio, Qt.SmoothTransformation)
        preview.setPixmap(pixmap)
        layout.addWidget(preview, 1)
        buttons = QDialogButtonBox(QDialogButtonBox.Close)
        buttons.rejected.connect(dialog.reject)
        layout.addWidget(buttons)
        dialog.exec()

    def character_recent_text(self, card: dict[str, Any]) -> str:
        if self.draft is None:
            return "最近登场：未打开项目"
        name = card.get("name", "")
        matched: list[str] = []
        temp = QTextEdit()
        for volume, chapter in DraftStore.iter_chapters(self.draft):
            temp.setHtml(chapter.get("content", ""))
            summary = chapter.get("summary", {})
            haystack = " ".join([temp.toPlainText(), " ".join(str(value) for value in summary.values())])
            if name and name in haystack:
                matched.append(f"{volume.get('title', '')} / {chapter.get('title', '')}")
        if not matched:
            return "最近登场：暂未在章节正文或总结中检索到"
        return f"最近登场：{matched[-1]} · 首次：{matched[0]}"

    def apply_character_ai_scope_settings(self) -> None:
        if not hasattr(self, "character_scope_checks"):
            return
        saved = self.app_settings.get("character_ai_scope", {})
        defaults = default_character_ai_scope()
        scope = {key: bool(saved.get(key, value)) if isinstance(saved, dict) else value for key, value in defaults.items()}
        for key, check in self.character_scope_checks.items():
            check.blockSignals(True)
            check.setChecked(scope.get(key, defaults.get(key, False)))
            check.blockSignals(False)

    def current_character_ai_scope(self) -> dict[str, bool]:
        defaults = default_character_ai_scope()
        if not hasattr(self, "character_scope_checks"):
            return defaults
        return {key: self.character_scope_checks.get(key).isChecked() if key in self.character_scope_checks else value for key, value in defaults.items()}

    def saved_character_ai_scope_preferences(self) -> dict[str, bool]:
        scope = self.current_character_ai_scope()
        for key in ("current_chapter_body", "selected_chapter_bodies", "all_chapter_bodies"):
            scope[key] = False
        return scope

    def on_character_ai_scope_changed(self) -> None:
        self.update_character_ai_scope_controls()
        self.app_settings["character_ai_scope"] = self.saved_character_ai_scope_preferences()
        try:
            save_app_settings(self.app_settings)
        except OSError:
            pass

    def update_character_selected_chapters_label(self) -> None:
        if not hasattr(self, "character_selected_chapters_label"):
            return
        count = len(self.character_selected_chapter_ids)
        self.character_selected_chapters_label.setText(f"已选 {count} 章" if count else "未选择章节")

    def update_character_ai_scope_controls(self) -> None:
        if not hasattr(self, "character_scope_checks"):
            return
        busy = bool((self.character_ai_thread and self.character_ai_thread.isRunning()) or self.character_ai_stop_btn.isEnabled())
        has_current_chapter = bool(self.draft and (self.draft.get("current_chapter_id") or self.current_chapter_id))
        for check in self.character_scope_checks.values():
            check.setEnabled(not busy)
        self.character_scope_checks["current_chapter_body"].setEnabled(has_current_chapter and not busy)
        selected_enabled = self.character_scope_checks["selected_chapter_bodies"].isChecked()
        self.character_select_chapters_btn.setEnabled(selected_enabled and not busy)
        if not has_current_chapter:
            self.character_scope_checks["current_chapter_body"].setChecked(False)
        self.update_character_selected_chapters_label()

    def toggle_character_ai_scope(self) -> None:
        visible = not self.character_scope_frame.isVisible()
        self.character_scope_frame.setVisible(visible)
        self.character_scope_toggle_btn.setText("读取范围 v" if visible else "读取范围 >")

    def choose_character_ai_chapters(self) -> None:
        self.save_current_character(silent=True, refresh_ui=False)
        if self.selected_project:
            self.draft = DraftStore.load(self.selected_project)
            self.ensure_character_data()
        selected_ids = self.choose_ai_chapters(self.character_selected_chapter_ids)
        if selected_ids is None:
            return
        self.character_selected_chapter_ids = selected_ids
        if self.character_selected_chapter_ids:
            self.character_scope_checks["selected_chapter_bodies"].setChecked(True)
        self.update_character_selected_chapters_label()

    def validate_character_ai_ready(self, settings: dict[str, Any]) -> tuple[bool, str]:
        if not self.selected_project or self.draft is None:
            return False, "请先打开一个小说项目。"
        if not self.current_character_id or not self.find_character(self.current_character_id):
            return False, "请先选择一个人物。"
        if not settings.get("ai_enabled", True):
            return False, "AI 辅助已关闭，请先到设置页启用。"
        if not str(settings.get("api_key", "")).strip():
            return False, "AI 接口未配置：缺少 API Key。"
        if not str(settings.get("base_url", "")).strip():
            return False, "AI 接口未配置：缺少 Base URL。"
        if not str(settings.get("model", "")).strip():
            return False, "AI 接口未配置：缺少模型名。"
        return True, ""

    def character_card_context_text(self, card: dict[str, Any]) -> str:
        tag_lines = []
        for tag_name, values in card.get("tags", {}).items():
            if values:
                tag_lines.append(f"{tag_name}：{'，'.join(values)}")
        history_lines = [f"{item.get('time', '')}：{item.get('event', '')}" for item in card.get("history", []) if item.get("time") or item.get("event")]
        return "\n".join(
            item
            for item in [
                f"姓名：{card.get('name', '未命名')}",
                f"性别：{card.get('gender', '')}",
                f"年龄：{card.get('age', '')}",
                f"身份：{card.get('identity', '')}",
                f"阵营：{card.get('faction', '')}",
                f"状态：{card.get('status', '')}",
                "标签：" + "；".join(tag_lines) if tag_lines else "",
                "人物历程：\n" + "\n".join(history_lines) if history_lines else "",
                "补充说明：\n" + self.short_plain_text(card.get("notes", ""), 700),
            ]
            if item.strip() and not item.endswith("：")
        )

    def character_relations_context_text(self, card: dict[str, Any]) -> str:
        lines = []
        for relation in card.get("relations", []):
            target = relation.get("target_name", "未命名")
            if relation.get("target_id"):
                target_card = self.find_character(relation.get("target_id"))
                if target_card:
                    target = target_card.get("name", target)
            lines.append(
                f"{card.get('name', '未命名')} -> {target}："
                f"{relation.get('type', '关系')} / {relation.get('status', '')} / {relation.get('note', '')}"
            )
        return "\n".join(lines)

    def build_character_ai_context(self) -> list[tuple[str, str]]:
        sections: list[tuple[str, str]] = []
        if self.draft is None:
            return sections
        scope = self.current_character_ai_scope()
        current_card = self.find_character(self.current_character_id)
        if current_card and scope.get("current_character"):
            self.append_context_section(sections, f"当前人物卡 - {current_card.get('name', '未命名')}", self.character_card_context_text(current_card))
        if current_card and scope.get("current_relations"):
            self.append_context_section(sections, f"当前人物关系 - {current_card.get('name', '未命名')}", self.character_relations_context_text(current_card))

        characters = self.draft.get("characters")
        if isinstance(characters, dict):
            if scope.get("all_characters"):
                card_lines = [self.character_card_context_text(card) for card in characters.get("cards", [])]
                self.append_context_section(sections, "全部人物卡", "\n\n".join(card_lines))
            if scope.get("all_relations"):
                relation_lines = [self.character_relations_context_text(card) for card in characters.get("cards", [])]
                self.append_context_section(sections, "全部人物关系记录", "\n".join(item for item in relation_lines if item.strip()))

        outline = self.draft.get("outline")
        if isinstance(outline, dict):
            if scope.get("outline"):
                for _parent, node in self.iter_outline_nodes(outline.get("nodes", [])):
                    node_text = "\n".join(
                        item
                        for item in [
                            f"类型：{node.get('kind', '节点')}",
                            f"目标：{node.get('goal', '')}",
                            f"时间线：{node.get('timeline_tag', '')}",
                            self.short_plain_text(node.get("content", ""), 600),
                        ]
                        if item.strip() and not item.endswith("：")
                    )
                    self.append_context_section(sections, f"大纲 - {node.get('title', '未命名')}", node_text)
            if scope.get("timeline"):
                timeline_lines = [
                    f"{point.get('time', '')} / {point.get('line', '')}：{point.get('event', '')}"
                    for point in outline.get("timeline_points", [])
                    if point.get("time") or point.get("event") or point.get("line")
                ]
                self.append_context_section(sections, "时间线", "\n".join(timeline_lines))

        if scope.get("summaries"):
            for volume, chapter in self.outline_chapter_items():
                summary = self.chapter_summary_text(chapter)
                if summary:
                    self.append_context_section(sections, f"章节总结 - {self.chapter_display_name(volume, chapter)}", summary)

        if scope.get("world"):
            world = self.draft.get("worldbuilding")
            world_lines: list[str] = []
            if isinstance(world, dict):
                for module in world.get("modules", []):
                    for _parent, node in self.iter_world_nodes([module]):
                        if node.get("kind") != "entry":
                            continue
                        if node.get("ai_read_allowed", node.get("allow_ai_read", node.get("ai_enabled", True))) is False:
                            continue
                        tags = "，".join(node.get("tags", []))
                        world_lines.append(
                            f"{node.get('title', '未命名词条')} [{node.get('entry_type', '设定')}] {tags}\n"
                            f"{self.short_plain_text(node.get('content', ''), 600)}"
                        )
            self.append_context_section(sections, "设定库", "\n\n".join(world_lines))

        seen_body_ids: set[str] = set()
        if scope.get("all_chapter_bodies"):
            for volume, chapter in self.outline_chapter_items():
                seen_body_ids.add(chapter.get("id", ""))
                self.append_context_section(sections, f"正文 - {self.chapter_display_name(volume, chapter)}", self.html_to_plain_text(chapter.get("content", "")))
        else:
            if scope.get("current_chapter_body"):
                current_id = self.draft.get("current_chapter_id") or self.current_chapter_id
                found = DraftStore.find_chapter(self.draft, current_id)
                if found:
                    volume, chapter = found
                    seen_body_ids.add(chapter.get("id", ""))
                    self.append_context_section(sections, f"当前章正文 - {self.chapter_display_name(volume, chapter)}", self.html_to_plain_text(chapter.get("content", "")))
            if scope.get("selected_chapter_bodies"):
                for volume, chapter in self.outline_chapter_items():
                    chapter_id = chapter.get("id")
                    if chapter_id in self.character_selected_chapter_ids and chapter_id not in seen_body_ids:
                        seen_body_ids.add(chapter_id)
                        self.append_context_section(sections, f"指定章正文 - {self.chapter_display_name(volume, chapter)}", self.html_to_plain_text(chapter.get("content", "")))
        return sections

    def character_ai_context_preview(self, sections: list[tuple[str, str]]) -> str:
        preview = self.ai_context_preview(sections)
        total_chars = sum(len(body) for _title, body in sections)
        return f"{preview}\n\n预计读取：{len(sections)} 项，约 {total_chars} 字符。"

    def confirm_character_ai_call(self, title: str, sections: list[tuple[str, str]], settings: dict[str, Any]) -> bool:
        scope = self.current_character_ai_scope()
        if scope.get("selected_chapter_bodies") and not self.character_selected_chapter_ids:
            QMessageBox.information(self, "未选择章节", "已勾选“指定章节正文”，请先选择至少一个章节。")
            return False
        if settings.get("ai_confirm_each_call", True):
            answer = QMessageBox.question(
                self,
                title,
                "本次 AI 将读取以下范围：\n\n"
                f"{self.character_ai_context_preview(sections)}\n\n"
                "AI 只会返回建议，不会自动覆盖正文、设定、人物卡或大纲。是否继续？",
                QMessageBox.Yes | QMessageBox.No,
                QMessageBox.No,
            )
            if answer != QMessageBox.Yes:
                return False
        if scope.get("all_chapter_bodies"):
            answer = QMessageBox.question(
                self,
                "确认读取全书正文",
                "你勾选了“全书正文”。这可能增加接口成本、等待时间和隐私暴露范围。确定继续吗？",
                QMessageBox.Yes | QMessageBox.No,
                QMessageBox.No,
            )
            if answer != QMessageBox.Yes:
                return False
        return True

    def character_ai_system_prompt(self) -> str:
        settings = self.ai_settings_for_request()
        return (
            f"{self.ai_role_instruction(settings)}\n\n"
            "你是本地小说创作软件中的 AI 人物建议助手。你只能基于本次提供的上下文回答，"
            "重点帮助作者检查人物性格一致性、动机、关系变化、能力限制、出场信息和剧情风险。"
            "不要声称已经修改正文、设定、人物卡或大纲；如需要修改，只输出候选文本和理由，等待用户确认。"
        )

    def set_character_ai_streaming(self, active: bool) -> None:
        self.character_ai_send_btn.setEnabled(not active)
        self.character_ai_suggest_btn.setEnabled(not active)
        self.character_ai_stop_btn.setEnabled(active)
        self.character_ai_clear_btn.setEnabled(not active)
        self.character_ai_input.setEnabled(not active)
        self.update_character_ai_scope_controls()

    def append_character_ai_text(self, text: str) -> None:
        cursor = self.character_ai_box.textCursor()
        cursor.movePosition(QTextCursor.End)
        cursor.insertText(text)
        self.character_ai_box.setTextCursor(cursor)
        self.character_ai_box.ensureCursorVisible()

    def start_character_ai_stream(self, settings: dict[str, Any], messages: list[dict[str, str]], max_tokens: int = 1000) -> None:
        self.character_ai_stream_text = ""
        self.character_ai_thread = AIStreamThread(settings, messages, max_tokens=max_tokens)
        self.character_ai_thread.chunk_received.connect(self.on_character_ai_stream_chunk)
        self.character_ai_thread.result_ready.connect(self.on_character_ai_stream_finished)
        self.character_ai_thread.start()

    def on_character_ai_stream_chunk(self, text: str) -> None:
        self.character_ai_stream_text += text
        self.append_character_ai_text(text)

    def on_character_ai_stream_finished(self, ok: bool, message: str, stopped: bool) -> None:
        if message and (stopped or not ok or not self.character_ai_stream_text.strip()):
            self.append_character_ai_text(message)
        self.append_character_ai_text("\n")
        self.set_character_ai_streaming(False)
        if self.draft is not None:
            self.ensure_character_data()["ai_note"] = self.character_ai_box.toPlainText()
            DraftStore.save(self.selected_project, self.draft)
        if self.character_ai_thread:
            self.character_ai_thread.wait(1000)
            self.character_ai_thread = None

    def stop_character_ai_stream(self) -> None:
        if self.character_ai_thread and self.character_ai_thread.isRunning():
            self.character_ai_thread.request_stop()
            self.character_ai_stop_btn.setEnabled(False)

    def run_character_ai_task(self, visible_question: str, prompt: str, max_tokens: int = 1000) -> None:
        if self.character_ai_thread and self.character_ai_thread.isRunning():
            return
        self.save_current_character(silent=True)
        settings = self.ai_settings_for_request()
        role_name = self.ai_role_name(settings)
        current_log = self.character_ai_box.toPlainText().strip()
        if current_log:
            current_log += "\n\n"
        current_log += f"你：{visible_question}"
        ready, message = self.validate_character_ai_ready(settings)
        if not ready:
            current_log += f"\n\n{role_name}：{message}"
            self.character_ai_box.setPlainText(current_log)
            self.character_ai_box.moveCursor(QTextCursor.End)
            self.character_ai_input.clear()
            return
        sections = self.limited_ai_context(self.build_character_ai_context(), settings)
        if not self.confirm_character_ai_call("发送给 AI 人物建议", sections, settings):
            return
        messages = [
            {"role": "system", "content": self.character_ai_system_prompt()},
            {
                "role": "user",
                "content": (
                    "下面是本次允许读取的项目上下文。请严格基于这些内容回答。\n\n"
                    f"{self.ai_context_text(sections)}\n\n"
                    f"用户请求：{prompt}"
                ),
            },
        ]
        current_log += f"\n\n{role_name}："
        self.character_ai_box.setPlainText(current_log)
        self.character_ai_box.moveCursor(QTextCursor.End)
        self.character_ai_input.clear()
        self.set_character_ai_streaming(True)
        self.start_character_ai_stream(settings, messages, max_tokens=max_tokens)

    def send_character_ai_message(self) -> None:
        question = self.character_ai_input.toPlainText().strip()
        if not question:
            return
        self.run_character_ai_task(question, question, max_tokens=1000)

    def generate_character_ai_suggestions(self) -> None:
        self.run_character_ai_task(
            "生成建议",
            "请基于当前人物卡和已授权资料，生成人物建议。请重点检查性格一致性、能力限制、人物动机、剧情风险、人物关系变化和出场信息，并输出可采纳的候选修改建议。",
            max_tokens=1200,
        )

    def clear_character_ai_chat(self) -> None:
        if self.character_ai_thread and self.character_ai_thread.isRunning():
            self.character_ai_thread.request_stop()
        text = "当前对话已清除。\n\nAI 人物建议会根据当前人物卡、人物关系记录、设定库和章节总结给出建议。"
        self.character_ai_box.setPlainText(text)
        if self.draft is not None:
            self.ensure_character_data()["ai_note"] = text
            DraftStore.save(self.selected_project, self.draft)

    def change_character_font(self, font: QFont) -> None:
        if self.current_page != "character":
            return
        char_format = QTextCharFormat()
        char_format.setFontFamily(font.family())
        cursor = self.character_notes_editor.textCursor()
        if cursor.hasSelection():
            cursor.mergeCharFormat(char_format)
        else:
            self.character_notes_editor.mergeCurrentCharFormat(char_format)

    def change_character_font_size(self, value: str) -> None:
        if self.current_page != "character":
            return
        try:
            size = int(value.replace("pt", "").strip())
        except ValueError:
            return
        char_format = QTextCharFormat()
        char_format.setFontPointSize(size)
        cursor = self.character_notes_editor.textCursor()
        if cursor.hasSelection():
            cursor.mergeCharFormat(char_format)
        else:
            self.character_notes_editor.mergeCurrentCharFormat(char_format)

    def worldbuilding_defaults(self) -> dict[str, Any]:
        def entry(title: str, entry_type: str, tags: list[str], content: str) -> dict[str, Any]:
            return {
                "id": DraftStore.new_id("wb"),
                "title": title,
                "kind": "entry",
                "entry_type": entry_type,
                "tags": tags,
                "content": content,
                "updated_at": now_iso(),
                "children": [],
            }

        geography_entry = entry(
            "黑石码头",
            "地点",
            ["雾港", "港口", "巡逻队辖区"],
            "<h2>概述</h2><p>黑石码头位于雾港东侧，是旧巡逻队控制的货运区。码头常年潮湿，夜间能听到海底铁链声。</p>"
            "<h2>细节</h2><p>归属：雾港巡逻队名义管理，实际受旧港商会影响。</p>",
        )
        modules = [
            {
                "id": DraftStore.new_id("wb"),
                "title": "世界观",
                "kind": "module",
                "default": True,
                "children": [
                    entry("历史纪年", "世界观", ["历史", "时间"], "<p>记录世界历史、时代分期和关键年份。</p>"),
                    entry("文明规则", "世界观", ["社会", "规则"], "<p>记录文明结构、社会常识和默认规则。</p>"),
                ],
            },
            {
                "id": DraftStore.new_id("wb"),
                "title": "世界地理",
                "kind": "module",
                "default": True,
                "children": [
                    geography_entry,
                    entry("旧灯塔", "地点", ["雾港", "灯塔"], "<p>旧灯塔位于雾港外侧，是早期线索地点。</p>"),
                ],
            },
            {
                "id": DraftStore.new_id("wb"),
                "title": "组织势力",
                "kind": "module",
                "default": True,
                "children": [entry("巡逻队", "组织", ["雾港", "治安"], "<p>雾港巡逻队负责名义治安。</p>")],
            },
            {
                "id": DraftStore.new_id("wb"),
                "title": "能力设定",
                "kind": "module",
                "default": True,
                "children": [entry("潮汐术", "能力", ["能力体系"], "<p>潮汐术会改变水流，也会留下黑色盐晶。</p>")],
            },
            {
                "id": DraftStore.new_id("wb"),
                "title": "道具物品",
                "kind": "module",
                "default": True,
                "children": [entry("黑盐晶", "物品", ["证物", "潮汐术"], "<p>黑盐晶是潮汐术使用后的残留物。</p>")],
            },
        ]
        return {"current_entry_id": geography_entry["id"], "modules": modules, "ai_note": ""}

    def ensure_worldbuilding_data(self) -> dict[str, Any]:
        if self.draft is None:
            raise RuntimeError("draft is not loaded")
        world = self.draft.setdefault("worldbuilding", self.worldbuilding_defaults())
        if not world.get("modules"):
            self.draft["worldbuilding"] = self.worldbuilding_defaults()
            world = self.draft["worldbuilding"]
        world.setdefault("ai_note", "")
        self.normalize_worldbuilding_modules(world)
        return world

    def normalize_worldbuilding_modules(self, world: dict[str, Any]) -> None:
        modules = world.get("modules", [])
        default_module_titles = {"世界观", "世界地理", "组织势力", "能力设定", "道具物品"}
        default_entry_parents = {
            "历史纪年": ("世界观", "世界观"),
            "文明规则": ("世界观", "世界观"),
            "黑石码头": ("世界地理", "地点"),
            "旧灯塔": ("世界地理", "地点"),
            "巡逻队": ("组织势力", "组织"),
            "潮汐术": ("能力设定", "能力"),
            "黑盐晶": ("道具物品", "物品"),
        }
        default_type_by_parent = {
            "世界观": "世界观",
            "世界地理": "地点",
            "组织势力": "组织",
            "能力设定": "能力",
            "道具物品": "物品",
        }

        def normalize_children(nodes: list[dict[str, Any]], is_top_level: bool) -> None:
            for node in nodes:
                if is_top_level and node.get("kind") == "submenu":
                    node["kind"] = "module"
                    node.setdefault("default", False)
                elif not is_top_level and node.get("kind") in {"module", "submenu"}:
                    node["kind"] = "entry"
                    if node.get("entry_type") in {"", "module", "submenu", None}:
                        node["entry_type"] = "设定"
                    node.pop("default", None)
                node.setdefault("children", [])
                normalize_children(node.get("children", []), False)

        normalize_children(modules, True)
        modules_by_title = {module.get("title"): module for module in modules if module.get("kind") == "module"}
        normalized: list[dict[str, Any]] = []
        moved_default_ids: set[str] = set()

        def infer_legacy_parent(node: dict[str, Any]) -> tuple[str | None, str | None]:
            direct_parent, direct_type = default_entry_parents.get(node.get("title"), (None, None))
            if direct_parent:
                return direct_parent, direct_type
            if node.get("default") or node.get("title") in default_module_titles:
                return None, None
            if node.get("entry_type") != "submenu":
                return None, None
            parent_votes: dict[str, int] = {}
            type_votes: dict[str, int] = {}
            for _, child in self.iter_world_nodes(node.get("children", [])):
                child_parent, child_type = default_entry_parents.get(child.get("title"), (None, None))
                if child_parent:
                    parent_votes[child_parent] = parent_votes.get(child_parent, 0) + 1
                if child_type:
                    type_votes[child_type] = type_votes.get(child_type, 0) + 1
            if not parent_votes:
                return None, None
            parent_title = max(parent_votes, key=parent_votes.get)
            entry_type = max(type_votes, key=type_votes.get) if type_votes else default_type_by_parent.get(parent_title, "设定")
            return parent_title, entry_type

        for module in modules:
            title = module.get("title")
            parent_title, entry_type = infer_legacy_parent(module)
            target_parent = modules_by_title.get(parent_title) if parent_title else None
            if target_parent and target_parent is not module:
                module["kind"] = "entry"
                module["entry_type"] = entry_type or default_type_by_parent.get(parent_title, "设定")
                module.pop("default", None)
                target_parent.setdefault("children", [])
                if not any(child.get("id") == module.get("id") for child in target_parent["children"]):
                    target_parent["children"].append(module)
                moved_default_ids.add(module.get("id", ""))
            else:
                normalized.append(module)

        world["modules"] = [module for module in normalized if module.get("id") not in moved_default_ids]

    def iter_world_nodes(self, nodes: list[dict[str, Any]], parent: dict[str, Any] | None = None):
        for node in nodes:
            yield parent, node
            yield from self.iter_world_nodes(node.get("children", []), node)

    def find_world_node(self, node_id: str | None) -> tuple[dict[str, Any] | None, dict[str, Any]] | None:
        if self.draft is None or not node_id:
            return None
        world = self.ensure_worldbuilding_data()
        for parent, node in self.iter_world_nodes(world.get("modules", [])):
            if node.get("id") == node_id:
                return parent, node
        return None

    def first_world_entry(self) -> dict[str, Any] | None:
        if self.draft is None:
            return None
        for _, node in self.iter_world_nodes(self.ensure_worldbuilding_data().get("modules", [])):
            if node.get("kind") == "entry":
                return node
        return None

    def load_worldbuilding_project(self) -> None:
        if not self.selected_project:
            return
        self.draft = DraftStore.load(self.selected_project)
        world = self.ensure_worldbuilding_data()
        self.current_world_entry_id = world.get("current_entry_id")
        if not self.find_world_node(self.current_world_entry_id):
            first = self.first_world_entry()
            self.current_world_entry_id = first.get("id") if first else None
        self.populate_world_tree(self.current_world_entry_id)
        if self.current_world_entry_id:
            self.load_world_entry(self.current_world_entry_id)
        self.search_world_entries()
        self.update_world_status()

    def populate_world_tree(self, selected_id: str | None = None) -> None:
        if self.draft is None:
            return
        self.world_tree.blockSignals(True)
        self.world_tree.clear()
        selected_item: QTreeWidgetItem | None = None

        def add_items(parent_item: QTreeWidgetItem | None, nodes: list[dict[str, Any]]) -> None:
            nonlocal selected_item
            for node in nodes:
                item = QTreeWidgetItem([node.get("title", "未命名")])
                item.setIcon(0, self.status_icon("完稿" if node.get("kind") == "module" else "草稿"))
                item.setData(0, Qt.UserRole, node.get("id"))
                item.setToolTip(0, node.get("kind", "entry"))
                if parent_item is None:
                    self.world_tree.addTopLevelItem(item)
                else:
                    parent_item.addChild(item)
                if node.get("id") == selected_id:
                    selected_item = item
                add_items(item, node.get("children", []))
                item.setExpanded(True)

        add_items(None, self.ensure_worldbuilding_data().get("modules", []))
        if selected_item:
            self.world_tree.setCurrentItem(selected_item)
        self.world_tree.blockSignals(False)

    def load_world_entry(self, node_id: str) -> None:
        found = self.find_world_node(node_id)
        if not found:
            return
        _, node = found
        self.loading_worldbuilding = True
        self.current_world_entry_id = node_id
        self.ensure_worldbuilding_data()["current_entry_id"] = node_id
        self.world_entry_title_label.setText("词条卡编辑" if node.get("kind") == "entry" else "目录说明")
        self.world_entry_meta_label.setText(self.world_node_path(node_id))
        self.world_entry_name_edit.setText(node.get("title", ""))
        self.world_entry_type_edit.setText(node.get("entry_type", node.get("kind", "")))
        self.world_entry_tags_edit.setText("，".join(node.get("tags", [])))
        self.world_entry_editor.setHtml(node.get("content", ""))
        self.update_world_image_preview(node)
        self.world_reference_box.setPlainText(self.world_reference_text(node))
        self.loading_worldbuilding = False
        self.update_world_status()

    def save_current_world_entry(self, silent: bool = False, refresh_ui: bool = True) -> None:
        if not self.selected_project or self.draft is None or not self.current_world_entry_id:
            return
        found = self.find_world_node(self.current_world_entry_id)
        if not found:
            return
        _, node = found
        title = self.world_entry_name_edit.text().strip() or node.get("title", "未命名")
        node["title"] = title
        node["entry_type"] = self.world_entry_type_edit.text().strip()
        node["tags"] = [item.strip() for item in self.world_entry_tags_edit.text().replace("，", ",").split(",") if item.strip()]
        node["content"] = self.world_entry_editor.toHtml()
        node["updated_at"] = now_iso()
        self.ensure_worldbuilding_data()["current_entry_id"] = self.current_world_entry_id
        DraftStore.save(self.selected_project, self.draft)
        if refresh_ui:
            self.populate_world_tree(self.current_world_entry_id)
            self.search_world_entries()
        self.update_world_status()
        if not silent:
            QMessageBox.information(self, "已保存", "当前设定词条已保存。")

    def current_world_image_path(self, node: dict[str, Any] | None = None) -> Path | None:
        if not self.selected_project:
            return None
        if node is None:
            found = self.find_world_node(self.current_world_entry_id)
            node = found[1] if found else None
        if not node:
            return None
        image_path = node.get("image_path", "")
        if not image_path:
            return None
        path = Path(image_path)
        if not path.is_absolute():
            path = Path(self.selected_project.path) / path
        return path

    def update_world_image_preview(self, node: dict[str, Any] | None = None) -> None:
        if not hasattr(self, "world_image_label"):
            return
        image_path = self.current_world_image_path(node)
        if image_path:
            pixmap = cached_pixmap(image_path, QSize(150, 108))
            if pixmap:
                self.world_image_label.setPixmap(pixmap)
                self.world_image_label.setText("")
                self.world_image_label.setToolTip("点击放大预览")
                return
        self.world_image_label.clear()
        self.world_image_label.setText("未添加图片\n点击放大预览")
        self.world_image_label.setToolTip("当前词条没有图片")

    def set_world_entry_image(self, source: Path) -> None:
        if not self.selected_project or self.draft is None or not self.current_world_entry_id:
            return
        if source.suffix.lower() not in IMAGE_EXTENSIONS:
            QMessageBox.warning(self, "格式不支持", "请选择 png、jpg、jpeg、webp 或 bmp 图片。")
            return
        found = self.find_world_node(self.current_world_entry_id)
        if not found:
            return
        self.save_current_world_entry(silent=True, refresh_ui=False)
        _, node = found
        project_dir = Path(self.selected_project.path)
        if not project_dir.exists():
            QMessageBox.warning(self, "路径不存在", "项目路径不存在，无法保存图片。")
            return
        image_dir = project_dir / "assets" / "worldbuilding"
        image_dir.mkdir(parents=True, exist_ok=True)
        target = image_dir / f"{self.current_world_entry_id}{source.suffix.lower()}"
        try:
            if source.resolve() != target.resolve():
                shutil.copyfile(source, target)
            node["image_path"] = str(target.relative_to(project_dir))
            node["updated_at"] = now_iso()
            DraftStore.save(self.selected_project, self.draft)
        except OSError as exc:
            QMessageBox.critical(self, "图片保存失败", str(exc))
            return
        PIXMAP_CACHE.clear()
        self.update_world_image_preview(node)
        self.search_world_entries()
        self.update_world_status()

    def choose_world_entry_image(self) -> None:
        if not self.selected_project or self.draft is None or not self.current_world_entry_id:
            QMessageBox.information(self, "未选择词条", "请先选择一个设定词条。")
            return
        project_dir = Path(self.selected_project.path)
        file_name, _ = QFileDialog.getOpenFileName(
            self,
            "选择词条图片",
            str(project_dir),
            "图片文件 (*.png *.jpg *.jpeg *.webp *.bmp)",
        )
        if not file_name:
            return
        self.set_world_entry_image(Path(file_name))

    def remove_world_entry_image(self) -> None:
        if not self.selected_project or self.draft is None or not self.current_world_entry_id:
            return
        found = self.find_world_node(self.current_world_entry_id)
        if not found:
            return
        _, node = found
        image_path = self.current_world_image_path(node)
        node.pop("image_path", None)
        node["updated_at"] = now_iso()
        if image_path and image_path.exists():
            try:
                project_dir = Path(self.selected_project.path).resolve()
                image_resolved = image_path.resolve()
                if project_dir in image_resolved.parents and image_resolved.parent.name == "worldbuilding":
                    image_path.unlink()
            except OSError:
                pass
        DraftStore.save(self.selected_project, self.draft)
        PIXMAP_CACHE.clear()
        self.update_world_image_preview(node)
        self.update_world_status()

    def preview_world_entry_image(self) -> None:
        image_path = self.current_world_image_path()
        if not image_path or not image_path.exists():
            QMessageBox.information(self, "没有图片", "当前词条还没有添加图片。")
            return
        dialog = QDialog(self)
        dialog.setWindowTitle("词条图片预览")
        dialog.resize(720, 520)
        layout = QVBoxLayout(dialog)
        preview = QLabel()
        preview.setAlignment(Qt.AlignCenter)
        pixmap = QPixmap(str(image_path)).scaled(QSize(680, 440), Qt.KeepAspectRatio, Qt.SmoothTransformation)
        preview.setPixmap(pixmap)
        layout.addWidget(preview, 1)
        buttons = QDialogButtonBox(QDialogButtonBox.Close)
        buttons.rejected.connect(dialog.reject)
        layout.addWidget(buttons)
        dialog.exec()

    def on_world_text_changed(self) -> None:
        if self.loading_worldbuilding:
            return
        self.update_world_status(dirty=True)

    def update_world_status(self, dirty: bool = False) -> None:
        project = self.selected_project
        title = "未选择词条"
        found = self.find_world_node(self.current_world_entry_id)
        if found:
            title = found[1].get("title", title)
        suffix = "有未保存修改" if dirty else "自动保存覆盖设定库内容"
        self.world_status_label.setText(f"{project.name if project else '未打开项目'} · 当前：{title} · {suffix}")

    def world_node_path(self, node_id: str | None) -> str:
        if self.draft is None or not node_id:
            return ""
        path: list[str] = []

        def walk(nodes: list[dict[str, Any]], trail: list[str]) -> bool:
            for node in nodes:
                next_trail = trail + [node.get("title", "未命名")]
                if node.get("id") == node_id:
                    path.extend(next_trail)
                    return True
                if walk(node.get("children", []), next_trail):
                    return True
            return False

        walk(self.ensure_worldbuilding_data().get("modules", []), [])
        return " / ".join(path)

    def world_reference_text(self, node: dict[str, Any]) -> str:
        title = node.get("title", "当前词条")
        return f"正文：尚未接入真实引用统计\n人物卡：可作为标签引用“{title}”\n大纲：可在剧情节点中引用“{title}”"

    def on_world_node_selected(self) -> None:
        if self.loading_worldbuilding:
            return
        item = self.world_tree.currentItem()
        if not item:
            return
        node_id = item.data(0, Qt.UserRole)
        if not node_id:
            return
        if self.current_world_entry_id and node_id != self.current_world_entry_id:
            self.save_current_world_entry(silent=True, refresh_ui=False)
        self.load_world_entry(node_id)

    def selected_world_node(self) -> tuple[dict[str, Any] | None, dict[str, Any]] | None:
        item = self.world_tree.currentItem()
        if item:
            return self.find_world_node(item.data(0, Qt.UserRole))
        return self.find_world_node(self.current_world_entry_id)

    def world_node_chain(self, node_id: str | None) -> list[dict[str, Any]]:
        if self.draft is None or not node_id:
            return []

        def walk(nodes: list[dict[str, Any]], trail: list[dict[str, Any]]) -> list[dict[str, Any]]:
            for node in nodes:
                next_trail = trail + [node]
                if node.get("id") == node_id:
                    return next_trail
                found = walk(node.get("children", []), next_trail)
                if found:
                    return found
            return []

        return walk(self.ensure_worldbuilding_data().get("modules", []), [])

    def selected_world_module_parent(self) -> dict[str, Any] | None:
        selected = self.selected_world_node()
        if not selected:
            return None
        _, node = selected
        chain = self.world_node_chain(node.get("id"))
        for item in chain:
            if item.get("kind") == "module":
                return item
        return None

    def selected_world_submodule_parent(self) -> dict[str, Any] | None:
        selected = self.selected_world_node()
        if not selected:
            return None
        parent, node = selected
        if node.get("kind") == "submenu":
            return node
        if node.get("kind") == "entry" and parent and parent.get("kind") == "submenu":
            return parent
        return None

    def selected_world_entry_parent(self) -> dict[str, Any] | None:
        selected = self.selected_world_node()
        if not selected:
            return None
        _, node = selected
        if node.get("kind") in {"module", "entry"}:
            return node
        return None

    def add_world_node(self, kind: str) -> None:
        if self.draft is None:
            self.load_worldbuilding_project()
        if self.draft is None:
            return
        self.save_current_world_entry(silent=True)
        parent = None if kind == "submenu" else self.selected_world_entry_parent()
        if kind == "entry" and parent is None:
            QMessageBox.information(self, "请选择模块或词条", "请先选择一个设定模块或已有词条，再新增词条。")
            return
        kind_label = "子模块" if kind == "submenu" else "词条"
        title, ok = QInputDialog.getText(self, f"新增{kind_label}", f"{kind_label}名称：", text=f"新{kind_label}")
        if not ok:
            return
        node_kind = "module" if kind == "submenu" else "entry"
        node = {
            "id": DraftStore.new_id("wb"),
            "title": title.strip() or f"新{kind_label}",
            "kind": node_kind,
            "entry_type": "" if node_kind == "module" else "设定",
            "tags": [],
            "content": "",
            "updated_at": now_iso(),
            "children": [],
        }
        if node_kind == "module":
            node["default"] = False
            self.ensure_worldbuilding_data().setdefault("modules", []).append(node)
        else:
            parent.setdefault("children", []).append(node)
        self.current_world_entry_id = node["id"]
        DraftStore.save(self.selected_project, self.draft)
        self.populate_world_tree(node["id"])
        self.load_world_entry(node["id"])

    def show_world_node_menu(self, pos: QPoint) -> None:
        if self.draft is None:
            return
        item = self.world_tree.itemAt(pos)
        menu = QMenu(self.world_tree)
        if item:
            self.world_tree.setCurrentItem(item)
            node_id = item.data(0, Qt.UserRole)
            found = self.find_world_node(node_id)
            node = found[1] if found else {}
            menu.addAction("新增词库模块", lambda: self.add_world_node("submenu"))
            if node.get("kind") == "module":
                menu.addAction("新增词条", lambda: self.add_world_node("entry"))
            elif node.get("kind") == "entry":
                menu.addAction("新增子词条", lambda: self.add_world_node("entry"))
            menu.addAction("更改名称", lambda: self.rename_world_node(node_id))
            menu.addSeparator()
            menu.addAction("删除", lambda: self.delete_world_node(node_id))
        else:
            menu.addAction("新增词库模块", lambda: self.add_world_node("submenu"))
        menu.exec(self.world_tree.viewport().mapToGlobal(pos))

    def rename_world_node(self, node_id: str) -> None:
        found = self.find_world_node(node_id)
        if not found:
            return
        _, node = found
        title, ok = QInputDialog.getText(self, "更改名称", "名称：", text=node.get("title", "未命名"))
        if not ok or not title.strip():
            return
        node["title"] = title.strip()
        DraftStore.save(self.selected_project, self.draft)
        self.populate_world_tree(node_id)
        self.load_world_entry(node_id)

    def delete_world_node(self, node_id: str) -> None:
        found = self.find_world_node(node_id)
        if not found or self.draft is None:
            return
        parent, node = found
        if node.get("default") and node.get("kind") == "module":
            QMessageBox.information(self, "默认模块", "默认五大模块第一版不支持删除，可在后续管理入口中隐藏或重命名。")
            return
        answer = QMessageBox.question(self, "删除设定", f"确定删除“{node.get('title', '未命名')}”及其子项吗？", QMessageBox.Yes | QMessageBox.No, QMessageBox.No)
        if answer != QMessageBox.Yes:
            return
        self.draft.setdefault("deleted_items", []).append({"type": "worldbuilding", "deleted_at": now_iso(), "data": node})
        if parent is not None:
            parent["children"] = [item for item in parent.get("children", []) if item.get("id") != node_id]
        else:
            world = self.ensure_worldbuilding_data()
            world["modules"] = [item for item in world.get("modules", []) if item.get("id") != node_id]
        DraftStore.save(self.selected_project, self.draft)
        first = self.first_world_entry()
        self.current_world_entry_id = first.get("id") if first else None
        self.populate_world_tree(self.current_world_entry_id)
        if self.current_world_entry_id:
            self.load_world_entry(self.current_world_entry_id)

    def show_world_module_manage_info(self) -> None:
        QMessageBox.information(self, "模块管理", "第一版默认五模块固定显示。后续可在这里加入隐藏、重命名和恢复默认模块。")

    def search_world_entries(self) -> None:
        if self.draft is None:
            return
        keyword = self.world_search_edit.text().strip() if hasattr(self, "world_search_edit") else ""
        self.world_search_results.clear()
        world = self.ensure_worldbuilding_data()
        temp = QTextEdit()
        for _, node in self.iter_world_nodes(world.get("modules", [])):
            if node.get("kind") != "entry":
                continue
            temp.setHtml(node.get("content", ""))
            haystack = " ".join([node.get("title", ""), node.get("entry_type", ""), " ".join(node.get("tags", [])), temp.toPlainText()])
            if keyword and keyword not in haystack:
                continue
            item = QListWidgetItem(f"{node.get('title', '未命名')}\n{self.world_node_path(node.get('id'))}")
            item.setData(Qt.UserRole, node.get("id"))
            item.setSizeHint(QSize(260, 58))
            self.world_search_results.addItem(item)

    def open_world_search_result(self, item: QListWidgetItem) -> None:
        node_id = item.data(Qt.UserRole)
        if not node_id:
            return
        self.save_current_world_entry(silent=True)
        self.current_world_entry_id = node_id
        self.populate_world_tree(node_id)
        self.load_world_entry(node_id)

    def check_worldbuilding_with_ai(self) -> None:
        self.world_ai_box.setPlainText(
            "AI：接口配置完成后，会读取全部设定词条、人物卡和章节总结，检查命名冲突、规则矛盾和设定前后不一致。"
        )

    def change_world_font(self, font: QFont) -> None:
        if self.current_page != "worldbuilding":
            return
        char_format = QTextCharFormat()
        char_format.setFontFamily(font.family())
        cursor = self.world_entry_editor.textCursor()
        if cursor.hasSelection():
            cursor.mergeCharFormat(char_format)
        else:
            self.world_entry_editor.mergeCurrentCharFormat(char_format)

    def change_world_font_size(self, value: str) -> None:
        if self.current_page != "worldbuilding":
            return
        try:
            size = int(value.replace("pt", "").strip())
        except ValueError:
            return
        char_format = QTextCharFormat()
        char_format.setFontPointSize(size)
        cursor = self.world_entry_editor.textCursor()
        if cursor.hasSelection():
            cursor.mergeCharFormat(char_format)
        else:
            self.world_entry_editor.mergeCurrentCharFormat(char_format)

    def worldbuilding_to_markdown(self) -> str:
        if self.draft is None:
            return ""
        temp = QTextEdit()
        lines = [f"# {self.selected_project.name if self.selected_project else '设定库'}", ""]

        def append_node(node: dict[str, Any], level: int) -> None:
            heading = "#" * min(level + 1, 6)
            lines.append(f"{heading} {node.get('title', '未命名')}")
            if node.get("kind") == "entry":
                if node.get("entry_type"):
                    lines.append(f"- 类型：{node.get('entry_type')}")
                if node.get("tags"):
                    lines.append(f"- 标签：{'，'.join(node.get('tags', []))}")
                content = node.get("content", "")
                if content:
                    temp.setHtml(content)
                    plain = temp.toPlainText().strip()
                    if plain:
                        lines.extend(["", plain])
            lines.append("")
            for child in node.get("children", []):
                append_node(child, level + 1)

        for module in self.ensure_worldbuilding_data().get("modules", []):
            append_node(module, 1)
        return "\n".join(lines).strip() + "\n"

    def export_worldbuilding(self) -> None:
        if not self.selected_project:
            QMessageBox.information(self, "没有项目", "请先选择或创建一个项目。")
            return
        self.save_current_world_entry(silent=True)
        export_dir = Path(self.selected_project.path) / "exports"
        export_dir.mkdir(parents=True, exist_ok=True)
        output = export_dir / f"{self.selected_project.name}_设定库.md"
        try:
            output.write_text(self.worldbuilding_to_markdown(), encoding="utf-8")
        except OSError as exc:
            QMessageBox.critical(self, "导出失败", str(exc))
            return
        QMessageBox.information(self, "已导出", f"设定库已导出到：\n{output}")

    def switch_page(self, page_name: str) -> None:
        project_pages = {"editor", "outline", "worldbuilding", "character"}
        if self.current_page == "editor":
            self.save_current_chapter(silent=True)
        elif self.current_page == "outline":
            self.save_current_outline_node(silent=True)
        elif self.current_page == "worldbuilding":
            self.save_current_world_entry(silent=True)
        elif self.current_page == "character":
            self.save_current_character(silent=True)

        if page_name in project_pages:
            if not self.selected_project:
                QMessageBox.information(self, "没有项目", "请先选择或创建一个项目。")
                return
            if not Path(self.selected_project.path).exists():
                QMessageBox.warning(self, "路径不存在", "项目路径不存在，请先重新关联项目。")
                return
            if page_name == "editor":
                self.load_editor_project()
                self.page_stack.setCurrentWidget(self.editor_page)
                self.setWindowTitle(f"{APP_NAME} - 正文")
            elif page_name == "outline":
                self.load_outline_project()
                self.page_stack.setCurrentWidget(self.outline_page)
                self.setWindowTitle(f"{APP_NAME} - 大纲")
            elif page_name == "worldbuilding":
                self.load_worldbuilding_project()
                self.page_stack.setCurrentWidget(self.worldbuilding_page)
                self.setWindowTitle(f"{APP_NAME} - 设定库")
            else:
                self.load_character_project()
                self.page_stack.setCurrentWidget(self.character_page)
                self.setWindowTitle(f"{APP_NAME} - 人物卡")
            self.current_page = page_name
            self.topbar_widget.setVisible(False)
            self.content_layout.setContentsMargins(0, 0, 0, 0)
            self.content_layout.setSpacing(0)
        elif page_name == "settings":
            self.load_settings_page()
            self.page_stack.setCurrentWidget(self.settings_page)
            self.current_page = "settings"
            self.topbar_widget.setVisible(False)
            self.content_layout.setContentsMargins(0, 0, 0, 0)
            self.content_layout.setSpacing(0)
            self.setWindowTitle(f"{APP_NAME} - 设置")
        else:
            self.page_stack.setCurrentWidget(self.home_page)
            self.page_title.setText("项目首页")
            self.current_page = "home"
            self.topbar_widget.setVisible(True)
            self.content_layout.setContentsMargins(28, 24, 28, 28)
            self.content_layout.setSpacing(18)
            self.setWindowTitle(f"{APP_NAME} - 项目首页")
            self.refresh_projects(keep_project=self.selected_project)
        self.update_nav_state()
        self.update_topbar_actions()
        self.update_status_line()

    def update_nav_state(self) -> None:
        for name, button in self.nav_buttons.items():
            active = name == self.current_page
            button.setObjectName("NavActive" if active else "NavItem")
            icon_name = button.property("nav_icon") or "config"
            button.setIcon(nav_icon(str(icon_name), PALETTE["ink"] if active else "#FFFFFF"))
            button.style().unpolish(button)
            button.style().polish(button)

    def update_topbar_actions(self) -> None:
        for button in getattr(self, "project_action_buttons", []):
            button.setVisible(self.current_page == "home")

    def setup_shortcuts(self) -> None:
        QShortcut(QKeySequence("Ctrl+S"), self, activated=self.save_current_project)
        QShortcut(QKeySequence("Ctrl+F"), self, activated=self.focus_find_box)
        QShortcut(QKeySequence("Ctrl+B"), self, activated=self.toggle_bold)
        QShortcut(QKeySequence("Ctrl+Z"), self, activated=self.editor_undo)
        QShortcut(QKeySequence("Ctrl+Y"), self, activated=self.editor_redo)
        QShortcut(QKeySequence("Ctrl+Shift+Z"), self, activated=self.editor_redo)

    def closeEvent(self, event: Any) -> None:
        if self.editor_ai_thread and self.editor_ai_thread.isRunning():
            self.editor_ai_thread.request_stop()
            self.editor_ai_thread.wait(1500)
        if self.outline_ai_thread and self.outline_ai_thread.isRunning():
            self.outline_ai_thread.request_stop()
            self.outline_ai_thread.wait(1500)
        if self.character_ai_thread and self.character_ai_thread.isRunning():
            self.character_ai_thread.request_stop()
            self.character_ai_thread.wait(1500)
        super().closeEvent(event)

    def load_settings_page(self) -> None:
        if not hasattr(self, "eye_mode_check"):
            return
        self.loading_settings_page = True
        self.preview_app_settings = None
        self.app_settings = load_app_settings()
        settings = self.app_settings
        try:
            self.eye_mode_check.setChecked(bool(settings.get("eye_mode")))
            self.ui_scale_box.setCurrentText(f"{int(settings.get('ui_scale', 100))}%")
            self.settings_font_box.setCurrentFont(QFont(str(settings.get("font_family") or DEFAULT_BODY_FONT_FAMILY)))
            self.set_combo_text(self.settings_body_font_size_box, int(settings.get("body_font_size", DEFAULT_BODY_FONT_SIZE)))
            self.set_combo_text(self.settings_title_font_size_box, int(settings.get("title_font_size", DEFAULT_TITLE_FONT_SIZE)))
            self.auto_save_enabled_check.setChecked(bool(settings.get("auto_save_enabled", True)))
            self.set_combo_text(
                self.settings_auto_save_box,
                f"{int(self.selected_project.auto_save_minutes if self.selected_project else settings.get('auto_save_minutes', 10))} 分钟",
            )
            self.set_combo_text(self.backup_retention_box, f"{int(settings.get('backup_retention', 10))} 份")
            self.settings_last_auto_label.setText(fmt_time(self.selected_project.last_auto_save_at) if self.selected_project else "-")
            self.ai_enabled_check.setChecked(bool(settings.get("ai_enabled", True)))
            self.ai_key_edit.setText(str(settings.get("api_key", "")))
            self.set_combo_text(self.ai_base_url_box, str(settings.get("base_url", "")))
            self.set_combo_text(self.ai_model_box, str(settings.get("model", "")))
            self.set_combo_text(self.ai_context_box, int(settings.get("max_context_items", 60)))
            self.ai_role_name_edit.setText(str(settings.get("ai_role_name", "AI") or "AI"))
            self.ai_role_identity_edit.setText(str(settings.get("ai_role_identity", "创作助手") or ""))
            self.ai_role_prompt_edit.setPlainText(str(settings.get("ai_role_prompt", "") or ""))
            self.ai_status_label.setText("尚未测试连接。")
            self.ai_status_label.setObjectName("Muted")
            self.ai_status_label.style().unpolish(self.ai_status_label)
            self.ai_status_label.style().polish(self.ai_status_label)
            self.export_format_box.setCurrentText(str(settings.get("export_format", "Markdown")))
            self.export_volume_check.setChecked(bool(settings.get("export_include_volume", True)))
            self.export_chapter_check.setChecked(bool(settings.get("export_include_chapter_title", True)))
            self.export_status_check.setChecked(bool(settings.get("export_include_chapter_status", False)))
        finally:
            self.loading_settings_page = False

    def preview_eye_mode_from_ui(self, checked: bool) -> None:
        if self.loading_settings_page:
            return
        self.preview_app_settings = dict(self.app_settings)
        self.preview_app_settings["eye_mode"] = checked
        self.apply_styles()

    def collect_app_settings_from_ui(self) -> dict[str, Any]:
        scale_text = self.ui_scale_box.currentText().replace("%", "").strip()
        return {
            "eye_mode": self.eye_mode_check.isChecked(),
            "ui_scale": int(scale_text or "100"),
            "font_family": self.settings_font_box.currentFont().family(),
            "body_font_size": self.combo_int_value(self.settings_body_font_size_box, DEFAULT_BODY_FONT_SIZE, 10, 72),
            "title_font_size": self.combo_int_value(self.settings_title_font_size_box, DEFAULT_TITLE_FONT_SIZE, 12, 96),
            "auto_save_enabled": self.auto_save_enabled_check.isChecked(),
            "auto_save_minutes": self.combo_int_value(self.settings_auto_save_box, 10, 1, 120),
            "backup_retention": self.combo_int_value(self.backup_retention_box, 10, 1, 200),
            "ai_enabled": self.ai_enabled_check.isChecked(),
            "api_key": self.ai_key_edit.text().strip(),
            "base_url": self.ai_base_url_box.currentText().strip(),
            "model": self.ai_model_box.currentText().strip(),
            "max_context_items": self.combo_int_value(self.ai_context_box, 60, 10, 10_000),
            "ai_role_name": self.ai_role_name_edit.text().strip() or "AI",
            "ai_role_identity": self.ai_role_identity_edit.text().strip(),
            "ai_role_prompt": self.ai_role_prompt_edit.toPlainText().strip(),
            "outline_ai_scope": self.saved_outline_ai_scope_preferences() if hasattr(self, "outline_scope_checks") else self.app_settings.get("outline_ai_scope", default_outline_ai_scope()),
            "export_format": self.export_format_box.currentText(),
            "export_include_volume": self.export_volume_check.isChecked(),
            "export_include_chapter_title": self.export_chapter_check.isChecked(),
            "export_include_chapter_status": self.export_status_check.isChecked(),
        }

    def save_app_settings_from_ui(self, show_message: bool = True) -> None:
        settings = self.collect_app_settings_from_ui()
        try:
            save_app_settings(settings)
        except OSError as exc:
            QMessageBox.critical(self, "保存失败", str(exc))
            return
        self.app_settings = settings
        self.preview_app_settings = None
        if self.selected_project and Path(self.selected_project.path).exists():
            self.selected_project.auto_save_minutes = int(settings.get("auto_save_minutes", 10))
            self.selected_project.ai_summary_enabled = bool(settings.get("ai_enabled", True))
            try:
                self.store.write_project(self.selected_project)
                self.store.add_recent(self.selected_project)
            except OSError as exc:
                QMessageBox.critical(self, "项目设置保存失败", str(exc))
                return
        self.apply_styles()
        self.update_status_line()
        if show_message:
            QMessageBox.information(self, "已保存", "全局设置已保存。")

    def restore_default_app_settings(self) -> None:
        answer = QMessageBox.question(
            self,
            "恢复默认设置",
            "将恢复默认设置，并清空当前保存的 API Key。是否继续？",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No,
        )
        if answer != QMessageBox.Yes:
            return
        self.app_settings = default_app_settings()
        try:
            save_app_settings(self.app_settings)
        except OSError as exc:
            QMessageBox.critical(self, "保存失败", str(exc))
            return
        self.load_settings_page()
        self.apply_styles()
        QMessageBox.information(self, "已恢复", "设置已恢复为默认值。")

    def perform_ai_connection_test(self, settings: dict[str, Any]) -> tuple[bool, str]:
        if not settings.get("ai_enabled", True):
            return False, "AI 辅助已关闭。"
        api_key = str(settings.get("api_key", "")).strip()
        base_url = str(settings.get("base_url", "")).strip().rstrip("/")
        model = str(settings.get("model", "")).strip()
        if not api_key:
            return False, "缺少 API Key。"
        if not base_url:
            return False, "缺少 Base URL。"
        if not model:
            return False, "缺少模型名。"
        payload = {
            "model": model,
            "messages": [{"role": "user", "content": "请只回复：连接正常"}],
            "max_tokens": 12,
            "temperature": 0,
        }
        last_error = ""
        for attempt in range(1, 4):
            request = urllib.request.Request(
                f"{base_url}/chat/completions",
                data=json.dumps(payload).encode("utf-8"),
                headers={
                    "Authorization": f"Bearer {api_key}",
                    "Content-Type": "application/json",
                    "Accept": "application/json",
                    "Connection": "close",
                    "User-Agent": f"WenshaCreator/{APP_VERSION}",
                },
                method="POST",
            )
            try:
                with urllib.request.urlopen(request, timeout=20) as response:
                    status = response.status
                    body = response.read(4096).decode("utf-8", errors="replace")
                    break
            except urllib.error.HTTPError as exc:
                return False, f"连接失败：HTTP {exc.code}。请检查 Key、Base URL 或模型名。"
            except urllib.error.URLError as exc:
                last_error = str(exc.reason)
            except TimeoutError:
                last_error = "连接超时"
            QApplication.processEvents()
        else:
            if "10054" in last_error:
                return False, "连接失败：远程主机强制关闭连接，已重试 3 次。通常是网络波动、代理/防火墙或服务商临时断开。"
            return False, f"连接失败：{last_error or '网络请求未完成'}"
        if status < 200 or status >= 300:
            return False, f"连接失败：HTTP {status}。"
        try:
            data = json.loads(body)
        except json.JSONDecodeError:
            return False, "接口已响应，但返回内容不是 JSON。"
        if not data.get("choices"):
            return False, "接口已响应，但未返回 choices。"
        suffix = f"（第 {attempt} 次尝试成功）" if attempt > 1 else ""
        return True, f"连接正常{suffix}。"

    def test_ai_connection(self) -> None:
        settings = self.collect_app_settings_from_ui()
        self.ai_status_label.setText("正在测试连接...")
        QApplication.processEvents()
        ok, message = self.perform_ai_connection_test(settings)
        self.ai_status_label.setText(message)
        self.ai_status_label.setObjectName("SuccessBadge" if ok else "ErrorBadge")
        self.ai_status_label.style().unpolish(self.ai_status_label)
        self.ai_status_label.style().polish(self.ai_status_label)

    def save_active_project_silently(self) -> None:
        if not self.selected_project or not Path(self.selected_project.path).exists():
            return
        if self.current_page == "editor":
            self.save_current_chapter(silent=True)
        elif self.current_page == "outline":
            self.save_current_outline_node(silent=True)
        elif self.current_page == "worldbuilding":
            self.save_current_world_entry(silent=True)
        elif self.current_page == "character":
            self.save_current_character(silent=True)
        if self.draft is not None:
            DraftStore.save(self.selected_project, self.draft)
        self.store.write_project(self.selected_project)

    def backup_files(self, project: ProjectMeta) -> list[Path]:
        project_path = Path(project.path)
        backup_dir = project_path / "backups"
        files: list[Path] = []
        for item in project_path.rglob("*"):
            if not item.is_file():
                continue
            try:
                item.relative_to(backup_dir)
                continue
            except ValueError:
                pass
            files.append(item)
        return files

    def enforce_backup_retention(self, project: ProjectMeta) -> None:
        keep = int(self.collect_app_settings_from_ui().get("backup_retention", 10)) if hasattr(self, "backup_retention_spin") else 10
        backup_dir = Path(project.path) / "backups"
        backups = sorted(backup_dir.glob("*_backup_*.zip"), key=lambda path: path.stat().st_mtime, reverse=True)
        for old_backup in backups[keep:]:
            old_backup.unlink(missing_ok=True)

    def create_manual_backup(self, silent: bool = False) -> Path | None:
        project = self.selected_project
        if not project:
            if not silent:
                QMessageBox.information(self, "没有项目", "请先选择或创建一个项目。")
            return None
        project_path = Path(project.path)
        if not project_path.exists():
            if not silent:
                QMessageBox.warning(self, "路径不存在", "项目路径不存在，无法备份。")
            return None
        self.save_active_project_silently()
        backup_dir = project_path / "backups"
        backup_dir.mkdir(parents=True, exist_ok=True)
        stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        safe_name = "".join(ch for ch in project.name if ch not in '\\/:*?"<>|').strip() or "project"
        output = backup_dir / f"{safe_name}_backup_{stamp}.zip"
        try:
            with zipfile.ZipFile(output, "w", zipfile.ZIP_DEFLATED) as archive:
                for item in self.backup_files(project):
                    archive.write(item, item.relative_to(project_path))
            project.last_backup_at = now_iso()
            self.store.write_project(project)
            self.store.add_recent(project)
            self.enforce_backup_retention(project)
        except OSError as exc:
            if not silent:
                QMessageBox.critical(self, "备份失败", str(exc))
            return None
        if not silent:
            self.settings_last_auto_label.setText(fmt_time(project.last_auto_save_at))
            QMessageBox.information(self, "已创建备份", f"备份已保存到：\n{output}")
        return output

    def safe_extract_backup(self, archive_path: Path, project_path: Path) -> None:
        project_root = project_path.resolve()
        with zipfile.ZipFile(archive_path, "r") as archive:
            for member in archive.infolist():
                target = (project_root / member.filename).resolve()
                try:
                    target.relative_to(project_root)
                except ValueError:
                    raise OSError(f"备份文件包含不安全路径：{member.filename}")
                if member.is_dir():
                    target.mkdir(parents=True, exist_ok=True)
                    continue
                target.parent.mkdir(parents=True, exist_ok=True)
                with archive.open(member) as source, target.open("wb") as dest:
                    shutil.copyfileobj(source, dest)

    def restore_from_backup(self) -> None:
        project = self.selected_project
        if not project:
            QMessageBox.information(self, "没有项目", "请先选择或创建一个项目。")
            return
        project_path = Path(project.path)
        if not project_path.exists():
            QMessageBox.warning(self, "路径不存在", "项目路径不存在，无法恢复。")
            return
        file_name, _ = QFileDialog.getOpenFileName(
            self,
            "选择备份文件",
            str(project_path / "backups"),
            "Backup (*.zip)",
        )
        if not file_name:
            return
        answer = QMessageBox.question(
            self,
            "从备份恢复",
            "恢复会覆盖当前项目文件。程序会先创建一份当前状态备份。是否继续？",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No,
        )
        if answer != QMessageBox.Yes:
            return
        self.create_manual_backup(silent=True)
        try:
            self.safe_extract_backup(Path(file_name), project_path)
            self.selected_project = self.store.open_project(project_path)
            self.draft = None
        except (OSError, zipfile.BadZipFile, ValueError, json.JSONDecodeError) as exc:
            QMessageBox.critical(self, "恢复失败", str(exc))
            return
        self.refresh_projects(keep_project=self.selected_project)
        self.load_settings_page()
        QMessageBox.information(self, "已恢复", "项目已从备份恢复。")

    def resolve_project_asset(self, project: ProjectMeta, value: str) -> Path:
        path = Path(value)
        if path.is_absolute():
            return path
        return Path(project.path) / path

    def project_integrity_issues(self, project: ProjectMeta) -> list[str]:
        project_path = Path(project.path)
        issues: list[str] = []
        for required in [PROJECT_CONFIG, DRAFT_FILE, "assets", "exports", "backups"]:
            if not (project_path / required).exists():
                issues.append(f"缺少 {required}")
        if project.cover_image_path and not self.resolve_project_asset(project, project.cover_image_path).exists():
            issues.append("项目封面图片引用失效")
        try:
            draft = DraftStore.load(project)
        except Exception as exc:
            return [f"草稿文件无法读取：{exc}"]
        for module in draft.get("worldbuilding", {}).get("modules", []):
            for _parent, node in self.iter_world_nodes([module]):
                image_path = node.get("image_path")
                if image_path and not self.resolve_project_asset(project, image_path).exists():
                    issues.append(f"设定图片缺失：{node.get('title', '未命名词条')}")
        for card in draft.get("characters", {}).get("cards", []):
            portrait_path = card.get("portrait_path")
            if portrait_path and not self.resolve_project_asset(project, portrait_path).exists():
                issues.append(f"人物画像缺失：{card.get('name', '未命名人物')}")
        return issues

    def check_project_integrity(self, silent: bool = False) -> list[str]:
        project = self.selected_project
        if not project:
            if not silent:
                QMessageBox.information(self, "没有项目", "请先选择或创建一个项目。")
            return ["没有项目"]
        issues = self.project_integrity_issues(project)
        if not silent:
            if issues:
                QMessageBox.warning(self, "检查结果", "发现以下问题：\n" + "\n".join(issues[:20]))
            else:
                QMessageBox.information(self, "检查结果", "项目结构与图片引用未发现问题。")
        return issues

    def clear_missing_image_refs(self, silent: bool = False) -> int:
        project = self.selected_project
        if not project:
            if not silent:
                QMessageBox.information(self, "没有项目", "请先选择或创建一个项目。")
            return 0
        if not Path(project.path).exists():
            if not silent:
                QMessageBox.warning(self, "路径不存在", "项目路径不存在，无法清理。")
            return 0
        draft = DraftStore.load(project)
        count = 0
        if project.cover_image_path and not self.resolve_project_asset(project, project.cover_image_path).exists():
            project.cover_image_path = None
            count += 1
        for module in draft.get("worldbuilding", {}).get("modules", []):
            for _parent, node in self.iter_world_nodes([module]):
                image_path = node.get("image_path")
                if image_path and not self.resolve_project_asset(project, image_path).exists():
                    node["image_path"] = ""
                    count += 1
        for card in draft.get("characters", {}).get("cards", []):
            portrait_path = card.get("portrait_path")
            if portrait_path and not self.resolve_project_asset(project, portrait_path).exists():
                card["portrait_path"] = ""
                count += 1
        if count:
            DraftStore.save(project, draft)
            self.store.write_project(project)
            self.draft = draft if self.draft is not None else self.draft
        if not silent:
            QMessageBox.information(self, "清理完成", f"已清理 {count} 个失效图片引用。")
        return count

    def editor_settings(self) -> dict[str, Any]:
        defaults = {
            "font_family": DEFAULT_BODY_FONT_FAMILY,
            "font_size": DEFAULT_BODY_FONT_SIZE,
            "line_spacing": DEFAULT_LINE_SPACING,
            "letter_spacing": DEFAULT_LETTER_SPACING,
            "style_version": DEFAULT_EDITOR_STYLE_VERSION,
        }
        if self.draft is None:
            return defaults
        settings = self.draft.setdefault("editor_settings", defaults.copy())
        for key, value in defaults.items():
            settings.setdefault(key, value)
        if int(settings.get("style_version", 1)) < DEFAULT_EDITOR_STYLE_VERSION:
            if int(settings.get("font_size", 16)) == 16:
                settings["font_size"] = DEFAULT_BODY_FONT_SIZE
            settings["letter_spacing"] = DEFAULT_LETTER_SPACING
            settings["style_version"] = DEFAULT_EDITOR_STYLE_VERSION
        return settings

    def apply_editor_settings(self) -> None:
        settings = self.editor_settings()
        font_family = settings.get("font_family", DEFAULT_BODY_FONT_FAMILY)
        font_size = int(settings.get("font_size", DEFAULT_BODY_FONT_SIZE))
        line_spacing = int(settings.get("line_spacing", DEFAULT_LINE_SPACING))
        letter_spacing = int(settings.get("letter_spacing", DEFAULT_LETTER_SPACING))
        self.font_box.blockSignals(True)
        self.font_size_spin.blockSignals(True)
        self.font_size_box.blockSignals(True)
        self.line_spacing_spin.blockSignals(True)
        self.font_box.setCurrentFont(QFont(font_family))
        self.font_size_spin.setValue(font_size)
        self.font_size_box.setCurrentText(str(font_size))
        self.line_spacing_spin.setValue(line_spacing)
        self.font_box.blockSignals(False)
        self.font_size_spin.blockSignals(False)
        self.font_size_box.blockSignals(False)
        self.line_spacing_spin.blockSignals(False)
        self.editor.set_editor_style(font_family, font_size, line_spacing, letter_spacing)

    def update_editor_setting(self, key: str, value: Any) -> None:
        if self.draft is None:
            return
        self.editor_settings()[key] = value
        self.editor_settings()["style_version"] = DEFAULT_EDITOR_STYLE_VERSION
        if self.selected_project:
            DraftStore.save(self.selected_project, self.draft)

    def load_editor_project(self) -> None:
        if not self.selected_project:
            return
        self.draft = DraftStore.load(self.selected_project)
        self.apply_editor_settings()
        self.current_chapter_id = self.draft.get("current_chapter_id")
        if not self.current_chapter_id:
            first = DraftStore.first_chapter(self.draft)
            self.current_chapter_id = first[1]["id"] if first else None
        self.populate_outline(self.current_chapter_id)
        if self.current_chapter_id:
            self.load_chapter(self.current_chapter_id)

    def populate_outline(self, selected_chapter_id: str | None = None) -> None:
        if self.draft is None:
            return
        self.chapter_tree.blockSignals(True)
        self.chapter_tree.clear()
        selected_item: QTreeWidgetItem | None = None
        for volume in self.draft.get("volumes", []):
            volume_item = QTreeWidgetItem([volume.get("title", "未命名卷")])
            volume_item.setData(0, Qt.UserRole, {"kind": "volume", "id": volume.get("id")})
            self.chapter_tree.addTopLevelItem(volume_item)
            for chapter in volume.get("chapters", []):
                status = chapter.get("status", "草稿")
                chapter_item = QTreeWidgetItem([chapter.get("title", "未命名章节")])
                chapter_item.setIcon(0, self.status_icon(status))
                chapter_item.setData(0, Qt.UserRole, {"kind": "chapter", "id": chapter.get("id")})
                volume_item.addChild(chapter_item)
                if chapter.get("id") == selected_chapter_id:
                    selected_item = chapter_item
            volume_item.setExpanded(True)
        if selected_item:
            self.chapter_tree.setCurrentItem(selected_item)
        self.chapter_tree.blockSignals(False)

    def status_icon(self, status: str) -> QIcon:
        color = {"修订中": PALETTE["accent"], "草稿": PALETTE["amber"], "完稿": PALETTE["green"]}.get(status, PALETTE["amber"])
        if color in self.status_icon_cache:
            return self.status_icon_cache[color]
        pixmap = QPixmap(10, 10)
        pixmap.fill(Qt.transparent)
        painter = QPainter(pixmap)
        painter.setRenderHint(QPainter.Antialiasing)
        painter.setBrush(QBrush(QColor(color)))
        painter.setPen(Qt.NoPen)
        painter.drawEllipse(2, 2, 6, 6)
        painter.end()
        icon = QIcon(pixmap)
        self.status_icon_cache[color] = icon
        return icon

    def show_outline_context_menu(self, pos: QPoint) -> None:
        if self.draft is None:
            return
        item = self.chapter_tree.itemAt(pos)
        menu = QMenu(self.chapter_tree)
        if item is None:
            menu.addAction("新增卷", self.add_volume)
            menu.addAction("新增章节", self.add_chapter)
        else:
            self.chapter_tree.setCurrentItem(item)
            data = item.data(0, Qt.UserRole) or {}
            if data.get("kind") == "volume":
                menu.addAction("新增章节", self.add_chapter)
                menu.addAction("更改名称", lambda: self.rename_volume(data.get("id")))
                menu.addSeparator()
                menu.addAction("删除卷", lambda: self.delete_volume(data.get("id")))
            elif data.get("kind") == "chapter":
                menu.addAction("更改名称", lambda: self.rename_chapter(data.get("id")))
                menu.addSeparator()
                menu.addAction("删除章节", lambda: self.delete_chapter(data.get("id")))
        menu.exec(self.chapter_tree.viewport().mapToGlobal(pos))

    def on_outline_selected(self) -> None:
        item = self.chapter_tree.currentItem()
        if not item or self.loading_chapter:
            return
        data = item.data(0, Qt.UserRole) or {}
        if data.get("kind") != "chapter":
            return
        target_chapter_id = data.get("id")
        if not target_chapter_id:
            return
        if self.current_chapter_id and self.current_chapter_id != target_chapter_id:
            self.save_current_chapter(silent=True)
        self.load_chapter(target_chapter_id)
        self.populate_outline(target_chapter_id)

    def load_chapter(self, chapter_id: str) -> None:
        if self.draft is None:
            return
        found = DraftStore.find_chapter(self.draft, chapter_id)
        if not found:
            return
        volume, chapter = found
        self.loading_chapter = True
        self.current_chapter_id = chapter_id
        self.draft["current_chapter_id"] = chapter_id
        self.chapter_title_label.setText(f"{volume.get('title', '未命名卷')} / {chapter.get('title', '未命名章节')}")
        self.editor.setHtml(chapter.get("content", ""))
        self.editor.apply_document_structure()
        summary = chapter.get("summary", {})
        self.summary_box.setPlainText(summary.get("events", ""))
        self.ai_chapter_enabled_check.blockSignals(True)
        self.ai_chapter_enabled_check.setChecked(bool(chapter.get("ai_enabled", True)))
        self.ai_chapter_enabled_check.blockSignals(False)
        self.set_status_button(chapter.get("status", "草稿"))
        self.update_word_count()
        self.loading_chapter = False

    def save_current_chapter(self, silent: bool = False) -> None:
        if not self.selected_project or self.draft is None or not self.current_chapter_id:
            return
        found = DraftStore.find_chapter(self.draft, self.current_chapter_id)
        if not found:
            return
        volume, chapter = found
        self.editor.apply_document_structure()
        html = self.editor.toHtml()
        title = self.first_editor_line() or chapter.get("title", "未命名章节")
        chapter["title"] = title
        chapter["content"] = html
        chapter["ai_enabled"] = self.ai_chapter_enabled_check.isChecked()
        chapter.setdefault("summary", {})["events"] = self.summary_box.toPlainText().strip()
        chapter["updated_at"] = now_iso()
        self.draft["current_chapter_id"] = self.current_chapter_id
        DraftStore.save(self.selected_project, self.draft)

        self.selected_project.current_position = f"{volume.get('title', '未命名卷')} · {title}"
        self.selected_project.total_words = sum(DraftStore.text_count(item.get("content", "")) for _, item in DraftStore.iter_chapters(self.draft))
        self.selected_project.today_words = DraftStore.text_count(html)
        self.selected_project.last_manual_save_at = now_iso()
        self.store.write_project(self.selected_project)
        self.store.save_recent()
        self.populate_outline(self.current_chapter_id)
        self.chapter_title_label.setText(f"{volume.get('title', '未命名卷')} / {title}")
        self.update_word_count()
        self.update_status_line()
        if not silent:
            QMessageBox.information(self, "已保存", "当前章节已保存。")

    def first_editor_line(self) -> str:
        for line in self.editor.toPlainText().splitlines():
            text = line.strip()
            if text:
                return text[:40]
        return ""

    def on_editor_changed(self) -> None:
        if self.loading_chapter:
            return
        self.update_word_count()

    def on_summary_changed(self) -> None:
        if self.loading_chapter:
            return

    def set_current_chapter_ai_enabled(self, enabled: bool) -> None:
        if self.loading_chapter or self.draft is None or not self.current_chapter_id:
            return
        found = DraftStore.find_chapter(self.draft, self.current_chapter_id)
        if not found:
            return
        _, chapter = found
        chapter["ai_enabled"] = enabled
        if self.selected_project:
            DraftStore.save(self.selected_project, self.draft)

    def html_to_plain_text(self, html: str) -> str:
        text = QTextEdit()
        text.setHtml(html or "")
        return text.toPlainText().strip()

    def ai_settings_for_request(self) -> dict[str, Any]:
        if hasattr(self, "ai_key_edit"):
            settings = self.collect_app_settings_from_ui()
            settings["ai_confirm_each_call"] = self.app_settings.get("ai_confirm_each_call", True)
            return settings
        return dict(self.app_settings)

    def ai_role_name(self, settings: dict[str, Any]) -> str:
        return str(settings.get("ai_role_name", "")).strip() or "AI"

    def ai_role_instruction(self, settings: dict[str, Any]) -> str:
        name = self.ai_role_name(settings)
        identity = str(settings.get("ai_role_identity", "")).strip() or "创作助手"
        prompt = str(settings.get("ai_role_prompt", "")).strip()
        lines = [
            f"你的名称是：{name}。",
            f"你的身份是：{identity}。",
        ]
        if prompt:
            lines.append(f"你的角色设定是：{prompt}")
        return "\n".join(lines)

    def ai_working_message(self, settings: dict[str, Any], task: str) -> str:
        name = self.ai_role_name(settings)
        role_text = f"{settings.get('ai_role_identity', '')}\n{settings.get('ai_role_prompt', '')}"
        if any(word in role_text for word in ["严厉", "审稿", "冷静", "理性"]):
            phrase = f"正在逐条核对{task}，我会把事件、人物变化和伏笔线索整理清楚。"
        elif any(word in role_text for word in ["温柔", "陪写", "鼓励", "耐心"]):
            phrase = f"正在认真陪你梳理{task}，马上把这一章的脉络整理出来。"
        elif any(word in role_text for word in ["幽默", "活泼", "轻松"]):
            phrase = f"正在奋力整理{task}，让我把线索捞清楚再交给你。"
        else:
            phrase = f"正在整理{task}，请稍等。"
        return f"{name}：{phrase}"

    def validate_editor_ai_ready(self, settings: dict[str, Any]) -> tuple[bool, str]:
        if not self.selected_project or self.draft is None:
            return False, "请先打开一个小说项目。"
        if not settings.get("ai_enabled", True):
            return False, "AI 辅助已关闭，请先到设置页启用。"
        if not self.current_chapter_id:
            return False, "请先选择一个章节。"
        found = DraftStore.find_chapter(self.draft, self.current_chapter_id)
        if not found:
            return False, "当前章节不存在。"
        if not found[1].get("ai_enabled", True):
            return False, "本章已关闭 AI 辅助。"
        if not str(settings.get("api_key", "")).strip():
            return False, "AI 接口未配置：缺少 API Key。"
        if not str(settings.get("base_url", "")).strip():
            return False, "AI 接口未配置：缺少 Base URL。"
        if not str(settings.get("model", "")).strip():
            return False, "AI 接口未配置：缺少模型名。"
        return True, ""

    def short_plain_text(self, html: str, limit: int = 600) -> str:
        text = self.html_to_plain_text(html)
        if len(text) <= limit:
            return text
        return text[:limit].rstrip() + "\n..."

    def append_context_section(self, sections: list[tuple[str, str]], title: str, body: str) -> None:
        body = body.strip()
        if body:
            sections.append((title, body))

    def chapter_summary_text(self, chapter: dict[str, Any]) -> str:
        summary = chapter.get("summary", {})
        if isinstance(summary, dict):
            parts = [str(value).strip() for value in summary.values() if str(value).strip()]
            return "\n".join(parts)
        return str(summary).strip()

    def build_chapter_summary_context(self) -> list[tuple[str, str]]:
        sections: list[tuple[str, str]] = []
        if self.draft is None or not self.current_chapter_id:
            return sections
        found = DraftStore.find_chapter(self.draft, self.current_chapter_id)
        if not found:
            return sections
        volume, chapter = found
        title = f"{volume.get('title', '未命名卷')} / {chapter.get('title', '未命名章节')}"
        self.append_context_section(sections, "当前章节", title)
        self.append_context_section(sections, "当前章正文", self.html_to_plain_text(chapter.get("content", "")))
        return sections

    def build_editor_chat_context(self) -> list[tuple[str, str]]:
        sections: list[tuple[str, str]] = []
        if self.draft is None:
            return sections
        for volume, chapter in DraftStore.iter_chapters(self.draft):
            summary = self.chapter_summary_text(chapter)
            if summary:
                title = f"章节总结 - {volume.get('title', '未命名卷')} / {chapter.get('title', '未命名章节')}"
                self.append_context_section(sections, title, summary)

        outline = self.draft.get("outline")
        if isinstance(outline, dict):
            for _parent, node in self.iter_outline_nodes(outline.get("nodes", [])):
                node_text = "\n".join(
                    item
                    for item in [
                        f"类型：{node.get('kind', '节点')}",
                        f"目标：{node.get('goal', '')}",
                        f"时间线：{node.get('timeline_tag', '')}",
                        self.short_plain_text(node.get("content", ""), 500),
                    ]
                    if item.strip() and not item.endswith("：")
                )
                self.append_context_section(sections, f"大纲 - {node.get('title', '未命名')}", node_text)
            timeline_lines = [
                f"{point.get('time', '')} / {point.get('line', '')}：{point.get('event', '')}"
                for point in outline.get("timeline_points", [])
                if point.get("time") or point.get("event") or point.get("line")
            ]
            self.append_context_section(sections, "时间线", "\n".join(timeline_lines))

        world = self.draft.get("worldbuilding")
        if isinstance(world, dict):
            world_lines: list[str] = []
            for module in world.get("modules", []):
                for _parent, node in self.iter_world_nodes([module]):
                    if node.get("kind") != "entry":
                        continue
                    if node.get("ai_read_allowed", node.get("allow_ai_read", node.get("ai_enabled", True))) is False:
                        continue
                    tags = "，".join(node.get("tags", []))
                    world_lines.append(
                        f"{node.get('title', '未命名词条')} [{node.get('entry_type', '设定')}] {tags}\n"
                        f"{self.short_plain_text(node.get('content', ''), 500)}"
                    )
            self.append_context_section(sections, "设定库", "\n\n".join(world_lines))

        characters = self.draft.get("characters")
        if isinstance(characters, dict):
            card_lines: list[str] = []
            relation_lines: list[str] = []
            for card in characters.get("cards", []):
                tags = []
                for tag_name, values in card.get("tags", {}).items():
                    if values:
                        tags.append(f"{tag_name}：{'，'.join(values)}")
                card_lines.append(
                    "\n".join(
                        item
                        for item in [
                            f"{card.get('name', '未命名')} / {card.get('identity', '')} / {card.get('status', '')}",
                            f"阵营：{card.get('faction', '')}",
                            "；".join(tags),
                            self.short_plain_text(card.get("notes", ""), 450),
                        ]
                        if item.strip()
                    )
                )
                for relation in card.get("relations", []):
                    relation_lines.append(
                        f"{card.get('name', '未命名')} -> {relation.get('target_name', '未命名')}："
                        f"{relation.get('type', '关系')} / {relation.get('status', '')} / {relation.get('note', '')}"
                    )
            self.append_context_section(sections, "人物卡", "\n\n".join(card_lines))
            self.append_context_section(sections, "人物关系记录", "\n".join(relation_lines))
        return sections

    def limited_ai_context(self, sections: list[tuple[str, str]], settings: dict[str, Any]) -> list[tuple[str, str]]:
        try:
            limit = int(settings.get("max_context_items", 60))
        except (TypeError, ValueError):
            limit = 60
        return sections[: max(1, limit)]

    def ai_context_preview(self, sections: list[tuple[str, str]]) -> str:
        names = [title for title, _body in sections]
        if not names:
            return "本次没有可读取的项目资料。"
        shown = "\n".join(f"- {name}" for name in names[:20])
        if len(names) > 20:
            shown += f"\n- 另外 {len(names) - 20} 项..."
        return shown

    def ai_context_text(self, sections: list[tuple[str, str]]) -> str:
        return "\n\n".join(f"## {title}\n{body}" for title, body in sections)

    def confirm_ai_call(self, title: str, sections: list[tuple[str, str]], settings: dict[str, Any]) -> bool:
        if not settings.get("ai_confirm_each_call", True):
            return True
        answer = QMessageBox.question(
            self,
            title,
            "本次 AI 将读取以下范围：\n\n"
            f"{self.ai_context_preview(sections)}\n\n"
            "AI 只会返回建议或总结，不会自动覆盖正文、设定、人物卡或大纲。是否继续？",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No,
        )
        return answer == QMessageBox.Yes

    def extract_ai_reply(self, data: dict[str, Any]) -> str:
        choices = data.get("choices") or []
        if not choices:
            return ""
        message = choices[0].get("message", {})
        content = message.get("content", "")
        if isinstance(content, list):
            return "".join(str(item.get("text", "")) if isinstance(item, dict) else str(item) for item in content).strip()
        return str(content).strip()

    def call_ai_chat_completion(self, settings: dict[str, Any], messages: list[dict[str, str]], max_tokens: int = 900) -> tuple[bool, str]:
        base_url = str(settings.get("base_url", "")).strip().rstrip("/")
        payload = {
            "model": str(settings.get("model", "")).strip(),
            "messages": messages,
            "max_tokens": max_tokens,
            "temperature": 0.4,
        }
        request = urllib.request.Request(
            f"{base_url}/chat/completions",
            data=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
            headers={
                "Authorization": f"Bearer {str(settings.get('api_key', '')).strip()}",
                "Content-Type": "application/json",
                "Accept": "application/json",
                "Connection": "close",
                "User-Agent": f"WenshaCreator/{APP_VERSION}",
            },
            method="POST",
        )
        try:
            with urllib.request.urlopen(request, timeout=60) as response:
                body = response.read().decode("utf-8", errors="replace")
        except urllib.error.HTTPError as exc:
            return False, f"AI 请求失败：HTTP {exc.code}。请检查 Key、Base URL 或模型名。"
        except urllib.error.URLError as exc:
            return False, f"AI 请求失败：{exc.reason}"
        except TimeoutError:
            return False, "AI 请求失败：连接超时。"
        try:
            data = json.loads(body)
        except json.JSONDecodeError:
            return False, "AI 请求失败：返回内容不是 JSON。"
        reply = self.extract_ai_reply(data)
        if not reply:
            return False, "AI 请求失败：未返回有效内容。"
        return True, reply

    def editor_ai_system_prompt(self) -> str:
        settings = self.ai_settings_for_request()
        return (
            f"{self.ai_role_instruction(settings)}\n\n"
            "你是本地小说创作软件中的 AI 助手。你只能基于本次提供的上下文回答，"
            "以建议、分析、总结为主。不要声称已经修改正文、设定、人物卡或大纲；"
            "如需要修改，只输出候选文本和理由，等待用户确认。"
        )

    def set_summary_ai_progress(self, text: str = "", busy: bool = False) -> None:
        self.summary_ai_progress_label.setText(text)
        self.summary_ai_progress_label.setVisible(bool(text))
        self.summary_generate_btn.setEnabled(not busy)
        self.ai_chapter_enabled_check.setEnabled(not busy)
        QApplication.processEvents()

    def set_editor_ai_streaming(self, active: bool) -> None:
        self.chat_send_btn.setEnabled(not active)
        self.chat_stop_btn.setEnabled(active)
        self.chat_clear_btn.setEnabled(not active)
        self.chat_input.setEnabled(not active)

    def append_editor_chat_text(self, text: str) -> None:
        cursor = self.chat_log.textCursor()
        cursor.movePosition(QTextCursor.End)
        cursor.insertText(text)
        self.chat_log.setTextCursor(cursor)
        self.chat_log.ensureCursorVisible()

    def start_editor_ai_stream(self, settings: dict[str, Any], messages: list[dict[str, str]], max_tokens: int = 900) -> None:
        self.editor_ai_stream_text = ""
        self.editor_ai_thread = AIStreamThread(settings, messages, max_tokens=max_tokens)
        self.editor_ai_thread.chunk_received.connect(self.on_editor_ai_stream_chunk)
        self.editor_ai_thread.result_ready.connect(self.on_editor_ai_stream_finished)
        self.editor_ai_thread.start()

    def on_editor_ai_stream_chunk(self, text: str) -> None:
        self.editor_ai_stream_text += text
        self.append_editor_chat_text(text)

    def on_editor_ai_stream_finished(self, ok: bool, message: str, stopped: bool) -> None:
        if message and (stopped or not ok or not self.editor_ai_stream_text.strip()):
            self.append_editor_chat_text(message)
        self.append_editor_chat_text("\n")
        self.set_editor_ai_streaming(False)
        if self.editor_ai_thread:
            self.editor_ai_thread.wait(1000)
            self.editor_ai_thread = None

    def stop_editor_ai_stream(self) -> None:
        if self.editor_ai_thread and self.editor_ai_thread.isRunning():
            self.editor_ai_thread.request_stop()
            self.chat_stop_btn.setEnabled(False)

    def request_chapter_summary(self) -> None:
        if not self.current_chapter_id:
            QMessageBox.information(self, "没有章节", "请先选择一个章节。")
            return
        self.save_current_chapter(silent=True)
        settings = self.ai_settings_for_request()
        ready, message = self.validate_editor_ai_ready(settings)
        if not ready:
            QMessageBox.information(self, "AI 总结", message)
            return
        sections = self.limited_ai_context(self.build_chapter_summary_context(), settings)
        if not self.confirm_ai_call("生成本章总结", sections, settings):
            return
        self.set_summary_ai_progress(self.ai_working_message(settings, "本章总结"), busy=True)
        messages = [
            {"role": "system", "content": self.editor_ai_system_prompt()},
            {
                "role": "user",
                "content": (
                    "请根据本次提供的当前章正文生成结构化章节总结。要求：\n"
                    "1. 只总结当前章节，不补写剧情。\n"
                    "2. 覆盖时间、地点、出场人物、关键事件、冲突变化、待回收伏笔。\n"
                    "3. 输出中文，条理清楚，便于后续 AI 聊天读取。\n\n"
                    f"{self.ai_context_text(sections)}"
                ),
            },
        ]
        try:
            ok, reply = self.call_ai_chat_completion(settings, messages, max_tokens=1200)
        finally:
            self.set_summary_ai_progress("", busy=False)
        if not ok:
            self.set_summary_ai_progress(f"{self.ai_role_name(settings)}：总结生成失败。")
            QMessageBox.warning(self, "AI 总结失败", reply)
            return
        self.summary_box.setPlainText(reply)
        self.save_current_chapter(silent=True)
        self.set_summary_ai_progress(f"{self.ai_role_name(settings)}：本章总结已生成，可继续手动编辑后保存。")

    def send_ai_message(self) -> None:
        question = self.chat_input.toPlainText().strip()
        if not question:
            return
        if self.editor_ai_thread and self.editor_ai_thread.isRunning():
            return
        self.save_current_chapter(silent=True)
        current_log = self.chat_log.toPlainText().strip()
        if current_log:
            current_log += "\n\n"
        current_log += f"你：{question}"
        settings = self.ai_settings_for_request()
        ready, message = self.validate_editor_ai_ready(settings)
        if not ready:
            current_log += f"\n\nAI：{message}"
            self.chat_log.setPlainText(current_log)
            self.chat_log.moveCursor(QTextCursor.End)
            self.chat_input.clear()
            return
        sections = self.limited_ai_context(self.build_editor_chat_context(), settings)
        if not self.confirm_ai_call("发送给 AI 聊天助手", sections, settings):
            return
        role_name = self.ai_role_name(settings)
        messages = [
            {"role": "system", "content": self.editor_ai_system_prompt()},
            {
                "role": "user",
                "content": (
                    "下面是本次允许读取的项目上下文。默认不包含完整正文。\n\n"
                    f"{self.ai_context_text(sections)}\n\n"
                    f"用户问题：{question}"
                ),
            },
        ]
        current_log += f"\n\n{role_name}："
        self.chat_log.setPlainText(current_log)
        self.chat_log.moveCursor(QTextCursor.End)
        self.chat_input.clear()
        self.set_editor_ai_streaming(True)
        self.start_editor_ai_stream(settings, messages)

    def clear_ai_chat(self) -> None:
        if self.editor_ai_thread and self.editor_ai_thread.isRunning():
            self.editor_ai_thread.request_stop()
        self.chat_log.setPlainText(
            "当前对话已清除。\n\nAI 聊天会在接口配置完成后启用；默认不直接读取完整正文。"
        )

    def set_status_button(self, status: str) -> None:
        self.chapter_status_btn.setText(f"● {status}")
        object_name = {"修订中": "StatusRevision", "草稿": "StatusDraft", "完稿": "StatusDone"}.get(status, "StatusDraft")
        self.chapter_status_btn.setObjectName(object_name)
        self.chapter_status_btn.style().unpolish(self.chapter_status_btn)
        self.chapter_status_btn.style().polish(self.chapter_status_btn)

    def set_chapter_status(self, status: str) -> None:
        if self.draft is None or not self.current_chapter_id:
            return
        found = DraftStore.find_chapter(self.draft, self.current_chapter_id)
        if not found:
            return
        _, chapter = found
        chapter["status"] = status
        self.set_status_button(status)
        DraftStore.save(self.selected_project, self.draft)
        self.populate_outline(self.current_chapter_id)

    def add_volume(self) -> None:
        if self.draft is None:
            self.load_editor_project()
        if self.draft is None:
            return
        title, ok = QInputDialog.getText(self, "新增卷", "卷名称：", text=f"第{len(self.draft.get('volumes', [])) + 1}卷")
        if not ok:
            return
        title = title.strip() or "新卷"
        self.save_current_chapter(silent=True)
        volume = {"id": DraftStore.new_id("vol"), "title": title, "chapters": []}
        self.draft.setdefault("volumes", []).append(volume)
        DraftStore.save(self.selected_project, self.draft)
        self.populate_outline()

    def add_chapter(self) -> None:
        if self.draft is None:
            self.load_editor_project()
        if self.draft is None:
            return
        self.save_current_chapter(silent=True)
        volume = self.selected_or_default_volume()
        if volume is None:
            volume = {"id": DraftStore.new_id("vol"), "title": "第1卷", "chapters": []}
            self.draft.setdefault("volumes", []).append(volume)
        title, ok = QInputDialog.getText(self, "新增章节", "章节名称：", text=f"第{len(volume.get('chapters', [])) + 1}章")
        if not ok:
            return
        title = title.strip() or "新章节"
        chapter = {
            "id": DraftStore.new_id("ch"),
            "title": title,
            "content": f"<h1 style='text-align:center;'>{title}</h1><p>{PARAGRAPH_INDENT}</p>",
            "summary": {"time": "", "place": "", "characters": "", "events": "尚未生成总结。", "key_sentence": ""},
            "status": "草稿",
            "updated_at": now_iso(),
        }
        volume.setdefault("chapters", []).append(chapter)
        self.current_chapter_id = chapter["id"]
        DraftStore.save(self.selected_project, self.draft)
        self.populate_outline(self.current_chapter_id)
        self.load_chapter(self.current_chapter_id)

    def rename_volume(self, volume_id: str) -> None:
        if self.draft is None:
            return
        volume = DraftStore.find_volume(self.draft, volume_id)
        if not volume:
            return
        title, ok = QInputDialog.getText(self, "更改卷名", "卷名称：", text=volume.get("title", "未命名卷"))
        if not ok:
            return
        title = title.strip()
        if not title:
            return
        volume["title"] = title
        DraftStore.save(self.selected_project, self.draft)
        self.populate_outline(self.current_chapter_id)
        if self.current_chapter_id:
            self.load_chapter(self.current_chapter_id)

    def rename_chapter(self, chapter_id: str) -> None:
        if self.draft is None:
            return
        found = DraftStore.find_chapter(self.draft, chapter_id)
        if not found:
            return
        _, chapter = found
        title, ok = QInputDialog.getText(self, "更改章节名", "章节名称：", text=chapter.get("title", "未命名章节"))
        if not ok:
            return
        title = title.strip()
        if not title:
            return
        chapter["title"] = title
        chapter["content"] = self.update_chapter_content_title(chapter.get("content", ""), title)
        if chapter_id == self.current_chapter_id:
            self.editor.setHtml(chapter["content"])
        DraftStore.save(self.selected_project, self.draft)
        self.populate_outline(self.current_chapter_id)
        if chapter_id == self.current_chapter_id:
            self.load_chapter(chapter_id)

    def update_chapter_content_title(self, html: str, title: str) -> str:
        text = QTextEdit()
        if html:
            text.setHtml(html)
        else:
            text.setPlainText(title)
        cursor = text.textCursor()
        cursor.movePosition(QTextCursor.Start)
        cursor.select(QTextCursor.LineUnderCursor)
        cursor.insertText(title)
        return text.toHtml()

    def selected_or_default_volume(self) -> dict[str, Any] | None:
        if self.draft is None:
            return None
        item = self.chapter_tree.currentItem()
        if item:
            data = item.data(0, Qt.UserRole) or {}
            if data.get("kind") == "volume":
                return DraftStore.find_volume(self.draft, data.get("id"))
            if data.get("kind") == "chapter":
                found = DraftStore.find_chapter(self.draft, data.get("id"))
                return found[0] if found else None
        volumes = self.draft.get("volumes", [])
        return volumes[0] if volumes else None

    def delete_selected_outline_item(self) -> None:
        if self.draft is None:
            return
        item = self.chapter_tree.currentItem()
        if not item:
            QMessageBox.information(self, "未选择", "请先选择要删除的卷或章节。")
            return
        data = item.data(0, Qt.UserRole) or {}
        if data.get("kind") == "chapter":
            self.delete_chapter(data.get("id"))
        elif data.get("kind") == "volume":
            self.delete_volume(data.get("id"))

    def delete_chapter(self, chapter_id: str) -> None:
        found = DraftStore.find_chapter(self.draft, chapter_id)
        if not found:
            return
        volume, chapter = found
        answer = QMessageBox.question(
            self,
            "删除章节",
            f"确定删除章节“{chapter.get('title', '未命名章节')}”吗？\n\n第一版会从目录中移除，并记录到草稿回收区。",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No,
        )
        if answer != QMessageBox.Yes:
            return
        self.save_current_chapter(silent=True)
        self.draft.setdefault("deleted_items", []).append({"type": "chapter", "deleted_at": now_iso(), "data": chapter})
        volume["chapters"] = [item for item in volume.get("chapters", []) if item.get("id") != chapter_id]
        self.after_outline_delete()

    def delete_volume(self, volume_id: str) -> None:
        volume = DraftStore.find_volume(self.draft, volume_id)
        if not volume:
            return
        chapters = volume.get("chapters", [])
        if chapters:
            confirm, ok = QInputDialog.getText(
                self,
                "删除卷",
                f"卷“{volume.get('title', '未命名卷')}”下有 {len(chapters)} 个章节。\n请输入卷名确认删除：",
            )
            if not ok or confirm.strip() != volume.get("title"):
                return
        else:
            answer = QMessageBox.question(
                self,
                "删除卷",
                f"确定删除卷“{volume.get('title', '未命名卷')}”吗？",
                QMessageBox.Yes | QMessageBox.No,
                QMessageBox.No,
            )
            if answer != QMessageBox.Yes:
                return
        self.save_current_chapter(silent=True)
        self.draft.setdefault("deleted_items", []).append({"type": "volume", "deleted_at": now_iso(), "data": volume})
        self.draft["volumes"] = [item for item in self.draft.get("volumes", []) if item.get("id") != volume_id]
        self.after_outline_delete()

    def after_outline_delete(self) -> None:
        first = DraftStore.first_chapter(self.draft)
        self.current_chapter_id = first[1]["id"] if first else None
        self.draft["current_chapter_id"] = self.current_chapter_id
        DraftStore.save(self.selected_project, self.draft)
        self.populate_outline(self.current_chapter_id)
        if self.current_chapter_id:
            self.load_chapter(self.current_chapter_id)
        else:
            self.editor.clear()
            self.summary_box.clear()
            self.chapter_title_label.setText("正文")

    def editor_undo(self) -> None:
        if self.current_page == "editor":
            self.editor.undo()
        elif self.current_page == "outline":
            self.outline_editor.undo()
        elif self.current_page == "worldbuilding":
            self.world_entry_editor.undo()
        elif self.current_page == "character":
            self.character_notes_editor.undo()

    def editor_redo(self) -> None:
        if self.current_page == "editor":
            self.editor.redo()
        elif self.current_page == "outline":
            self.outline_editor.redo()
        elif self.current_page == "worldbuilding":
            self.world_entry_editor.redo()
        elif self.current_page == "character":
            self.character_notes_editor.redo()

    def focus_find_box(self) -> None:
        if self.current_page != "editor":
            return
        self.find_edit.show()
        self.find_btn.show()
        self.find_edit.setFocus()
        self.find_edit.selectAll()

    def set_editor_alignment(self, alignment: Qt.AlignmentFlag) -> None:
        self.editor.setAlignment(alignment)

    def merge_editor_char_format(self, char_format: QTextCharFormat) -> None:
        cursor = self.editor.textCursor()
        if not cursor.hasSelection():
            self.editor.mergeCurrentCharFormat(char_format)
            return
        cursor.mergeCharFormat(char_format)
        self.editor.setTextCursor(cursor)
        self.editor.mergeCurrentCharFormat(char_format)

    def sync_editor_toolbar_state(self) -> None:
        if not hasattr(self, "editor") or not hasattr(self, "font_box") or not hasattr(self, "font_size_spin") or self.current_page != "editor":
            return
        char_format = self.editor.currentCharFormat()
        family = char_format.font().family() or self.editor.body_font_family
        size = char_format.fontPointSize()
        if size <= 0:
            size = self.editor.title_font_size if self.editor.textCursor().blockNumber() == 0 else self.editor.body_font_size

        self.font_box.blockSignals(True)
        self.font_size_spin.blockSignals(True)
        self.font_size_box.blockSignals(True)
        if family:
            self.font_box.setCurrentFont(QFont(family))
        self.font_size_spin.setValue(int(round(size)))
        self.font_size_box.setCurrentText(str(int(round(size))))
        self.font_size_spin.blockSignals(False)
        self.font_size_box.blockSignals(False)
        self.font_box.blockSignals(False)

    def change_editor_font(self, font: QFont) -> None:
        family = font.family()
        self.editor.set_editor_style(family, self.font_size_spin.value(), self.line_spacing_spin.value())
        self.font_box.blockSignals(True)
        self.font_box.setCurrentFont(QFont(family))
        self.font_box.blockSignals(False)
        char_format = QTextCharFormat()
        char_format.setFontFamily(family)
        self.merge_editor_char_format(char_format)
        self.update_editor_setting("font_family", family)

    def change_editor_font_size(self, size: int) -> None:
        self.editor.set_editor_style(self.editor.body_font_family, size, self.line_spacing_spin.value())
        self.font_size_spin.blockSignals(True)
        self.font_size_box.blockSignals(True)
        self.font_size_spin.setValue(size)
        self.font_size_box.setCurrentText(str(size))
        self.font_size_spin.blockSignals(False)
        self.font_size_box.blockSignals(False)
        char_format = QTextCharFormat()
        char_format.setFontPointSize(size)
        self.merge_editor_char_format(char_format)
        self.update_editor_setting("font_size", size)

    def on_font_size_box_changed(self, value: str) -> None:
        try:
            size = int(value)
        except ValueError:
            return
        self.apply_editor_font_size(size)

    def change_editor_line_spacing(self, spacing: int) -> None:
        self.editor.set_editor_style(self.editor.body_font_family, self.font_size_spin.value(), spacing)
        self.update_editor_setting("line_spacing", spacing)

    def apply_editor_font_family(self, family: str) -> None:
        self.font_box.blockSignals(True)
        self.font_box.setCurrentFont(QFont(family))
        self.font_box.blockSignals(False)
        self.change_editor_font(QFont(family))

    def apply_editor_font_size(self, size: int) -> None:
        self.font_size_spin.blockSignals(True)
        self.font_size_box.blockSignals(True)
        self.font_size_spin.setValue(size)
        self.font_size_box.setCurrentText(str(size))
        self.font_size_spin.blockSignals(False)
        self.font_size_box.blockSignals(False)
        self.change_editor_font_size(size)

    def apply_editor_line_spacing(self, spacing: int) -> None:
        self.line_spacing_spin.blockSignals(True)
        self.line_spacing_spin.setValue(spacing)
        self.line_spacing_spin.blockSignals(False)
        self.change_editor_line_spacing(spacing)

    def clear_editor_format(self) -> None:
        cursor = self.editor.textCursor()
        if not cursor.hasSelection():
            cursor.select(QTextCursor.LineUnderCursor)
        char_format = self.editor.body_char_format()
        block_format = self.editor.body_block_format()
        cursor.mergeCharFormat(char_format)
        cursor.mergeBlockFormat(block_format)
        self.editor.setTextCursor(cursor)

    def update_word_count(self) -> None:
        if not hasattr(self, "word_count_label"):
            return
        count = len("".join(self.editor.toPlainText().split()))
        project = self.selected_project
        today = project.today_words if project else count
        saved_at = fmt_time(project.last_manual_save_at) if project and project.last_manual_save_at else "尚未保存"
        self.word_count_label.setText(f"本章 {count} 字 · 今日 {today} 字 · 上次保存 {saved_at}")

    def toggle_bold(self) -> None:
        if self.current_page == "editor":
            weight = QFont.Normal if self.editor.fontWeight() == QFont.Bold else QFont.Bold
            self.editor.setFontWeight(weight)
        elif self.current_page == "outline":
            weight = QFont.Normal if self.outline_editor.fontWeight() == QFont.Bold else QFont.Bold
            self.outline_editor.setFontWeight(weight)
        elif self.current_page == "worldbuilding":
            weight = QFont.Normal if self.world_entry_editor.fontWeight() == QFont.Bold else QFont.Bold
            self.world_entry_editor.setFontWeight(weight)
        elif self.current_page == "character":
            weight = QFont.Normal if self.character_notes_editor.fontWeight() == QFont.Bold else QFont.Bold
            self.character_notes_editor.setFontWeight(weight)

    def apply_heading(self) -> None:
        target = (
            self.editor
            if self.current_page == "editor"
            else self.outline_editor
            if self.current_page == "outline"
            else self.world_entry_editor
            if self.current_page == "worldbuilding"
            else self.character_notes_editor
            if self.current_page == "character"
            else None
        )
        if target is None:
            return
        cursor = target.textCursor()
        cursor.select(QTextCursor.LineUnderCursor)
        text = cursor.selectedText().strip() or "标题"
        cursor.insertHtml(f"<h2>{text}</h2>")

    def apply_comment_style(self) -> None:
        target = (
            self.editor
            if self.current_page == "editor"
            else self.outline_editor
            if self.current_page == "outline"
            else self.world_entry_editor
            if self.current_page == "worldbuilding"
            else self.character_notes_editor
            if self.current_page == "character"
            else None
        )
        if target is None:
            return
        cursor = target.textCursor()
        selected = cursor.selectedText().strip() or "批注"
        cursor.insertHtml(f"<span style='background-color:#F5EBD0;color:#466A8C;'>【批注：{selected}】</span>")

    def find_in_editor(self) -> None:
        keyword = self.find_edit.text().strip()
        if not keyword:
            return
        if not self.editor.find(keyword):
            cursor = self.editor.textCursor()
            cursor.movePosition(QTextCursor.Start)
            self.editor.setTextCursor(cursor)
            if not self.editor.find(keyword):
                QMessageBox.information(self, "未找到", f"没有找到“{keyword}”。")

    def build_project_list(self) -> QWidget:
        box = QFrame()
        box.setObjectName("Card")
        layout = QVBoxLayout(box)
        layout.setContentsMargins(18, 18, 18, 20)
        layout.setSpacing(12)

        header = QLabel("最近项目")
        header.setObjectName("SectionTitle")
        sub = QLabel("用于快速切换，详情看左侧概览")
        sub.setObjectName("Muted")
        layout.addWidget(header)
        layout.addWidget(sub)

        self.project_list = QListWidget()
        self.project_list.setObjectName("RecentList")
        self.project_list.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.project_list.setAlternatingRowColors(False)
        self.project_list.itemSelectionChanged.connect(self.on_project_selected)
        layout.addWidget(self.project_list, 1)

        self.management_btn = QPushButton("项目管理")
        self.management_btn.setObjectName("ProjectMenuButton")
        self.management_btn.setMenu(self.build_project_management_menu())
        layout.addWidget(self.management_btn)

        hint = QLabel("路径失效的项目可以重新关联或从备份恢复。")
        hint.setObjectName("Muted")
        hint.setWordWrap(True)
        layout.addWidget(hint)
        return box

    def build_project_management_menu(self) -> QMenu:
        menu = QMenu(self)
        menu.addAction("从最近项目移除", self.remove_selected_from_recent)
        menu.addAction("重新关联路径", self.relink_selected_project)
        menu.addAction("打开项目文件夹", self.open_project_folder)
        menu.addSeparator()
        menu.addAction("删除项目文件...", self.delete_selected_project)
        return menu

    def build_project_detail(self) -> QWidget:
        box = QFrame()
        box.setObjectName("Card")
        layout = QVBoxLayout(box)
        layout.setContentsMargins(22, 18, 22, 20)
        layout.setSpacing(14)

        title = QLabel("项目概览")
        title.setObjectName("SectionTitle")
        subtitle = QLabel("打开前判断是否安全继续写")
        subtitle.setObjectName("Muted")
        layout.addWidget(title)
        layout.addWidget(subtitle)

        overview_top = QHBoxLayout()
        overview_top.setSpacing(24)

        cover_col = QVBoxLayout()
        cover_col.setSpacing(10)
        self.cover = QLabel("")
        self.cover.setObjectName("CoverBox")
        self.cover.setFixedSize(220, 311)
        self.cover.setAlignment(Qt.AlignCenter)
        cover_col.addWidget(self.cover, 0, Qt.AlignLeft | Qt.AlignTop)
        cover_btn = QPushButton("编辑图片")
        cover_btn.setObjectName("CoverButton")
        cover_btn.clicked.connect(self.change_project_cover)
        cover_col.addWidget(cover_btn)
        cover_col.addStretch(1)
        overview_top.addLayout(cover_col)

        info_panel = QFrame()
        info_panel.setObjectName("OverviewInfo")
        info_layout = QVBoxLayout(info_panel)
        info_layout.setContentsMargins(18, 14, 18, 14)
        info_layout.setSpacing(14)

        title_row = QHBoxLayout()
        title_group = QVBoxLayout()
        title_group.setSpacing(4)
        self.detail_project_name = QLabel("-")
        self.detail_project_name.setObjectName("ProjectName")
        self.detail_stage = QLabel("-")
        self.detail_stage.setObjectName("Muted")
        title_group.addWidget(self.detail_project_name)
        title_group.addWidget(self.detail_stage)
        edit_title_btn = QPushButton("编辑标题")
        edit_title_btn.setObjectName("SmallButton")
        edit_title_btn.clicked.connect(self.rename_current_project)
        self.health_badge = QLabel("-")
        self.health_badge.setObjectName("HealthBadge")
        self.health_badge.setAlignment(Qt.AlignCenter)
        title_row.addLayout(title_group, 1)
        title_row.addWidget(edit_title_btn)
        title_row.addWidget(self.health_badge)
        info_layout.addLayout(title_row)

        self.primary_labels: dict[str, QLabel] = {}
        for label, key in [
            ("总字数 / 今日新增", "words"),
            ("当前章节", "current_position"),
        ]:
            stat = QFrame()
            stat.setObjectName("StatRow")
            stat_layout = QVBoxLayout(stat)
            stat_layout.setContentsMargins(12, 8, 12, 8)
            stat_layout.setSpacing(3)
            name_label = QLabel(label)
            name_label.setObjectName("StatLabel")
            value_label = QLabel("-")
            value_label.setObjectName("StatValue")
            value_label.setWordWrap(True)
            stat_layout.addWidget(name_label)
            stat_layout.addWidget(value_label)
            info_layout.addWidget(stat)
            self.primary_labels[key] = value_label
        info_layout.addStretch(1)
        overview_top.addWidget(info_panel, 1)
        layout.addLayout(overview_top)

        self.detail_grid = QGridLayout()
        self.detail_grid.setHorizontalSpacing(22)
        self.detail_grid.setVerticalSpacing(12)
        self.detail_labels: dict[str, QLabel] = {}
        fields = [
            ("上次手动保存", "last_manual_save_at"),
            ("上次自动保存", "last_auto_save_at"),
            ("最近备份", "last_backup_at"),
            ("摘要状态", "pending_summaries"),
            ("资源状态", "resources_status"),
        ]
        for row, (label, key) in enumerate(fields):
            name_label = QLabel(label)
            name_label.setObjectName("DetailName")
            value_label = QLabel("-")
            value_label.setWordWrap(True)
            self.detail_grid.addWidget(name_label, row, 0)
            self.detail_grid.addWidget(value_label, row, 1)
            self.detail_labels[key] = value_label
        layout.addLayout(self.detail_grid)
        layout.addStretch(1)

        actions = QHBoxLayout()
        open_btn = QPushButton("继续写作")
        open_btn.setObjectName("PrimaryButton")
        open_btn.clicked.connect(self.open_selected_project)
        inspect_btn = QPushButton("打开项目资料")
        inspect_btn.clicked.connect(self.open_selected_project)
        relink_btn = QPushButton("重新关联")
        relink_btn.clicked.connect(self.relink_selected_project)
        backup_btn = QPushButton("从备份恢复")
        backup_btn.clicked.connect(lambda: QMessageBox.information(self, "从备份恢复", "备份恢复会在后续数据模块中实现。"))
        actions.addWidget(open_btn)
        actions.addWidget(inspect_btn)
        actions.addWidget(relink_btn)
        actions.addWidget(backup_btn)
        layout.addLayout(actions)
        return box

    def refresh_projects(self, keep_project: ProjectMeta | None = None) -> None:
        keep_project = keep_project or self.selected_project
        keep_path = str(Path(keep_project.path)) if keep_project else None
        self.project_list.blockSignals(True)
        self.project_list.clear()
        for row, project in enumerate(self.store.recent):
            path_exists = Path(project.path).exists()
            health = project.health if path_exists else "路径不存在"
            health_color = project.health_color if path_exists else "accent"
            item = QListWidgetItem(
                f"{project.name}\n"
                f"{project.writing_stage} · {health}\n"
                f"自动保存 {relative_time(project.last_auto_save_at)}"
            )
            item.setData(Qt.UserRole, row)
            item.setToolTip(project.path)
            item.setForeground(QColor(PALETTE.get(health_color, PALETTE["ink"])))
            item.setFont(QFont("Microsoft YaHei", 10, QFont.Bold))
            item.setSizeHint(QSize(260, 76))
            self.project_list.addItem(item)
        if self.store.recent:
            selected_row = 0
            if keep_path:
                for idx, project in enumerate(self.store.recent):
                    if str(Path(project.path)) == keep_path:
                        selected_row = idx
                        break
            self.project_list.setCurrentRow(selected_row)
            self.selected_project = self.store.recent[selected_row]
        else:
            self.selected_project = None
        self.project_list.blockSignals(False)
        self.management_btn.setEnabled(bool(self.selected_project))
        self.update_detail()
        self.update_status_line()

    def on_project_selected(self) -> None:
        item = self.project_list.currentItem()
        if not item:
            return
        row = item.data(Qt.UserRole)
        if 0 <= row < len(self.store.recent):
            self.selected_project = self.store.recent[row]
            self.update_detail()

    def update_detail(self) -> None:
        project = self.selected_project
        if not project:
            for label in self.detail_labels.values():
                label.setText("-")
            for label in self.primary_labels.values():
                label.setText("-")
            self.detail_project_name.setText("-")
            self.detail_stage.setText("-")
            self.health_badge.setText("-")
            self.cover.clear()
            return
        cover_path = self.project_cover_path(project)
        if cover_path and cover_path.exists():
            if pixmap := cached_pixmap(cover_path, QSize(206, 292)):
                self.cover.setPixmap(pixmap)
        elif logo := white_logo_pixmap(QSize(142, 102)):
            self.cover.setPixmap(logo)
        else:
            self.cover.setText(project.name[:6] or "封面")
        path_exists = Path(project.path).exists()
        health = project.health if path_exists else "路径不存在"
        health_color = project.health_color if path_exists else "accent"
        self.detail_project_name.setText(project.name)
        self.detail_stage.setText(f"{project.writing_stage} · {project.template}")
        self.health_badge.setText(health)
        self.health_badge.setProperty("tone", health_color)
        self.health_badge.style().unpolish(self.health_badge)
        self.health_badge.style().polish(self.health_badge)
        self.primary_labels["current_position"].setText(project.current_position)
        self.primary_labels["words"].setText(f"{project.total_words:,} / {project.today_words:,}")
        self.detail_labels["last_manual_save_at"].setText(fmt_time(project.last_manual_save_at))
        self.detail_labels["last_auto_save_at"].setText(f"{relative_time(project.last_auto_save_at)} · {fmt_time(project.last_auto_save_at)}")
        self.detail_labels["last_backup_at"].setText(fmt_time(project.last_backup_at))
        self.detail_labels["pending_summaries"].setText(f"{project.pending_summaries} 章待更新")
        self.detail_labels["resources_status"].setText(project.resources_status)

    def project_cover_path(self, project: ProjectMeta) -> Path | None:
        if not project.cover_image_path:
            return None
        path = Path(project.cover_image_path)
        if not path.is_absolute():
            path = Path(project.path) / path
        return path

    def change_project_cover(self) -> None:
        project = self.selected_project
        if not project:
            QMessageBox.information(self, "没有项目", "请先选择或创建一个项目。")
            return
        project_dir = Path(project.path)
        if not project_dir.exists():
            QMessageBox.warning(self, "路径不存在", "项目路径不存在，无法保存图片。")
            return
        file_name, _ = QFileDialog.getOpenFileName(
            self,
            "选择项目概览图片",
            str(project_dir),
            "图片文件 (*.png *.jpg *.jpeg *.webp *.bmp)",
        )
        if not file_name:
            return
        source = Path(file_name)
        if source.suffix.lower() not in IMAGE_EXTENSIONS:
            QMessageBox.warning(self, "格式不支持", "请选择 png、jpg、jpeg、webp 或 bmp 图片。")
            return
        cover_dir = project_dir / "assets" / "covers"
        cover_dir.mkdir(parents=True, exist_ok=True)
        target = cover_dir / f"project_cover{source.suffix.lower()}"
        try:
            if source.resolve() != target.resolve():
                shutil.copyfile(source, target)
            project.cover_image_path = str(target.relative_to(project_dir))
            project.last_manual_save_at = now_iso()
            self.store.write_project(project)
            self.store.save_recent()
        except OSError as exc:
            QMessageBox.critical(self, "图片保存失败", str(exc))
            return
        self.selected_project = project
        self.refresh_projects(keep_project=project)

    def rename_current_project(self) -> None:
        project = self.selected_project
        if not project:
            QMessageBox.information(self, "没有项目", "请先选择或创建一个项目。")
            return
        if not Path(project.path).exists():
            QMessageBox.warning(self, "路径不存在", "项目路径不存在，请先重新关联项目。")
            return
        new_name, ok = QInputDialog.getText(self, "编辑标题", "项目标题：", text=project.name)
        if not ok:
            return
        new_name = new_name.strip()
        if not new_name:
            QMessageBox.warning(self, "标题为空", "项目标题不能为空。")
            return
        if new_name == project.name:
            return
        project.name = new_name
        project.last_manual_save_at = now_iso()
        try:
            self.store.write_project(project)
            self.store.save_recent()
        except OSError as exc:
            QMessageBox.critical(self, "标题保存失败", str(exc))
            return
        self.selected_project = project
        self.refresh_projects(keep_project=project)

    def update_status_line(self) -> None:
        project = self.selected_project
        if project and self.current_page == "editor":
            self.status_line.setText(f"{project.name} · 自动保存默认 {project.auto_save_minutes} 分钟")
        elif project:
            self.status_line.setText(
                f"自动保存默认 {project.auto_save_minutes} 分钟 · "
                f"上次自动保存 {relative_time(project.last_auto_save_at)}"
            )
        else:
            self.status_line.setText("自动保存默认 10 分钟 · 尚未选择项目")

    def new_project(self) -> None:
        dialog = NewProjectDialog(self)
        if dialog.exec() != QDialog.Accepted:
            return
        try:
            project = self.store.create_project(**dialog.values())
        except OSError as exc:
            QMessageBox.critical(self, "创建失败", f"无法创建项目：{exc}")
            return
        self.selected_project = project
        self.refresh_projects(keep_project=project)
        QMessageBox.information(self, "项目已创建", f"已创建项目：{project.name}")

    def open_project(self) -> None:
        folder = QFileDialog.getExistingDirectory(self, "选择小说项目文件夹", str(APP_DIR))
        if not folder:
            return
        try:
            project = self.store.open_project(Path(folder))
        except (OSError, ValueError, json.JSONDecodeError) as exc:
            QMessageBox.warning(self, "无法打开项目", str(exc))
            return
        self.selected_project = project
        self.refresh_projects(keep_project=project)

    def open_selected_project(self) -> None:
        project = self.selected_project
        if not project:
            return
        if not Path(project.path).exists():
            QMessageBox.warning(self, "路径不存在", "项目路径不存在，请重新关联或从备份恢复。")
            return
        self.switch_page("editor")

    def relink_selected_project(self) -> None:
        project = self.selected_project
        if not project:
            return
        folder = QFileDialog.getExistingDirectory(self, "重新选择项目位置", str(APP_DIR))
        if not folder:
            return
        config = Path(folder) / PROJECT_CONFIG
        if not config.exists():
            QMessageBox.warning(self, "无法关联", "所选文件夹缺少 project.json。")
            return
        try:
            relinked = self.store.open_project(Path(folder))
        except (OSError, ValueError, json.JSONDecodeError) as exc:
            QMessageBox.warning(self, "无法关联", str(exc))
            return
        self.selected_project = relinked
        self.refresh_projects(keep_project=relinked)

    def open_project_folder(self) -> None:
        project = self.selected_project
        if not project:
            return
        project_path = Path(project.path)
        if not project_path.exists():
            QMessageBox.warning(self, "路径不存在", "项目路径不存在，请先重新关联项目。")
            return
        QDesktopServices.openUrl(QUrl.fromLocalFile(str(project_path)))

    def remove_selected_from_recent(self) -> None:
        project = self.selected_project
        if not project:
            return
        answer = QMessageBox.question(
            self,
            "从最近项目移除",
            f"只从最近项目列表移除“{project.name}”，不会删除本地文件。是否继续？",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No,
        )
        if answer != QMessageBox.Yes:
            return
        self.remove_project_record(project)

    def delete_selected_project(self) -> None:
        project = self.selected_project
        if not project:
            return
        project_path = Path(project.path)
        if not project_path.exists():
            QMessageBox.warning(self, "路径不存在", "项目路径不存在，无法删除文件。可以使用“从最近项目移除”。")
            return
        confirm, ok = QInputDialog.getText(
            self,
            "删除项目文件",
            f"将把项目文件夹移入回收站。\n请输入项目标题“{project.name}”确认：",
        )
        if not ok:
            return
        if confirm.strip() != project.name:
            QMessageBox.warning(self, "确认失败", "输入的项目标题不一致，已取消删除。")
            return
        try:
            move_path_to_recycle_bin(project_path)
        except OSError as exc:
            QMessageBox.critical(self, "删除失败", str(exc))
            return
        self.remove_project_record(project)
        QMessageBox.information(self, "已删除", f"项目“{project.name}”已移入回收站。")

    def remove_project_record(self, project: ProjectMeta) -> None:
        normalized = str(Path(project.path))
        old_index = 0
        for idx, item in enumerate(self.store.recent):
            if str(Path(item.path)) == normalized:
                old_index = idx
                break
        self.store.recent = [item for item in self.store.recent if str(Path(item.path)) != normalized]
        self.store.save_recent()
        if self.store.recent:
            next_index = min(old_index, len(self.store.recent) - 1)
            self.selected_project = self.store.recent[next_index]
        else:
            self.selected_project = None
        self.refresh_projects(keep_project=self.selected_project)

    def save_current_project(self) -> None:
        if self.current_page == "settings":
            self.save_app_settings_from_ui()
            return
        if self.current_page == "editor":
            self.save_current_chapter()
            return
        if self.current_page == "outline":
            self.save_current_outline_node(silent=True)
        if self.current_page == "worldbuilding":
            self.save_current_world_entry(silent=True)
        if self.current_page == "character":
            self.save_current_character(silent=True)
        project = self.selected_project
        if not project:
            QMessageBox.information(self, "没有项目", "请先选择或创建一个项目。")
            return
        if not Path(project.path).exists():
            QMessageBox.warning(self, "路径不存在", "项目路径不存在，无法保存。")
            return
        project.last_manual_save_at = now_iso()
        project.last_auto_save_at = now_iso()
        try:
            if self.current_page in {"outline", "worldbuilding", "character"} and self.draft is not None:
                DraftStore.save(project, self.draft)
            self.store.write_project(project)
            self.store.add_recent(project)
        except OSError as exc:
            QMessageBox.critical(self, "保存失败", str(exc))
            return
        if self.current_page == "home":
            self.refresh_projects(keep_project=project)
        elif self.current_page == "outline":
            self.update_outline_status()
        elif self.current_page == "worldbuilding":
            self.update_world_status()
        elif self.current_page == "character":
            self.update_character_status()
        QMessageBox.information(self, "已保存", "已保存当前项目。")

    def apply_styles(self) -> None:
        settings = getattr(self, "app_settings", default_app_settings())
        if self.preview_app_settings is not None:
            settings = self.preview_app_settings
        ui_scale = int(settings.get("ui_scale", 100) or 100)
        base_font_size = max(12, round(14 * ui_scale / 100))
        eye_mode = bool(settings.get("eye_mode"))
        if eye_mode:
            content_bg = "#DDEED8"
            page_bg = "#EAF4E8"
            pane_bg = "#E8F3E2"
            center_bg = "#EEF7EA"
            paper_bg = "#F7FCF2"
            card_bg = "#F8FCF4"
            editor_bg = "#EEF8E7"
            field_bg = "#F4FAEF"
            field_hover_bg = "#E8F3E2"
            field_focus_bg = "#FEFFF9"
            panel_bg = "#E6F0E1"
            control_bg = "#F3F9EE"
            selected_bg = "#DCEBD6"
            scope_bg = "#D9EBD3"
            muted_box_bg = "#EAF4E6"
            scrollbar_bg = "#D3E5CC"
        else:
            content_bg = PALETTE["bg"]
            page_bg = "#F6F9F5"
            pane_bg = "#F4F8F3"
            center_bg = "#F8FAF7"
            paper_bg = PALETTE["paper"]
            card_bg = "#FFFDFC"
            editor_bg = PALETTE["paper"]
            field_bg = "#FAFAF7"
            field_hover_bg = PALETTE["panel"]
            field_focus_bg = "#FFFFFF"
            panel_bg = PALETTE["panel"]
            control_bg = "#FAFAF7"
            selected_bg = PALETTE["soft_yellow"]
            scope_bg = PALETTE["soft_green"]
            muted_box_bg = "#F1F5EF"
            scrollbar_bg = PALETTE["panel"]
        self.setStyleSheet(
            f"""
            QWidget {{
                background: {content_bg};
                color: {PALETTE["ink"]};
                font-family: "Microsoft YaHei";
                font-size: {base_font_size}px;
            }}
            QLabel {{
                background: transparent;
            }}
            #Sidebar {{
                background: {PALETTE["nav"]};
            }}
            #LogoMark {{
                background: transparent;
            }}
            #Logo {{
                background: transparent;
                color: #FFFFFF;
                font-family: "Microsoft YaHei UI", "Microsoft YaHei";
                font-size: 21px;
                font-weight: 700;
            }}
            #SidebarSub {{
                background: transparent;
                color: #CAD7D1;
                font-size: 12px;
            }}
            #SidebarVersion {{
                background: transparent;
                color: #CAD7D1;
                font-size: 12px;
            }}
            #NavItem {{
                background: transparent;
                border: none;
                color: #DBE2DC;
                padding: 11px 14px;
                border-radius: 8px;
                text-align: left;
            }}
            #NavActive {{
                color: {PALETTE["nav"]};
                background: {paper_bg};
                border: none;
                padding: 11px 14px;
                border-radius: 8px;
                font-weight: 700;
                text-align: left;
            }}
            #Content {{
                background: {content_bg};
            }}
            #EditorPage {{
                background: {page_bg};
            }}
            #EditorChapterPane {{
                background: {pane_bg};
                border-right: 1px solid {PALETTE["line"]};
            }}
            #EditorCenterPane {{
                background: {center_bg};
                border-right: 1px solid {PALETTE["line"]};
            }}
            #EditorAIPane {{
                background: {pane_bg};
            }}
            #OutlinePage {{
                background: {page_bg};
            }}
            #WorldbuildingPage {{
                background: {page_bg};
            }}
            #CharacterPage {{
                background: {page_bg};
            }}
            #SettingsPage {{
                background: {page_bg};
            }}
            #CharacterEditorScroll {{
                background: transparent;
                border: none;
            }}
            #CharacterEditorScroll > QWidget > QWidget {{
                background: transparent;
            }}
            #OutlineDirectoryPane {{
                background: {pane_bg};
                border: 1px solid {PALETTE["line"]};
                border-radius: 8px;
            }}
            #WorldDirectoryPane {{
                background: {pane_bg};
                border: 1px solid {PALETTE["line"]};
                border-radius: 8px;
            }}
            #CharacterListPane {{
                background: {pane_bg};
                border: 1px solid {PALETTE["line"]};
                border-radius: 8px;
            }}
            #OutlineEditorPane {{
                background: {card_bg};
                border: 1px solid {PALETTE["line"]};
                border-radius: 8px;
            }}
            #WorldEditorPane {{
                background: {card_bg};
                border: 1px solid {PALETTE["line"]};
                border-radius: 8px;
            }}
            #CharacterEditorPane {{
                background: {card_bg};
                border: 1px solid {PALETTE["line"]};
                border-radius: 8px;
            }}
            #OutlineAIPane {{
                background: {card_bg};
                border: 1px solid {PALETTE["line"]};
                border-radius: 8px;
            }}
            #WorldAIPane {{
                background: {card_bg};
                border: 1px solid {PALETTE["line"]};
                border-radius: 8px;
            }}
            #CharacterAIPane {{
                background: {card_bg};
                border: 1px solid {PALETTE["line"]};
                border-radius: 8px;
            }}
            #SettingsScroll {{
                background: transparent;
                border: none;
            }}
            #SettingsScroll > QWidget > QWidget {{
                background: transparent;
            }}
            #SettingsInlineGroup {{
                background: transparent;
            }}
            #SettingsCard {{
                background: {card_bg};
                border: 1px solid {PALETTE["line"]};
                border-radius: 8px;
            }}
            #SettingsDangerCard {{
                background: {card_bg};
                border: 1px solid #E6C5C0;
                border-radius: 8px;
            }}
            #SettingsCardTitle {{
                background: transparent;
                color: {PALETTE["ink"]};
                font-size: 18px;
                font-weight: 800;
            }}
            #SettingsRowLabel {{
                background: transparent;
                color: {PALETTE["blue"]};
                font-size: 12px;
                font-weight: 800;
                min-width: 84px;
            }}
            #SettingsValueLabel {{
                background: {field_bg};
                border: 1px solid {PALETTE["line"]};
                border-radius: 8px;
                padding: 8px 10px;
                color: {PALETTE["ink"]};
            }}
            #SettingsInput, #SettingsCombo {{
                background: {field_bg};
                border: 1px solid {PALETTE["line"]};
                border-radius: 8px;
                min-height: 34px;
                padding: 0 28px 0 10px;
                color: {PALETTE["ink"]};
                selection-background-color: {selected_bg};
            }}
            #SettingsInput:focus, #SettingsCombo:focus {{
                background: {field_focus_bg};
                border-color: {PALETTE["nav2"]};
            }}
            #SettingsCombo::drop-down {{
                subcontrol-origin: padding;
                subcontrol-position: top right;
                width: 24px;
                border-left: 1px solid {PALETTE["line"]};
                border-top-right-radius: 7px;
                border-bottom-right-radius: 7px;
                background: {muted_box_bg};
            }}
            #SettingsCombo QLineEdit {{
                background: transparent;
                border: none;
                padding: 0 0 0 2px;
                min-height: 30px;
                color: {PALETTE["ink"]};
            }}
            #SettingsCombo QAbstractItemView {{
                background: {paper_bg};
                border: 1px solid {PALETTE["line"]};
                border-radius: 8px;
                padding: 4px;
                outline: none;
                selection-background-color: {selected_bg};
                selection-color: {PALETTE["ink"]};
            }}
            #SettingsScopeBox {{
                background: {scope_bg};
                border: 1px solid #C9DED2;
                border-radius: 8px;
                padding: 10px;
                color: {PALETTE["green"]};
                font-size: 12px;
            }}
            #ShortcutKey {{
                background: {muted_box_bg};
                border: 1px solid {PALETTE["line"]};
                border-radius: 7px;
                padding: 5px 9px;
                min-width: 142px;
                font-weight: 800;
            }}
            #DangerButton {{
                background: {PALETTE["soft_red"]};
                color: {PALETTE["accent"]};
                border: 1px solid #DDA5A0;
                font-weight: 800;
            }}
            #DangerButton:hover {{
                background: #F1D5D0;
            }}
            #SuccessBadge {{
                background: {PALETTE["soft_green"]};
                color: {PALETTE["green"]};
                border: 1px solid #C9DED2;
                border-radius: 8px;
                padding: 8px 10px;
                font-weight: 800;
            }}
            #ErrorBadge {{
                background: {PALETTE["soft_red"]};
                color: {PALETTE["accent"]};
                border: 1px solid #E6C5C0;
                border-radius: 8px;
                padding: 8px 10px;
                font-weight: 800;
            }}
            #OutlineTimelinePane {{
                background: {card_bg};
                border: 1px solid {PALETTE["line"]};
                border-radius: 8px;
            }}
            #OutlineGoalBox {{
                background: {field_bg};
                border: 1px solid {PALETTE["line"]};
                border-radius: 8px;
            }}
            #WorldImageBox {{
                background: {card_bg};
                border: 1px solid {PALETTE["line"]};
                border-radius: 8px;
            }}
            #WorldImagePreview {{
                background: {muted_box_bg};
                border: 1px dashed {PALETTE["line"]};
                border-radius: 8px;
                color: {PALETTE["muted"]};
                font-size: 12px;
            }}
            #CharacterPortraitBox, #CharacterTagBox, #CharacterHistoryBox, #CharacterRelationBox {{
                background: {card_bg};
                border: 1px solid {PALETTE["line"]};
                border-radius: 8px;
            }}
            #CharacterPortraitPreview {{
                background: {muted_box_bg};
                border: 1px dashed {PALETTE["line"]};
                border-radius: 8px;
                color: {PALETTE["muted"]};
                font-size: 12px;
            }}
            #PageTitle {{
                background: transparent;
                font-size: 30px;
                font-weight: 800;
            }}
            #SectionTitle {{
                background: transparent;
                font-size: 21px;
                font-weight: 800;
            }}
            #ProjectName {{
                background: transparent;
                color: {PALETTE["ink"]};
                font-size: 26px;
                font-weight: 800;
            }}
            #OverviewInfo {{
                background: {card_bg};
                border: 1px solid {PALETTE["line"]};
                border-radius: 8px;
            }}
            #StatRow {{
                background: {panel_bg};
                border: 1px solid {PALETTE["line"]};
                border-radius: 8px;
            }}
            #StatLabel {{
                background: transparent;
                color: {PALETTE["blue"]};
                font-size: 12px;
                font-weight: 700;
            }}
            #StatValue {{
                background: transparent;
                color: {PALETTE["ink"]};
                font-size: 18px;
                font-weight: 800;
            }}
            #Muted {{
                background: transparent;
                color: {PALETTE["muted"]};
                font-size: 12px;
            }}
            #Card {{
                background: {card_bg};
                border: 1px solid {PALETTE["line"]};
                border-radius: 8px;
            }}
            QPushButton {{
                background: {paper_bg};
                border: 1px solid {PALETTE["line"]};
                border-radius: 8px;
                padding: 8px 14px;
            }}
            QPushButton:hover {{
                background: {field_hover_bg};
            }}
            QCheckBox {{
                background: transparent;
                color: {PALETTE["ink"]};
                spacing: 8px;
            }}
            #PrimaryButton {{
                background: {PALETTE["nav2"]};
                color: #FFFFFF;
                border: 1px solid {PALETTE["nav2"]};
                font-weight: 700;
            }}
            #SmallButton {{
                padding: 6px 10px;
                min-height: 30px;
            }}
            #ToolIconButton {{
                background: {control_bg};
                border: 1px solid {PALETTE["line"]};
                border-radius: 8px;
                min-width: 34px;
                max-width: 34px;
                min-height: 34px;
                max-height: 34px;
                padding: 0;
            }}
            #ToolIconButton:hover {{
                background: {field_hover_bg};
                border-color: {PALETTE["green"]};
            }}
            #ToolPrimaryButton {{
                background: {PALETTE["nav2"]};
                border: 1px solid {PALETTE["nav2"]};
                border-radius: 8px;
                min-width: 38px;
                max-width: 38px;
                min-height: 34px;
                max-height: 34px;
                padding: 0;
            }}
            #ToolPrimaryButton:hover {{
                background: {PALETTE["green"]};
                border-color: {PALETTE["green"]};
            }}
            #AIInputPanel {{
                background: transparent;
                border: none;
            }}
            #AIIconButton {{
                background: {control_bg};
                color: {PALETTE["ink"]};
                border: 1px solid {PALETTE["line"]};
                border-radius: 7px;
                min-width: 28px;
                max-width: 28px;
                min-height: 28px;
                max-height: 28px;
                padding: 0;
            }}
            #AIIconButton:hover {{
                background: {field_hover_bg};
                border-color: {PALETTE["green"]};
            }}
            #AIPrimaryIconButton {{
                background: {PALETTE["nav2"]};
                color: #FFFFFF;
                border: 1px solid {PALETTE["nav2"]};
                border-radius: 7px;
                min-width: 28px;
                max-width: 28px;
                min-height: 28px;
                max-height: 28px;
                padding: 0;
            }}
            #AIPrimaryIconButton:hover {{
                background: {PALETTE["green"]};
                border-color: {PALETTE["green"]};
            }}
            #AIIconButton:disabled, #AIPrimaryIconButton:disabled {{
                background: {muted_box_bg};
                border-color: {PALETTE["line"]};
            }}
            #CompactCombo {{
                background: {control_bg};
                border: 1px solid {PALETTE["line"]};
                border-radius: 8px;
                padding: 5px 8px;
                min-height: 30px;
            }}
            #CompactSpin {{
                background: {control_bg};
                border: 1px solid {PALETTE["line"]};
                border-radius: 8px;
                padding: 5px 8px;
                min-width: 72px;
                min-height: 30px;
            }}
            #ToolbarFontCombo, #ToolbarSizeCombo {{
                background: {control_bg};
                border: 1px solid {PALETTE["line"]};
                border-radius: 8px;
                min-height: 34px;
                max-height: 34px;
                padding: 0 28px 0 10px;
                color: {PALETTE["ink"]};
                selection-background-color: {selected_bg};
            }}
            #ToolbarFontCombo:hover, #ToolbarSizeCombo:hover {{
                background: {field_hover_bg};
                border-color: {PALETTE["green"]};
            }}
            #ToolbarFontCombo:focus, #ToolbarSizeCombo:focus {{
                border-color: {PALETTE["nav2"]};
                background: {field_focus_bg};
            }}
            #ToolbarFontCombo::drop-down, #ToolbarSizeCombo::drop-down {{
                subcontrol-origin: padding;
                subcontrol-position: top right;
                width: 24px;
                border-left: 1px solid {PALETTE["line"]};
                border-top-right-radius: 7px;
                border-bottom-right-radius: 7px;
                background: {muted_box_bg};
            }}
            #ToolbarSizeCombo QLineEdit {{
                background: transparent;
                border: none;
                padding: 0 0 0 2px;
                min-height: 30px;
                color: {PALETTE["ink"]};
            }}
            #ToolbarFontCombo QAbstractItemView, #ToolbarSizeCombo QAbstractItemView {{
                background: {paper_bg};
                border: 1px solid {PALETTE["line"]};
                border-radius: 8px;
                padding: 4px;
                outline: none;
                selection-background-color: {selected_bg};
                selection-color: {PALETTE["ink"]};
            }}
            #CharacterFieldInput, #CharacterFieldCombo {{
                background: {field_bg};
                border: 1px solid {PALETTE["line"]};
                border-radius: 8px;
                min-height: 34px;
                padding: 0 10px;
                color: {PALETTE["ink"]};
                selection-background-color: {selected_bg};
            }}
            #CharacterFieldInput:hover, #CharacterFieldCombo:hover {{
                background: {field_hover_bg};
                border-color: {PALETTE["green"]};
            }}
            #CharacterFieldInput:focus, #CharacterFieldCombo:focus {{
                background: {field_focus_bg};
                border-color: {PALETTE["nav2"]};
            }}
            #CharacterFieldCombo {{
                padding: 0 28px 0 10px;
            }}
            #CharacterFieldCombo::drop-down {{
                subcontrol-origin: padding;
                subcontrol-position: top right;
                width: 24px;
                border-left: 1px solid {PALETTE["line"]};
                border-top-right-radius: 7px;
                border-bottom-right-radius: 7px;
                background: {muted_box_bg};
            }}
            #CharacterFieldCombo QLineEdit {{
                background: transparent;
                border: none;
                padding: 0 0 0 2px;
                min-height: 30px;
                color: {PALETTE["ink"]};
            }}
            #CharacterFieldCombo QAbstractItemView {{
                background: {paper_bg};
                border: 1px solid {PALETTE["line"]};
                border-radius: 8px;
                padding: 4px;
                outline: none;
                selection-background-color: {selected_bg};
                selection-color: {PALETTE["ink"]};
            }}
            #ProjectMenuButton {{
                background: {panel_bg};
                color: {PALETTE["ink"]};
                border: 1px solid {PALETTE["line"]};
                min-height: 34px;
            }}
            #RoundToolButton {{
                background: {PALETTE["nav2"]};
                color: #FFFFFF;
                border: 1px solid {PALETTE["nav2"]};
                border-radius: 8px;
                font-size: 18px;
                font-weight: 800;
                min-width: 34px;
                max-width: 34px;
                min-height: 34px;
                padding: 0;
            }}
            #StatusRevision {{
                background: {PALETTE["soft_red"]};
                color: {PALETTE["accent"]};
                border: 1px solid {PALETTE["accent"]};
                font-weight: 800;
            }}
            #StatusDraft {{
                background: {PALETTE["soft_yellow"]};
                color: {PALETTE["amber"]};
                border: 1px solid {PALETTE["amber"]};
                font-weight: 800;
            }}
            #StatusDone {{
                background: {PALETTE["soft_green"]};
                color: {PALETTE["green"]};
                border: 1px solid {PALETTE["green"]};
                font-weight: 800;
            }}
            QMenu {{
                background: {paper_bg};
                border: 1px solid {PALETTE["line"]};
                border-radius: 8px;
                padding: 6px;
            }}
            QMenu::item {{
                padding: 8px 24px 8px 12px;
                border-radius: 6px;
            }}
            QMenu::item:selected {{
                background: {selected_bg};
                color: {PALETTE["ink"]};
            }}
            #RecentList {{
                background: {paper_bg};
                border: 1px solid {PALETTE["line"]};
                border-radius: 8px;
                padding: 6px;
                outline: none;
            }}
            #RecentList::item {{
                border-bottom: 1px solid {PALETTE["line"]};
                border-radius: 6px;
                padding: 9px 8px;
                margin: 2px;
            }}
            #RecentList::item:selected {{
                background: {selected_bg};
                color: {PALETTE["ink"]};
            }}
            #RecentList::item:hover {{
                background: {field_hover_bg};
            }}
            #ChapterTree {{
                background: transparent;
                border: none;
                border-radius: 0;
                padding: 0 0 0 8px;
                outline: none;
            }}
            #OutlineTree {{
                background: transparent;
                border: none;
                border-radius: 0;
                padding: 0 0 0 8px;
                outline: none;
            }}
            #WorldTree {{
                background: transparent;
                border: none;
                border-radius: 0;
                padding: 0 0 0 8px;
                outline: none;
            }}
            #ChapterTree::item {{
                min-height: 30px;
                border-radius: 6px;
                padding: 3px 8px;
            }}
            #OutlineTree::item {{
                min-height: 30px;
                border-radius: 6px;
                padding: 3px 8px;
            }}
            #WorldTree::item {{
                min-height: 30px;
                border-radius: 6px;
                padding: 3px 8px;
            }}
            #ChapterTree::item:selected {{
                background: rgba(34, 94, 74, 0.08);
                color: {PALETTE["ink"]};
            }}
            #OutlineTree::item:selected {{
                background: rgba(34, 94, 74, 0.10);
                color: {PALETTE["ink"]};
            }}
            #WorldTree::item:selected {{
                background: rgba(34, 94, 74, 0.10);
                color: {PALETTE["ink"]};
            }}
            #ManuscriptEditor {{
                background: {editor_bg};
                border: 1px solid {PALETTE["line"]};
                border-radius: 8px;
                padding: 0;
                font-size: 16px;
            }}
            #OutlineTextEdit {{
                background: {paper_bg};
                border: 1px solid {PALETTE["line"]};
                border-radius: 8px;
                padding: 10px;
                font-size: 14px;
            }}
            #WorldTextEdit {{
                background: {paper_bg};
                border: 1px solid {PALETTE["line"]};
                border-radius: 8px;
                padding: 10px;
                font-size: 14px;
            }}
            #CharacterTextEdit {{
                background: {paper_bg};
                border: 1px solid {PALETTE["line"]};
                border-radius: 8px;
                padding: 10px;
                font-size: 14px;
            }}
            #CharacterAIBox {{
                background: {field_bg};
                border: 1px solid {PALETTE["line"]};
                border-radius: 8px;
                padding: 10px;
            }}
            #AIChatInput {{
                background: {editor_bg};
                border: 1px solid {PALETTE["line"]};
                border-radius: 8px;
                padding: 8px 10px;
                color: {PALETTE["ink"]};
                selection-background-color: {selected_bg};
            }}
            #AIChatInput:focus {{
                border-color: {PALETTE["nav2"]};
                background: {field_focus_bg};
            }}
            #SummaryBox {{
                background: {field_bg};
                border: 1px solid {PALETTE["line"]};
                border-radius: 8px;
                padding: 10px;
            }}
            #ScopeBadge {{
                background: {scope_bg};
                color: {PALETTE["green"]};
                border: none;
                border-radius: 8px;
                padding: 10px;
                font-size: 12px;
            }}
            #TimelineTree {{
                background: {field_bg};
                border: 1px solid {PALETTE["line"]};
                border-radius: 8px;
                padding: 4px;
                outline: none;
            }}
            #TimelineTree::item {{
                min-height: 28px;
                border-radius: 6px;
                padding: 3px 8px;
            }}
            #TimelineTree::item:selected {{
                background: {selected_bg};
                color: {PALETTE["ink"]};
            }}
            #CharacterTree {{
                background: {field_bg};
                border: 1px solid {PALETTE["line"]};
                border-radius: 8px;
                padding: 6px;
                outline: none;
            }}
            #CharacterTree::item {{
                min-height: 34px;
                border-radius: 7px;
                padding: 4px 8px;
            }}
            #CharacterTree::item:selected {{
                background: {selected_bg};
                color: {PALETTE["ink"]};
            }}
            #TagLinkButton {{
                background: {scope_bg};
                color: {PALETTE["green"]};
                border: 1px solid #C9DAD0;
                border-radius: 8px;
                padding: 5px 9px;
                min-height: 28px;
                font-size: 12px;
            }}
            QLineEdit, QComboBox, QSpinBox, QTextEdit {{
                background: {field_bg};
                border: 1px solid {PALETTE["line"]};
                border-radius: 8px;
                padding: 8px;
            }}
            #CoverBox {{
                background: {PALETTE["nav2"]};
                border: 1px solid {PALETTE["green"]};
                border-radius: 8px;
                font-size: 28px;
                font-weight: 800;
                color: #FFFFFF;
            }}
            #CoverButton {{
                min-height: 34px;
            }}
            #HealthBadge {{
                background: {PALETTE["soft_green"]};
                border: 1px solid {PALETTE["green"]};
                color: {PALETTE["green"]};
                border-radius: 8px;
                padding: 7px 12px;
                font-weight: 700;
            }}
            #HealthBadge[tone="amber"] {{
                background: {PALETTE["soft_yellow"]};
                border-color: {PALETTE["amber"]};
                color: {PALETTE["amber"]};
            }}
            #HealthBadge[tone="accent"] {{
                background: {PALETTE["soft_red"]};
                border-color: {PALETTE["accent"]};
                color: {PALETTE["accent"]};
            }}
            #DetailName {{
                color: {PALETTE["blue"]};
                font-weight: 700;
            }}
            #DialogTitle {{
                font-size: 22px;
                font-weight: 800;
            }}
            QScrollBar:vertical {{
                background: {scrollbar_bg};
                width: 10px;
                margin: 2px;
                border-radius: 5px;
            }}
            QScrollBar::handle:vertical {{
                background: {PALETTE["green"]};
                min-height: 34px;
                border-radius: 5px;
            }}
            QScrollBar::handle:vertical:hover {{
                background: {PALETTE["nav2"]};
            }}
            QScrollBar::add-line:vertical,
            QScrollBar::sub-line:vertical {{
                height: 0;
                border: none;
                background: transparent;
            }}
            QScrollBar:horizontal {{
                background: {scrollbar_bg};
                height: 10px;
                margin: 2px;
                border-radius: 5px;
            }}
            QScrollBar::handle:horizontal {{
                background: {PALETTE["green"]};
                min-width: 34px;
                border-radius: 5px;
            }}
            QScrollBar::handle:horizontal:hover {{
                background: {PALETTE["nav2"]};
            }}
            QScrollBar::add-line:horizontal,
            QScrollBar::sub-line:horizontal {{
                width: 0;
                border: none;
                background: transparent;
            }}
            """
        )
        if hasattr(self, "editor"):
            self.editor.set_canvas_background(editor_bg)


def main() -> int:
    app = QApplication(sys.argv)
    app.setApplicationName(APP_NAME)
    app.setApplicationVersion(APP_VERSION)
    app.setWindowIcon(app_icon())
    install_wensha_check_style(app)
    load_application_fonts(app)
    window = ProjectHomeWindow()
    window.show()
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
