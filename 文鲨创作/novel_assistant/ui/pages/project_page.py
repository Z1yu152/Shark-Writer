# -*- coding: utf-8 -*-
"""项目首页、项目管理、备份与完整性检查页面模块。"""

from __future__ import annotations

import json
import shutil
import zipfile
from datetime import datetime
from pathlib import Path
from typing import Any

from PySide6.QtCore import QSize, QUrl, Qt
from PySide6.QtGui import QColor, QDesktopServices, QFont
from PySide6.QtWidgets import (
    QDialog,
    QFileDialog,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QInputDialog,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QMenu,
    QMessageBox,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from ...core.config import APP_DIR, DRAFT_FILE, IMAGE_EXTENSIONS, PALETTE, PROJECT_CONFIG, now_iso
from ...core.storage import DraftStore, ProjectMeta
from ...services.files import move_path_to_recycle_bin
from ...ui.dialogs import NewProjectDialog
from ..common import cached_pixmap, fmt_time, relative_time, white_logo_pixmap


class ProjectPageMixin:
    def save_active_project_silently(self) -> None:
        if not self.selected_project or not Path(self.selected_project.path).exists():
            return
        if self.current_page == "editor":
            self.save_current_chapter(silent=True)
        elif self.current_page == "outline":
            self.save_current_outline_node(silent=True)
        elif self.current_page == "worldbuilding":
            self.save_current_world_entry(silent=True)
        elif self.current_page == "character":
            self.save_current_character(silent=True)
        if self.draft is not None:
            DraftStore.save(self.selected_project, self.draft)
        self.store.write_project(self.selected_project)

    def backup_files(self, project: ProjectMeta) -> list[Path]:
        project_path = Path(project.path)
        backup_dir = project_path / "backups"
        files: list[Path] = []
        for item in project_path.rglob("*"):
            if not item.is_file():
                continue
            try:
                item.relative_to(backup_dir)
                continue
            except ValueError:
                pass
            files.append(item)
        return files

    def enforce_backup_retention(self, project: ProjectMeta) -> None:
        keep = int(self.collect_app_settings_from_ui().get("backup_retention", 10)) if hasattr(self, "backup_retention_spin") else 10
        backup_dir = Path(project.path) / "backups"
        backups = sorted(backup_dir.glob("*_backup_*.zip"), key=lambda path: path.stat().st_mtime, reverse=True)
        for old_backup in backups[keep:]:
            old_backup.unlink(missing_ok=True)

    def create_manual_backup(self, silent: bool = False) -> Path | None:
        project = self.selected_project
        if not project:
            if not silent:
                QMessageBox.information(self, "没有项目", "请先选择或创建一个项目。")
            return None
        project_path = Path(project.path)
        if not project_path.exists():
            if not silent:
                QMessageBox.warning(self, "路径不存在", "项目路径不存在，无法备份。")
            return None
        self.save_active_project_silently()
        backup_dir = project_path / "backups"
        backup_dir.mkdir(parents=True, exist_ok=True)
        stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        safe_name = "".join(ch for ch in project.name if ch not in '\\/:*?"<>|').strip() or "project"
        output = backup_dir / f"{safe_name}_backup_{stamp}.zip"
        try:
            with zipfile.ZipFile(output, "w", zipfile.ZIP_DEFLATED) as archive:
                for item in self.backup_files(project):
                    archive.write(item, item.relative_to(project_path))
            project.last_backup_at = now_iso()
            self.store.write_project(project)
            self.store.add_recent(project)
            self.enforce_backup_retention(project)
        except OSError as exc:
            if not silent:
                QMessageBox.critical(self, "备份失败", str(exc))
            return None
        if not silent:
            self.settings_last_auto_label.setText(fmt_time(project.last_auto_save_at))
            QMessageBox.information(self, "已创建备份", f"备份已保存到：\n{output}")
        return output

    def safe_extract_backup(self, archive_path: Path, project_path: Path) -> None:
        project_root = project_path.resolve()
        with zipfile.ZipFile(archive_path, "r") as archive:
            for member in archive.infolist():
                target = (project_root / member.filename).resolve()
                try:
                    target.relative_to(project_root)
                except ValueError:
                    raise OSError(f"备份文件包含不安全路径：{member.filename}")
                if member.is_dir():
                    target.mkdir(parents=True, exist_ok=True)
                    continue
                target.parent.mkdir(parents=True, exist_ok=True)
                with archive.open(member) as source, target.open("wb") as dest:
                    shutil.copyfileobj(source, dest)

    def restore_from_backup(self) -> None:
        project = self.selected_project
        if not project:
            QMessageBox.information(self, "没有项目", "请先选择或创建一个项目。")
            return
        project_path = Path(project.path)
        if not project_path.exists():
            QMessageBox.warning(self, "路径不存在", "项目路径不存在，无法恢复。")
            return
        file_name, _ = QFileDialog.getOpenFileName(
            self,
            "选择备份文件",
            str(project_path / "backups"),
            "Backup (*.zip)",
        )
        if not file_name:
            return
        answer = QMessageBox.question(
            self,
            "从备份恢复",
            "恢复会覆盖当前项目文件。程序会先创建一份当前状态备份。是否继续？",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No,
        )
        if answer != QMessageBox.Yes:
            return
        self.create_manual_backup(silent=True)
        try:
            self.safe_extract_backup(Path(file_name), project_path)
            self.selected_project = self.store.open_project(project_path)
            self.draft = None
        except (OSError, zipfile.BadZipFile, ValueError, json.JSONDecodeError) as exc:
            QMessageBox.critical(self, "恢复失败", str(exc))
            return
        self.refresh_projects(keep_project=self.selected_project)
        self.load_settings_page()
        QMessageBox.information(self, "已恢复", "项目已从备份恢复。")

    def resolve_project_asset(self, project: ProjectMeta, value: str) -> Path:
        path = Path(value)
        if path.is_absolute():
            return path
        return Path(project.path) / path

    def project_integrity_issues(self, project: ProjectMeta) -> list[str]:
        project_path = Path(project.path)
        issues: list[str] = []
        for required in [PROJECT_CONFIG, DRAFT_FILE, "assets", "exports", "backups"]:
            if not (project_path / required).exists():
                issues.append(f"缺少 {required}")
        if project.cover_image_path and not self.resolve_project_asset(project, project.cover_image_path).exists():
            issues.append("项目封面图片引用失效")
        try:
            draft = DraftStore.load(project)
        except Exception as exc:
            return [f"草稿文件无法读取：{exc}"]
        for module in draft.get("worldbuilding", {}).get("modules", []):
            for _parent, node in self.iter_world_nodes([module]):
                image_path = node.get("image_path")
                if image_path and not self.resolve_project_asset(project, image_path).exists():
                    issues.append(f"设定图片缺失：{node.get('title', '未命名词条')}")
        for card in draft.get("characters", {}).get("cards", []):
            portrait_path = card.get("portrait_path")
            if portrait_path and not self.resolve_project_asset(project, portrait_path).exists():
                issues.append(f"人物画像缺失：{card.get('name', '未命名人物')}")
        return issues

    def check_project_integrity(self, silent: bool = False) -> list[str]:
        project = self.selected_project
        if not project:
            if not silent:
                QMessageBox.information(self, "没有项目", "请先选择或创建一个项目。")
            return ["没有项目"]
        issues = self.project_integrity_issues(project)
        if not silent:
            if issues:
                QMessageBox.warning(self, "检查结果", "发现以下问题：\n" + "\n".join(issues[:20]))
            else:
                QMessageBox.information(self, "检查结果", "项目结构与图片引用未发现问题。")
        return issues

    def clear_missing_image_refs(self, silent: bool = False) -> int:
        project = self.selected_project
        if not project:
            if not silent:
                QMessageBox.information(self, "没有项目", "请先选择或创建一个项目。")
            return 0
        if not Path(project.path).exists():
            if not silent:
                QMessageBox.warning(self, "路径不存在", "项目路径不存在，无法清理。")
            return 0
        draft = DraftStore.load(project)
        count = 0
        if project.cover_image_path and not self.resolve_project_asset(project, project.cover_image_path).exists():
            project.cover_image_path = None
            count += 1
        for module in draft.get("worldbuilding", {}).get("modules", []):
            for _parent, node in self.iter_world_nodes([module]):
                image_path = node.get("image_path")
                if image_path and not self.resolve_project_asset(project, image_path).exists():
                    node["image_path"] = ""
                    count += 1
        for card in draft.get("characters", {}).get("cards", []):
            portrait_path = card.get("portrait_path")
            if portrait_path and not self.resolve_project_asset(project, portrait_path).exists():
                card["portrait_path"] = ""
                count += 1
        if count:
            DraftStore.save(project, draft)
            self.store.write_project(project)
            self.draft = draft if self.draft is not None else self.draft
        if not silent:
            QMessageBox.information(self, "清理完成", f"已清理 {count} 个失效图片引用。")
        return count

    def build_project_list(self) -> QWidget:
        box = QFrame()
        box.setObjectName("Card")
        layout = QVBoxLayout(box)
        layout.setContentsMargins(18, 18, 18, 20)
        layout.setSpacing(12)

        header = QLabel("最近项目")
        header.setObjectName("SectionTitle")
        sub = QLabel("用于快速切换，详情看左侧概览")
        sub.setObjectName("Muted")
        layout.addWidget(header)
        layout.addWidget(sub)

        self.project_list = QListWidget()
        self.project_list.setObjectName("RecentList")
        self.project_list.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.project_list.setAlternatingRowColors(False)
        self.project_list.itemSelectionChanged.connect(self.on_project_selected)
        layout.addWidget(self.project_list, 1)

        self.management_btn = QPushButton("项目管理")
        self.management_btn.setObjectName("ProjectMenuButton")
        self.management_btn.setMenu(self.build_project_management_menu())
        layout.addWidget(self.management_btn)

        hint = QLabel("路径失效的项目可以重新关联或从备份恢复。")
        hint.setObjectName("Muted")
        hint.setWordWrap(True)
        layout.addWidget(hint)
        return box

    def build_project_management_menu(self) -> QMenu:
        menu = QMenu(self)
        menu.addAction("从最近项目移除", self.remove_selected_from_recent)
        menu.addAction("重新关联路径", self.relink_selected_project)
        menu.addAction("打开项目文件夹", self.open_project_folder)
        menu.addSeparator()
        menu.addAction("删除项目文件...", self.delete_selected_project)
        return menu

    def build_project_detail(self) -> QWidget:
        box = QFrame()
        box.setObjectName("Card")
        layout = QVBoxLayout(box)
        layout.setContentsMargins(22, 18, 22, 20)
        layout.setSpacing(14)

        title = QLabel("项目概览")
        title.setObjectName("SectionTitle")
        subtitle = QLabel("打开前判断是否安全继续写")
        subtitle.setObjectName("Muted")
        layout.addWidget(title)
        layout.addWidget(subtitle)

        overview_top = QHBoxLayout()
        overview_top.setSpacing(24)

        cover_col = QVBoxLayout()
        cover_col.setSpacing(10)
        self.cover = QLabel("")
        self.cover.setObjectName("CoverBox")
        self.cover.setFixedSize(220, 311)
        self.cover.setAlignment(Qt.AlignCenter)
        cover_col.addWidget(self.cover, 0, Qt.AlignLeft | Qt.AlignTop)
        cover_btn = QPushButton("编辑图片")
        cover_btn.setObjectName("CoverButton")
        cover_btn.clicked.connect(self.change_project_cover)
        cover_col.addWidget(cover_btn)
        cover_col.addStretch(1)
        overview_top.addLayout(cover_col)

        info_panel = QFrame()
        info_panel.setObjectName("OverviewInfo")
        info_layout = QVBoxLayout(info_panel)
        info_layout.setContentsMargins(18, 14, 18, 14)
        info_layout.setSpacing(14)

        title_row = QHBoxLayout()
        title_group = QVBoxLayout()
        title_group.setSpacing(4)
        self.detail_project_name = QLabel("-")
        self.detail_project_name.setObjectName("ProjectName")
        self.detail_stage = QLabel("-")
        self.detail_stage.setObjectName("Muted")
        title_group.addWidget(self.detail_project_name)
        title_group.addWidget(self.detail_stage)
        edit_title_btn = QPushButton("编辑标题")
        edit_title_btn.setObjectName("SmallButton")
        edit_title_btn.clicked.connect(self.rename_current_project)
        self.health_badge = QLabel("-")
        self.health_badge.setObjectName("HealthBadge")
        self.health_badge.setAlignment(Qt.AlignCenter)
        title_row.addLayout(title_group, 1)
        title_row.addWidget(edit_title_btn)
        title_row.addWidget(self.health_badge)
        info_layout.addLayout(title_row)

        self.primary_labels: dict[str, QLabel] = {}
        for label, key in [
            ("总字数 / 今日新增", "words"),
            ("当前章节", "current_position"),
        ]:
            stat = QFrame()
            stat.setObjectName("StatRow")
            stat_layout = QVBoxLayout(stat)
            stat_layout.setContentsMargins(12, 8, 12, 8)
            stat_layout.setSpacing(3)
            name_label = QLabel(label)
            name_label.setObjectName("StatLabel")
            value_label = QLabel("-")
            value_label.setObjectName("StatValue")
            value_label.setWordWrap(True)
            stat_layout.addWidget(name_label)
            stat_layout.addWidget(value_label)
            info_layout.addWidget(stat)
            self.primary_labels[key] = value_label
        info_layout.addStretch(1)
        overview_top.addWidget(info_panel, 1)
        layout.addLayout(overview_top)

        self.detail_grid = QGridLayout()
        self.detail_grid.setHorizontalSpacing(22)
        self.detail_grid.setVerticalSpacing(12)
        self.detail_labels: dict[str, QLabel] = {}
        fields = [
            ("上次手动保存", "last_manual_save_at"),
            ("上次自动保存", "last_auto_save_at"),
            ("最近备份", "last_backup_at"),
            ("摘要状态", "pending_summaries"),
            ("资源状态", "resources_status"),
        ]
        for row, (label, key) in enumerate(fields):
            name_label = QLabel(label)
            name_label.setObjectName("DetailName")
            value_label = QLabel("-")
            value_label.setWordWrap(True)
            self.detail_grid.addWidget(name_label, row, 0)
            self.detail_grid.addWidget(value_label, row, 1)
            self.detail_labels[key] = value_label
        layout.addLayout(self.detail_grid)
        layout.addStretch(1)

        actions = QHBoxLayout()
        open_btn = QPushButton("继续写作")
        open_btn.setObjectName("PrimaryButton")
        open_btn.clicked.connect(self.open_selected_project)
        inspect_btn = QPushButton("打开项目资料")
        inspect_btn.clicked.connect(self.open_selected_project)
        relink_btn = QPushButton("重新关联")
        relink_btn.clicked.connect(self.relink_selected_project)
        backup_btn = QPushButton("从备份恢复")
        backup_btn.clicked.connect(lambda: QMessageBox.information(self, "从备份恢复", "备份恢复会在后续数据模块中实现。"))
        actions.addWidget(open_btn)
        actions.addWidget(inspect_btn)
        actions.addWidget(relink_btn)
        actions.addWidget(backup_btn)
        layout.addLayout(actions)
        return box

    def refresh_projects(self, keep_project: ProjectMeta | None = None) -> None:
        keep_project = keep_project or self.selected_project
        keep_path = str(Path(keep_project.path)) if keep_project else None
        self.project_list.blockSignals(True)
        self.project_list.clear()
        for row, project in enumerate(self.store.recent):
            path_exists = Path(project.path).exists()
            health = project.health if path_exists else "路径不存在"
            health_color = project.health_color if path_exists else "accent"
            item = QListWidgetItem(
                f"{project.name}\n"
                f"{project.writing_stage} · {health}\n"
                f"自动保存 {relative_time(project.last_auto_save_at)}"
            )
            item.setData(Qt.UserRole, row)
            item.setToolTip(project.path)
            item.setForeground(QColor(PALETTE.get(health_color, PALETTE["ink"])))
            item.setFont(QFont("Microsoft YaHei", 10, QFont.Bold))
            item.setSizeHint(QSize(260, 76))
            self.project_list.addItem(item)
        if self.store.recent:
            selected_row = 0
            if keep_path:
                for idx, project in enumerate(self.store.recent):
                    if str(Path(project.path)) == keep_path:
                        selected_row = idx
                        break
            self.project_list.setCurrentRow(selected_row)
            self.selected_project = self.store.recent[selected_row]
        else:
            self.selected_project = None
        self.project_list.blockSignals(False)
        self.management_btn.setEnabled(bool(self.selected_project))
        self.update_detail()
        self.update_status_line()

    def on_project_selected(self) -> None:
        item = self.project_list.currentItem()
        if not item:
            return
        row = item.data(Qt.UserRole)
        if 0 <= row < len(self.store.recent):
            self.selected_project = self.store.recent[row]
            self.update_detail()

    def update_detail(self) -> None:
        project = self.selected_project
        if not project:
            for label in self.detail_labels.values():
                label.setText("-")
            for label in self.primary_labels.values():
                label.setText("-")
            self.detail_project_name.setText("-")
            self.detail_stage.setText("-")
            self.health_badge.setText("-")
            self.cover.clear()
            return
        cover_path = self.project_cover_path(project)
        if cover_path and cover_path.exists():
            if pixmap := cached_pixmap(cover_path, QSize(206, 292)):
                self.cover.setPixmap(pixmap)
        elif logo := white_logo_pixmap(QSize(142, 102)):
            self.cover.setPixmap(logo)
        else:
            self.cover.setText(project.name[:6] or "封面")
        path_exists = Path(project.path).exists()
        health = project.health if path_exists else "路径不存在"
        health_color = project.health_color if path_exists else "accent"
        self.detail_project_name.setText(project.name)
        self.detail_stage.setText(f"{project.writing_stage} · {project.template}")
        self.health_badge.setText(health)
        self.health_badge.setProperty("tone", health_color)
        self.health_badge.style().unpolish(self.health_badge)
        self.health_badge.style().polish(self.health_badge)
        self.primary_labels["current_position"].setText(project.current_position)
        self.primary_labels["words"].setText(f"{project.total_words:,} / {project.today_words:,}")
        self.detail_labels["last_manual_save_at"].setText(fmt_time(project.last_manual_save_at))
        self.detail_labels["last_auto_save_at"].setText(f"{relative_time(project.last_auto_save_at)} · {fmt_time(project.last_auto_save_at)}")
        self.detail_labels["last_backup_at"].setText(fmt_time(project.last_backup_at))
        self.detail_labels["pending_summaries"].setText(f"{project.pending_summaries} 章待更新")
        self.detail_labels["resources_status"].setText(project.resources_status)

    def project_cover_path(self, project: ProjectMeta) -> Path | None:
        if not project.cover_image_path:
            return None
        path = Path(project.cover_image_path)
        if not path.is_absolute():
            path = Path(project.path) / path
        return path

    def change_project_cover(self) -> None:
        project = self.selected_project
        if not project:
            QMessageBox.information(self, "没有项目", "请先选择或创建一个项目。")
            return
        project_dir = Path(project.path)
        if not project_dir.exists():
            QMessageBox.warning(self, "路径不存在", "项目路径不存在，无法保存图片。")
            return
        file_name, _ = QFileDialog.getOpenFileName(
            self,
            "选择项目概览图片",
            str(project_dir),
            "图片文件 (*.png *.jpg *.jpeg *.webp *.bmp)",
        )
        if not file_name:
            return
        source = Path(file_name)
        if source.suffix.lower() not in IMAGE_EXTENSIONS:
            QMessageBox.warning(self, "格式不支持", "请选择 png、jpg、jpeg、webp 或 bmp 图片。")
            return
        cover_dir = project_dir / "assets" / "covers"
        cover_dir.mkdir(parents=True, exist_ok=True)
        target = cover_dir / f"project_cover{source.suffix.lower()}"
        try:
            if source.resolve() != target.resolve():
                shutil.copyfile(source, target)
            project.cover_image_path = str(target.relative_to(project_dir))
            project.last_manual_save_at = now_iso()
            self.store.write_project(project)
            self.store.save_recent()
        except OSError as exc:
            QMessageBox.critical(self, "图片保存失败", str(exc))
            return
        self.selected_project = project
        self.refresh_projects(keep_project=project)

    def rename_current_project(self) -> None:
        project = self.selected_project
        if not project:
            QMessageBox.information(self, "没有项目", "请先选择或创建一个项目。")
            return
        if not Path(project.path).exists():
            QMessageBox.warning(self, "路径不存在", "项目路径不存在，请先重新关联项目。")
            return
        new_name, ok = QInputDialog.getText(self, "编辑标题", "项目标题：", text=project.name)
        if not ok:
            return
        new_name = new_name.strip()
        if not new_name:
            QMessageBox.warning(self, "标题为空", "项目标题不能为空。")
            return
        if new_name == project.name:
            return
        project.name = new_name
        project.last_manual_save_at = now_iso()
        try:
            self.store.write_project(project)
            self.store.save_recent()
        except OSError as exc:
            QMessageBox.critical(self, "标题保存失败", str(exc))
            return
        self.selected_project = project
        self.refresh_projects(keep_project=project)

    def update_status_line(self) -> None:
        project = self.selected_project
        if project and self.current_page == "editor":
            self.status_line.setText(f"{project.name} · 自动保存默认 {project.auto_save_minutes} 分钟")
        elif project:
            self.status_line.setText(
                f"自动保存默认 {project.auto_save_minutes} 分钟 · "
                f"上次自动保存 {relative_time(project.last_auto_save_at)}"
            )
        else:
            self.status_line.setText("自动保存默认 10 分钟 · 尚未选择项目")

    def new_project(self) -> None:
        dialog = NewProjectDialog(self)
        if dialog.exec() != QDialog.Accepted:
            return
        try:
            project = self.store.create_project(**dialog.values())
        except OSError as exc:
            QMessageBox.critical(self, "创建失败", f"无法创建项目：{exc}")
            return
        self.selected_project = project
        self.refresh_projects(keep_project=project)
        QMessageBox.information(self, "项目已创建", f"已创建项目：{project.name}")

    def open_project(self) -> None:
        folder = QFileDialog.getExistingDirectory(self, "选择小说项目文件夹", str(APP_DIR))
        if not folder:
            return
        try:
            project = self.store.open_project(Path(folder))
        except (OSError, ValueError, json.JSONDecodeError) as exc:
            QMessageBox.warning(self, "无法打开项目", str(exc))
            return
        self.selected_project = project
        self.refresh_projects(keep_project=project)

    def open_selected_project(self) -> None:
        project = self.selected_project
        if not project:
            return
        if not Path(project.path).exists():
            QMessageBox.warning(self, "路径不存在", "项目路径不存在，请重新关联或从备份恢复。")
            return
        self.switch_page("editor")

    def relink_selected_project(self) -> None:
        project = self.selected_project
        if not project:
            return
        folder = QFileDialog.getExistingDirectory(self, "重新选择项目位置", str(APP_DIR))
        if not folder:
            return
        config = Path(folder) / PROJECT_CONFIG
        if not config.exists():
            QMessageBox.warning(self, "无法关联", "所选文件夹缺少 project.json。")
            return
        try:
            relinked = self.store.open_project(Path(folder))
        except (OSError, ValueError, json.JSONDecodeError) as exc:
            QMessageBox.warning(self, "无法关联", str(exc))
            return
        self.selected_project = relinked
        self.refresh_projects(keep_project=relinked)

    def open_project_folder(self) -> None:
        project = self.selected_project
        if not project:
            return
        project_path = Path(project.path)
        if not project_path.exists():
            QMessageBox.warning(self, "路径不存在", "项目路径不存在，请先重新关联项目。")
            return
        QDesktopServices.openUrl(QUrl.fromLocalFile(str(project_path)))

    def remove_selected_from_recent(self) -> None:
        project = self.selected_project
        if not project:
            return
        answer = QMessageBox.question(
            self,
            "从最近项目移除",
            f"只从最近项目列表移除“{project.name}”，不会删除本地文件。是否继续？",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No,
        )
        if answer != QMessageBox.Yes:
            return
        self.remove_project_record(project)

    def delete_selected_project(self) -> None:
        project = self.selected_project
        if not project:
            return
        project_path = Path(project.path)
        if not project_path.exists():
            QMessageBox.warning(self, "路径不存在", "项目路径不存在，无法删除文件。可以使用“从最近项目移除”。")
            return
        confirm, ok = QInputDialog.getText(
            self,
            "删除项目文件",
            f"将把项目文件夹移入回收站。\n请输入项目标题“{project.name}”确认：",
        )
        if not ok:
            return
        if confirm.strip() != project.name:
            QMessageBox.warning(self, "确认失败", "输入的项目标题不一致，已取消删除。")
            return
        try:
            move_path_to_recycle_bin(project_path)
        except OSError as exc:
            QMessageBox.critical(self, "删除失败", str(exc))
            return
        self.remove_project_record(project)
        QMessageBox.information(self, "已删除", f"项目“{project.name}”已移入回收站。")

    def remove_project_record(self, project: ProjectMeta) -> None:
        normalized = str(Path(project.path))
        old_index = 0
        for idx, item in enumerate(self.store.recent):
            if str(Path(item.path)) == normalized:
                old_index = idx
                break
        self.store.recent = [item for item in self.store.recent if str(Path(item.path)) != normalized]
        self.store.save_recent()
        if self.store.recent:
            next_index = min(old_index, len(self.store.recent) - 1)
            self.selected_project = self.store.recent[next_index]
        else:
            self.selected_project = None
        self.refresh_projects(keep_project=self.selected_project)
