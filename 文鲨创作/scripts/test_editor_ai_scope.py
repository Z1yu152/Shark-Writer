# -*- coding: utf-8 -*-
import json
import os
import sys
import tempfile
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from PySide6.QtWidgets import QApplication, QMessageBox, QTextEdit, QToolButton  # noqa: E402

from novel_assistant.main import DraftStore, ProjectHomeWindow, ProjectMeta, now_iso, tool_icon  # noqa: E402


CURRENT_BODY_MARKER = "CURRENT_BODY_SECRET"
OTHER_BODY_MARKER = "OTHER_BODY_SECRET"
PRIVATE_WORLD_MARKER = "WORLD_PRIVATE_SECRET"


def assert_true(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


def message_text(messages: list[dict[str, str]]) -> str:
    return json.dumps(messages, ensure_ascii=False)


def icon_alpha_bounds(kind: str) -> tuple[int, int, int, int]:
    image = tool_icon(kind, "#25313B", 16).pixmap(16, 16).toImage()
    points = [
        (x, y)
        for y in range(image.height())
        for x in range(image.width())
        if image.pixelColor(x, y).alpha() > 0
    ]
    xs = [x for x, _y in points]
    ys = [y for _x, y in points]
    return min(xs), max(xs), min(ys), max(ys)


def build_scope_draft() -> dict:
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
                        "summary": {"events": "SUMMARY_CURRENT 当前章总结。"},
                        "status": "草稿",
                        "ai_enabled": True,
                        "updated_at": now_iso(),
                    },
                    {
                        "id": "ch_other",
                        "title": "其他章",
                        "content": f"<h1>其他章</h1><p>{OTHER_BODY_MARKER} 其他章正文。</p>",
                        "summary": {"events": "SUMMARY_OTHER 其他章总结。"},
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
                    "goal": "OUTLINE_ALLOWED",
                    "timeline_tag": "T0",
                    "content": "<p>OUTLINE_ALLOWED 细纲。</p>",
                    "children": [],
                }
            ],
            "timeline_points": [{"id": "tl_1", "time": "T0", "event": "TIMELINE_ALLOWED", "line": "主线"}],
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
                            "tags": ["WORLD_ALLOWED"],
                            "content": "<p>WORLD_ALLOWED 可读设定。</p>",
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
                    "identity": "CHAR_ALLOWED",
                    "faction": "未分组",
                    "status": "登场",
                    "tags": {"性格": ["CHAR_ALLOWED"]},
                    "notes": "<p>CHAR_ALLOWED 人物备注。</p>",
                    "history": [],
                    "relations": [
                        {
                            "id": "rel_1",
                            "target_name": "角色乙",
                            "type": "合作",
                            "status": "当前",
                            "note": "REL_ALLOWED",
                        }
                    ],
                }
            ],
        },
    }


