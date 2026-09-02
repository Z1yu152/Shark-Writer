# -*- coding: utf-8 -*-
"""项目元数据、草稿和本地数据库的存储层。"""

from __future__ import annotations

import json
import sqlite3
import uuid
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from PySide6.QtWidgets import QTextEdit

from .config import (
    APP_DIR,
    DRAFT_FILE,
    PARAGRAPH_INDENT,
    PROJECT_CONFIG,
    STATE_DIR,
    STATE_FILE,
    now_iso,
)


@dataclass
class ProjectMeta:
    name: str
    path: str
    author: str = ""
    template: str = "长篇"
    writing_stage: str = "构思中"
    health: str = "正常"
    health_color: str = "green"
    current_position: str = "尚未开始"
    total_words: int = 0
    today_words: int = 0
    pending_summaries: int = 0
    resources_status: str = "资源完整"
    cover_image_path: str | None = None
    auto_save_minutes: int = 10
    ai_summary_enabled: bool = True
    created_at: str = field(default_factory=now_iso)
    last_opened_at: str = field(default_factory=now_iso)
    last_manual_save_at: str | None = None
    last_auto_save_at: str | None = None
    last_backup_at: str | None = None

    @classmethod
    def from_dict(cls, data: dict[str, Any], path: Path) -> "ProjectMeta":
        payload = dict(data)
        payload["path"] = str(path)
        allowed = {f.name for f in cls.__dataclass_fields__.values()}
        return cls(**{k: v for k, v in payload.items() if k in allowed})

    def to_project_json(self) -> dict[str, Any]:
        data = self.__dict__.copy()
        data.pop("path", None)
        return data


