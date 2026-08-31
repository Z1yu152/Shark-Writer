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
from PySide6.QtGui import QColor, QPixmap
from PySide6.QtWidgets import QApplication, QMessageBox, QPushButton, QSplitter, QTextEdit, QToolButton

from novel_assistant.main import DRAFT_FILE, DraftStore, ProjectHomeWindow, ProjectMeta, default_character_ai_scope, load_application_fonts, now_iso


CURRENT_BODY_MARKER = "CHARACTER_CURRENT_BODY_SECRET"
OTHER_BODY_MARKER = "CHARACTER_OTHER_BODY_SECRET"
PRIVATE_WORLD_MARKER = "CHARACTER_WORLD_PRIVATE_SECRET"


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


def build_character_ai_scope_draft() -> dict:
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
                        "summary": {"events": "CHARACTER_SUMMARY_CURRENT 当前章总结。"},
                        "status": "草稿",
                        "ai_enabled": True,
                        "updated_at": now_iso(),
                    },
                    {
                        "id": "ch_other",
                        "title": "其他章",
                        "content": f"<h1>其他章</h1><p>{OTHER_BODY_MARKER} 其他章正文。</p>",
                        "summary": {"events": "CHARACTER_SUMMARY_OTHER 其他章总结。"},
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
                    "goal": "CHARACTER_OUTLINE_ALLOWED",
                    "timeline_tag": "T0",
                    "content": "<p>CHARACTER_OUTLINE_ALLOWED 细纲。</p>",
                    "children": [],
                }
            ],
            "timeline_points": [{"id": "tl_1", "time": "T0", "event": "CHARACTER_TIMELINE_ALLOWED", "line": "主线"}],
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
                            "tags": ["CHARACTER_WORLD_ALLOWED"],
                            "content": "<p>CHARACTER_WORLD_ALLOWED 可读设定。</p>",
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
                    "gender": "未知",
                    "age": "24",
                    "identity": "CHARACTER_CURRENT_ALLOWED",
                    "faction": "未分组",
                    "status": "登场",
                    "tags": {"性格": ["CHARACTER_CURRENT_ALLOWED"], "能力": [], "角色特点": [], "喜好": []},
                    "notes": "<p>CHARACTER_CURRENT_ALLOWED 当前人物备注。</p>",
                    "history": [{"id": "his_1", "time": "T0", "event": "CHARACTER_HISTORY_ALLOWED"}],
                    "relations": [
                        {
                            "id": "rel_1",
                            "target_id": "char_2",
                            "target_name": "角色乙",
                            "type": "合作",
                            "status": "当前",
                            "note": "CHARACTER_REL_ALLOWED",
                        }
                    ],
                },
                {
                    "id": "char_2",
                    "name": "角色乙",
                    "gender": "未知",
                    "age": "28",
                    "identity": "CHARACTER_OTHER_ALLOWED",
                    "faction": "未分组",
                    "status": "登场",
                    "tags": {"性格": ["CHARACTER_OTHER_ALLOWED"], "能力": [], "角色特点": [], "喜好": []},
                    "notes": "<p>CHARACTER_OTHER_ALLOWED 其他人物备注。</p>",
                    "history": [],
                    "relations": [],
                },
            ],
            "ai_note": "",
        },
    }


