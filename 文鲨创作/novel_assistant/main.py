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


from .core.config import *
from .core.storage import DraftStore, ProjectMeta, ProjectStore


from .ui.common import (
    PIXMAP_CACHE,
    app_icon,
    cached_pixmap,
    fmt_time,
    load_application_fonts,
    nav_icon,
    relative_time,
    text_icon,
    tool_icon,
    white_logo_pixmap,
)



from .ui.styles import WenshaCheckStyle, install_wensha_check_style


from .services.ai_client import AIStreamThread




from .services.files import move_path_to_recycle_bin


from .widgets.editor import ManuscriptEditor


from .ui.dialogs import NewProjectDialog
from .ui.pages.outline_page import OutlinePageMixin
from .ui.pages.character_page import CharacterPageMixin
from .ui.pages.editor_page import EditorPageMixin
from .ui.pages.project_page import ProjectPageMixin
from .ui.pages.settings_page import SettingsPageMixin
from .ui.pages.worldbuilding_page import WorldbuildingPageMixin


class ProjectHomeWindow(ProjectPageMixin, SettingsPageMixin, EditorPageMixin, CharacterPageMixin, WorldbuildingPageMixin, OutlinePageMixin, QMainWindow):
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
