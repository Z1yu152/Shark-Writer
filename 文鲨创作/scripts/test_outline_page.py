# -*- coding: utf-8 -*-
import json
import os
import sys
import tempfile
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QApplication, QSplitter, QTextEdit, QToolButton
from PySide6.QtWidgets import QMessageBox, QInputDialog

from novel_assistant.main import DRAFT_FILE, DraftStore, PALETTE, ProjectHomeWindow, ProjectMeta, default_outline_ai_scope, load_application_fonts, now_iso


CURRENT_BODY_MARKER = "OUTLINE_CURRENT_BODY_SECRET"
OTHER_BODY_MARKER = "OUTLINE_OTHER_BODY_SECRET"
PRIVATE_WORLD_MARKER = "OUTLINE_WORLD_PRIVATE_SECRET"


def assert_true(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


def message_text(messages: list[dict[str, str]]) -> str:
    return json.dumps(messages, ensure_ascii=False)


class FakeRunningThread:
    def __init__(self) -> None:
        self.stopped = False

    def isRunning(self) -> bool:
        return True

    def request_stop(self) -> None:
        self.stopped = True


def build_ai_scope_draft() -> dict:
    return {
        "version": 1,
        "current_chapter_id": "ch_current",
        "volumes": [
            {
                "id": "vol_1",
                "title": "第一卷",
                "chapters": [
                    {
                        "id": "ch_current",
                        "title": "当前章",
                        "content": f"<h1>当前章</h1><p>{CURRENT_BODY_MARKER} 当前章正文。</p>",
                        "summary": {"events": "OUTLINE_SUMMARY_CURRENT 当前章总结。"},
                        "status": "草稿",
                        "ai_enabled": True,
                        "updated_at": now_iso(),
                    },
                    {
                        "id": "ch_other",
                        "title": "其他章",
                        "content": f"<h1>其他章</h1><p>{OTHER_BODY_MARKER} 其他章正文。</p>",
                        "summary": {"events": "OUTLINE_SUMMARY_OTHER 其他章总结。"},
                        "status": "草稿",
                        "ai_enabled": True,
                        "updated_at": now_iso(),
                    },
                ],
            }
        ],
        "outline": {
            "current_node_id": "ol_1",
            "timeline_expanded": True,
            "nodes": [
                {
                    "id": "ol_1",
                    "title": "主线",
                    "kind": "总纲",
                    "goal": "OUTLINE_SCOPE_ALLOWED",
                    "timeline_tag": "T0",
                    "content": "<p>OUTLINE_SCOPE_ALLOWED 细纲。</p>",
                    "children": [],
                }
            ],
            "timeline_points": [{"id": "tl_1", "time": "T0", "event": "OUTLINE_TIMELINE_ALLOWED", "line": "主线"}],
            "ai_chat": "",
        },
        "worldbuilding": {
            "current_entry_id": "wb_public",
            "modules": [
                {
                    "id": "wb_module",
                    "title": "世界观",
                    "kind": "module",
                    "children": [
                        {
                            "id": "wb_public",
                            "title": "公开设定",
                            "kind": "entry",
                            "entry_type": "设定",
                            "tags": ["OUTLINE_WORLD_ALLOWED"],
                            "content": "<p>OUTLINE_WORLD_ALLOWED 可读设定。</p>",
                            "children": [],
                        },
                        {
                            "id": "wb_private",
                            "title": "私密设定",
                            "kind": "entry",
                            "entry_type": "设定",
                            "tags": ["private"],
                            "content": f"<p>{PRIVATE_WORLD_MARKER} 不应读取。</p>",
                            "ai_read_allowed": False,
                            "children": [],
                        },
                    ],
                }
            ],
        },
        "characters": {
            "current_character_id": "char_1",
            "groups": ["未分组"],
            "cards": [
                {
                    "id": "char_1",
                    "name": "角色甲",
                    "identity": "OUTLINE_CHAR_ALLOWED",
                    "faction": "未分组",
                    "status": "登场",
                    "tags": {"性格": ["OUTLINE_CHAR_ALLOWED"]},
                    "notes": "<p>OUTLINE_CHAR_ALLOWED 人物备注。</p>",
                    "history": [],
                    "relations": [
                        {
                            "id": "rel_1",
                            "target_name": "角色乙",
                            "type": "合作",
                            "status": "当前",
                            "note": "OUTLINE_REL_ALLOWED",
                        }
                    ],
                }
            ],
        },
    }


def main() -> int:
    app = QApplication.instance() or QApplication([])
    load_application_fonts(app)
    window = ProjectHomeWindow()
    window.show()
    app.processEvents()

    with tempfile.TemporaryDirectory(prefix="wensha_outline_", dir=str(ROOT)) as temp_dir:
        project = ProjectMeta(name="QA大纲项目", path=temp_dir, auto_save_minutes=10)
        window.store.write_project(project)
        window.selected_project = project

        window.switch_page("outline")
        app.processEvents()

        assert_true(window.current_page == "outline", "应切换到大纲页")
        assert_true(window.topbar_widget.isHidden(), "大纲页应隐藏项目首页顶部按钮")
        assert_true(window.outline_tree.topLevelItemCount() > 0, "大纲目录应有默认节点")
        assert_true(app.property("wensha_check_style_installed") is True, "全局复选框应使用自绘样式")
        assert_true("QCheckBox::indicator" not in window.styleSheet(), "复选框图形不应被 QSS 填成实心块")
        assert_true(PALETTE["ink"] in window.styleSheet(), "复选框文字颜色应跟随字体主色")
        assert_true(isinstance(window.outline_chat_input, QTextEdit), "大纲 AI 输入框应使用多行输入")
        assert_true(window.outline_chat_input.minimumHeight() >= 124, "大纲 AI 输入框应继续加大")
        assert_true(isinstance(window.outline_send_btn, QToolButton), "大纲 AI 发送按钮应为图标按钮")
        assert_true(isinstance(window.outline_stop_btn, QToolButton), "大纲 AI 停止按钮应为图标按钮")
        assert_true(isinstance(window.outline_clear_btn, QToolButton), "大纲 AI 清除按钮应为图标按钮")
        assert_true(window.outline_send_btn.objectName() == "AIPrimaryIconButton", "大纲 AI 发送按钮应使用紧凑主按钮样式")
        assert_true(window.outline_stop_btn.objectName() == "AIIconButton", "大纲 AI 停止按钮应使用紧凑普通按钮样式")
        assert_true(window.outline_clear_btn.objectName() == "AIIconButton", "大纲 AI 清除按钮应使用紧凑普通按钮样式")
        assert_true(window.outline_send_btn.maximumWidth() <= 30 and window.outline_send_btn.maximumHeight() <= 30, "大纲 AI 发送按钮应控制在约 30px 内")
        assert_true(window.outline_stop_btn.maximumWidth() <= 30 and window.outline_stop_btn.maximumHeight() <= 30, "大纲 AI 停止按钮应控制在约 30px 内")
        assert_true(window.outline_clear_btn.maximumWidth() <= 30 and window.outline_clear_btn.maximumHeight() <= 30, "大纲 AI 清除按钮应控制在约 30px 内")
        assert_true(window.outline_send_btn.iconSize().width() <= 16, "大纲 AI 发送图标应更紧凑")
        assert_true(window.outline_send_btn.toolTip() == "发送", "大纲 AI 发送图标应有提示")
        assert_true(window.outline_stop_btn.toolTip() == "停止生成", "大纲 AI 停止图标应有提示")
        assert_true(window.outline_clear_btn.toolTip() == "清除对话", "大纲 AI 清除图标应有提示")
        assert_true(isinstance(window.outline_ai_splitter, QSplitter), "大纲 AI 回复框和输入区应可拖动调节")
        assert_true(window.outline_ai_splitter.orientation() == Qt.Vertical, "大纲 AI 分割器应为上下调节")
        assert_true(window.outline_ai_splitter.count() == 2, "大纲 AI 分割器应包含回复区和输入区")
        story_item = window.outline_tree.topLevelItem(0)
        assert_true(story_item.text(0) == "故事总纲", "故事总纲应是顶层入口")
        assert_true(story_item.childCount() == 0, "故事总纲不应承载子级和折叠内容")
        first_volume_item = window.outline_tree.topLevelItem(1)
        assert_true(first_volume_item is not None, "默认大纲应有与故事总纲并列的卷")
        first_volume = window.find_outline_node(first_volume_item.data(0, Qt.UserRole))
        assert_true(first_volume is not None and first_volume[1].get("kind") == "卷", "故事总纲后的顶层节点应是卷")
        first_chapter_item = first_volume_item.child(0)
        first_chapter = window.find_outline_node(first_chapter_item.data(0, Qt.UserRole))
        assert_true(first_chapter is not None and first_chapter[1].get("kind") == "章", "默认卷下应有章节")
        first_chapter_id = first_chapter[1].get("id")
        assert_true(window.timeline_body.isVisible(), "时间轴默认展开")
        assert_true(not window.outline_scope_frame.isVisible(), "大纲页 AI 读取范围默认应折叠")
        window.outline_scope_toggle_btn.click()
        app.processEvents()
        assert_true(window.outline_scope_frame.isVisible(), "大纲页 AI 读取范围应可展开")
        window.outline_scope_toggle_btn.click()
        app.processEvents()
        assert_true(not window.outline_scope_frame.isVisible(), "大纲页 AI 读取范围应可收起")

        window.outline_goal_edit.setText("测试本章目标")
        window.outline_timeline_tag_edit.setText("主线 · T0")
        window.outline_editor.setPlainText("测试细纲内容")
        window.toggle_outline_timeline()
        assert_true(not window.timeline_body.isVisible(), "时间轴应可收起")
        window.save_current_outline_node(silent=True)

        original_get_text = QInputDialog.getText
        original_information = QMessageBox.information
        info_messages: list[str] = []
        try:
            window.outline_tree.setCurrentItem(first_chapter_item)
            QInputDialog.getText = lambda *args, **kwargs: ("并列第二章", True)  # type: ignore[assignment]
            window.add_outline_node("chapter")
            outline_after_chapter = window.ensure_outline_data()
            volume_after_chapter = next(node for node in outline_after_chapter["nodes"] if node.get("kind") == "卷")
            sibling_titles = [node.get("title") for node in volume_after_chapter.get("children", [])]
            assert_true("并列第二章" in sibling_titles, "选中章节后新增章应进入同一卷并列")
            original_chapter = next(node for node in volume_after_chapter.get("children", []) if node.get("id") == first_chapter_id)
            assert_true("并列第二章" not in [node.get("title") for node in original_chapter.get("children", [])], "新增章不应成为当前章节子级")

            QInputDialog.getText = lambda *args, **kwargs: ("第二卷", True)  # type: ignore[assignment]
            before_top_count = len(outline_after_chapter.get("nodes", []))
            window.add_outline_node("volume")
            outline_after_volume = window.ensure_outline_data()
            assert_true(len(outline_after_volume.get("nodes", [])) == before_top_count + 1, "选中章节后新增卷应作为顶层节点")
            assert_true(outline_after_volume["nodes"][-1].get("title") == "第二卷", "新增卷应出现在顶层末尾")

            story_item = window.outline_tree.topLevelItem(0)
            window.outline_tree.setCurrentItem(story_item)

            def fake_information(_parent, _title, text, *args, **kwargs):
                info_messages.append(text)
                return QMessageBox.Ok

            def fail_get_text(*args, **kwargs):
                raise AssertionError("选中故事总纲新增章时不应打开名称输入框")

            QMessageBox.information = fake_information  # type: ignore[assignment]
            QInputDialog.getText = fail_get_text  # type: ignore[assignment]
            before_chapter_count = window.count_outline_kind("章")
            window.add_outline_node("chapter")
            assert_true(info_messages and info_messages[-1] == "请先选择一个卷。", "选中故事总纲新增章应提示先选择卷")
            assert_true(window.count_outline_kind("章") == before_chapter_count, "无法判断所属卷时不应新增章节")
        finally:
            QInputDialog.getText = original_get_text
            QMessageBox.information = original_information

        draft = json.loads((Path(temp_dir) / DRAFT_FILE).read_text(encoding="utf-8"))
        outline = draft.get("outline", {})
        assert_true(bool(outline.get("nodes")), "draft.json 应保存 outline.nodes")
        assert_true(outline.get("timeline_expanded") is False, "draft.json 应保存时间轴展开状态")
        current_id = outline.get("current_node_id")
        assert_true(bool(current_id), "draft.json 应保存当前大纲节点")

        window.resize(1440, 900)
        app.processEvents()
        window.grab().save(str(ROOT / "qa_outline_page.png"))

    captured: list[list[dict[str, str]]] = []
    confirmations: list[tuple[str, list[str]]] = []
    QMessageBox.information = lambda *args, **kwargs: QMessageBox.Ok  # type: ignore[assignment]
    QMessageBox.warning = lambda *args, **kwargs: QMessageBox.Ok  # type: ignore[assignment]

    def fake_confirm(title, sections, settings):
        confirmations.append((title, [name for name, _body in sections]))
        return True

    def fake_stream(settings, messages, max_tokens=1000):
        assert_true(not window.outline_send_btn.isEnabled(), "流式输出时发送按钮应暂时禁用")
        assert_true(window.outline_stop_btn.isEnabled(), "流式输出时停止按钮应启用")
        assert_true(not window.outline_clear_btn.isEnabled(), "流式输出时清除按钮应暂时禁用")
        assert_true(not window.outline_chat_input.isEnabled(), "流式输出时输入框应暂时禁用")
        assert_true(not window.outline_scope_checks["outline"].isEnabled(), "流式输出时读取范围应锁定")
        captured.append(messages)
        window.append_outline_chat_text("OUTLINE_FAKE_STREAM_REPLY")
        window.on_outline_ai_stream_finished(True, "", False)

    window.confirm_outline_ai_call = fake_confirm  # type: ignore[method-assign]
    window.start_outline_ai_stream = fake_stream  # type: ignore[method-assign]
    window.current_page = "home"
    window.draft = None
    window.current_outline_node_id = None

    with tempfile.TemporaryDirectory(prefix="wensha_outline_ai_", dir=str(ROOT)) as temp_dir:
        project = ProjectMeta(name="AI大纲QA", path=temp_dir, auto_save_minutes=10)
        window.store.write_project(project)
        DraftStore.save(project, build_ai_scope_draft())
        window.selected_project = project
        window.app_settings["outline_ai_scope"] = default_outline_ai_scope()
        window.switch_page("outline")
        app.processEvents()

        window.ai_enabled_check.setChecked(True)
        window.ai_key_edit.setText("test-key")
        window.ai_base_url_box.setCurrentText("https://example.invalid/v1")
        window.ai_model_box.setCurrentText("test-model")
        window.ai_context_box.setCurrentText("10000")
        window.ai_role_name_edit.setText("墨衡")
        window.ai_role_identity_edit.setText("冷静的大纲审稿人")
        window.ai_role_prompt_edit.setPlainText("优先检查时间线、伏笔和章节动机。")

        window.switch_page("editor")
        original_get_text = QInputDialog.getText
        try:
            QInputDialog.getText = lambda *args, **kwargs: ("新增实测章", True)  # type: ignore[assignment]
            window.add_chapter()
        finally:
            QInputDialog.getText = original_get_text
        new_chapter_id = window.current_chapter_id
        assert_true(bool(new_chapter_id), "新增章节后应有当前章节 ID")
        window.switch_page("outline")
        app.processEvents()

        tree, chapter_items = window.build_ai_chapter_selection_tree(set())
        volume_item = tree.topLevelItem(0)
        assert_true(volume_item.checkState(0) == Qt.Unchecked, "初始未选择章节时卷应未勾选")
        labels = [item.text(0) for item, _chapter_id in chapter_items]
        ids = {chapter_id for _item, chapter_id in chapter_items}
        assert_true("新增实测章" in labels, "新增章节应出现在 AI 选择章节弹窗")
        assert_true(new_chapter_id in ids, "新增章节 ID 应进入 AI 选择章节列表")
        volume_item.setCheckState(0, Qt.Checked)
        app.processEvents()
        assert_true({"ch_current", "ch_other", new_chapter_id}.issubset(window.selected_ai_chapter_ids_from_tree(chapter_items)), "勾选卷应自动勾选卷内所有章节")
        volume_item.child(0).setCheckState(0, Qt.Unchecked)
        app.processEvents()
        assert_true(volume_item.checkState(0) == Qt.PartiallyChecked, "只勾选部分章节时卷应半选")
        window.clear_ai_chapter_selection_tree(tree)
        app.processEvents()
        assert_true(window.selected_ai_chapter_ids_from_tree(chapter_items) == set(), "清除全部应取消所有章节勾选")
        assert_true(volume_item.checkState(0) == Qt.Unchecked, "清除全部后卷应未勾选")
        window.draft["current_chapter_id"] = "ch_current"
        window.current_chapter_id = "ch_current"
        DraftStore.save(project, window.draft)

        window.outline_chat_input.setText("检查主线")
        window.send_outline_ai_message()
        default_payload = message_text(captured[-1])
        assert_true("OUTLINE_SCOPE_ALLOWED" in default_payload, "大纲助手默认应读取大纲")
        assert_true("OUTLINE_TIMELINE_ALLOWED" in default_payload, "大纲助手默认应读取时间线")
        assert_true("OUTLINE_SUMMARY_CURRENT" in default_payload, "大纲助手默认应读取章节总结")
        assert_true("OUTLINE_WORLD_ALLOWED" in default_payload, "大纲助手默认应读取允许的设定")
        assert_true("OUTLINE_CHAR_ALLOWED" in default_payload, "大纲助手默认应读取人物卡")
        assert_true("OUTLINE_REL_ALLOWED" in default_payload, "大纲助手默认应读取关系记录")
        assert_true(CURRENT_BODY_MARKER not in default_payload, "大纲助手默认不应读取当前章正文")
        assert_true(OTHER_BODY_MARKER not in default_payload, "大纲助手默认不应读取其他章正文")
        assert_true(PRIVATE_WORLD_MARKER not in default_payload, "大纲助手不应读取禁止 AI 读取的设定")
        assert_true("墨衡" in default_payload, "大纲助手应注入全局 AI 角色名称")
        assert_true("冷静的大纲审稿人" in default_payload, "大纲助手应注入全局 AI 角色身份")
        assert_true("OUTLINE_FAKE_STREAM_REPLY" in window.outline_chat_log.toPlainText(), "大纲助手应流式显示 AI 回复")

        window.outline_scope_checks["current_chapter_body"].setChecked(True)
        window.outline_chat_input.setText("只读当前章正文")
        window.send_outline_ai_message()
        current_payload = message_text(captured[-1])
        assert_true(CURRENT_BODY_MARKER in current_payload, "勾选当前章正文后应读取当前章正文")
        assert_true(OTHER_BODY_MARKER not in current_payload, "只勾选当前章正文时不应读取其他章正文")

        window.outline_scope_checks["current_chapter_body"].setChecked(False)
        window.outline_scope_checks["selected_chapter_bodies"].setChecked(True)
        window.outline_selected_chapter_ids = {"ch_other"}
        window.outline_chat_input.setText("只读指定章正文")
        window.send_outline_ai_message()
        selected_payload = message_text(captured[-1])
        assert_true(CURRENT_BODY_MARKER not in selected_payload, "只勾选指定章时不应读取当前章正文")
        assert_true(OTHER_BODY_MARKER in selected_payload, "勾选指定章后应读取指定章节正文")
        assert_true(any(title == "发送给 AI 大纲助手" for title, _sections in confirmations), "大纲助手发送前应确认读取范围")

        fake_thread = FakeRunningThread()
        window.outline_ai_thread = fake_thread  # type: ignore[assignment]
        window.outline_stop_btn.setEnabled(True)
        window.stop_outline_ai_stream()
        assert_true(fake_thread.stopped, "停止生成应向大纲 AI 线程发出停止请求")
        assert_true(not window.outline_stop_btn.isEnabled(), "点击停止后停止按钮应暂时禁用")
        window.outline_ai_thread = None

    window.close()
    app.quit()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
