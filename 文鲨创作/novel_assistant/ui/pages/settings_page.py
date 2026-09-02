# -*- coding: utf-8 -*-
"""设置页面模块。"""

from __future__ import annotations

import json
import urllib.request
from pathlib import Path
from typing import Any

from PySide6.QtCore import Qt
from PySide6.QtGui import QFont, QKeySequence, QShortcut
from PySide6.QtWidgets import (
    QApplication,
    QCheckBox,
    QComboBox,
    QFontComboBox,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from ...core.config import (
    APP_NAME,
    APP_VERSION,
    DEFAULT_BODY_FONT_FAMILY,
    DEFAULT_BODY_FONT_SIZE,
    DEFAULT_TITLE_FONT_SIZE,
    PALETTE,
    default_app_settings,
    default_outline_ai_scope,
    load_app_settings,
    save_app_settings,
)
from ..common import fmt_time, nav_icon


class SettingsPageMixin:
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
