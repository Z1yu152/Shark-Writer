# -*- coding: utf-8 -*-
from __future__ import annotations

import os
import shutil
import sys
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from PySide6.QtWidgets import QApplication  # noqa: E402

from novel_assistant.main import (  # noqa: E402
    APP_SETTINGS_FILE,
    DraftStore,
    ProjectHomeWindow,
    default_app_settings,
    load_app_settings,
    save_app_settings,
)


def main() -> None:
    original_settings = APP_SETTINGS_FILE.read_text(encoding="utf-8") if APP_SETTINGS_FILE.exists() else None
    baseline_settings = default_app_settings()
    baseline_settings["eye_mode"] = False
    save_app_settings(baseline_settings)
    test_root = ROOT / "tmp_settings_page_project"
    if test_root.exists():
        shutil.rmtree(test_root)
    test_root.mkdir(parents=True, exist_ok=True)

    app = QApplication.instance() or QApplication([])
    window = ProjectHomeWindow()
    project = window.store.create_project("设置页测试项目", test_root, "测试", "长篇", 10, True)
    window.selected_project = project
    window.refresh_projects(keep_project=project)
    window.switch_page("settings")

    assert window.current_page == "settings"
    assert window.page_stack.currentWidget() is window.settings_page
    assert "settings" in window.nav_buttons

    window.eye_mode_check.setChecked(True)
    assert window.preview_app_settings is not None
    assert window.preview_app_settings["eye_mode"] is True
    assert "#DDEED8" in window.styleSheet()
    assert "#F8FCF4" in window.styleSheet()
    assert load_app_settings()["eye_mode"] is False
    window.ui_scale_box.setCurrentText("110%")
    window.settings_body_font_size_box.setCurrentText("16")
    window.settings_title_font_size_box.setCurrentText("24")
    window.auto_save_enabled_check.setChecked(True)
    window.settings_auto_save_box.setCurrentText("5 分钟")
    window.backup_retention_box.setCurrentText("3 份")
    window.ai_enabled_check.setChecked(True)
    window.ai_key_edit.setText("test-key")
    window.ai_base_url_box.setCurrentText("https://example.invalid/v1")
    window.ai_model_box.setCurrentText("mock-model")
    window.ai_context_box.setCurrentText("10000")
    window.ai_role_name_edit.setText("墨衡")
    window.ai_role_identity_edit.setText("冷静的剧情审稿人")
    window.ai_role_prompt_edit.setPlainText("优先检查因果、动机和伏笔。")
    window.export_format_box.setCurrentText("TXT")
    window.export_status_check.setChecked(True)

    window.perform_ai_connection_test = lambda settings: (True, "连接正常：测试桩")  # type: ignore[method-assign]
    window.test_ai_connection()
    assert "连接正常" in window.ai_status_label.text()

    window.save_app_settings_from_ui(show_message=False)
    saved = load_app_settings()
    assert saved["eye_mode"] is True
    assert window.preview_app_settings is None
    assert saved["ui_scale"] == 110
    assert saved["auto_save_minutes"] == 5
    assert saved["max_context_items"] == 10000
    assert saved["api_key"] == "test-key"
    assert saved["ai_role_name"] == "墨衡"
    assert saved["ai_role_identity"] == "冷静的剧情审稿人"
    assert "伏笔" in saved["ai_role_prompt"]
    assert window.selected_project.auto_save_minutes == 5

    backup = window.create_manual_backup(silent=True)
    assert backup is not None and backup.exists()
    assert backup.suffix == ".zip"

    draft = DraftStore.load(window.selected_project)
    draft.setdefault("worldbuilding", {}).setdefault("modules", [])
    DraftStore.save(window.selected_project, draft)
    issues = window.check_project_integrity(silent=True)
    assert isinstance(issues, list)
    cleared = window.clear_missing_image_refs(silent=True)
    assert isinstance(cleared, int)

    window.resize(1440, 900)
    image_path = ROOT / "qa_settings_page.png"
    assert window.grab().save(str(image_path))
    assert image_path.exists() and image_path.stat().st_size > 10_000

    window.close()
    shutil.rmtree(test_root, ignore_errors=True)
    if original_settings is None:
        APP_SETTINGS_FILE.unlink(missing_ok=True)
    else:
        APP_SETTINGS_FILE.write_text(original_settings, encoding="utf-8")


if __name__ == "__main__":
    main()
