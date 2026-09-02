# -*- coding: utf-8 -*-
"""人物卡页面模块：人物、关系、历史记录与人物 AI。"""

from __future__ import annotations

import shutil
from pathlib import Path
from typing import Any

from PySide6.QtCore import QPoint, QSize, Qt
from PySide6.QtGui import QFont, QIcon, QPixmap, QTextCharFormat, QTextCursor
from PySide6.QtWidgets import (
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
    QMenu,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QSplitter,
    QTextEdit,
    QTreeWidget,
    QTreeWidgetItem,
    QVBoxLayout,
    QWidget,
)

from ...core.config import (
    DEFAULT_BODY_FONT_FAMILY,
    IMAGE_EXTENSIONS,
    PALETTE,
    default_character_ai_scope,
    now_iso,
    save_app_settings,
)
from ...core.storage import DraftStore
from ...services.ai_client import AIStreamThread
from ..common import PIXMAP_CACHE, cached_pixmap, text_icon


class CharacterPageMixin:
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