class ProjectStore:
    def __init__(self) -> None:
        STATE_DIR.mkdir(exist_ok=True)
        self.recent: list[ProjectMeta] = self.load_recent()

    def load_recent(self) -> list[ProjectMeta]:
        if not STATE_FILE.exists():
            return self.sample_recent()
        try:
            data = json.loads(STATE_FILE.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return self.sample_recent()
        projects: list[ProjectMeta] = []
        for item in data.get("projects", []):
            path = Path(item.get("path", ""))
            projects.append(ProjectMeta.from_dict(item, path))
        return projects or self.sample_recent()

    def sample_recent(self) -> list[ProjectMeta]:
        base = APP_DIR / "sample_projects"
        return [
            ProjectMeta(
                name="长夜纪事",
                path=str(base / "长夜纪事"),
                writing_stage="连载中",
                health="正常",
                health_color="green",
                current_position="第一卷 · 第十二章",
                total_words=186420,
                today_words=2180,
                pending_summaries=2,
                resources_status="人物图片完整",
                last_manual_save_at=now_iso(),
                last_auto_save_at=now_iso(),
                last_backup_at=now_iso(),
            ),
            ProjectMeta(
                name="雾港手记",
                path=str(base / "雾港手记"),
                writing_stage="修订中",
                health="待备份",
                health_color="amber",
                current_position="第二卷 · 第三章",
                total_words=72400,
                today_words=640,
                pending_summaries=0,
                resources_status="资源完整",
                last_auto_save_at=now_iso(),
            ),
            ProjectMeta(
                name="旧神目录",
                path=str(base / "旧神目录"),
                writing_stage="构思中",
                health="摘要待更新",
                health_color="accent",
                current_position="大纲 · 第一幕",
                total_words=18300,
                today_words=0,
                pending_summaries=4,
                resources_status="人物关系待整理",
            ),
        ]

    def save_recent(self) -> None:
        payload = {"projects": [p.__dict__ for p in self.recent]}
        STATE_FILE.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")

    def add_recent(self, project: ProjectMeta) -> None:
        normalized = str(Path(project.path))
        self.recent = [p for p in self.recent if str(Path(p.path)) != normalized]
        self.recent.insert(0, project)
        self.recent = self.recent[:12]
        self.save_recent()

    def create_project(
        self,
        name: str,
        root_dir: Path,
        author: str,
        template: str,
        auto_save_minutes: int,
        ai_summary_enabled: bool,
    ) -> ProjectMeta:
        project_dir = root_dir / name
        project_dir.mkdir(parents=True, exist_ok=True)
        for sub in ["assets/portraits", "assets/covers", "exports", "backups"]:
            (project_dir / sub).mkdir(parents=True, exist_ok=True)
        project = ProjectMeta(
            name=name,
            path=str(project_dir),
            author=author,
            template=template,
            auto_save_minutes=auto_save_minutes,
            ai_summary_enabled=ai_summary_enabled,
            last_manual_save_at=now_iso(),
            last_auto_save_at=now_iso(),
        )
        self.write_project(project)
        self.init_db(project_dir / "project.db")
        self.add_recent(project)
        return project

    def open_project(self, folder: Path) -> ProjectMeta:
        config_path = folder / PROJECT_CONFIG
        if not config_path.exists():
            raise ValueError("所选文件夹不是有效小说项目：缺少 project.json")
        data = json.loads(config_path.read_text(encoding="utf-8"))
        project = ProjectMeta.from_dict(data, folder)
        project.last_opened_at = now_iso()
        self.write_project(project)
        self.add_recent(project)
        return project

    def write_project(self, project: ProjectMeta) -> None:
        path = Path(project.path)
        path.mkdir(parents=True, exist_ok=True)
        (path / PROJECT_CONFIG).write_text(
            json.dumps(project.to_project_json(), ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

    def init_db(self, db_path: Path) -> None:
        with sqlite3.connect(db_path) as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS meta (
                    key TEXT PRIMARY KEY,
                    value TEXT NOT NULL
                )
                """
            )
            conn.execute("INSERT OR REPLACE INTO meta(key, value) VALUES('schema_version', '1')")


class DraftStore:
    @staticmethod
    def new_id(prefix: str) -> str:
        return f"{prefix}_{uuid.uuid4().hex[:10]}"

    @staticmethod
    def default_draft() -> dict[str, Any]:
        volume_id = DraftStore.new_id("vol")
        chapter_id = DraftStore.new_id("ch")
        return {
            "version": 1,
            "current_chapter_id": chapter_id,
            "volumes": [
                {
                    "id": volume_id,
                    "title": "第一卷",
                    "chapters": [
                        {
                            "id": chapter_id,
                            "title": "第一章",
                            "content": f"<h1 style='text-align:center;'>第一章</h1><p>{PARAGRAPH_INDENT}从这里开始写正文。</p>",
                            "summary": {
                                "time": "",
                                "place": "",
                                "characters": "",
                                "events": "尚未生成总结。",
                                "key_sentence": "",
                            },
                            "status": "草稿",
                            "updated_at": now_iso(),
                        }
                    ],
                }
            ],
        }

    @staticmethod
    def path_for(project: ProjectMeta) -> Path:
        return Path(project.path) / DRAFT_FILE

    @classmethod
    def load(cls, project: ProjectMeta) -> dict[str, Any]:
        path = cls.path_for(project)
        if not path.exists():
            draft = cls.default_draft()
            cls.save(project, draft)
            return draft
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            data = cls.default_draft()
        if not data.get("volumes"):
            data = cls.default_draft()
        return data

    @classmethod
    def save(cls, project: ProjectMeta, draft: dict[str, Any]) -> None:
        path = cls.path_for(project)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(draft, ensure_ascii=False, indent=2), encoding="utf-8")

    @staticmethod
    def iter_chapters(draft: dict[str, Any]):
        for volume in draft.get("volumes", []):
            for chapter in volume.get("chapters", []):
                yield volume, chapter

    @staticmethod
    def find_volume(draft: dict[str, Any], volume_id: str) -> dict[str, Any] | None:
        for volume in draft.get("volumes", []):
            if volume.get("id") == volume_id:
                return volume
        return None

    @classmethod
    def find_chapter(cls, draft: dict[str, Any], chapter_id: str) -> tuple[dict[str, Any], dict[str, Any]] | None:
        for volume, chapter in cls.iter_chapters(draft):
            if chapter.get("id") == chapter_id:
                return volume, chapter
        return None

    @classmethod
    def first_chapter(cls, draft: dict[str, Any]) -> tuple[dict[str, Any], dict[str, Any]] | None:
        for volume, chapter in cls.iter_chapters(draft):
            return volume, chapter
        return None

    @staticmethod
    def text_count(html: str) -> int:
        text = QTextEdit()
        text.setHtml(html)
        plain = text.toPlainText()
        return len("".join(plain.split()))
