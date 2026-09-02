# -*- coding: utf-8 -*-
import os
import sys
import tempfile
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from PySide6.QtCore import QPoint, Qt
from PySide6.QtGui import QFont, QTextCursor
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication, QToolButton

from novel_assistant.main import PARAGRAPH_INDENT, ProjectHomeWindow, ProjectMeta


def assert_true(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


def main() -> int:
    app = QApplication.instance() or QApplication([])
    window = ProjectHomeWindow()
    window.show()
    app.processEvents()

    with tempfile.TemporaryDirectory(prefix="wensha_v20_", dir=str(ROOT)) as temp_dir:
        project = ProjectMeta(name="QA项目", path=temp_dir, auto_save_minutes=10)
        window.store.write_project(project)
        window.selected_project = project

        assert_true(all(not button.isHidden() for button in window.project_action_buttons), "项目首页按钮应默认显示")
        window.switch_page("editor")
        app.processEvents()

        assert_true(all(button.isHidden() for button in window.project_action_buttons), "正文页应隐藏项目级按钮")
        assert_true("本章" in window.chapter_meta_label.text(), "字数信息应显示在章节名下方")
        assert_true(window.status_line.text().startswith("QA项目"), "正文页顶部状态应显示项目名")

        align_buttons = [
            button
            for button in window.findChildren(QToolButton)
            if button.toolTip() == "对齐方式"
        ]
        assert_true(len(align_buttons) == 1, "应只有一个对齐方式图标按钮")
        actions = [action.text() for action in align_buttons[0].menu().actions()]
        assert_true(actions == ["左对齐", "居中", "右对齐"], "对齐按钮应提供左中右菜单")
        assert_true(not window.font_box.isHidden(), "字体框应在工具栏中可见")
        assert_true(not window.font_size_box.isHidden(), "字号框应在工具栏中可见")

        window.editor.setPlainText("标题\n")
        window.editor.apply_document_structure()
        second_line_y = window.editor.line_start_y() + 4
        QTest.mouseClick(window.editor.viewport(), Qt.LeftButton, Qt.NoModifier, QPoint(80, second_line_y))
        app.processEvents()
        assert_true(PARAGRAPH_INDENT in window.editor.toPlainText().splitlines()[-1], "点击正文空行应自动空两格")
        assert_true(window.editor.line_start_y() > window.editor.document().documentMargin() + 30, "标题区应在第一条横线上方")

        window.editor.setPlainText("标题\n正文内容")
        window.editor.apply_document_structure()
        cursor = window.editor.document().find("正文")
        assert_true(not cursor.isNull(), "应能找到测试正文")
        window.editor.setTextCursor(cursor)
        window.change_editor_font_size(18)
        html_after_size = window.editor.toHtml()
        assert_true("font-size:18pt" in html_after_size, "选中文字应能应用字号")
        assert_true(window.font_size_box.currentText() == "18", "字号框应同步显示当前字号")
        window.editor.apply_document_structure()
        assert_true("font-size:18pt" in window.editor.toHtml(), "整理正文结构后不应覆盖选区字号")

        cursor = window.editor.document().find("内容")
        assert_true(not cursor.isNull(), "应能找到第二段测试正文")
        window.editor.setTextCursor(cursor)
        window.change_editor_font(QFont("SimSun"))
        assert_true("SimSun" in window.editor.toHtml(), "选中文字应能应用字体")

        window.resize(1440, 900)
        app.processEvents()
        window.grab().save(str(ROOT / "qa_editor_v20_layout.png"))

        window.preview_app_settings = dict(window.app_settings)
        window.preview_app_settings["eye_mode"] = True
        window.apply_styles()
        assert_true("#EEF8E7" in window.styleSheet(), "护眼模式应改变正文写作区底色")
        assert_true(window.editor.canvas_background == "#EEF8E7", "正文编辑器内部画布也应使用护眼底色")
        window.grab().save(str(ROOT / "qa_editor_eye_mode.png"))

    window.close()
    app.quit()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
