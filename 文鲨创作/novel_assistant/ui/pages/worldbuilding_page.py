# -*- coding: utf-8 -*-
"""世界观/设定库页面模块。"""

from __future__ import annotations

import shutil
from pathlib import Path
from typing import Any

from PySide6.QtCore import QPoint, QSize, Qt
from PySide6.QtGui import QFont, QPixmap, QTextCharFormat
from PySide6.QtWidgets import (
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFileDialog,
    QFrame,
    QFontComboBox,
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
    QTreeWidget,
    QTreeWidgetItem,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from ...core.config import DEFAULT_BODY_FONT_FAMILY, IMAGE_EXTENSIONS, now_iso
from ...core.storage import DraftStore
from ..common import PIXMAP_CACHE, cached_pixmap


class WorldbuildingPageMixin:
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
