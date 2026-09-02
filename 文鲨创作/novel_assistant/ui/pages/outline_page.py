# -*- coding: utf-8 -*-
"""大纲页模块。

页面通过宿主窗口提供项目状态和导航能力，具体业务逻辑集中在本模块。
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

from PySide6.QtCore import QPoint, QSize, Qt
from PySide6.QtGui import QFont, QTextCharFormat, QTextCursor
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFrame,
    QFontComboBox,
    QGridLayout,
    QHBoxLayout,
    QInputDialog,
    QLabel,
    QLineEdit,
    QMenu,
    QMessageBox,
    QPushButton,
    QSplitter,
    QTextEdit,
    QTreeWidget,
    QTreeWidgetItem,
    QVBoxLayout,
    QWidget,
)

from ...core.config import DEFAULT_BODY_FONT_FAMILY, default_outline_ai_scope, now_iso, save_app_settings
from ...core.storage import DraftStore
from ...services.ai_client import AIStreamThread


class OutlinePageMixin:
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
