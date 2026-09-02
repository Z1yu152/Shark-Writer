# -*- coding: utf-8 -*-
"""正文编辑器页面模块：章节、格式、保存和编辑器 AI。"""

from __future__ import annotations

import json
import urllib.request
from pathlib import Path
from typing import Any

from PySide6.QtCore import QPoint, QSize, Qt
from PySide6.QtGui import QBrush, QColor, QFont, QIcon, QKeySequence, QPainter, QPixmap, QShortcut, QTextCharFormat, QTextCursor
from PySide6.QtWidgets import (
    QApplication,
    QCheckBox,
    QComboBox,
    QFontComboBox,
    QFrame,
    QHBoxLayout,
    QInputDialog,
    QLabel,
    QLineEdit,
    QMenu,
    QMessageBox,
    QPushButton,
    QSizePolicy,
    QSpinBox,
    QTextEdit,
    QToolButton,
    QTreeWidget,
    QTreeWidgetItem,
    QVBoxLayout,
    QWidget,
)

from ...core.config import (
    APP_VERSION,
    DEFAULT_BODY_FONT_FAMILY,
    DEFAULT_BODY_FONT_SIZE,
    DEFAULT_EDITOR_STYLE_VERSION,
    DEFAULT_LETTER_SPACING,
    DEFAULT_LINE_SPACING,
    PALETTE,
    PARAGRAPH_INDENT,
    now_iso,
)
from ...core.storage import DraftStore
from ...services.ai_client import AIStreamThread
from ...widgets.editor import ManuscriptEditor
from ..common import fmt_time, tool_icon


class EditorPageMixin:
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
