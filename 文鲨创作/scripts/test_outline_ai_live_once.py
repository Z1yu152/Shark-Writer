# -*- coding: utf-8 -*-
import json
import os
import sys
import tempfile
import time
from pathlib import Path
from types import MethodType

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))

from PySide6.QtWidgets import QApplication, QMessageBox  # noqa: E402

from novel_assistant.main import DraftStore, ProjectHomeWindow, ProjectMeta, default_outline_ai_scope, load_application_fonts  # noqa: E402
from test_outline_page import CURRENT_BODY_MARKER, OTHER_BODY_MARKER, PRIVATE_WORLD_MARKER, build_ai_scope_draft  # noqa: E402


def fail(message: str) -> int:
    print(message)
    return 1


def main() -> int:
    api_key = sys.stdin.readline().strip()
    if not api_key:
        return fail("missing_key")

    app = QApplication.instance() or QApplication([])
    load_application_fonts(app)
    window = ProjectHomeWindow()
    QMessageBox.question = lambda *args, **kwargs: QMessageBox.Yes  # type: ignore[assignment]
    QMessageBox.information = lambda *args, **kwargs: QMessageBox.Ok  # type: ignore[assignment]
    QMessageBox.warning = lambda *args, **kwargs: QMessageBox.Ok  # type: ignore[assignment]
    captured: list[list[dict[str, str]]] = []

    original_start = window.start_outline_ai_stream

    def capture_and_start(self, settings, messages, max_tokens=1000):
        captured.append(messages)
        return original_start(settings, messages, max_tokens=max_tokens)

    window.start_outline_ai_stream = MethodType(capture_and_start, window)  # type: ignore[method-assign]

    with tempfile.TemporaryDirectory(prefix="wensha_outline_ai_live_", dir=str(ROOT)) as temp_dir:
        project = ProjectMeta(name="AI大纲实测", path=temp_dir, auto_save_minutes=10)
        window.store.write_project(project)
        DraftStore.save(project, build_ai_scope_draft())
        window.selected_project = project
        window.current_page = "home"
        window.draft = None
        window.current_outline_node_id = None
        window.app_settings["outline_ai_scope"] = default_outline_ai_scope()
        window.app_settings["ai_confirm_each_call"] = True
        window.switch_page("outline")
        app.processEvents()

        window.ai_enabled_check.setChecked(True)
        window.ai_key_edit.setText(api_key)
        window.ai_base_url_box.setCurrentText("https://api.deepseek.com/v1")
        window.ai_model_box.setCurrentText("deepseek-chat")
        window.ai_context_box.setCurrentText("10000")
        window.ai_role_name_edit.setText("墨衡")
        window.ai_role_identity_edit.setText("冷静的大纲审稿人")
        window.ai_role_prompt_edit.setPlainText("输出简洁，优先检查结构与因果。")

        ok, message = window.perform_ai_connection_test(window.collect_app_settings_from_ui())
        if not ok:
            return fail(f"connection_failed: {message}")
        print("connection_ok")

        window.outline_chat_input.setText("请只用一句中文短句说明：大纲AI助手正常。")
        window.send_outline_ai_message()
        deadline = time.time() + 70
        while window.outline_ai_thread is not None and time.time() < deadline:
            app.processEvents()
            time.sleep(0.05)
        app.processEvents()

        if window.outline_ai_thread is not None:
            window.stop_outline_ai_stream()
            return fail("stream_timeout")
        if not window.outline_ai_stream_text.strip():
            return fail("stream_empty")
        payload = json.dumps(captured[-1], ensure_ascii=False)
        forbidden = [CURRENT_BODY_MARKER, OTHER_BODY_MARKER, PRIVATE_WORLD_MARKER]
        if any(marker in payload for marker in forbidden):
            return fail("scope_failed")
        if "OUTLINE_SCOPE_ALLOWED" not in payload or "OUTLINE_SUMMARY_CURRENT" not in payload:
            return fail("scope_missing_expected_context")
        print("stream_ok")
        print(f"stream_chars={len(window.outline_ai_stream_text.strip())}")
        print("scope_default_ok")

        window.ai_key_edit.setText("")
        window.app_settings["api_key"] = ""

    window.close()
    app.quit()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
