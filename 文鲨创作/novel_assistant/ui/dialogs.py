# -*- coding: utf-8 -*-
"""独立对话框组件。"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFileDialog,
    QGridLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

from ..core.config import APP_DIR


class NewProjectDialog(QDialog):
    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("新建小说项目")
        self.setMinimumWidth(520)

        self.name_edit = QLineEdit()
        self.name_edit.setPlaceholderText("例如：长夜纪事")
        self.author_edit = QLineEdit()
        self.author_edit.setPlaceholderText("可选")
        self.path_edit = QLineEdit(str(APP_DIR / "projects"))
        self.template_box = QComboBox()
        self.template_box.addItems(["长篇", "单卷", "系列作", "空白"])
        self.auto_save_spin = QSpinBox()
        self.auto_save_spin.setRange(1, 30)
        self.auto_save_spin.setValue(10)
        self.auto_save_spin.setSuffix(" 分钟")
        self.ai_summary_check = QCheckBox("保存章节时启用 AI 总结")
        self.ai_summary_check.setChecked(True)

        browse_btn = QPushButton("选择位置")
        browse_btn.clicked.connect(self.choose_path)

        form = QGridLayout()
        form.addWidget(QLabel("项目名称"), 0, 0)
        form.addWidget(self.name_edit, 0, 1, 1, 2)
        form.addWidget(QLabel("保存位置"), 1, 0)
        form.addWidget(self.path_edit, 1, 1)
        form.addWidget(browse_btn, 1, 2)
        form.addWidget(QLabel("作者/笔名"), 2, 0)
        form.addWidget(self.author_edit, 2, 1, 1, 2)
        form.addWidget(QLabel("类型模板"), 3, 0)
        form.addWidget(self.template_box, 3, 1, 1, 2)
        form.addWidget(QLabel("自动保存"), 4, 0)
        form.addWidget(self.auto_save_spin, 4, 1, 1, 2)
        form.addWidget(self.ai_summary_check, 5, 1, 1, 2)

        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.button(QDialogButtonBox.Ok).setText("创建项目")
        buttons.button(QDialogButtonBox.Cancel).setText("取消")
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)

        layout = QVBoxLayout(self)
        title = QLabel("新建项目")
        title.setObjectName("DialogTitle")
        layout.addWidget(title)
        layout.addLayout(form)
        layout.addWidget(buttons)

    def choose_path(self) -> None:
        folder = QFileDialog.getExistingDirectory(self, "选择项目保存位置", self.path_edit.text())
        if folder:
            self.path_edit.setText(folder)

    def accept(self) -> None:
        if not self.name_edit.text().strip():
            QMessageBox.warning(self, "缺少项目名称", "请输入项目名称。")
            return
        super().accept()

    def values(self) -> dict[str, Any]:
        return {
            "name": self.name_edit.text().strip(),
            "root_dir": Path(self.path_edit.text().strip()),
            "author": self.author_edit.text().strip(),
            "template": self.template_box.currentText(),
            "auto_save_minutes": self.auto_save_spin.value(),
            "ai_summary_enabled": self.ai_summary_check.isChecked(),
        }