def main() -> int:
    app = QApplication.instance() or QApplication([])
    load_application_fonts(app)
    window = ProjectHomeWindow()
    window.show()
    app.processEvents()

    with tempfile.TemporaryDirectory(prefix="wensha_character_", dir=str(ROOT)) as temp_dir:
        project = ProjectMeta(name="QA人物项目", path=temp_dir, auto_save_minutes=10)
        window.store.write_project(project)
        window.selected_project = project

        window.switch_page("character")
        app.processEvents()

        assert_true(window.current_page == "character", "应切换到人物卡页")
        characters = window.ensure_character_data()
        assert_true(len(characters.get("cards", [])) >= 2, "应有默认人物卡")
        assert_true(window.character_tree.objectName() == "CharacterTree", "人物树应存在")
        assert_true(window.character_tree.topLevelItemCount() >= 3, "人物列表应按分组展示")
        assert_true(window.current_character_id is not None, "应自动选中一个人物")
        assert_true(window.character_gender_box.objectName() == "CharacterFieldCombo", "性别字段应使用统一下拉编辑框样式")
        assert_true(window.character_faction_box.objectName() == "CharacterFieldCombo", "当前阵营字段应使用统一下拉编辑框样式")
        assert_true(window.character_status_box.objectName() == "CharacterFieldCombo", "当前状态字段应使用统一下拉编辑框样式")
        assert_true(isinstance(window.character_ai_input, QTextEdit), "人物卡 AI 输入框应使用多行输入")
        assert_true(window.character_ai_input.minimumHeight() >= 124, "人物卡 AI 输入框应继续加大")
        assert_true(isinstance(window.character_ai_send_btn, QToolButton), "人物卡 AI 发送按钮应为图标按钮")
        assert_true(isinstance(window.character_ai_stop_btn, QToolButton), "人物卡 AI 停止按钮应为图标按钮")
        assert_true(isinstance(window.character_ai_clear_btn, QToolButton), "人物卡 AI 清除按钮应为图标按钮")
        assert_true(window.character_ai_send_btn.objectName() == "AIPrimaryIconButton", "人物卡 AI 发送按钮应使用紧凑主按钮样式")
        assert_true(window.character_ai_stop_btn.objectName() == "AIIconButton", "人物卡 AI 停止按钮应使用紧凑普通按钮样式")
        assert_true(window.character_ai_clear_btn.objectName() == "AIIconButton", "人物卡 AI 清除按钮应使用紧凑普通按钮样式")
        assert_true(window.character_ai_send_btn.maximumWidth() <= 30 and window.character_ai_send_btn.maximumHeight() <= 30, "人物卡 AI 发送按钮应控制在约 30px 内")
        assert_true(window.character_ai_stop_btn.maximumWidth() <= 30 and window.character_ai_stop_btn.maximumHeight() <= 30, "人物卡 AI 停止按钮应控制在约 30px 内")
        assert_true(window.character_ai_clear_btn.maximumWidth() <= 30 and window.character_ai_clear_btn.maximumHeight() <= 30, "人物卡 AI 清除按钮应控制在约 30px 内")
        assert_true(window.character_ai_send_btn.iconSize().width() <= 16, "人物卡 AI 发送图标应更紧凑")
        assert_true(window.character_ai_send_btn.toolTip() == "发送", "人物卡 AI 发送图标应有提示")
        assert_true(window.character_ai_stop_btn.toolTip() == "停止生成", "人物卡 AI 停止图标应有提示")
        assert_true(window.character_ai_clear_btn.toolTip() == "清除对话", "人物卡 AI 清除图标应有提示")
        assert_true(isinstance(window.character_ai_splitter, QSplitter), "人物卡 AI 回复框和输入区应可拖动调节")
        assert_true(window.character_ai_splitter.orientation() == Qt.Vertical, "人物卡 AI 分割器应为上下调节")
        assert_true(window.character_ai_splitter.count() == 2, "人物卡 AI 分割器应包含回复区和输入区")
        assert_true(not window.character_scope_frame.isVisible(), "人物卡 AI 读取范围默认应折叠")
        window.character_scope_toggle_btn.click()
        app.processEvents()
        assert_true(window.character_scope_frame.isVisible(), "人物卡 AI 读取范围应可展开")
        window.character_scope_toggle_btn.click()
        app.processEvents()
        assert_true(not window.character_scope_frame.isVisible(), "人物卡 AI 读取范围应可收起")
        nav_texts = [button.text().strip() for button in window.findChildren(QPushButton)]
        assert_true("关系图" not in nav_texts, "第一版人物关系应合并到人物卡，不显示独立关系图入口")

        card = window.find_character(window.current_character_id)
        assert_true(card is not None, "应能读取当前人物")
        card_id = card["id"]
        assert_true(bool(card.get("relations")), "默认人物卡应包含示例人物关系")
        window.character_relation_toggle.click()
        app.processEvents()
        assert_true(window.character_relation_box.isVisible(), "人物关系模块应可展开")
        assert_true("苏雁回" in window.character_relation_list.item(0).text(), "人物关系列表应展示关联人物")

        original_question = QMessageBox.question
        try:
            QMessageBox.question = lambda *args, **kwargs: QMessageBox.Yes
            window.character_faction_box.setCurrentText("新阵营")
            window.on_character_faction_committed()
        finally:
            QMessageBox.question = original_question
        card = window.find_character(card_id)
        assert_true("新阵营" in window.ensure_character_data().get("groups", []), "输入新阵营后应新建同名分组")
        assert_true(card.get("faction") == "新阵营", "人物应自动归入当前阵营分组")

        source_image = Path(temp_dir) / "portrait.png"
        image = QPixmap(32, 32)
        image.fill(QColor("#4D7A68"))
        assert_true(image.save(str(source_image)), "应能创建测试画像")
        window.set_character_portrait(source_image)
        card = window.find_character(card_id)
        portrait_path = card.get("portrait_path", "")
        assert_true(portrait_path.startswith("assets"), "人物画像应保存为项目相对路径")
        assert_true((Path(temp_dir) / portrait_path).exists(), "人物画像应复制到项目 assets/portraits")
        assert_true(window.character_portrait_label.pixmap() is not None, "人物画像预览应显示图片")
        window.remove_character_portrait()
        assert_true(not card.get("portrait_path"), "删除画像后应清空引用")

        window.character_tag_edits["能力"].setText("影步")
        window.save_current_character(silent=True)
        original_question = QMessageBox.question
        try:
            QMessageBox.question = lambda *args, **kwargs: QMessageBox.Yes
            window.handle_character_ability_tag("影步")
        finally:
            QMessageBox.question = original_question
        assert_true(window.current_page == "worldbuilding", "新建能力词条后应跳转到设定库")
        linked_card = next(item for item in window.ensure_character_data()["cards"] if item["id"] == card_id)
        assert_true(bool(linked_card.get("ability_links", {}).get("影步")), "能力标签应绑定设定词条 ID")
        ability_entry = window.find_world_entry_by_title("影步")
        assert_true(ability_entry is not None and ability_entry.get("entry_type") == "能力", "应在设定库生成能力词条")

        window.switch_page("character")
        app.processEvents()
        original_question = QMessageBox.question
        try:
            QMessageBox.question = lambda *args, **kwargs: QMessageBox.Yes
            window.delete_character_group("新阵营")
        finally:
            QMessageBox.question = original_question
        moved_card = window.find_character(card_id)
        assert_true(moved_card.get("faction") == "未分组", "删除分组后人物应移动到未分组")

        window.resize(1440, 900)
        app.processEvents()
        window.character_editor_scroll.verticalScrollBar().setValue(window.character_editor_scroll.verticalScrollBar().maximum())
        app.processEvents()
        window.grab().save(str(ROOT / "qa_character_page.png"))

        draft = json.loads((Path(temp_dir) / DRAFT_FILE).read_text(encoding="utf-8"))
        assert_true("characters" in draft, "draft.json 应保存人物卡数据")

    captured: list[list[dict[str, str]]] = []
    confirmations: list[tuple[str, list[str]]] = []
    QMessageBox.information = lambda *args, **kwargs: QMessageBox.Ok  # type: ignore[assignment]
    QMessageBox.warning = lambda *args, **kwargs: QMessageBox.Ok  # type: ignore[assignment]

    def fake_confirm(title, sections, settings):
        confirmations.append((title, [name for name, _body in sections]))
        return True

    def fake_stream(settings, messages, max_tokens=1000):
        assert_true(not window.character_ai_send_btn.isEnabled(), "流式输出时发送按钮应暂时禁用")
        assert_true(window.character_ai_stop_btn.isEnabled(), "流式输出时停止按钮应启用")
        assert_true(not window.character_ai_clear_btn.isEnabled(), "流式输出时清除按钮应暂时禁用")
        assert_true(not window.character_ai_input.isEnabled(), "流式输出时输入框应暂时禁用")
        assert_true(not window.character_scope_checks["current_character"].isEnabled(), "流式输出时读取范围应锁定")
        captured.append(messages)
        window.append_character_ai_text("CHARACTER_FAKE_STREAM_REPLY")
        window.on_character_ai_stream_finished(True, "", False)

    window.confirm_character_ai_call = fake_confirm  # type: ignore[method-assign]
    window.start_character_ai_stream = fake_stream  # type: ignore[method-assign]
    window.current_page = "home"
    window.draft = None
    window.current_character_id = None

    with tempfile.TemporaryDirectory(prefix="wensha_character_ai_", dir=str(ROOT)) as temp_dir:
        project = ProjectMeta(name="AI人物QA", path=temp_dir, auto_save_minutes=10)
        window.store.write_project(project)
        DraftStore.save(project, build_character_ai_scope_draft())
        window.selected_project = project
        window.app_settings["character_ai_scope"] = default_character_ai_scope()
        window.switch_page("character")
        app.processEvents()

        window.ai_enabled_check.setChecked(True)
        window.ai_key_edit.setText("test-key")
        window.ai_base_url_box.setCurrentText("https://example.invalid/v1")
        window.ai_model_box.setCurrentText("test-model")
        window.ai_context_box.setCurrentText("10000")
        window.ai_role_name_edit.setText("墨衡")
        window.ai_role_identity_edit.setText("冷静的人物审稿人")
        window.ai_role_prompt_edit.setPlainText("优先检查人物动机、关系和能力限制。")

        window.character_ai_input.setText("检查人物动机")
        window.send_character_ai_message()
        default_payload = message_text(captured[-1])
        assert_true("CHARACTER_CURRENT_ALLOWED" in default_payload, "人物 AI 默认应读取当前人物卡")
        assert_true("CHARACTER_REL_ALLOWED" in default_payload, "人物 AI 默认应读取当前人物关系")
        assert_true("CHARACTER_SUMMARY_CURRENT" in default_payload, "人物 AI 默认应读取章节总结")
        assert_true("CHARACTER_WORLD_ALLOWED" in default_payload, "人物 AI 默认应读取允许的设定")
        assert_true("CHARACTER_OTHER_ALLOWED" not in default_payload, "人物 AI 默认不应读取全部人物卡")
        assert_true("CHARACTER_OUTLINE_ALLOWED" not in default_payload, "人物 AI 默认不应读取大纲")
        assert_true(CURRENT_BODY_MARKER not in default_payload, "人物 AI 默认不应读取当前章正文")
        assert_true(OTHER_BODY_MARKER not in default_payload, "人物 AI 默认不应读取其他章正文")
        assert_true(PRIVATE_WORLD_MARKER not in default_payload, "人物 AI 不应读取禁止 AI 读取的设定")
        assert_true("墨衡" in default_payload, "人物 AI 应注入全局 AI 角色名称")
        assert_true("冷静的人物审稿人" in default_payload, "人物 AI 应注入全局 AI 角色身份")
        assert_true("CHARACTER_FAKE_STREAM_REPLY" in window.character_ai_box.toPlainText(), "人物 AI 应流式显示回复")
        window.clear_character_ai_chat()
        assert_true("当前对话已清除" in window.character_ai_box.toPlainText(), "人物 AI 应支持清除对话")

        window.character_scope_checks["current_chapter_body"].setChecked(True)
        window.character_ai_input.setText("只读当前章正文")
        window.send_character_ai_message()
        current_payload = message_text(captured[-1])
        assert_true(CURRENT_BODY_MARKER in current_payload, "勾选当前章正文后应读取当前章正文")
        assert_true(OTHER_BODY_MARKER not in current_payload, "只勾选当前章正文时不应读取其他章正文")

        window.character_scope_checks["current_chapter_body"].setChecked(False)
        window.character_scope_checks["selected_chapter_bodies"].setChecked(True)
        window.character_selected_chapter_ids = {"ch_other"}
        window.character_ai_input.setText("只读指定章正文")
        window.send_character_ai_message()
        selected_payload = message_text(captured[-1])
        assert_true(CURRENT_BODY_MARKER not in selected_payload, "只勾选指定章时不应读取当前章正文")
        assert_true(OTHER_BODY_MARKER in selected_payload, "勾选指定章后应读取指定章节正文")
        assert_true(any(title == "发送给 AI 人物建议" for title, _sections in confirmations), "人物 AI 发送前应确认读取范围")

        fake_thread = FakeRunningThread()
        window.character_ai_thread = fake_thread  # type: ignore[assignment]
        window.character_ai_stop_btn.setEnabled(True)
        window.stop_character_ai_stream()
        assert_true(fake_thread.stopped, "停止生成应向人物 AI 线程发出停止请求")
        assert_true(not window.character_ai_stop_btn.isEnabled(), "点击停止后停止按钮应暂时禁用")
        window.character_ai_thread = None

    window.close()
    app.quit()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