def main() -> int:
    app = QApplication.instance() or QApplication([])
    window = ProjectHomeWindow()
    captured: list[list[dict[str, str]]] = []
    confirmations: list[tuple[str, list[str]]] = []
    QMessageBox.information = lambda *args, **kwargs: QMessageBox.Ok  # type: ignore[assignment]
    QMessageBox.warning = lambda *args, **kwargs: QMessageBox.Ok  # type: ignore[assignment]

    def fake_confirm(title, sections, settings):
        confirmations.append((title, [name for name, _body in sections]))
        return True

    def fake_call(settings, messages, max_tokens=900):
        captured.append(messages)
        return True, "AI_FAKE_REPLY"

    def fake_stream(settings, messages, max_tokens=900):
        assert_true(not window.chat_send_btn.isEnabled(), "流式输出时发送按钮应暂时禁用")
        assert_true(window.chat_stop_btn.isEnabled(), "流式输出时停止生成按钮应启用")
        assert_true(not window.chat_input.isEnabled(), "流式输出时输入框应暂时禁用")
        captured.append(messages)
        window.append_editor_chat_text("AI_FAKE_STREAM_REPLY")
        window.on_editor_ai_stream_finished(True, "", False)

    window.confirm_ai_call = fake_confirm  # type: ignore[method-assign]
    window.call_ai_chat_completion = fake_call  # type: ignore[method-assign]
    window.start_editor_ai_stream = fake_stream  # type: ignore[method-assign]

    with tempfile.TemporaryDirectory(prefix="wensha_ai_scope_", dir=str(ROOT)) as temp_dir:
        project = ProjectMeta(name="AI范围QA", path=temp_dir, auto_save_minutes=10)
        window.store.write_project(project)
        DraftStore.save(project, build_scope_draft())
        window.selected_project = project
        window.switch_page("editor")
        app.processEvents()

        assert_true(isinstance(window.chat_input, QTextEdit), "正文 AI 输入框应使用多行输入")
        assert_true(window.chat_input.minimumHeight() >= 124, "正文 AI 输入框应继续加大")
        assert_true(isinstance(window.chat_send_btn, QToolButton), "正文 AI 发送按钮应为图标按钮")
        assert_true(isinstance(window.chat_stop_btn, QToolButton), "正文 AI 停止按钮应为图标按钮")
        assert_true(isinstance(window.chat_clear_btn, QToolButton), "正文 AI 清除按钮应为图标按钮")
        assert_true(window.chat_send_btn.objectName() == "AIPrimaryIconButton", "正文 AI 发送按钮应使用紧凑主按钮样式")
        assert_true(window.chat_stop_btn.objectName() == "AIIconButton", "正文 AI 停止按钮应使用紧凑普通按钮样式")
        assert_true(window.chat_clear_btn.objectName() == "AIIconButton", "正文 AI 清除按钮应使用紧凑普通按钮样式")
        assert_true(window.chat_send_btn.maximumWidth() <= 30 and window.chat_send_btn.maximumHeight() <= 30, "正文 AI 发送按钮应控制在约 30px 内")
        assert_true(window.chat_stop_btn.maximumWidth() <= 30 and window.chat_stop_btn.maximumHeight() <= 30, "正文 AI 停止按钮应控制在约 30px 内")
        assert_true(window.chat_clear_btn.maximumWidth() <= 30 and window.chat_clear_btn.maximumHeight() <= 30, "正文 AI 清除按钮应控制在约 30px 内")
        assert_true(window.chat_send_btn.iconSize().width() <= 16, "正文 AI 发送图标应更紧凑")
        for icon_name in ["send", "stop", "trash"]:
            left, right, top, bottom = icon_alpha_bounds(icon_name)
            assert_true(left > 0 and top > 0 and right < 15 and bottom < 15, f"{icon_name} 图标应按 16px 画布等比缩放且不裁边")
        assert_true(window.chat_send_btn.toolTip() == "发送", "正文 AI 发送图标应有提示")
        assert_true(window.chat_stop_btn.toolTip() == "停止生成", "正文 AI 停止图标应有提示")
        assert_true(window.chat_clear_btn.toolTip() == "清除对话", "正文 AI 清除图标应有提示")
        window.ai_enabled_check.setChecked(True)
        window.ai_key_edit.setText("test-key")
        window.ai_base_url_box.setCurrentText("https://example.invalid/v1")
        window.ai_model_box.setCurrentText("test-model")
        window.ai_context_box.setCurrentText("10000")
        window.ai_role_name_edit.setText("墨衡")
        window.ai_role_identity_edit.setText("冷静的剧情审稿人")
        window.ai_role_prompt_edit.setPlainText("说话克制，优先检查因果和人物动机。")

        window.chat_input.setText("根据资料分析人物动机")
        window.send_ai_message()
        chat_payload = message_text(captured[-1])
        assert_true("SUMMARY_CURRENT" in chat_payload, "聊天应读取当前章总结")
        assert_true("SUMMARY_OTHER" in chat_payload, "聊天应读取其他章节总结")
        assert_true("OUTLINE_ALLOWED" in chat_payload, "聊天应读取大纲")
        assert_true("TIMELINE_ALLOWED" in chat_payload, "聊天应读取时间线")
        assert_true("WORLD_ALLOWED" in chat_payload, "聊天应读取允许的设定")
        assert_true("CHAR_ALLOWED" in chat_payload, "聊天应读取人物卡")
        assert_true("REL_ALLOWED" in chat_payload, "聊天应读取人物关系记录")
        assert_true(CURRENT_BODY_MARKER not in chat_payload, "聊天默认不应读取当前章正文")
        assert_true(OTHER_BODY_MARKER not in chat_payload, "聊天默认不应读取其他章正文")
        assert_true(PRIVATE_WORLD_MARKER not in chat_payload, "聊天不应读取禁止 AI 读取的设定")
        assert_true("墨衡" in chat_payload, "聊天应注入全局 AI 角色名称")
        assert_true("冷静的剧情审稿人" in chat_payload, "聊天应注入全局 AI 角色身份")
        assert_true("AI_FAKE_STREAM_REPLY" in window.chat_log.toPlainText(), "聊天应流式显示 AI 回复")

        window.request_chapter_summary()
        summary_payload = message_text(captured[-1])
        assert_true(CURRENT_BODY_MARKER in summary_payload, "生成总结应读取当前章正文")
        assert_true(OTHER_BODY_MARKER not in summary_payload, "生成总结不应读取其他章正文")
        assert_true(PRIVATE_WORLD_MARKER not in summary_payload, "生成总结不应读取禁止 AI 读取的设定")
        assert_true("墨衡" in summary_payload, "生成总结应注入全局 AI 角色名称")
        assert_true(any(title == "发送给 AI 聊天助手" for title, _sections in confirmations), "聊天发送前应确认读取范围")
        assert_true(any(title == "生成本章总结" for title, _sections in confirmations), "生成总结前应确认读取范围")

    window.close()
    app.quit()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
