# -*- coding: utf-8 -*-
"""应用级配置与持久化设置。

这一层不依赖任何页面，页面和服务都通过这里读取统一配置。
"""

from __future__ import annotations

import json
import sys
from datetime import datetime
from pathlib import Path
from typing import Any


FROZEN = bool(getattr(sys, "frozen", False))
PACKAGE_ROOT = Path(__file__).resolve().parents[1]
RESOURCE_DIR = Path(getattr(sys, "_MEIPASS", PACKAGE_ROOT.parent))
APP_DIR = Path(sys.executable).resolve().parent if FROZEN else PACKAGE_ROOT.parent
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


def now_iso() -> str:
    return datetime.now().isoformat(timespec="seconds")


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


def _normalize_scopes(settings: dict[str, Any]) -> dict[str, Any]:
    outline_scope = settings.get("outline_ai_scope")
    outline_defaults = default_outline_ai_scope()
    if isinstance(outline_scope, dict):
        settings["outline_ai_scope"] = {
            key: bool(outline_scope.get(key, value))
            for key, value in outline_defaults.items()
        }
    else:
        settings["outline_ai_scope"] = outline_defaults

    character_scope = settings.get("character_ai_scope")
    character_defaults = default_character_ai_scope()
    if isinstance(character_scope, dict):
        settings["character_ai_scope"] = {
            key: bool(character_scope.get(key, value))
            for key, value in character_defaults.items()
        }
    else:
        settings["character_ai_scope"] = character_defaults
    return settings


def load_app_settings() -> dict[str, Any]:
    settings = default_app_settings()
    if APP_SETTINGS_FILE.exists():
        try:
            data = json.loads(APP_SETTINGS_FILE.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            data = {}
        if isinstance(data, dict):
            settings.update({key: value for key, value in data.items() if key in settings})
    return _normalize_scopes(settings)


def save_app_settings(settings: dict[str, Any]) -> None:
    STATE_DIR.mkdir(exist_ok=True)
    payload = default_app_settings()
    payload.update({key: value for key, value in settings.items() if key in payload})
    payload = _normalize_scopes(payload)
    APP_SETTINGS_FILE.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
