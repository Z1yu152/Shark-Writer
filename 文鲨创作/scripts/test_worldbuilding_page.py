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
from PySide6.QtWidgets import QApplication, QMessageBox, QPushButton, QToolButton

from novel_assistant.main import DRAFT_FILE, DraftStore, ProjectHomeWindow, ProjectMeta, load_application_fonts
from novel_assistant.ui.pages import worldbuilding_page


def assert_true(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


def find_tree_item_by_text(root, text: str):
    for index in range(root.topLevelItemCount()):
        item = root.topLevelItem(index)
        found = find_child_item_by_text(item, text)
        if found:
            return found
    return None


def find_child_item_by_text(item, text: str):
    if item.text(0) == text:
        return item
    for index in range(item.childCount()):
        found = find_child_item_by_text(item.child(index), text)
        if found:
            return found
    return None


def find_button_by_text(root, text: str):
    for button in root.findChildren(QPushButton):
        if button.text() == text:
            return button
    return None


def main() -> int:
    app = QApplication.instance() or QApplication([])
    load_application_fonts(app)
    window = ProjectHomeWindow()
    window.show()
    app.processEvents()

    with tempfile.TemporaryDirectory(prefix="wensha_world_", dir=str(ROOT)) as temp_dir:
        project = ProjectMeta(name="QA设定项目", path=temp_dir, auto_save_minutes=10)
        window.store.write_project(project)
        window.selected_project = project

        window.switch_page("worldbuilding")
        app.processEvents()

        assert_true(window.current_page == "worldbuilding", "应切换到设定库页")
        assert_true(window.world_tree.topLevelItemCount() == 5, "默认应有五个设定模块")
        assert_true("黑石码头" in window.world_entry_name_edit.text(), "应加载默认词条")
        image_action_names = {button.accessibleName() for button in window.findChildren(QToolButton)}
        assert_true({"添加词条图片", "替换词条图片", "删除词条图片", "预览词条图片"}.issubset(image_action_names), "词条图片操作应使用小图标按钮")
        legacy_world = {
            "modules": [
                {"id": "wb_module_world", "title": "世界观", "kind": "module", "children": []},
                {"id": "wb_legacy_history", "title": "历史纪年", "kind": "module", "entry_type": "submenu", "children": []},
            ]
        }
        window.normalize_worldbuilding_modules(legacy_world)
        assert_true(len(legacy_world["modules"]) == 1, "旧数据中的默认词条不应保留为顶层模块")
        assert_true(legacy_world["modules"][0]["children"][0]["title"] == "历史纪年", "历史纪年应回到世界观下")
        assert_true(legacy_world["modules"][0]["children"][0]["kind"] == "entry", "历史纪年应按词条处理")
        legacy_geo = {
            "modules": [
                {"id": "wb_module_geo", "title": "世界地理", "kind": "module", "children": []},
                {
                    "id": "wb_legacy_fog",
                    "title": "雾港",
                    "kind": "module",
                    "entry_type": "submenu",
                    "children": [{"id": "wb_legacy_dock", "title": "黑石码头", "kind": "entry", "children": []}],
                },
            ]
        }
        window.normalize_worldbuilding_modules(legacy_geo)
        assert_true(len(legacy_geo["modules"]) == 1, "旧数据中的地理下级不应保留为顶层模块")
        assert_true(legacy_geo["modules"][0]["children"][0]["title"] == "雾港", "雾港应回到世界地理下")
        assert_true(legacy_geo["modules"][0]["children"][0]["kind"] == "entry", "雾港应按词条处理")
        module_item = find_tree_item_by_text(window.world_tree, "世界地理")
        assert_true(module_item is not None, "应能找到默认模块世界地理")
        window.world_tree.setCurrentItem(module_item)
        app.processEvents()
        assert_true(window.selected_world_entry_parent().get("title") == "世界地理", "选中模块时词条应创建在当前模块下")

        original_get_text = worldbuilding_page.QInputDialog.getText
        dialog_titles = iter(["测试子模块", "测试词条"])
        try:
            worldbuilding_page.QInputDialog.getText = staticmethod(lambda *args, **kwargs: (next(dialog_titles), True))
            submenu_button = find_button_by_text(window, "+ 子模块")
            assert_true(submenu_button is not None, "应能找到新增子模块按钮")
            submenu_button.click()
            app.processEvents()
            assert_true(find_tree_item_by_text(window.world_tree, "测试子模块") is not None, "点击新增子模块后应出现新模块")

            module_item = find_tree_item_by_text(window.world_tree, "世界地理")
            assert_true(module_item is not None, "新增子模块后仍应能找到默认模块世界地理")
            window.world_tree.setCurrentItem(module_item)
            app.processEvents()
            entry_button = find_button_by_text(window, "+ 词条")
            assert_true(entry_button is not None, "应能找到新增词条按钮")
            entry_button.click()
            app.processEvents()
            assert_true(find_tree_item_by_text(window.world_tree, "测试词条") is not None, "点击新增词条后应出现新词条")
        finally:
            worldbuilding_page.QInputDialog.getText = original_get_text

        entry_item = find_tree_item_by_text(window.world_tree, "黑石码头")
        assert_true(entry_item is not None, "应能找到默认词条黑石码头")
        window.world_tree.setCurrentItem(entry_item)
        app.processEvents()
        assert_true(window.selected_world_module_parent().get("title") == "世界地理", "选中词条时仍应能追溯所属模块")
        assert_true(window.selected_world_entry_parent().get("title") == "黑石码头", "选中词条时新增词条应创建为子词条")
        source_image = Path(temp_dir) / "source_world_image.png"
        image = QPixmap(24, 24)
        image.fill(QColor("#4D7A68"))
        assert_true(image.save(str(source_image)), "应能创建测试图片")
        window.set_world_entry_image(source_image)
        found = window.find_world_node(window.current_world_entry_id)
        assert_true(found is not None, "应能找到当前词条")
        image_path = found[1].get("image_path", "")
        assert_true(image_path.startswith("assets"), "词条图片应保存为项目相对路径")
        assert_true((Path(temp_dir) / image_path).exists(), "词条图片应复制到项目目录")
        assert_true(window.world_image_label.pixmap() is not None, "词条图片预览应显示图片")
        window.remove_world_entry_image()
        assert_true(not found[1].get("image_path"), "删除图片后应清空词条图片引用")
        assert_true(window.world_image_label.text(), "删除图片后应恢复占位提示")

        window.world_entry_name_edit.setText("测试码头")
        window.world_entry_type_edit.setText("地点")
        window.world_entry_tags_edit.setText("雾港, 测试")
        window.world_entry_editor.setPlainText("测试设定内容")
        window.save_current_world_entry(silent=True)

        window.world_search_edit.setText("测试码头")
        window.search_world_entries()
        assert_true(window.world_search_results.count() >= 1, "应能搜索到保存后的词条")

        old_id = window.current_world_entry_id
        old_title = window.world_entry_name_edit.text()
        target_item = find_tree_item_by_text(window.world_tree, "旧灯塔")
        assert_true(target_item is not None, "应能找到用于切换测试的旧灯塔词条")
        window.world_entry_editor.setPlainText("切换前未保存的内容")
        window.world_tree.setCurrentItem(target_item)
        app.processEvents()
        assert_true(window.world_entry_name_edit.text() == "旧灯塔", "点击旧灯塔后不应跳回其他词条")
        assert_true(window.current_world_entry_id != old_id, "当前词条 ID 应随点击目标改变")
        window.world_tree.setCurrentItem(find_tree_item_by_text(window.world_tree, old_title))
        app.processEvents()
        assert_true("切换前未保存的内容" in window.world_entry_editor.toPlainText(), "切换前内容应被静默保存")

        draft = json.loads((Path(temp_dir) / DRAFT_FILE).read_text(encoding="utf-8"))
        world = draft.get("worldbuilding", {})
        assert_true(sum(1 for module in world.get("modules", []) if module.get("default")) == 5, "draft.json 应保存五个默认模块")
        assert_true(find_tree_item_by_text(window.world_tree, "测试子模块") is not None, "新增子模块应保存在 draft.json 对应的设定树中")
        assert_true(bool(world.get("current_entry_id")), "draft.json 应保存当前词条")
        deletable_module = {
            "id": "wb_delete_me",
            "title": "临时词库模块",
            "kind": "module",
            "default": False,
            "children": [],
        }
        world["modules"].append(deletable_module)
        DraftStore.save(project, draft)
        window.draft = draft
        original_question = QMessageBox.question
        try:
            QMessageBox.question = lambda *args, **kwargs: QMessageBox.Yes
            window.delete_world_node("wb_delete_me")
        finally:
            QMessageBox.question = original_question
        assert_true(not window.find_world_node("wb_delete_me"), "非默认顶层模块应能删除")

        window.resize(1440, 900)
        app.processEvents()
        window.grab().save(str(ROOT / "qa_worldbuilding_page.png"))

    window.close()
    app.quit()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
